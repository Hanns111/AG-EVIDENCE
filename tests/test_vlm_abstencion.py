# -*- coding: utf-8 -*-
"""
Tests para vlm_abstencion.py (Tarea #25)
==========================================
Verifica la abstención automática cuando el VLM falla.
"""

import os
import sys

import pytest

# Asegurar path del proyecto
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.settings import MetodoExtraccion, NivelObservacion
from src.extraction.abstencion import EvidenceStatus
from src.extraction.expediente_contract import ComprobanteExtraido
from src.extraction.vlm_abstencion import (
    AGENTE_VLM_ABSTENCION,
    VERSION_VLM_ABSTENCION,
    EstadisticasAbstencion,
    RazonFalloVLM,
    RegistroAbstencionVLM,
    VLMAbstencionHandler,
)

# ==============================================================================
# MOCK CLIENT
# ==============================================================================


class MockVLMClient:
    """Simula QwenFallbackClient para tests."""

    def __init__(self, resultado=None, excepcion=None):
        self.resultado = resultado
        self.excepcion = excepcion
        self.model = "qwen3-vl:8b"
        self.llamadas = 0

    def extraer_comprobante(self, image_b64, archivo="", pagina=0):
        self.llamadas += 1
        if self.excepcion:
            raise self.excepcion
        return self.resultado


class MockComprobanteExtraido:
    """Comprobante simulado exitoso."""

    pass


def _comprobante_real():
    """Crea un ComprobanteExtraido mínimo válido."""
    from src.extraction.expediente_contract import (
        ClasificacionGasto,
        CondicionesComerciales,
        DatosAdquirente,
        DatosComprobante,
        DatosEmisor,
        MetadatosExtraccion,
        TotalesTributos,
        ValidacionesAritmeticas,
    )

    return ComprobanteExtraido(
        grupo_a=DatosEmisor(),
        grupo_b=DatosComprobante(),
        grupo_c=DatosAdquirente(),
        grupo_d=CondicionesComerciales(),
        grupo_e=[],
        grupo_f=TotalesTributos(),
        grupo_g=ClasificacionGasto(),
        grupo_h=None,
        grupo_i=None,
        grupo_j=ValidacionesAritmeticas(),
        grupo_k=MetadatosExtraccion(pagina_origen=1),
    )


# ==============================================================================
# CONSTANTES
# ==============================================================================


class TestConstantes:
    def test_version(self):
        assert VERSION_VLM_ABSTENCION == "1.0.0"

    def test_agente_id(self):
        assert AGENTE_VLM_ABSTENCION == "VLM_ABSTENCION"


# ==============================================================================
# RazonFalloVLM
# ==============================================================================


class TestRazonFalloVLM:
    def test_json_corrupto(self):
        assert (
            RazonFalloVLM.desde_error("JSON corrupto tras 2 intentos")
            == RazonFalloVLM.JSON_CORRUPTO
        )

    def test_timeout(self):
        assert RazonFalloVLM.desde_error("Request timed out") == RazonFalloVLM.TIMEOUT

    def test_conexion(self):
        assert RazonFalloVLM.desde_error("connection_error: refused") == RazonFalloVLM.CONEXION

    def test_respuesta_vacia(self):
        assert (
            RazonFalloVLM.desde_error("respuesta vacía del modelo") == RazonFalloVLM.RESPUESTA_VACIA
        )

    def test_modelo_no_disponible(self):
        assert RazonFalloVLM.desde_error("model not found") == RazonFalloVLM.MODELO_NO_DISPONIBLE

    def test_error_desconocido(self):
        assert RazonFalloVLM.desde_error("algo raro pasó") == RazonFalloVLM.ERROR_INESPERADO

    def test_urlopen_es_conexion(self):
        assert RazonFalloVLM.desde_error("urlopen error") == RazonFalloVLM.CONEXION


# ==============================================================================
# RegistroAbstencionVLM
# ==============================================================================


class TestRegistroAbstencionVLM:
    def test_creacion(self):
        r = RegistroAbstencionVLM(
            archivo="test.pdf",
            pagina=5,
            razon=RazonFalloVLM.JSON_CORRUPTO,
            detalle_error="JSON corrupto",
        )
        assert r.archivo == "test.pdf"
        assert r.pagina == 5
        assert r.timestamp != ""

    def test_to_dict(self):
        r = RegistroAbstencionVLM(
            archivo="test.pdf",
            pagina=5,
            razon=RazonFalloVLM.TIMEOUT,
            detalle_error="timed out",
            modelo_intentado="qwen3-vl:8b",
        )
        d = r.to_dict()
        assert d["razon"] == "timeout"
        assert d["modelo_intentado"] == "qwen3-vl:8b"


# ==============================================================================
# EstadisticasAbstencion
# ==============================================================================


class TestEstadisticasAbstencion:
    def test_defaults(self):
        e = EstadisticasAbstencion()
        assert e.total_intentos == 0
        assert e.tasa_fallo == 0.0

    def test_tasa_fallo(self):
        e = EstadisticasAbstencion(total_intentos=10, total_abstenciones=3)
        assert e.tasa_fallo == 0.3

    def test_to_dict(self):
        e = EstadisticasAbstencion(total_intentos=5, total_exitos=4, total_abstenciones=1)
        d = e.to_dict()
        assert d["tasa_fallo"] == 0.2
        assert d["total_exitos"] == 4


# ==============================================================================
# VLMAbstencionHandler — extraer_o_abstener
# ==============================================================================


class TestExtraerOAbstener:
    def setup_method(self):
        self.handler = VLMAbstencionHandler()

    def test_extraccion_exitosa(self):
        comp = _comprobante_real()
        client = MockVLMClient(resultado=comp)
        resultado = self.handler.extraer_o_abstener(
            client=client, image_b64="img", archivo="test.pdf", pagina=1
        )
        assert resultado is comp
        assert self.handler.stats.total_exitos == 1
        assert self.handler.stats.total_abstenciones == 0

    def test_extraccion_fallida_genera_abstencion(self):
        client = MockVLMClient(resultado=None)
        resultado = self.handler.extraer_o_abstener(
            client=client, image_b64="img", archivo="test.pdf", pagina=3
        )
        assert isinstance(resultado, ComprobanteExtraido)
        assert resultado.grupo_k.metodo_extraccion == "vlm_abstencion"
        assert resultado.grupo_k.confianza_global == "ilegible"
        assert self.handler.stats.total_abstenciones == 1

    def test_excepcion_genera_abstencion(self):
        client = MockVLMClient(excepcion=RuntimeError("GPU OOM"))
        resultado = self.handler.extraer_o_abstener(
            client=client, image_b64="img", archivo="test.pdf", pagina=7
        )
        assert isinstance(resultado, ComprobanteExtraido)
        assert resultado.grupo_k.metodo_extraccion == "vlm_abstencion"
        assert self.handler.stats.total_abstenciones == 1

    def test_nunca_retorna_none(self):
        """El contrato: SIEMPRE retorna ComprobanteExtraido."""
        client = MockVLMClient(resultado=None)
        for i in range(5):
            r = self.handler.extraer_o_abstener(
                client=client, image_b64="img", archivo="test.pdf", pagina=i
            )
            assert r is not None
        assert self.handler.stats.total_abstenciones == 5

    def test_estadisticas_se_acumulan(self):
        comp = _comprobante_real()
        client_ok = MockVLMClient(resultado=comp)
        client_fail = MockVLMClient(resultado=None)

        self.handler.extraer_o_abstener(client_ok, "img", "a.pdf", 1)
        self.handler.extraer_o_abstener(client_ok, "img", "a.pdf", 2)
        self.handler.extraer_o_abstener(client_fail, "img", "a.pdf", 3)

        assert self.handler.stats.total_intentos == 3
        assert self.handler.stats.total_exitos == 2
        assert self.handler.stats.total_abstenciones == 1


# ==============================================================================
# VLMAbstencionHandler — extraer_lote_o_abstener
# ==============================================================================


class TestExtraerLoteOAbstener:
    def setup_method(self):
        self.handler = VLMAbstencionHandler()

    def test_lote_completo_exitoso(self):
        comp = _comprobante_real()
        client = MockVLMClient(resultado=comp)
        resultados = self.handler.extraer_lote_o_abstener(
            client=client,
            imagenes_b64=["img1", "img2", "img3"],
            archivo="test.pdf",
        )
        assert len(resultados) == 3
        assert self.handler.stats.total_exitos == 3

    def test_lote_con_fallos(self):
        """Client que alterna éxito/fallo."""

        class AlternatingClient:
            model = "qwen3-vl:8b"

            def __init__(self):
                self.call_count = 0

            def extraer_comprobante(self, image_b64, archivo="", pagina=0):
                self.call_count += 1
                if self.call_count % 2 == 0:
                    return None
                return _comprobante_real()

        client = AlternatingClient()
        resultados = self.handler.extraer_lote_o_abstener(
            client=client,
            imagenes_b64=["img1", "img2", "img3", "img4"],
            archivo="test.pdf",
            paginas=[1, 2, 3, 4],
        )
        assert len(resultados) == 4  # Todos tienen resultado
        assert self.handler.stats.total_exitos == 2
        assert self.handler.stats.total_abstenciones == 2

    def test_lote_vacio(self):
        client = MockVLMClient()
        resultados = self.handler.extraer_lote_o_abstener(
            client=client, imagenes_b64=[], archivo="test.pdf"
        )
        assert len(resultados) == 0

    def test_lote_paginas_custom(self):
        comp = _comprobante_real()
        client = MockVLMClient(resultado=comp)
        resultados = self.handler.extraer_lote_o_abstener(
            client=client,
            imagenes_b64=["img1", "img2"],
            archivo="test.pdf",
            paginas=[10, 15],
        )
        assert len(resultados) == 2


# ==============================================================================
# VLMAbstencionHandler — generar_abstencion_vlm
# ==============================================================================


class TestGenerarAbstencionVLM:
    def setup_method(self):
        self.handler = VLMAbstencionHandler()

    def test_genera_comprobante_esqueleto(self):
        comp = self.handler.generar_abstencion_vlm(
            archivo="test.pdf", pagina=5, razon="JSON corrupto"
        )
        assert isinstance(comp, ComprobanteExtraido)
        assert comp.grupo_k.pagina_origen == 5
        assert comp.grupo_k.metodo_extraccion == "vlm_abstencion"
        assert comp.grupo_k.confianza_global == "ilegible"

    def test_campos_obligatorios_ilegibles(self):
        comp = self.handler.generar_abstencion_vlm(archivo="test.pdf", pagina=5, razon="timeout")
        # Grupo A
        assert comp.grupo_a.ruc_emisor is not None
        assert comp.grupo_a.ruc_emisor.valor is None
        assert comp.grupo_a.ruc_emisor.confianza == 0.0
        assert comp.grupo_a.ruc_emisor.status == EvidenceStatus.ILEGIBLE
        assert comp.grupo_a.ruc_emisor.regla_aplicada == "ABSTENCION"

    def test_grupo_b_ilegible(self):
        comp = self.handler.generar_abstencion_vlm(archivo="test.pdf", pagina=5, razon="error")
        assert comp.grupo_b.serie.valor is None
        assert comp.grupo_b.serie.confianza == 0.0
        assert comp.grupo_b.serie.status == EvidenceStatus.ILEGIBLE

    def test_grupo_f_totales_ilegibles(self):
        comp = self.handler.generar_abstencion_vlm(archivo="test.pdf", pagina=5, razon="error")
        assert comp.grupo_f.importe_total.valor is None
        assert comp.grupo_f.importe_total.confianza == 0.0

    def test_grupos_opcionales_none(self):
        comp = self.handler.generar_abstencion_vlm(archivo="test.pdf", pagina=5, razon="error")
        assert comp.grupo_h is None
        assert comp.grupo_i is None
        assert comp.grupo_e == []

    def test_snippet_contiene_razon(self):
        comp = self.handler.generar_abstencion_vlm(
            archivo="test.pdf", pagina=5, razon="JSON corrupto tras 2 intentos"
        )
        assert "ABSTENCION VLM" in comp.grupo_a.ruc_emisor.snippet
        assert "JSON corrupto" in comp.grupo_a.ruc_emisor.snippet

    def test_motor_ocr_refleja_modelo(self):
        comp = self.handler.generar_abstencion_vlm(
            archivo="test.pdf", pagina=5, razon="error", modelo="qwen3-vl:8b"
        )
        assert comp.grupo_a.ruc_emisor.motor_ocr == "qwen3-vl:8b"

    def test_motor_ocr_default_vlm_fallido(self):
        comp = self.handler.generar_abstencion_vlm(archivo="test.pdf", pagina=5, razon="error")
        assert comp.grupo_a.ruc_emisor.motor_ocr == "vlm_fallido"

    def test_metodo_es_heuristica(self):
        comp = self.handler.generar_abstencion_vlm(archivo="test.pdf", pagina=5, razon="error")
        assert comp.grupo_a.ruc_emisor.metodo == MetodoExtraccion.HEURISTICA


# ==============================================================================
# VLMAbstencionHandler — generar_hallazgo
# ==============================================================================


class TestGenerarHallazgo:
    def setup_method(self):
        self.handler = VLMAbstencionHandler()

    def test_hallazgo_nivel_mayor(self):
        h = self.handler.generar_hallazgo(
            archivo="test.pdf",
            pagina=5,
            razon=RazonFalloVLM.JSON_CORRUPTO,
        )
        assert h.nivel == NivelObservacion.MAYOR

    def test_hallazgo_requiere_revision(self):
        h = self.handler.generar_hallazgo(
            archivo="test.pdf",
            pagina=5,
            razon=RazonFalloVLM.TIMEOUT,
        )
        assert h.requiere_revision_humana is True

    def test_hallazgo_contiene_archivo_pagina(self):
        h = self.handler.generar_hallazgo(
            archivo="exp.pdf",
            pagina=10,
            razon=RazonFalloVLM.CONEXION,
        )
        assert "exp.pdf" in h.descripcion
        assert "10" in h.descripcion
        assert "exp.pdf" in h.evidencia

    def test_hallazgo_con_detalle(self):
        h = self.handler.generar_hallazgo(
            archivo="test.pdf",
            pagina=5,
            razon=RazonFalloVLM.JSON_CORRUPTO,
            detalle="respuesta contenía HTML en vez de JSON",
        )
        assert "HTML" in h.descripcion

    def test_hallazgo_agente_correcto(self):
        h = self.handler.generar_hallazgo(
            archivo="test.pdf",
            pagina=5,
            razon=RazonFalloVLM.ERROR_INESPERADO,
        )
        assert h.agente == AGENTE_VLM_ABSTENCION

    def test_hallazgo_regla_aplicada(self):
        h = self.handler.generar_hallazgo(
            archivo="test.pdf",
            pagina=5,
            razon=RazonFalloVLM.TIMEOUT,
        )
        assert h.regla_aplicada == "ABSTENCION_VLM_TIMEOUT"


# ==============================================================================
# VLMAbstencionHandler — estadísticas
# ==============================================================================


class TestEstadisticas:
    def test_reset(self):
        handler = VLMAbstencionHandler()
        handler.stats.total_intentos = 10
        handler.reset_estadisticas()
        assert handler.stats.total_intentos == 0

    def test_get_estadisticas(self):
        handler = VLMAbstencionHandler()
        stats = handler.get_estadisticas()
        assert isinstance(stats, EstadisticasAbstencion)

    def test_por_razon_se_acumula(self):
        handler = VLMAbstencionHandler()
        client = MockVLMClient(resultado=None)

        handler.extraer_o_abstener(client, "img", "a.pdf", 1)
        handler.extraer_o_abstener(client, "img", "a.pdf", 2)

        stats = handler.get_estadisticas()
        assert stats.total_abstenciones == 2
        assert len(stats.registros) == 2


# ==============================================================================
# VLMAbstencionHandler — trace logger
# ==============================================================================


class TestTraceLogger:
    def test_sin_logger(self):
        handler = VLMAbstencionHandler()
        client = MockVLMClient(resultado=None)
        r = handler.extraer_o_abstener(client, "img", "a.pdf", 1)
        assert r is not None  # No explota sin logger

    def test_con_logger(self):
        class MockLogger:
            def __init__(self):
                self.warnings = []

            def warning(self, msg, **kwargs):
                self.warnings.append(msg)

        log = MockLogger()
        handler = VLMAbstencionHandler(trace_logger=log)
        client = MockVLMClient(resultado=None)
        handler.extraer_o_abstener(client, "img", "a.pdf", 1)
        assert len(log.warnings) >= 1
        assert "Abstención VLM" in log.warnings[0]

    def test_logger_roto_no_explota(self):
        class BrokenLogger:
            def warning(self, msg, **kwargs):
                raise RuntimeError("boom")

        handler = VLMAbstencionHandler(trace_logger=BrokenLogger())
        client = MockVLMClient(resultado=None)
        r = handler.extraer_o_abstener(client, "img", "a.pdf", 1)
        assert r is not None
