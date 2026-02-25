# -*- coding: utf-8 -*-
"""
Tests para Política Formal de Abstención Operativa (Tarea #12)
===============================================================
Verifica:
  - CampoExtraido: creación, serialización, detección de abstención
  - UmbralesAbstencion: configuración, lookup por tipo, defaults
  - AbstencionPolicy: evaluación, decisión, generación de hallazgos
  - Integración con TraceLogger
  - Estadísticas de uso
  - Criterios de aceptación Notion: valor=None, confianza=0.0, fuente=ABSTENCION
"""

import os
import shutil
import sys
import tempfile

import pytest

# Asegurar imports del proyecto
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.settings import MetodoExtraccion, NivelObservacion
from src.extraction.abstencion import (
    FRASE_ABSTENCION_ESTANDAR,
    FUENTE_ABSTENCION,
    AbstencionPolicy,
    CampoExtraido,
    RazonAbstencion,
    UmbralesAbstencion,
)
from src.ingestion.trace_logger import TraceLogger


# ==============================================================================
# FIXTURES
# ==============================================================================
@pytest.fixture
def temp_log_dir():
    """Crea directorio temporal para logs de prueba."""
    base = tempfile.mkdtemp(prefix="ag_abstencion_test_")
    yield base
    shutil.rmtree(base, ignore_errors=True)


@pytest.fixture
def logger(temp_log_dir):
    """Crea un TraceLogger en directorio temporal."""
    return TraceLogger(log_dir=temp_log_dir)


@pytest.fixture
def policy():
    """Crea una AbstencionPolicy con defaults."""
    return AbstencionPolicy()


@pytest.fixture
def policy_con_logger(logger):
    """Crea una AbstencionPolicy con TraceLogger activo."""
    logger.start_trace(sinad="TEST-ABS-001", source="test")
    policy = AbstencionPolicy(trace_logger=logger)
    yield policy
    if logger.has_active_trace:
        logger.end_trace()


@pytest.fixture
def campo_valido():
    """Crea un CampoExtraido válido con alta confianza."""
    return CampoExtraido(
        nombre_campo="ruc_proveedor",
        valor="20123456789",
        archivo="expediente.pdf",
        pagina=3,
        confianza=0.95,
        metodo=MetodoExtraccion.OCR,
        snippet="RUC del proveedor: 20123456789",
        tipo_campo="ruc",
    )


@pytest.fixture
def campo_baja_confianza():
    """Crea un CampoExtraido con confianza baja."""
    return CampoExtraido(
        nombre_campo="ruc_proveedor",
        valor="20123456789",
        archivo="expediente.pdf",
        pagina=3,
        confianza=0.50,
        metodo=MetodoExtraccion.OCR,
        snippet="RUC: 2012345????",
        tipo_campo="ruc",
    )


@pytest.fixture
def campo_sin_valor():
    """Crea un CampoExtraido con valor None."""
    return CampoExtraido(
        nombre_campo="monto_total",
        valor=None,
        archivo="expediente.pdf",
        pagina=1,
        confianza=0.0,
        metodo=MetodoExtraccion.OCR,
        tipo_campo="monto",
    )


# ==============================================================================
# TESTS: CampoExtraido
# ==============================================================================
class TestCampoExtraido:
    """Tests para creación y comportamiento de CampoExtraido."""

    def test_crear_campo_con_valor(self):
        """Campo con valor extraído se crea correctamente."""
        campo = CampoExtraido(
            nombre_campo="ruc_proveedor",
            valor="20123456789",
            archivo="doc.pdf",
            pagina=3,
            confianza=0.95,
            metodo=MetodoExtraccion.OCR,
            snippet="RUC: 20123456789",
        )
        assert campo.nombre_campo == "ruc_proveedor"
        assert campo.valor == "20123456789"
        assert campo.confianza == 0.95
        assert campo.pagina == 3

    def test_crear_campo_abstencion_explicita(self):
        """Campo con valor=None y confianza=0.0 es abstención."""
        campo = CampoExtraido(
            nombre_campo="monto",
            valor=None,
            archivo="",
            pagina=0,
            confianza=0.0,
            metodo=MetodoExtraccion.MANUAL,
        )
        assert campo.es_abstencion() is True

    def test_campo_con_valor_no_es_abstencion(self, campo_valido):
        """Campo con valor y confianza alta no es abstención."""
        assert campo_valido.es_abstencion() is False

    def test_campo_con_valor_none_pero_confianza_no_cero(self):
        """Campo con valor=None pero confianza>0 no es abstención completa."""
        campo = CampoExtraido(
            nombre_campo="test",
            valor=None,
            archivo="doc.pdf",
            pagina=1,
            confianza=0.5,
            metodo=MetodoExtraccion.OCR,
        )
        # es_abstencion requiere AMBAS condiciones: None + 0.0
        assert campo.es_abstencion() is False

    def test_campo_con_valor_vacio_no_es_abstencion(self):
        """Campo con valor='' (vacío) no es abstención (valor no es None)."""
        campo = CampoExtraido(
            nombre_campo="test",
            valor="",
            archivo="doc.pdf",
            pagina=1,
            confianza=0.0,
            metodo=MetodoExtraccion.OCR,
        )
        assert campo.es_abstencion() is False

    def test_to_dict_incluye_es_abstencion(self, campo_sin_valor):
        """to_dict incluye flag es_abstencion."""
        d = campo_sin_valor.to_dict()
        assert "es_abstencion" in d
        assert d["es_abstencion"] is True

    def test_to_dict_trunca_snippet(self):
        """to_dict trunca snippet a 200 caracteres."""
        campo = CampoExtraido(
            nombre_campo="test",
            valor="x",
            archivo="doc.pdf",
            pagina=1,
            confianza=0.95,
            metodo=MetodoExtraccion.PDF_TEXT,
            snippet="A" * 500,
        )
        d = campo.to_dict()
        assert len(d["snippet"]) == 200

    def test_to_dict_metodo_como_string(self):
        """to_dict convierte MetodoExtraccion a string."""
        campo = CampoExtraido(
            nombre_campo="test",
            valor="x",
            archivo="doc.pdf",
            pagina=1,
            confianza=0.9,
            metodo=MetodoExtraccion.OCR,
        )
        d = campo.to_dict()
        assert d["metodo"] == "OCR"
        assert isinstance(d["metodo"], str)

    def test_from_dict_roundtrip(self, campo_valido):
        """from_dict reconstruye correctamente desde to_dict."""
        d = campo_valido.to_dict()
        restaurado = CampoExtraido.from_dict(d)
        assert restaurado.nombre_campo == campo_valido.nombre_campo
        assert restaurado.valor == campo_valido.valor
        assert restaurado.confianza == campo_valido.confianza
        assert restaurado.metodo == campo_valido.metodo

    def test_from_dict_con_metodo_string(self):
        """from_dict convierte string de método a enum."""
        d = {
            "nombre_campo": "ruc",
            "valor": "20111111111",
            "archivo": "test.pdf",
            "pagina": 1,
            "confianza": 0.88,
            "metodo": "PDF_TEXT",
        }
        campo = CampoExtraido.from_dict(d)
        assert campo.metodo == MetodoExtraccion.PDF_TEXT

    def test_from_dict_ignora_campos_extra(self):
        """from_dict ignora campos que no pertenecen al dataclass."""
        d = {
            "nombre_campo": "test",
            "valor": "x",
            "archivo": "doc.pdf",
            "pagina": 1,
            "confianza": 0.9,
            "metodo": "OCR",
            "campo_extra_inventado": "ignorar",
            "es_abstencion": False,
        }
        campo = CampoExtraido.from_dict(d)
        assert campo.nombre_campo == "test"

    def test_from_dict_metodo_invalido_usa_manual(self):
        """from_dict con método inválido usa MANUAL como fallback."""
        d = {
            "nombre_campo": "test",
            "valor": "x",
            "archivo": "doc.pdf",
            "pagina": 1,
            "confianza": 0.9,
            "metodo": "METODO_INEXISTENTE",
        }
        campo = CampoExtraido.from_dict(d)
        assert campo.metodo == MetodoExtraccion.MANUAL


# ==============================================================================
# TESTS: UmbralesAbstencion
# ==============================================================================
class TestUmbralesAbstencion:
    """Tests para configuración y lookup de umbrales."""

    def test_umbrales_default_valores(self):
        """Umbrales por defecto tienen valores correctos."""
        u = UmbralesAbstencion()
        assert u.ruc == 0.90
        assert u.monto == 0.90
        assert u.fecha == 0.85
        assert u.numero_documento == 0.85
        assert u.nombre_persona == 0.80
        assert u.texto_general == 0.70
        assert u.default == 0.75

    def test_get_umbral_tipo_conocido(self):
        """get_umbral retorna valor correcto para tipo conocido."""
        u = UmbralesAbstencion()
        assert u.get_umbral("ruc") == 0.90
        assert u.get_umbral("monto") == 0.90
        assert u.get_umbral("fecha") == 0.85
        assert u.get_umbral("texto_general") == 0.70

    def test_get_umbral_tipo_desconocido_retorna_default(self):
        """get_umbral retorna default para tipo no definido."""
        u = UmbralesAbstencion()
        assert u.get_umbral("campo_rarísimo") == 0.75
        assert u.get_umbral("xyz") == 0.75

    def test_get_umbral_case_insensitive(self):
        """get_umbral normaliza mayúsculas a minúsculas."""
        u = UmbralesAbstencion()
        assert u.get_umbral("RUC") == 0.90
        assert u.get_umbral("Monto") == 0.90
        assert u.get_umbral("FECHA") == 0.85

    def test_get_umbral_strip_espacios(self):
        """get_umbral elimina espacios del tipo."""
        u = UmbralesAbstencion()
        assert u.get_umbral(" ruc ") == 0.90
        assert u.get_umbral("  monto  ") == 0.90

    def test_umbrales_custom(self):
        """Se pueden crear umbrales con valores personalizados."""
        u = UmbralesAbstencion(ruc=0.95, monto=0.99, default=0.80)
        assert u.ruc == 0.95
        assert u.monto == 0.99
        assert u.default == 0.80
        assert u.get_umbral("ruc") == 0.95

    def test_to_dict(self):
        """to_dict serializa correctamente."""
        u = UmbralesAbstencion()
        d = u.to_dict()
        assert d["ruc"] == 0.90
        assert d["default"] == 0.75
        assert isinstance(d, dict)

    def test_get_umbral_string_vacio_retorna_default(self):
        """get_umbral con string vacío retorna default."""
        u = UmbralesAbstencion()
        assert u.get_umbral("") == 0.75


# ==============================================================================
# TESTS: AbstencionPolicy — Evaluación
# ==============================================================================
class TestAbstencionEvaluacion:
    """Tests para la evaluación de campos por la política."""

    def test_campo_confianza_alta_no_abstiene(self, policy, campo_valido):
        """Campo con confianza > umbral no se abstiene."""
        resultado = policy.evaluar_campo(campo_valido)
        assert resultado.debe_abstenerse is False
        assert resultado.hallazgo is None
        assert resultado.razon_abstencion == ""

    def test_campo_confianza_baja_abstiene(self, policy, campo_baja_confianza):
        """Campo con confianza < umbral se abstiene."""
        resultado = policy.evaluar_campo(campo_baja_confianza)
        assert resultado.debe_abstenerse is True
        assert resultado.razon_codigo == RazonAbstencion.CONFIANZA_BAJA

    def test_campo_valor_none_abstiene(self, policy, campo_sin_valor):
        """Campo con valor=None se abstiene siempre."""
        resultado = policy.evaluar_campo(campo_sin_valor)
        assert resultado.debe_abstenerse is True
        assert resultado.razon_codigo == RazonAbstencion.VALOR_AUSENTE

    def test_campo_snippet_vacio_abstiene(self, policy):
        """Campo sin snippet se abstiene."""
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor="20111111111",
            archivo="doc.pdf",
            pagina=1,
            confianza=0.95,
            metodo=MetodoExtraccion.OCR,
            snippet="",
            tipo_campo="ruc",
        )
        resultado = policy.evaluar_campo(campo)
        assert resultado.debe_abstenerse is True
        assert resultado.razon_codigo == RazonAbstencion.SNIPPET_VACIO

    def test_campo_snippet_solo_espacios_abstiene(self, policy):
        """Campo con snippet de solo espacios se abstiene."""
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor="20111111111",
            archivo="doc.pdf",
            pagina=1,
            confianza=0.95,
            metodo=MetodoExtraccion.OCR,
            snippet="   \t\n  ",
            tipo_campo="ruc",
        )
        resultado = policy.evaluar_campo(campo)
        assert resultado.debe_abstenerse is True
        assert resultado.razon_codigo == RazonAbstencion.SNIPPET_VACIO

    def test_campo_pagina_cero_abstiene(self, policy):
        """Campo con página=0 se abstiene."""
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor="20111111111",
            archivo="doc.pdf",
            pagina=0,
            confianza=0.95,
            metodo=MetodoExtraccion.OCR,
            snippet="RUC: 20111111111",
            tipo_campo="ruc",
        )
        resultado = policy.evaluar_campo(campo)
        assert resultado.debe_abstenerse is True
        assert resultado.razon_codigo == RazonAbstencion.PAGINA_INVALIDA

    def test_campo_pagina_negativa_abstiene(self, policy):
        """Campo con página negativa se abstiene."""
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor="20111111111",
            archivo="doc.pdf",
            pagina=-1,
            confianza=0.95,
            metodo=MetodoExtraccion.OCR,
            snippet="RUC: 20111111111",
            tipo_campo="ruc",
        )
        resultado = policy.evaluar_campo(campo)
        assert resultado.debe_abstenerse is True
        assert resultado.razon_codigo == RazonAbstencion.PAGINA_INVALIDA

    def test_tipo_campo_override(self, policy):
        """tipo_campo explícito sobreescribe el del campo."""
        campo = CampoExtraido(
            nombre_campo="dato",
            valor="texto",
            archivo="doc.pdf",
            pagina=1,
            confianza=0.75,
            metodo=MetodoExtraccion.PDF_TEXT,
            snippet="contexto",
            tipo_campo="texto_general",  # umbral 0.70 → pasaría
        )
        # Sin override: pasa (0.75 >= 0.70)
        r1 = policy.evaluar_campo(campo)
        assert r1.debe_abstenerse is False

        # Con override a ruc: no pasa (0.75 < 0.90)
        policy.reset_stats()
        r2 = policy.evaluar_campo(campo, tipo_campo="ruc")
        assert r2.debe_abstenerse is True
        assert r2.umbral_aplicado == 0.90

    def test_umbral_boundary_exacto_no_abstiene(self, policy):
        """Confianza exactamente igual al umbral no se abstiene."""
        campo = CampoExtraido(
            nombre_campo="texto",
            valor="dato",
            archivo="doc.pdf",
            pagina=1,
            confianza=0.70,  # Exactamente el umbral de texto_general
            metodo=MetodoExtraccion.PDF_TEXT,
            snippet="contexto",
            tipo_campo="texto_general",
        )
        resultado = policy.evaluar_campo(campo)
        assert resultado.debe_abstenerse is False

    def test_umbral_boundary_justo_debajo_abstiene(self, policy):
        """Confianza un epsilon debajo del umbral se abstiene."""
        campo = CampoExtraido(
            nombre_campo="texto",
            valor="dato",
            archivo="doc.pdf",
            pagina=1,
            confianza=0.6999,  # Justo debajo de 0.70
            metodo=MetodoExtraccion.PDF_TEXT,
            snippet="contexto",
            tipo_campo="texto_general",
        )
        resultado = policy.evaluar_campo(campo)
        assert resultado.debe_abstenerse is True

    def test_prioridad_evaluacion_valor_none_primero(self, policy):
        """Valor=None tiene prioridad sobre otras razones."""
        campo = CampoExtraido(
            nombre_campo="test",
            valor=None,
            archivo="doc.pdf",
            pagina=0,  # También inválido
            confianza=0.5,  # También bajo
            metodo=MetodoExtraccion.OCR,
            snippet="",  # También vacío
        )
        resultado = policy.evaluar_campo(campo)
        # Debe reportar VALOR_AUSENTE como razón primaria
        assert resultado.razon_codigo == RazonAbstencion.VALOR_AUSENTE


# ==============================================================================
# TESTS: AbstencionPolicy — Hallazgos
# ==============================================================================
class TestAbstencionHallazgo:
    """Tests para generación automática de hallazgos."""

    def test_abstencion_genera_hallazgo(self, policy, campo_baja_confianza):
        """Abstención genera hallazgo automático."""
        resultado = policy.evaluar_campo(campo_baja_confianza)
        assert resultado.hallazgo is not None

    def test_hallazgo_nivel_informativa(self, policy, campo_baja_confianza):
        """Hallazgo de abstención es nivel INFORMATIVA."""
        resultado = policy.evaluar_campo(campo_baja_confianza)
        assert resultado.hallazgo.nivel == NivelObservacion.INFORMATIVA

    def test_hallazgo_requiere_revision_humana(self, policy, campo_sin_valor):
        """Hallazgo de abstención marca revisión humana."""
        resultado = policy.evaluar_campo(campo_sin_valor)
        assert resultado.hallazgo.requiere_revision_humana is True

    def test_hallazgo_regla_abstencion(self, policy, campo_sin_valor):
        """Hallazgo tiene regla_aplicada = ABSTENCION."""
        resultado = policy.evaluar_campo(campo_sin_valor)
        assert resultado.hallazgo.regla_aplicada == FUENTE_ABSTENCION

    def test_hallazgo_contiene_frase_estandar(self, policy, campo_sin_valor):
        """Hallazgo contiene la frase estándar del Art. 12.1."""
        resultado = policy.evaluar_campo(campo_sin_valor)
        assert FRASE_ABSTENCION_ESTANDAR in resultado.hallazgo.descripcion

    def test_hallazgo_contiene_nombre_campo(self, policy, campo_baja_confianza):
        """Hallazgo menciona el nombre del campo."""
        resultado = policy.evaluar_campo(campo_baja_confianza)
        assert "ruc_proveedor" in resultado.hallazgo.descripcion

    def test_hallazgo_accion_requerida_menciona_campo(self, policy, campo_sin_valor):
        """Acción requerida menciona el campo a verificar."""
        resultado = policy.evaluar_campo(campo_sin_valor)
        assert "monto_total" in resultado.hallazgo.accion_requerida

    def test_no_abstencion_no_genera_hallazgo(self, policy, campo_valido):
        """Campo válido no genera hallazgo."""
        resultado = policy.evaluar_campo(campo_valido)
        assert resultado.hallazgo is None


# ==============================================================================
# TESTS: AbstencionPolicy — Generación
# ==============================================================================
class TestAbstencionGeneracion:
    """Tests para generar_campo_abstencion."""

    def test_campo_generado_valor_none(self, policy):
        """Campo generado tiene valor=None."""
        campo = policy.generar_campo_abstencion(nombre_campo="ruc", razon="test")
        assert campo.valor is None

    def test_campo_generado_confianza_cero(self, policy):
        """Campo generado tiene confianza=0.0."""
        campo = policy.generar_campo_abstencion(nombre_campo="ruc", razon="test")
        assert campo.confianza == 0.0

    def test_campo_generado_fuente_abstencion(self, policy):
        """Campo generado tiene regla_aplicada=ABSTENCION."""
        campo = policy.generar_campo_abstencion(nombre_campo="ruc", razon="test")
        assert campo.regla_aplicada == FUENTE_ABSTENCION

    def test_campo_generado_es_abstencion(self, policy):
        """Campo generado detecta es_abstencion()=True."""
        campo = policy.generar_campo_abstencion(nombre_campo="ruc", razon="test")
        assert campo.es_abstencion() is True

    def test_campo_generado_pagina_cero(self, policy):
        """Campo generado tiene pagina=0."""
        campo = policy.generar_campo_abstencion(nombre_campo="ruc", razon="test")
        assert campo.pagina == 0

    def test_campo_generado_preserva_tipo(self, policy):
        """Campo generado preserva el tipo de campo."""
        campo = policy.generar_campo_abstencion(
            nombre_campo="monto_total",
            razon="confianza baja",
            tipo_campo="monto",
        )
        assert campo.tipo_campo == "monto"
        assert campo.nombre_campo == "monto_total"


# ==============================================================================
# TESTS: ResultadoAbstencion
# ==============================================================================
class TestResultadoAbstencion:
    """Tests para ResultadoAbstencion y formato Excel."""

    def test_to_dict_cuando_abstiene(self, policy, campo_sin_valor):
        """to_dict incluye información completa cuando abstiene."""
        resultado = policy.evaluar_campo(campo_sin_valor)
        d = resultado.to_dict()
        assert d["debe_abstenerse"] is True
        assert d["razon_codigo"] == "valor_ausente"
        assert "hallazgo" in d
        assert d["hallazgo"]["nivel"] == "INFORMATIVA"

    def test_to_dict_cuando_no_abstiene(self, policy, campo_valido):
        """to_dict cuando no abstiene no tiene hallazgo."""
        resultado = policy.evaluar_campo(campo_valido)
        d = resultado.to_dict()
        assert d["debe_abstenerse"] is False
        assert "hallazgo" not in d

    def test_excel_format_rojo_cuando_abstiene(self, policy, campo_sin_valor):
        """get_excel_format_spec retorna rojo cuando abstiene."""
        resultado = policy.evaluar_campo(campo_sin_valor)
        spec = resultado.get_excel_format_spec()
        assert spec["bg_color"] == "FF0000"
        assert "comment" in spec
        assert len(spec["comment"]) > 0

    def test_excel_format_vacio_cuando_no_abstiene(self, policy, campo_valido):
        """get_excel_format_spec retorna {} cuando no abstiene."""
        resultado = policy.evaluar_campo(campo_valido)
        spec = resultado.get_excel_format_spec()
        assert spec == {}


# ==============================================================================
# TESTS: Integración con TraceLogger
# ==============================================================================
class TestIntegracionTraceLogger:
    """Tests para la integración con TraceLogger."""

    def test_evaluacion_se_registra_en_logger(
        self, policy_con_logger, logger, campo_baja_confianza
    ):
        """Evaluación con abstención se registra en TraceLogger."""
        policy_con_logger.evaluar_campo(campo_baja_confianza)

        entries = logger.get_recent_entries(limit=10)
        # Debe haber al menos 2 entradas: start_trace + evaluación
        assert len(entries) >= 2
        eval_entries = [e for e in entries if "ruc_proveedor" in e.message]
        assert len(eval_entries) > 0

    def test_evaluacion_sin_abstencion_se_registra(self, policy_con_logger, logger, campo_valido):
        """Evaluación sin abstención también se registra."""
        policy_con_logger.evaluar_campo(campo_valido)

        entries = logger.get_recent_entries(limit=10)
        eval_entries = [e for e in entries if "ruc_proveedor" in e.message]
        assert len(eval_entries) > 0

    def test_abstencion_registra_nivel_warning(self, policy_con_logger, logger, campo_sin_valor):
        """Abstención se registra como WARNING en el logger."""
        policy_con_logger.evaluar_campo(campo_sin_valor)

        entries = logger.get_recent_entries(limit=10)
        warning_entries = [e for e in entries if e.level == "WARNING"]
        assert len(warning_entries) > 0

    def test_no_abstencion_registra_nivel_info(self, policy_con_logger, logger, campo_valido):
        """No-abstención se registra como INFO en el logger."""
        policy_con_logger.evaluar_campo(campo_valido)

        entries = logger.get_recent_entries(limit=10)
        # Filtrar solo las de evaluación (no start_trace)
        info_eval = [e for e in entries if e.level == "INFO" and "evaluado" in e.message]
        assert len(info_eval) > 0

    def test_policy_sin_logger_no_falla(self, campo_valido):
        """Policy sin logger funciona sin error."""
        policy = AbstencionPolicy(trace_logger=None)
        resultado = policy.evaluar_campo(campo_valido)
        assert resultado is not None

    def test_logger_registra_contexto_completo(
        self, policy_con_logger, logger, campo_baja_confianza
    ):
        """Logger registra contexto con datos de la evaluación."""
        policy_con_logger.evaluar_campo(campo_baja_confianza)

        entries = logger.get_recent_entries(limit=10)
        eval_entries = [e for e in entries if e.operation == "evaluar_abstencion"]
        assert len(eval_entries) > 0
        ctx = eval_entries[0].context
        assert "campo" in ctx
        assert "confianza" in ctx
        assert "umbral" in ctx
        assert ctx["debe_abstenerse"] is True

    def test_multiples_evaluaciones_en_mismo_trace(
        self, policy_con_logger, logger, campo_valido, campo_sin_valor
    ):
        """Múltiples evaluaciones se registran en el mismo trace."""
        policy_con_logger.evaluar_campo(campo_valido)
        policy_con_logger.evaluar_campo(campo_sin_valor)

        entries = logger.get_recent_entries(limit=20)
        eval_entries = [e for e in entries if e.operation == "evaluar_abstencion"]
        assert len(eval_entries) == 2


# ==============================================================================
# TESTS: Estadísticas
# ==============================================================================
class TestEstadisticas:
    """Tests para estadísticas de uso de la política."""

    def test_stats_iniciales_en_cero(self, policy):
        """Estadísticas iniciales están en cero."""
        stats = policy.get_stats()
        assert stats["total_evaluados"] == 0
        assert stats["total_abstenciones"] == 0
        assert stats["tasa_abstencion"] == 0.0

    def test_stats_incrementan_con_evaluacion(self, policy, campo_valido):
        """Estadísticas incrementan al evaluar."""
        policy.evaluar_campo(campo_valido)
        stats = policy.get_stats()
        assert stats["total_evaluados"] == 1
        assert stats["total_abstenciones"] == 0

    def test_stats_cuentan_abstenciones(self, policy, campo_sin_valor):
        """Estadísticas cuentan abstenciones correctamente."""
        policy.evaluar_campo(campo_sin_valor)
        stats = policy.get_stats()
        assert stats["total_abstenciones"] == 1

    def test_tasa_abstencion_correcta(self, policy, campo_valido, campo_sin_valor):
        """Tasa de abstención se calcula correctamente."""
        policy.evaluar_campo(campo_valido)
        policy.evaluar_campo(campo_sin_valor)
        stats = policy.get_stats()
        assert stats["total_evaluados"] == 2
        assert stats["total_abstenciones"] == 1
        assert stats["tasa_abstencion"] == 0.5

    def test_stats_por_razon(self, policy, campo_sin_valor, campo_baja_confianza):
        """Estadísticas desglosan por razón de abstención."""
        policy.evaluar_campo(campo_sin_valor)
        policy.evaluar_campo(campo_baja_confianza)
        stats = policy.get_stats()
        assert "valor_ausente" in stats["por_razon"]
        assert "confianza_baja" in stats["por_razon"]
        assert stats["por_razon"]["valor_ausente"] == 1
        assert stats["por_razon"]["confianza_baja"] == 1

    def test_reset_stats(self, policy, campo_sin_valor):
        """reset_stats reinicia las estadísticas."""
        policy.evaluar_campo(campo_sin_valor)
        assert policy.get_stats()["total_evaluados"] == 1

        policy.reset_stats()
        stats = policy.get_stats()
        assert stats["total_evaluados"] == 0
        assert stats["total_abstenciones"] == 0
        assert stats["por_razon"] == {}

    def test_repr_muestra_estadisticas(self, policy, campo_sin_valor):
        """__repr__ muestra estadísticas legibles."""
        policy.evaluar_campo(campo_sin_valor)
        r = repr(policy)
        assert "AbstencionPolicy" in r
        assert "evaluados=1" in r
        assert "abstenciones=1" in r


# ==============================================================================
# TESTS: Evaluar Lote
# ==============================================================================
class TestEvaluarLote:
    """Tests para evaluación en lote."""

    def test_lote_vacio(self, policy):
        """Lote vacío retorna lista vacía."""
        resultados = policy.evaluar_lote([])
        assert resultados == []

    def test_lote_mixto(self, policy, campo_valido, campo_sin_valor):
        """Lote con campos mixtos evalúa cada uno."""
        resultados = policy.evaluar_lote([campo_valido, campo_sin_valor])
        assert len(resultados) == 2
        assert resultados[0].debe_abstenerse is False
        assert resultados[1].debe_abstenerse is True

    def test_lote_actualiza_stats(
        self, policy, campo_valido, campo_sin_valor, campo_baja_confianza
    ):
        """Evaluación en lote actualiza estadísticas."""
        policy.evaluar_lote([campo_valido, campo_sin_valor, campo_baja_confianza])
        stats = policy.get_stats()
        assert stats["total_evaluados"] == 3
        assert stats["total_abstenciones"] == 2
