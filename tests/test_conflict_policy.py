# -*- coding: utf-8 -*-
"""
Tests para conflict_policy.py (Tarea #24)
==========================================
Verifica la política de resolución de conflictos OCR vs VLM.
"""

import os
import sys

import pytest

# Asegurar path del proyecto
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.settings import MetodoExtraccion
from src.extraction.abstencion import CampoExtraido, EvidenceStatus
from src.extraction.conflict_policy import (
    CAMPOS_PREFER_OCR,
    CAMPOS_PREFER_VLM,
    MOTORES_OCR,
    MOTORES_VLM,
    VERSION_CONFLICT_POLICY,
    ConflictRecord,
    ConflictResolver,
    ResultadoResolucion,
    ResumenConflictos,
)

# ==============================================================================
# FIXTURES
# ==============================================================================


def _campo(
    nombre: str = "ruc",
    valor: str = "20123456789",
    confianza: float = 0.85,
    motor: str = "paddleocr_gpu",
    metodo: MetodoExtraccion = MetodoExtraccion.OCR,
) -> CampoExtraido:
    """Factory para CampoExtraido de prueba."""
    return CampoExtraido(
        nombre_campo=nombre,
        valor=valor,
        archivo="test.pdf",
        pagina=1,
        confianza=confianza,
        metodo=metodo,
        snippet=f"{nombre}: {valor}",
        motor_ocr=motor,
        status=EvidenceStatus.LEGIBLE,
    )


def _campo_ocr(
    nombre: str = "ruc",
    valor: str = "20123456789",
    confianza: float = 0.85,
) -> CampoExtraido:
    """Campo extraído por OCR."""
    return _campo(
        nombre=nombre,
        valor=valor,
        confianza=confianza,
        motor="paddleocr_gpu",
        metodo=MetodoExtraccion.OCR,
    )


def _campo_vlm(
    nombre: str = "ruc",
    valor: str = "20123456789",
    confianza: float = 0.80,
) -> CampoExtraido:
    """Campo extraído por VLM."""
    return _campo(
        nombre=nombre,
        valor=valor,
        confianza=confianza,
        motor="qwen3-vl:8b",
        metodo=MetodoExtraccion.HEURISTICA,
    )


# ==============================================================================
# CONSTANTES
# ==============================================================================


class TestConstantes:
    """Verificar constantes del módulo."""

    def test_version(self):
        assert VERSION_CONFLICT_POLICY == "1.0.0"

    def test_motores_ocr_no_vacio(self):
        assert len(MOTORES_OCR) > 0

    def test_motores_vlm_no_vacio(self):
        assert len(MOTORES_VLM) > 0

    def test_paddleocr_en_motores_ocr(self):
        assert "paddleocr_gpu" in MOTORES_OCR

    def test_qwen_en_motores_vlm(self):
        assert "qwen3-vl:8b" in MOTORES_VLM

    def test_campos_prefer_ocr_contiene_ruc(self):
        assert "ruc" in CAMPOS_PREFER_OCR

    def test_campos_prefer_ocr_contiene_monto(self):
        assert "monto" in CAMPOS_PREFER_OCR

    def test_campos_prefer_vlm_contiene_razon_social(self):
        assert "razon_social" in CAMPOS_PREFER_VLM

    def test_campos_prefer_vlm_contiene_direccion(self):
        assert "direccion_emisor" in CAMPOS_PREFER_VLM

    def test_sin_solapamiento_ocr_vlm(self):
        """OCR y VLM no deben compartir campos."""
        assert CAMPOS_PREFER_OCR & CAMPOS_PREFER_VLM == set()


# ==============================================================================
# DATACLASSES
# ==============================================================================


class TestConflictRecord:
    """Verificar ConflictRecord."""

    def test_to_dict(self):
        record = ConflictRecord(
            nombre_campo="ruc",
            valor_ocr="20123456789",
            valor_vlm="20123456780",
            confianza_ocr=0.85,
            confianza_vlm=0.75,
            motor_ocr="paddleocr_gpu",
            motor_vlm="qwen3-vl:8b",
            ganador="ocr",
            razon="campo_numerico_prefer_ocr",
        )
        d = record.to_dict()
        assert d["nombre_campo"] == "ruc"
        assert d["ganador"] == "ocr"
        assert d["requiere_revision"] is False

    def test_requiere_revision_flag(self):
        record = ConflictRecord(
            nombre_campo="ruc",
            valor_ocr="20123456789",
            valor_vlm="20123456780",
            confianza_ocr=0.85,
            confianza_vlm=0.75,
            motor_ocr="paddleocr_gpu",
            motor_vlm="qwen3-vl:8b",
            ganador="ocr",
            razon="test",
            requiere_revision=True,
        )
        assert record.requiere_revision is True
        assert record.to_dict()["requiere_revision"] is True


class TestResultadoResolucion:
    """Verificar ResultadoResolucion."""

    def test_sin_conflicto(self):
        campo = _campo_ocr()
        r = ResultadoResolucion(campo_ganador=campo)
        assert r.hubo_conflicto is False
        assert r.registro is None

    def test_to_dict_con_conflicto(self):
        campo = _campo_ocr()
        record = ConflictRecord(
            nombre_campo="ruc",
            valor_ocr="A",
            valor_vlm="B",
            confianza_ocr=0.8,
            confianza_vlm=0.7,
            motor_ocr="paddleocr_gpu",
            motor_vlm="qwen3-vl:8b",
            ganador="ocr",
            razon="test",
        )
        r = ResultadoResolucion(
            campo_ganador=campo,
            hubo_conflicto=True,
            registro=record,
        )
        d = r.to_dict()
        assert d["hubo_conflicto"] is True
        assert d["registro"]["ganador"] == "ocr"

    def test_to_dict_sin_ganador(self):
        r = ResultadoResolucion(campo_ganador=None)
        d = r.to_dict()
        assert d["campo_ganador"] is None


class TestResumenConflictos:
    """Verificar ResumenConflictos."""

    def test_default_values(self):
        r = ResumenConflictos()
        assert r.total_campos == 0
        assert r.conflictos == 0
        assert r.registros == []

    def test_to_dict(self):
        r = ResumenConflictos(total_campos=10, conflictos=2)
        d = r.to_dict()
        assert d["total_campos"] == 10
        assert d["conflictos"] == 2


# ==============================================================================
# RESOLVER — CASOS BÁSICOS
# ==============================================================================


class TestResolverCasosBasicos:
    """Casos donde no hay conflicto real."""

    def setup_method(self):
        self.resolver = ConflictResolver()

    def test_ambos_none(self):
        r = self.resolver.resolver(None, None)
        assert r.campo_ganador is None
        assert r.hubo_conflicto is False

    def test_solo_campo_a(self):
        campo = _campo_ocr()
        r = self.resolver.resolver(campo, None)
        assert r.campo_ganador is campo
        assert r.hubo_conflicto is False

    def test_solo_campo_b(self):
        campo = _campo_vlm()
        r = self.resolver.resolver(None, campo)
        assert r.campo_ganador is campo
        assert r.hubo_conflicto is False

    def test_campo_a_valor_none(self):
        a = _campo_ocr(valor=None)
        b = _campo_vlm(valor="20123456789")
        r = self.resolver.resolver(a, b)
        assert r.campo_ganador is b

    def test_campo_b_valor_none(self):
        a = _campo_ocr(valor="20123456789")
        b = _campo_vlm(valor=None)
        r = self.resolver.resolver(a, b)
        assert r.campo_ganador is a

    def test_ambos_valor_none_mayor_confianza(self):
        a = _campo_ocr(valor=None, confianza=0.5)
        b = _campo_vlm(valor=None, confianza=0.3)
        r = self.resolver.resolver(a, b)
        assert r.campo_ganador is a

    def test_valores_equivalentes_sin_conflicto(self):
        a = _campo_ocr(valor="20123456789", confianza=0.9)
        b = _campo_vlm(valor="20123456789", confianza=0.8)
        r = self.resolver.resolver(a, b)
        assert r.campo_ganador is a  # mayor confianza
        assert r.hubo_conflicto is False

    def test_valores_equivalentes_case_insensitive(self):
        a = _campo_ocr(nombre="razon_social", valor="EMPRESA SAC", confianza=0.7)
        b = _campo_vlm(nombre="razon_social", valor="empresa sac", confianza=0.9)
        r = self.resolver.resolver(a, b)
        assert r.campo_ganador is b  # mayor confianza
        assert r.hubo_conflicto is False

    def test_valores_equivalentes_espacios_extra(self):
        a = _campo_ocr(nombre="razon_social", valor="EMPRESA   SAC", confianza=0.8)
        b = _campo_vlm(nombre="razon_social", valor="EMPRESA SAC", confianza=0.7)
        r = self.resolver.resolver(a, b)
        assert r.hubo_conflicto is False


# ==============================================================================
# RESOLVER — CONFLICTOS POR TIPO DE CAMPO
# ==============================================================================


class TestResolverConflictoCampo:
    """Conflictos reales resueltos por tipo de campo."""

    def setup_method(self):
        self.resolver = ConflictResolver()

    def test_ruc_prefiere_ocr(self):
        a = _campo_ocr(nombre="ruc", valor="20123456789", confianza=0.8)
        b = _campo_vlm(nombre="ruc", valor="20123456780", confianza=0.9)
        r = self.resolver.resolver(a, b)
        assert r.hubo_conflicto is True
        assert r.campo_ganador.valor == "20123456789"
        assert r.registro.ganador == "ocr"
        assert r.registro.razon == "campo_numerico_prefer_ocr"

    def test_monto_prefiere_ocr(self):
        a = _campo_ocr(nombre="monto", valor="150.00", confianza=0.7)
        b = _campo_vlm(nombre="monto", valor="1500.00", confianza=0.9)
        r = self.resolver.resolver(a, b)
        assert r.hubo_conflicto is True
        assert r.campo_ganador.valor == "150.00"
        assert r.registro.ganador == "ocr"

    def test_serie_numero_prefiere_ocr(self):
        a = _campo_ocr(nombre="serie_numero", valor="F011-8846", confianza=0.85)
        b = _campo_vlm(nombre="serie_numero", valor="F011-8846X", confianza=0.80)
        r = self.resolver.resolver(a, b)
        assert r.campo_ganador.valor == "F011-8846"

    def test_igv_monto_prefiere_ocr(self):
        a = _campo_ocr(nombre="igv_monto", valor="27.00", confianza=0.75)
        b = _campo_vlm(nombre="igv_monto", valor="27.50", confianza=0.85)
        r = self.resolver.resolver(a, b)
        assert r.campo_ganador.valor == "27.00"

    def test_razon_social_prefiere_vlm(self):
        a = _campo_ocr(nombre="razon_social", valor="EMPR3SA SAC", confianza=0.9)
        b = _campo_vlm(nombre="razon_social", valor="EMPRESA SAC", confianza=0.8)
        r = self.resolver.resolver(a, b)
        assert r.hubo_conflicto is True
        assert r.campo_ganador.valor == "EMPRESA SAC"
        assert r.registro.ganador == "vlm"
        assert r.registro.razon == "campo_texto_prefer_vlm"

    def test_direccion_prefiere_vlm(self):
        a = _campo_ocr(nombre="direccion_emisor", valor="Jr. P3dro 398", confianza=0.85)
        b = _campo_vlm(nombre="direccion_emisor", valor="Jr. Pedro 398", confianza=0.80)
        r = self.resolver.resolver(a, b)
        assert r.campo_ganador.valor == "Jr. Pedro 398"

    def test_descripcion_prefiere_vlm(self):
        a = _campo_ocr(nombre="descripcion", valor="ALMUERZ0", confianza=0.7)
        b = _campo_vlm(nombre="descripcion", valor="ALMUERZO", confianza=0.8)
        r = self.resolver.resolver(a, b)
        assert r.campo_ganador.valor == "ALMUERZO"
        assert r.registro.ganador == "vlm"

    def test_monto_letras_prefiere_vlm(self):
        a = _campo_ocr(nombre="monto_letras", valor="C1EN SOLES", confianza=0.6)
        b = _campo_vlm(nombre="monto_letras", valor="CIEN SOLES", confianza=0.7)
        r = self.resolver.resolver(a, b)
        assert r.campo_ganador.valor == "CIEN SOLES"


# ==============================================================================
# RESOLVER — CAMPO NO CLASIFICADO (CONFIANZA)
# ==============================================================================


class TestResolverCampoNoClasificado:
    """Campos que no están en OCR ni VLM — se resuelven por confianza."""

    def setup_method(self):
        self.resolver = ConflictResolver()

    def test_campo_desconocido_mayor_confianza_ocr(self):
        a = _campo_ocr(nombre="campo_nuevo", valor="A", confianza=0.9)
        b = _campo_vlm(nombre="campo_nuevo", valor="B", confianza=0.7)
        r = self.resolver.resolver(a, b)
        assert r.campo_ganador.valor == "A"
        assert r.registro.razon == "confianza_mayor_ocr"

    def test_campo_desconocido_mayor_confianza_vlm(self):
        a = _campo_ocr(nombre="campo_nuevo", valor="A", confianza=0.6)
        b = _campo_vlm(nombre="campo_nuevo", valor="B", confianza=0.9)
        r = self.resolver.resolver(a, b)
        assert r.campo_ganador.valor == "B"
        assert r.registro.razon == "confianza_mayor_vlm"

    def test_campo_desconocido_empate_tiebreak_ocr(self):
        a = _campo_ocr(nombre="campo_nuevo", valor="A", confianza=0.8)
        b = _campo_vlm(nombre="campo_nuevo", valor="B", confianza=0.8)
        r = self.resolver.resolver(a, b)
        assert r.campo_ganador.valor == "A"
        assert r.registro.razon == "empate_tiebreak_ocr"


# ==============================================================================
# RESOLVER — REQUIERE REVISIÓN
# ==============================================================================


class TestRequiereRevision:
    """El flag requiere_revision se activa cuando el descartado tiene mucha más confianza."""

    def setup_method(self):
        self.resolver = ConflictResolver()

    def test_requiere_revision_cuando_descartado_mucho_mas_confiable(self):
        """OCR gana por regla de campo, pero VLM tiene 0.4 más confianza."""
        a = _campo_ocr(nombre="ruc", valor="20123456789", confianza=0.5)
        b = _campo_vlm(nombre="ruc", valor="20123456780", confianza=0.95)
        r = self.resolver.resolver(a, b)
        assert r.registro.requiere_revision is True

    def test_no_requiere_revision_diferencia_normal(self):
        a = _campo_ocr(nombre="ruc", valor="20123456789", confianza=0.8)
        b = _campo_vlm(nombre="ruc", valor="20123456780", confianza=0.9)
        r = self.resolver.resolver(a, b)
        assert r.registro.requiere_revision is False

    def test_no_requiere_revision_ganador_mas_confiable(self):
        a = _campo_ocr(nombre="ruc", valor="20123456789", confianza=0.95)
        b = _campo_vlm(nombre="ruc", valor="20123456780", confianza=0.5)
        r = self.resolver.resolver(a, b)
        assert r.registro.requiere_revision is False


# ==============================================================================
# RESOLVER — MOTORES NO DIFERENCIADOS
# ==============================================================================


class TestMotoresNoDiferenciados:
    """Cuando no se puede distinguir OCR de VLM, se usa confianza pura."""

    def setup_method(self):
        self.resolver = ConflictResolver()

    def test_ambos_motor_desconocido(self):
        a = _campo(
            nombre="ruc", valor="A", confianza=0.8, motor="desconocido", metodo=MetodoExtraccion.OCR
        )
        b = _campo(
            nombre="ruc", valor="B", confianza=0.6, motor="otro", metodo=MetodoExtraccion.OCR
        )
        r = self.resolver.resolver(a, b)
        assert r.campo_ganador.valor == "A"

    def test_ambos_motor_desconocido_b_gana(self):
        a = _campo(
            nombre="ruc", valor="A", confianza=0.5, motor="desconocido", metodo=MetodoExtraccion.OCR
        )
        b = _campo(
            nombre="ruc", valor="B", confianza=0.9, motor="otro", metodo=MetodoExtraccion.OCR
        )
        r = self.resolver.resolver(a, b)
        assert r.campo_ganador.valor == "B"


# ==============================================================================
# IDENTIFICACIÓN DE MOTORES
# ==============================================================================


class TestIdentificacionMotores:
    """Verificar _es_motor_ocr y _es_motor_vlm."""

    def setup_method(self):
        self.resolver = ConflictResolver()

    def test_paddleocr_es_ocr(self):
        c = _campo(motor="paddleocr_gpu", metodo=MetodoExtraccion.OCR)
        assert self.resolver._es_motor_ocr(c) is True
        assert self.resolver._es_motor_vlm(c) is False

    def test_tesseract_es_ocr(self):
        c = _campo(motor="tesseract", metodo=MetodoExtraccion.OCR)
        assert self.resolver._es_motor_ocr(c) is True

    def test_pymupdf_es_ocr(self):
        c = _campo(motor="pymupdf", metodo=MetodoExtraccion.PDF_TEXT)
        assert self.resolver._es_motor_ocr(c) is True

    def test_qwen_es_vlm(self):
        c = _campo(motor="qwen3-vl:8b", metodo=MetodoExtraccion.HEURISTICA)
        assert self.resolver._es_motor_vlm(c) is True
        assert self.resolver._es_motor_ocr(c) is False

    def test_qwen25_es_vlm(self):
        c = _campo(motor="qwen2.5vl:7b", metodo=MetodoExtraccion.HEURISTICA)
        assert self.resolver._es_motor_vlm(c) is True

    def test_qwen_substring_es_vlm(self):
        """Cualquier motor con 'qwen' en el nombre es VLM."""
        c = _campo(motor="qwen_custom", metodo=MetodoExtraccion.HEURISTICA)
        assert self.resolver._es_motor_vlm(c) is True

    def test_metodo_pdf_text_es_ocr(self):
        c = _campo(motor="algo", metodo=MetodoExtraccion.PDF_TEXT)
        assert self.resolver._es_motor_ocr(c) is True

    def test_metodo_regex_es_ocr(self):
        c = _campo(motor="algo", metodo=MetodoExtraccion.REGEX)
        assert self.resolver._es_motor_ocr(c) is True


# ==============================================================================
# VALORES EQUIVALENTES
# ==============================================================================


class TestValoresEquivalentes:
    """Verificar comparación de valores normalizada."""

    def setup_method(self):
        self.resolver = ConflictResolver()

    def test_iguales(self):
        assert self.resolver._valores_equivalentes("abc", "abc") is True

    def test_case_insensitive(self):
        assert self.resolver._valores_equivalentes("ABC", "abc") is True

    def test_espacios_extra(self):
        assert self.resolver._valores_equivalentes("A  B  C", "A B C") is True

    def test_trim(self):
        assert self.resolver._valores_equivalentes("  abc  ", "abc") is True

    def test_diferentes(self):
        assert self.resolver._valores_equivalentes("abc", "def") is False

    def test_none_none(self):
        assert self.resolver._valores_equivalentes(None, None) is True

    def test_none_valor(self):
        assert self.resolver._valores_equivalentes(None, "abc") is False

    def test_valor_none(self):
        assert self.resolver._valores_equivalentes("abc", None) is False


# ==============================================================================
# RESOLVER LOTE
# ==============================================================================


class TestResolverLote:
    """Verificar resolución de lotes completos."""

    def setup_method(self):
        self.resolver = ConflictResolver()

    def test_lote_vacio(self):
        campos, resumen = self.resolver.resolver_lote([], [])
        assert len(campos) == 0
        assert resumen.total_campos == 0

    def test_lote_sin_conflicto(self):
        ocr = [_campo_ocr(nombre="ruc", valor="20123456789")]
        vlm = [_campo_vlm(nombre="ruc", valor="20123456789")]
        campos, resumen = self.resolver.resolver_lote(ocr, vlm)
        assert len(campos) == 1
        assert resumen.conflictos == 0

    def test_lote_solo_ocr(self):
        ocr = [
            _campo_ocr(nombre="ruc", valor="20123456789"),
            _campo_ocr(nombre="monto", valor="100.00"),
        ]
        campos, resumen = self.resolver.resolver_lote(ocr, [])
        assert len(campos) == 2
        assert resumen.total_campos == 2
        assert resumen.conflictos == 0

    def test_lote_solo_vlm(self):
        vlm = [
            _campo_vlm(nombre="razon_social", valor="EMPRESA SAC"),
        ]
        campos, resumen = self.resolver.resolver_lote([], vlm)
        assert len(campos) == 1
        assert resumen.conflictos == 0

    def test_lote_con_conflicto(self):
        ocr = [
            _campo_ocr(nombre="ruc", valor="20123456789", confianza=0.8),
            _campo_ocr(nombre="razon_social", valor="EMPR3SA", confianza=0.7),
        ]
        vlm = [
            _campo_vlm(nombre="ruc", valor="20123456780", confianza=0.9),
            _campo_vlm(nombre="razon_social", valor="EMPRESA SAC", confianza=0.8),
        ]
        campos, resumen = self.resolver.resolver_lote(ocr, vlm)
        assert len(campos) == 2
        assert resumen.conflictos == 2
        assert resumen.resueltos_ocr == 1  # ruc → OCR
        assert resumen.resueltos_vlm == 1  # razon_social → VLM

    def test_lote_campos_disjuntos(self):
        """Campos que solo aparecen en un motor."""
        ocr = [_campo_ocr(nombre="ruc", valor="20123456789")]
        vlm = [_campo_vlm(nombre="razon_social", valor="EMPRESA SAC")]
        campos, resumen = self.resolver.resolver_lote(ocr, vlm)
        assert len(campos) == 2
        assert resumen.total_campos == 2
        assert resumen.conflictos == 0

    def test_lote_resumen_to_dict(self):
        ocr = [_campo_ocr(nombre="ruc", valor="A")]
        vlm = [_campo_vlm(nombre="ruc", valor="B")]
        _, resumen = self.resolver.resolver_lote(ocr, vlm)
        d = resumen.to_dict()
        assert "total_campos" in d
        assert "registros" in d
        assert len(d["registros"]) == 1

    def test_lote_multiples_campos(self):
        """Lote grande con mix de coincidencias y conflictos."""
        ocr = [
            _campo_ocr(nombre="ruc", valor="20123456789"),
            _campo_ocr(nombre="monto", valor="100.00"),
            _campo_ocr(nombre="serie", valor="F011"),
            _campo_ocr(nombre="razon_social", valor="EMPR3SA"),
            _campo_ocr(nombre="fecha_emision", valor="01/01/2026"),
        ]
        vlm = [
            _campo_vlm(nombre="ruc", valor="20123456789"),  # coincide
            _campo_vlm(nombre="monto", valor="1000.00"),  # conflicto
            _campo_vlm(nombre="serie", valor="F011"),  # coincide
            _campo_vlm(nombre="razon_social", valor="EMPRESA SAC"),  # conflicto
            _campo_vlm(nombre="direccion_emisor", valor="Jr. Lima 123"),  # solo VLM
        ]
        campos, resumen = self.resolver.resolver_lote(ocr, vlm)
        assert resumen.total_campos == 6  # 5 comunes + 1 solo OCR + 1 solo VLM = 6
        assert resumen.conflictos == 2  # monto + razon_social
        assert len(campos) == 6


# ==============================================================================
# TRACE LOGGER
# ==============================================================================


class TestTraceLogger:
    """Verificar integración con trace_logger."""

    def test_sin_trace_logger(self):
        resolver = ConflictResolver()
        a = _campo_ocr(nombre="ruc", valor="A")
        b = _campo_vlm(nombre="ruc", valor="B")
        r = resolver.resolver(a, b)
        assert r.hubo_conflicto is True

    def test_con_trace_logger(self):
        class MockLogger:
            def __init__(self):
                self.mensajes = []

            def info(self, msg, **kwargs):
                self.mensajes.append(msg)

        logger = MockLogger()
        resolver = ConflictResolver(trace_logger=logger)
        a = _campo_ocr(nombre="ruc", valor="A")
        b = _campo_vlm(nombre="ruc", valor="B")
        resolver.resolver(a, b)
        assert len(logger.mensajes) == 1
        assert "Conflicto ruc" in logger.mensajes[0]

    def test_trace_logger_error_no_rompe(self):
        class BrokenLogger:
            def info(self, msg, **kwargs):
                raise RuntimeError("boom")

        resolver = ConflictResolver(trace_logger=BrokenLogger())
        a = _campo_ocr(nombre="ruc", valor="A")
        b = _campo_vlm(nombre="ruc", valor="B")
        r = resolver.resolver(a, b)
        assert r.hubo_conflicto is True  # no explota


# ==============================================================================
# TODOS LOS CAMPOS PREFER_OCR
# ==============================================================================


class TestTodosCamposPreferOCR:
    """Verificar que TODOS los campos PREFER_OCR realmente dan OCR como ganador."""

    def setup_method(self):
        self.resolver = ConflictResolver()

    @pytest.mark.parametrize("campo", sorted(CAMPOS_PREFER_OCR))
    def test_campo_prefiere_ocr(self, campo):
        a = _campo_ocr(nombre=campo, valor="OCR_VALUE", confianza=0.5)
        b = _campo_vlm(nombre=campo, valor="VLM_VALUE", confianza=0.9)
        r = self.resolver.resolver(a, b)
        assert r.registro.ganador == "ocr", f"{campo} debería preferir OCR"


# ==============================================================================
# TODOS LOS CAMPOS PREFER_VLM
# ==============================================================================


class TestTodosCamposPreferVLM:
    """Verificar que TODOS los campos PREFER_VLM realmente dan VLM como ganador."""

    def setup_method(self):
        self.resolver = ConflictResolver()

    @pytest.mark.parametrize("campo", sorted(CAMPOS_PREFER_VLM))
    def test_campo_prefiere_vlm(self, campo):
        a = _campo_ocr(nombre=campo, valor="OCR_VALUE", confianza=0.9)
        b = _campo_vlm(nombre=campo, valor="VLM_VALUE", confianza=0.5)
        r = self.resolver.resolver(a, b)
        assert r.registro.ganador == "vlm", f"{campo} debería preferir VLM"
