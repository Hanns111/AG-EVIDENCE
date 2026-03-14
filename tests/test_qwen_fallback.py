# -*- coding: utf-8 -*-
"""
Tests para qwen_fallback.py — Tarea #23 (Fase 3)

Cobertura:
  - Parseo JSON (thinking blocks, markdown, texto extra)
  - Conversión JSON → ComprobanteExtraido tipado
  - Validaciones aritméticas Grupo J
  - Deduplicación por serie_numero
  - Retry lógica
  - Healthcheck
  - Abstención en fallo
  - Función de conveniencia
"""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from config.settings import VLM_CONFIG
from src.extraction.abstencion import CampoExtraido, EvidenceStatus
from src.extraction.expediente_contract import (
    ComprobanteExtraido,
    MetadatosExtraccion,
    ValidacionesAritmeticas,
)
from src.extraction.qwen_fallback import (
    EXTRACTION_PROMPT,
    TOLERANCIA_ARITMETICA,
    VERSION_QWEN_FALLBACK,
    QwenFallbackClient,
    ResultadoExtraccion,
    ResultadoVLM,
    extraer_comprobantes_vlm,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def client():
    """Cliente con config por defecto."""
    return QwenFallbackClient()


@pytest.fixture
def client_custom():
    """Cliente con config personalizada."""
    return QwenFallbackClient(
        config={
            "model": "test-model:1b",
            "fallback_model": "test-fallback:1b",
            "ollama_url": "http://localhost:99999",
            "timeout_seconds": 10,
            "max_tokens": 1024,
            "temperature": 0.0,
            "num_ctx": 4096,
            "max_retries": 1,
        }
    )


@pytest.fixture
def json_factura_valida():
    """JSON de una factura válida completa."""
    return {
        "grupo_a_emisor": {
            "ruc_emisor": "20341841357",
            "razon_social": "EL CHALAN SAC",
            "nombre_comercial": "El Chalan",
            "direccion_emisor": "Av. Lima 123",
            "ubigeo_emisor": "Lima - Lima - Lima",
        },
        "grupo_b_comprobante": {
            "tipo_comprobante": "FACTURA",
            "serie": "F011",
            "numero": "0008846",
            "fecha_emision": "06/02/2026",
            "fecha_vencimiento": None,
            "moneda": "PEN",
            "forma_pago": "CONTADO",
            "es_electronico": True,
        },
        "grupo_c_adquirente": {
            "ruc_adquirente": "20380795907",
            "razon_social_adquirente": "PROGRAMA EDUCACION BASICA PARA TODOS",
            "direccion_adquirente": None,
        },
        "grupo_d_condiciones": {
            "condicion_pago": None,
            "guia_remision": None,
            "orden_compra": None,
            "observaciones": None,
        },
        "grupo_e_items": [
            {
                "cantidad": 2.0,
                "unidad": "NIU",
                "descripcion": "Menu ejecutivo",
                "valor_unitario": 25.42,
                "importe": 50.84,
            }
        ],
        "grupo_f_totales": {
            "subtotal": 50.84,
            "igv_tasa": 18,
            "igv_monto": 9.15,
            "total_gravado": 50.84,
            "total_exonerado": 0.0,
            "total_inafecto": 0.0,
            "total_gratuito": None,
            "otros_cargos": None,
            "descuentos": None,
            "importe_total": 59.99,
            "monto_letras": "CINCUENTA Y NUEVE CON 99/100 SOLES",
        },
        "grupo_g_clasificacion": {
            "categoria_gasto": "ALIMENTACION",
            "subcategoria": "Almuerzo",
        },
        "grupo_h_hospedaje": {
            "fecha_checkin": None,
            "fecha_checkout": None,
            "numero_noches": None,
            "numero_habitacion": None,
            "nombre_huesped": None,
            "numero_reserva": None,
        },
        "grupo_i_movilidad": {
            "origen": None,
            "destino": None,
            "fecha_servicio": None,
            "placa_vehiculo": None,
            "nombre_pasajero": None,
        },
        "campos_no_encontrados": [],
        "confianza_global": "alta",
    }


@pytest.fixture
def json_hotel_valido():
    """JSON de un hotel con hospedaje."""
    return {
        "grupo_a_emisor": {
            "ruc_emisor": "20604955498",
            "razon_social": "WIN & WIN HOTEL SAC",
            "nombre_comercial": None,
            "direccion_emisor": None,
            "ubigeo_emisor": None,
        },
        "grupo_b_comprobante": {
            "tipo_comprobante": "FACTURA",
            "serie": "F700",
            "numero": "141",
            "fecha_emision": "10/02/2026",
            "fecha_vencimiento": None,
            "moneda": "PEN",
            "forma_pago": "CONTADO",
            "es_electronico": True,
        },
        "grupo_c_adquirente": {
            "ruc_adquirente": "20380795907",
            "razon_social_adquirente": "MINEDU",
            "direccion_adquirente": None,
        },
        "grupo_d_condiciones": {
            "condicion_pago": None,
            "guia_remision": None,
            "orden_compra": None,
            "observaciones": None,
        },
        "grupo_e_items": [
            {
                "cantidad": 3.0,
                "unidad": "NIU",
                "descripcion": "Habitacion simple",
                "valor_unitario": 84.75,
                "importe": 254.24,
            }
        ],
        "grupo_f_totales": {
            "subtotal": 254.24,
            "igv_tasa": 18,
            "igv_monto": 45.76,
            "total_gravado": 254.24,
            "total_exonerado": None,
            "total_inafecto": None,
            "total_gratuito": None,
            "otros_cargos": None,
            "descuentos": None,
            "importe_total": 300.00,
            "monto_letras": None,
        },
        "grupo_g_clasificacion": {
            "categoria_gasto": "HOSPEDAJE",
            "subcategoria": None,
        },
        "grupo_h_hospedaje": {
            "fecha_checkin": "07/02/2026",
            "fecha_checkout": "10/02/2026",
            "numero_noches": 3,
            "numero_habitacion": "201",
            "nombre_huesped": "Victor Martiarena",
            "numero_reserva": None,
        },
        "grupo_i_movilidad": {
            "origen": None,
            "destino": None,
            "fecha_servicio": None,
            "placa_vehiculo": None,
            "nombre_pasajero": None,
        },
        "campos_no_encontrados": [],
        "confianza_global": "alta",
    }


# =============================================================================
# Tests de constantes y configuración
# =============================================================================


class TestConstantes:
    def test_version(self):
        assert VERSION_QWEN_FALLBACK == "1.0.0"

    def test_tolerancia(self):
        assert TOLERANCIA_ARITMETICA == 0.02

    def test_prompt_contiene_regla_forense(self):
        assert "REGLA ABSOLUTA" in EXTRACTION_PROMPT
        assert "Extrae SOLO lo que ves literalmente" in EXTRACTION_PROMPT

    def test_prompt_contiene_grupos(self):
        for grupo in ["grupo_a_emisor", "grupo_b_comprobante", "grupo_f_totales"]:
            assert grupo in EXTRACTION_PROMPT

    def test_prompt_no_contiene_no_think(self):
        """Hallazgo Tarea #22: /no_think causa respuesta vacía."""
        assert "/no_think" not in EXTRACTION_PROMPT


class TestClientConfig:
    def test_config_default(self, client):
        assert client.model == VLM_CONFIG["model"]
        assert client.ollama_url == VLM_CONFIG["ollama_url"]
        assert client.max_retries == VLM_CONFIG["max_retries"]

    def test_config_custom(self, client_custom):
        assert client_custom.model == "test-model:1b"
        assert client_custom.fallback_model == "test-fallback:1b"
        assert client_custom.max_retries == 1

    def test_trace_logger_opcional(self):
        mock_logger = MagicMock()
        client = QwenFallbackClient(trace_logger=mock_logger)
        assert client.trace_logger is mock_logger

    def test_sin_trace_logger(self, client):
        assert client.trace_logger is None


# =============================================================================
# Tests de _extraer_json — parseo de respuestas VLM
# =============================================================================


class TestExtraerJson:
    def test_json_puro(self, client):
        result = client._extraer_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_con_thinking(self, client):
        content = '<think>Voy a analizar...</think>{"key": "value"}'
        result = client._extraer_json(content)
        assert result == {"key": "value"}

    def test_json_con_thinking_multilinea(self, client):
        content = """<think>
        Analizando la imagen...
        Veo un comprobante de pago.
        </think>
        {"ruc": "20341841357"}"""
        result = client._extraer_json(content)
        assert result["ruc"] == "20341841357"

    def test_json_con_markdown_code_block(self, client):
        content = '```json\n{"key": "value"}\n```'
        result = client._extraer_json(content)
        assert result == {"key": "value"}

    def test_json_con_texto_previo(self, client):
        content = 'Aqui esta el resultado:\n{"key": "value"}'
        result = client._extraer_json(content)
        assert result == {"key": "value"}

    def test_json_vacio(self, client):
        assert client._extraer_json("") is None

    def test_json_none(self, client):
        assert client._extraer_json(None) is None

    def test_json_invalido(self, client):
        assert client._extraer_json("esto no es json") is None

    def test_json_con_thinking_y_markdown(self, client):
        content = """<think>pensando...</think>
```json
{"resultado": true}
```"""
        result = client._extraer_json(content)
        assert result == {"resultado": True}

    def test_json_con_llaves_anidadas(self, client):
        content = 'texto {"a": {"b": 1}}'
        result = client._extraer_json(content)
        assert result == {"a": {"b": 1}}


# =============================================================================
# Tests de conversión JSON → ComprobanteExtraido
# =============================================================================


class TestJsonAComprobante:
    def test_factura_completa(self, client, json_factura_valida):
        comp = client._json_a_comprobante(json_factura_valida, archivo="test.pdf", pagina=5)
        assert isinstance(comp, ComprobanteExtraido)

        # Grupo A
        assert comp.grupo_a.ruc_emisor is not None
        assert comp.grupo_a.ruc_emisor.valor == "20341841357"
        assert comp.grupo_a.razon_social.valor == "EL CHALAN SAC"

        # Grupo B
        assert comp.grupo_b.serie.valor == "F011"
        assert comp.grupo_b.numero.valor == "0008846"
        assert comp.grupo_b.tipo_comprobante.valor == "FACTURA"

        # Grupo F
        assert comp.grupo_f.importe_total.valor == "59.99"

        # Grupo K (metadatos)
        assert comp.grupo_k.pagina_origen == 5
        assert comp.grupo_k.metodo_extraccion == "qwen_vl"
        assert comp.grupo_k.confianza_global == "alta"

    def test_campo_tiene_metadata(self, client, json_factura_valida):
        comp = client._json_a_comprobante(json_factura_valida, archivo="exp.pdf", pagina=3)
        campo = comp.grupo_a.ruc_emisor
        assert campo.archivo == "exp.pdf"
        assert campo.pagina == 3
        assert campo.confianza == 0.95  # alta
        assert campo.regla_aplicada == "qwen_fallback_v1"
        assert campo.tipo_campo == "ruc"

    def test_confianza_mapeo(self, client):
        data_alta = {"confianza_global": "alta", "grupo_a_emisor": {"ruc_emisor": "123"}}
        comp_alta = client._json_a_comprobante(data_alta)
        assert comp_alta.grupo_a.ruc_emisor.confianza == 0.95

        data_media = {"confianza_global": "media", "grupo_a_emisor": {"ruc_emisor": "123"}}
        comp_media = client._json_a_comprobante(data_media)
        assert comp_media.grupo_a.ruc_emisor.confianza == 0.75

        data_baja = {"confianza_global": "baja", "grupo_a_emisor": {"ruc_emisor": "123"}}
        comp_baja = client._json_a_comprobante(data_baja)
        assert comp_baja.grupo_a.ruc_emisor.confianza == 0.45

    def test_campos_null_no_crean_campo(self, client, json_factura_valida):
        comp = client._json_a_comprobante(json_factura_valida)
        # fecha_vencimiento es null en el fixture
        assert comp.grupo_b.fecha_vencimiento is None

    def test_hospedaje_con_datos(self, client, json_hotel_valido):
        comp = client._json_a_comprobante(json_hotel_valido)
        assert comp.grupo_h is not None
        assert comp.grupo_h.fecha_checkin.valor == "07/02/2026"
        assert comp.grupo_h.nombre_huesped.valor == "Victor Martiarena"

    def test_hospedaje_sin_datos(self, client, json_factura_valida):
        """Cuando todos los campos de hospedaje son null, grupo_h es None."""
        comp = client._json_a_comprobante(json_factura_valida)
        assert comp.grupo_h is None

    def test_movilidad_sin_datos(self, client, json_factura_valida):
        comp = client._json_a_comprobante(json_factura_valida)
        assert comp.grupo_i is None

    def test_items_se_convierten(self, client, json_factura_valida):
        comp = client._json_a_comprobante(json_factura_valida)
        assert len(comp.grupo_e) == 1
        item = comp.grupo_e[0]
        assert item.descripcion.valor == "Menu ejecutivo"
        assert item.cantidad.valor == "2.0"

    def test_serie_numero(self, client, json_factura_valida):
        comp = client._json_a_comprobante(json_factura_valida)
        assert comp.get_serie_numero() == "F011-0008846"

    def test_json_vacio(self, client):
        comp = client._json_a_comprobante({})
        assert isinstance(comp, ComprobanteExtraido)
        assert comp.grupo_a.ruc_emisor is None
        assert comp.get_serie_numero() == "SIN_IDENTIFICAR"

    def test_timestamp_generado(self, client, json_factura_valida):
        comp = client._json_a_comprobante(json_factura_valida)
        assert comp.grupo_k.timestamp_extraccion != ""
        # Debe ser ISO format parseable
        datetime.fromisoformat(comp.grupo_k.timestamp_extraccion)

    def test_campos_no_encontrados(self, client):
        data = {"campos_no_encontrados": ["ruc_emisor", "fecha_emision"]}
        comp = client._json_a_comprobante(data)
        assert comp.grupo_k.campos_no_encontrados == ["ruc_emisor", "fecha_emision"]

    def test_to_dict_round_trip(self, client, json_factura_valida):
        comp = client._json_a_comprobante(json_factura_valida, archivo="test.pdf", pagina=1)
        d = comp.to_dict()
        assert isinstance(d, dict)
        assert d["grupo_k"]["metodo_extraccion"] == "qwen_vl"

    def test_todos_los_campos_lista(self, client, json_factura_valida):
        comp = client._json_a_comprobante(json_factura_valida)
        campos = comp.todos_los_campos()
        assert len(campos) > 0
        assert all(isinstance(c, CampoExtraido) for c in campos)


# =============================================================================
# Tests de validación aritmética (Grupo J)
# =============================================================================


class TestValidacionAritmetica:
    def test_j1_suma_items_ok(self, client, json_factura_valida):
        comp = client._json_a_comprobante(json_factura_valida)
        result = client._validar_aritmetica(comp)
        assert result.suma_items_ok is True

    def test_j2_igv_ok(self, client, json_factura_valida):
        comp = client._json_a_comprobante(json_factura_valida)
        result = client._validar_aritmetica(comp)
        # 50.84 * 18% = 9.1512, factura dice 9.15 → dentro de tolerancia
        assert result.igv_ok is True

    def test_j3_total_ok(self, client, json_factura_valida):
        comp = client._json_a_comprobante(json_factura_valida)
        result = client._validar_aritmetica(comp)
        # 50.84 + 9.15 = 59.99
        assert result.total_ok is True

    def test_j4_noches_ok(self, client, json_hotel_valido):
        comp = client._json_a_comprobante(json_hotel_valido)
        result = client._validar_aritmetica(comp)
        assert result.noches_ok is True

    def test_j1_suma_items_error(self, client):
        data = {
            "grupo_e_items": [{"importe": 100.0}],
            "grupo_f_totales": {"subtotal": 200.0},
        }
        comp = client._json_a_comprobante(data)
        result = client._validar_aritmetica(comp)
        assert result.suma_items_ok is False
        assert any("J1" in e for e in result.errores_detalle)

    def test_j2_igv_error(self, client):
        data = {
            "grupo_f_totales": {"subtotal": 100.0, "igv_tasa": 18, "igv_monto": 20.0},
        }
        comp = client._json_a_comprobante(data)
        result = client._validar_aritmetica(comp)
        assert result.igv_ok is False

    def test_j3_total_error(self, client):
        data = {
            "grupo_f_totales": {
                "subtotal": 100.0,
                "igv_monto": 18.0,
                "importe_total": 999.0,
            },
        }
        comp = client._json_a_comprobante(data)
        result = client._validar_aritmetica(comp)
        assert result.total_ok is False

    def test_j4_noches_error(self, client):
        data = {
            "grupo_h_hospedaje": {
                "fecha_checkin": "01/01/2026",
                "fecha_checkout": "05/01/2026",
                "numero_noches": 5,  # Real son 4
            },
        }
        comp = client._json_a_comprobante(data)
        result = client._validar_aritmetica(comp)
        assert result.noches_ok is False

    def test_sin_datos_no_valida(self, client):
        comp = client._json_a_comprobante({})
        result = client._validar_aritmetica(comp)
        assert result.suma_items_ok is None
        assert result.igv_ok is None
        assert result.total_ok is None
        assert result.noches_ok is None
        assert result.todas_ok() is True  # No hay validaciones ejecutadas

    def test_tolerancia_correcta(self, client):
        """Diferencia de 0.01 debe pasar (dentro de tolerancia 0.02)."""
        data = {
            "grupo_f_totales": {"subtotal": 100.0, "igv_tasa": 18, "igv_monto": 18.01},
        }
        comp = client._json_a_comprobante(data)
        result = client._validar_aritmetica(comp)
        assert result.igv_ok is True


# =============================================================================
# Tests de deduplicación
# =============================================================================


class TestDeduplicacion:
    def test_sin_duplicados(self, client, json_factura_valida, json_hotel_valido):
        comp1 = client._json_a_comprobante(json_factura_valida)
        comp2 = client._json_a_comprobante(json_hotel_valido)
        result = client._deduplicar([comp1, comp2])
        assert len(result) == 2

    def test_con_duplicados(self, client, json_factura_valida):
        comp1 = client._json_a_comprobante(json_factura_valida)
        comp2 = client._json_a_comprobante(json_factura_valida)
        result = client._deduplicar([comp1, comp2])
        assert len(result) == 1

    def test_duplicado_conserva_mayor_confianza(self, client):
        data_alta = {
            "grupo_b_comprobante": {"serie": "F001", "numero": "100"},
            "confianza_global": "alta",
        }
        data_baja = {
            "grupo_b_comprobante": {"serie": "F001", "numero": "100"},
            "confianza_global": "baja",
        }
        comp_baja = client._json_a_comprobante(data_baja)
        comp_alta = client._json_a_comprobante(data_alta)
        result = client._deduplicar([comp_baja, comp_alta])
        assert len(result) == 1
        assert result[0].grupo_k.confianza_global == "alta"

    def test_sin_serie_no_deduplica(self, client):
        comp1 = client._json_a_comprobante({})
        comp2 = client._json_a_comprobante({})
        result = client._deduplicar([comp1, comp2])
        assert len(result) == 2

    def test_lista_vacia(self, client):
        result = client._deduplicar([])
        assert result == []


# =============================================================================
# Tests de invocación VLM (mockeados)
# =============================================================================


class TestInvocacionVLM:
    def _mock_urlopen(self, json_response):
        """Helper para mockear urllib.request.urlopen."""
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps(json_response).encode("utf-8")
        return mock_resp

    @patch("src.extraction.qwen_fallback.urllib.request.urlopen")
    def test_invocacion_exitosa(self, mock_urlopen, client, json_factura_valida):
        ollama_response = {
            "message": {"content": json.dumps(json_factura_valida)},
            "eval_count": 500,
        }
        mock_urlopen.return_value = self._mock_urlopen(ollama_response)

        resultado = client._invocar_vlm("base64img", "qwen3-vl:8b")
        assert resultado.exito is True
        assert resultado.json_extraido is not None
        assert resultado.intentos == 1

    @patch("src.extraction.qwen_fallback.urllib.request.urlopen")
    def test_invocacion_con_thinking(self, mock_urlopen, client):
        ollama_response = {
            "message": {"content": '<think>analizando...</think>{"ruc": "20341841357"}'},
            "eval_count": 100,
        }
        mock_urlopen.return_value = self._mock_urlopen(ollama_response)

        resultado = client._invocar_vlm("base64img", "qwen3-vl:8b")
        assert resultado.exito is True
        assert resultado.json_extraido["ruc"] == "20341841357"

    @patch("src.extraction.qwen_fallback.urllib.request.urlopen")
    def test_retry_en_json_corrupto(self, mock_urlopen, client):
        """Primer intento JSON corrupto, segundo exitoso."""
        resp_bad = self._mock_urlopen({"message": {"content": "no es json"}, "eval_count": 0})
        resp_ok = self._mock_urlopen(
            {
                "message": {"content": '{"ok": true}'},
                "eval_count": 50,
            }
        )
        mock_urlopen.side_effect = [resp_bad, resp_ok]

        resultado = client._invocar_vlm("base64img", "qwen3-vl:8b")
        assert resultado.exito is True
        assert resultado.intentos == 2

    @patch("src.extraction.qwen_fallback.urllib.request.urlopen")
    def test_fallo_tras_max_retries(self, mock_urlopen, client):
        """JSON corrupto en todos los intentos → fallo."""
        resp_bad = self._mock_urlopen({"message": {"content": "basura"}, "eval_count": 0})
        mock_urlopen.return_value = resp_bad

        resultado = client._invocar_vlm("base64img", "qwen3-vl:8b")
        assert resultado.exito is False
        assert "JSON corrupto" in resultado.error

    @patch("src.extraction.qwen_fallback.urllib.request.urlopen")
    def test_error_conexion(self, mock_urlopen, client):
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        resultado = client._invocar_vlm("base64img", "qwen3-vl:8b")
        assert resultado.exito is False
        assert "connection_error" in resultado.error


# =============================================================================
# Tests de extraer_comprobante (end-to-end mockeado)
# =============================================================================


class TestExtraerComprobante:
    @patch("src.extraction.qwen_fallback.urllib.request.urlopen")
    def test_extrae_comprobante_ok(self, mock_urlopen, client, json_factura_valida):
        resp = MagicMock()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        resp.read.return_value = json.dumps(
            {
                "message": {"content": json.dumps(json_factura_valida)},
                "eval_count": 500,
            }
        ).encode("utf-8")
        mock_urlopen.return_value = resp

        comp = client.extraer_comprobante("base64", archivo="test.pdf", pagina=5)
        assert comp is not None
        assert isinstance(comp, ComprobanteExtraido)
        assert comp.grupo_b.serie.valor == "F011"
        assert comp.grupo_k.pagina_origen == 5
        # Grupo J debe estar validado
        assert isinstance(comp.grupo_j, ValidacionesAritmeticas)

    @patch("src.extraction.qwen_fallback.urllib.request.urlopen")
    def test_sin_fallback_retorna_none(self, mock_urlopen, client):
        """Sin fallback_model, fallo del primario retorna None."""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("fail")
        comp = client.extraer_comprobante("base64", archivo="test.pdf", pagina=1)
        assert comp is None

    @patch("src.extraction.qwen_fallback.urllib.request.urlopen")
    def test_retorna_none_en_fallo_total(self, mock_urlopen, client):
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("fail")

        comp = client.extraer_comprobante("base64", archivo="test.pdf", pagina=1)
        assert comp is None


# =============================================================================
# Tests de extraer_comprobantes (multi-página)
# =============================================================================


class TestExtraerComprobantes:
    @patch("src.extraction.qwen_fallback.urllib.request.urlopen")
    def test_multiples_paginas(self, mock_urlopen, client, json_factura_valida, json_hotel_valido):
        responses = [
            json.dumps(
                {"message": {"content": json.dumps(json_factura_valida)}, "eval_count": 500}
            ),
            json.dumps({"message": {"content": json.dumps(json_hotel_valido)}, "eval_count": 400}),
        ]
        call_idx = [0]

        def urlopen_side_effect(*args, **kwargs):
            resp = MagicMock()
            resp.__enter__ = MagicMock(return_value=resp)
            resp.__exit__ = MagicMock(return_value=False)
            idx = min(call_idx[0], len(responses) - 1)
            resp.read.return_value = responses[idx].encode("utf-8")
            call_idx[0] += 1
            return resp

        mock_urlopen.side_effect = urlopen_side_effect

        result = client.extraer_comprobantes(
            imagenes_b64=["img1", "img2"],
            archivo="exp.pdf",
            paginas=[1, 5],
        )
        assert isinstance(result, ResultadoExtraccion)
        assert result.total_paginas == 2
        assert result.paginas_procesadas == 2
        assert len(result.comprobantes) == 2
        assert result.deduplicados == 0

    @patch("src.extraction.qwen_fallback.urllib.request.urlopen")
    def test_deduplicacion_en_extraccion(self, mock_urlopen, client, json_factura_valida):
        """Dos páginas con el mismo comprobante → deduplicado."""
        resp_data = json.dumps(
            {
                "message": {"content": json.dumps(json_factura_valida)},
                "eval_count": 500,
            }
        ).encode("utf-8")

        def urlopen_side_effect(*args, **kwargs):
            resp = MagicMock()
            resp.__enter__ = MagicMock(return_value=resp)
            resp.__exit__ = MagicMock(return_value=False)
            resp.read.return_value = resp_data
            return resp

        mock_urlopen.side_effect = urlopen_side_effect

        result = client.extraer_comprobantes(
            imagenes_b64=["img1", "img2"],
            archivo="exp.pdf",
        )
        assert len(result.comprobantes) == 1
        assert result.deduplicados == 1

    def test_lista_vacia(self, client):
        result = client.extraer_comprobantes(imagenes_b64=[], archivo="test.pdf")
        assert result.total_paginas == 0
        assert len(result.comprobantes) == 0

    @patch("src.extraction.qwen_fallback.urllib.request.urlopen")
    def test_resultado_to_dict(self, mock_urlopen, client, json_factura_valida):
        resp = MagicMock()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        resp.read.return_value = json.dumps(
            {
                "message": {"content": json.dumps(json_factura_valida)},
                "eval_count": 500,
            }
        ).encode("utf-8")
        mock_urlopen.return_value = resp

        result = client.extraer_comprobantes(imagenes_b64=["img1"], archivo="test.pdf")
        d = result.to_dict()
        assert "total_comprobantes" in d
        assert "tiempo_total_s" in d
        assert d["total_comprobantes"] == 1


# =============================================================================
# Tests de healthcheck
# =============================================================================


class TestHealthcheck:
    @patch("src.extraction.qwen_fallback.urllib.request.urlopen")
    def test_healthcheck_ok(self, mock_urlopen, client):
        resp = MagicMock()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        resp.read.return_value = json.dumps({"models": [{"name": "qwen2.5vl:7b"}]}).encode("utf-8")
        mock_urlopen.return_value = resp

        assert client.healthcheck() is True

    @patch("src.extraction.qwen_fallback.urllib.request.urlopen")
    def test_healthcheck_modelo_no_disponible(self, mock_urlopen, client):
        resp = MagicMock()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        resp.read.return_value = json.dumps({"models": [{"name": "otro-modelo:1b"}]}).encode(
            "utf-8"
        )
        mock_urlopen.return_value = resp

        assert client.healthcheck() is False

    @patch("src.extraction.qwen_fallback.urllib.request.urlopen")
    def test_healthcheck_sin_conexion(self, mock_urlopen, client):
        mock_urlopen.side_effect = Exception("Connection refused")
        assert client.healthcheck() is False


# =============================================================================
# Tests de función de conveniencia
# =============================================================================


class TestFuncionConveniencia:
    @patch("src.extraction.qwen_fallback.urllib.request.urlopen")
    def test_extraer_comprobantes_vlm(self, mock_urlopen, json_factura_valida):
        resp = MagicMock()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        resp.read.return_value = json.dumps(
            {
                "message": {"content": json.dumps(json_factura_valida)},
                "eval_count": 500,
            }
        ).encode("utf-8")
        mock_urlopen.return_value = resp

        result = extraer_comprobantes_vlm(
            imagenes_b64=["img1"],
            archivo="test.pdf",
            paginas=[1],
        )
        assert isinstance(result, ResultadoExtraccion)
        assert len(result.comprobantes) == 1

    @patch("src.extraction.qwen_fallback.urllib.request.urlopen")
    def test_con_config_custom(self, mock_urlopen, json_factura_valida):
        resp = MagicMock()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        resp.read.return_value = json.dumps(
            {
                "message": {"content": json.dumps(json_factura_valida)},
                "eval_count": 100,
            }
        ).encode("utf-8")
        mock_urlopen.return_value = resp

        result = extraer_comprobantes_vlm(
            imagenes_b64=["img1"],
            config={"model": "test:1b", "max_retries": 1},
        )
        assert isinstance(result, ResultadoExtraccion)


# =============================================================================
# Tests de logging con TraceLogger
# =============================================================================


class TestTraceLogger:
    @patch("src.extraction.qwen_fallback.urllib.request.urlopen")
    def test_log_info_con_trace(self, mock_urlopen, json_factura_valida):
        mock_trace = MagicMock()
        client = QwenFallbackClient(trace_logger=mock_trace)

        resp = MagicMock()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        resp.read.return_value = json.dumps(
            {
                "message": {"content": json.dumps(json_factura_valida)},
                "eval_count": 500,
            }
        ).encode("utf-8")
        mock_urlopen.return_value = resp

        client._invocar_vlm("base64", "qwen3-vl:8b")
        mock_trace.info.assert_called()

    def test_log_sin_trace_no_falla(self, client):
        # No debe lanzar excepción
        client._log_info("test message")
        client._log_warning("test warning")

    @patch("src.extraction.qwen_fallback.urllib.request.urlopen")
    def test_trace_error_no_rompe_pipeline(self, mock_urlopen, json_factura_valida):
        """Si TraceLogger falla, el pipeline continúa."""
        mock_trace = MagicMock()
        mock_trace.info.side_effect = Exception("TraceLogger roto")
        client = QwenFallbackClient(trace_logger=mock_trace)

        resp = MagicMock()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        resp.read.return_value = json.dumps(
            {
                "message": {"content": json.dumps(json_factura_valida)},
                "eval_count": 500,
            }
        ).encode("utf-8")
        mock_urlopen.return_value = resp

        resultado = client._invocar_vlm("base64", "qwen3-vl:8b")
        assert resultado.exito is True


# =============================================================================
# Tests de ResultadoVLM
# =============================================================================


class TestResultadoVLM:
    def test_resultado_exitoso(self):
        r = ResultadoVLM(exito=True, json_extraido={"key": "val"}, intentos=1, modelo="qwen3-vl:8b")
        assert r.exito
        assert r.json_extraido == {"key": "val"}

    def test_resultado_fallido(self):
        r = ResultadoVLM(exito=False, error="timeout", intentos=2, modelo="qwen3-vl:8b")
        assert not r.exito
        assert r.error == "timeout"


class TestResultadoExtraccion:
    def test_to_dict(self):
        r = ResultadoExtraccion(
            total_paginas=10,
            paginas_procesadas=8,
            paginas_con_comprobante=5,
            tiempo_total_s=123.456,
            deduplicados=2,
        )
        d = r.to_dict()
        assert d["total_comprobantes"] == 0
        assert d["total_paginas"] == 10
        assert d["tiempo_total_s"] == 123.46
        assert d["deduplicados"] == 2
