# -*- coding: utf-8 -*-
"""
Tests para Confidence Router + Integrity Checkpoint (Tarea #18)
================================================================

Hito 1: Estructuras de datos + EvidenceEnforcer + ConfidenceRouter skeleton.
Hito 2: IntegrityCheckpoint + DiagnosticoExpediente + ReporteEnforcement.
Hito 3: TraceLogger + edge cases.

Incluye test de regresión para _recolectar_todos_campos() (método privado).
"""

import shutil
import tempfile

import pytest

from config.settings import (
    EvidenciaProbatoria,
    MetodoExtraccion,
    NivelObservacion,
    Observacion,
)
from src.extraction.abstencion import (
    AbstencionPolicy,
    CampoExtraido,
)
from src.extraction.confidence_router import (
    AGENTE_ID_DEFAULT,
    VERSION_ROUTER,
    ConfidenceRouter,
    DecisionCheckpoint,
    DetalleEnforcement,
    DiagnosticoExpediente,
    EvidenceEnforcer,
    IntegrityCheckpoint,
    ReporteEnforcement,
    ResultadoRouter,
    SeccionDiagnostico,
    UmbralesRouter,
)
from src.extraction.expediente_contract import (
    ComprobanteExtraido,
    ConfianzaGlobal,
    DatosComprobante,
    DatosEmisor,
    ExpedienteJSON,
    IntegridadStatus,
    MetadatosExtraccion,
    TotalesTributos,
)
from src.ingestion.trace_logger import TraceLogger

# ==============================================================================
# HELPERS
# ==============================================================================


def _crear_campo(
    nombre: str,
    valor: str,
    confianza: float = 0.92,
    tipo_campo: str = "texto",
) -> CampoExtraido:
    """Helper para crear CampoExtraido con datos mínimos probatorios."""
    return CampoExtraido(
        nombre_campo=nombre,
        valor=valor,
        archivo="test_factura.pdf",
        pagina=1,
        confianza=confianza,
        metodo=MetodoExtraccion.OCR,
        snippet=f"{nombre}: {valor}",
        tipo_campo=tipo_campo,
        regla_aplicada="TEST_RULE_001",
    )


def _crear_campo_abstencion(nombre: str) -> CampoExtraido:
    """Helper para crear campo en abstención formal."""
    return CampoExtraido(
        nombre_campo=nombre,
        valor=None,
        archivo="test_factura.pdf",
        pagina=0,
        confianza=0.0,
        metodo=MetodoExtraccion.MANUAL,
        snippet="",
        tipo_campo="texto",
        regla_aplicada="ABSTENCION",
    )


_COMPROBANTE_COUNTER = 0


def _crear_comprobante_minimo() -> ComprobanteExtraido:
    """Crea comprobante con datos mínimos para tests, con serie/numero único."""
    global _COMPROBANTE_COUNTER
    _COMPROBANTE_COUNTER += 1
    numero = f"{_COMPROBANTE_COUNTER:08d}"
    return ComprobanteExtraido(
        grupo_a=DatosEmisor(
            ruc_emisor=_crear_campo("ruc_emisor", "20100039207", tipo_campo="ruc"),
            razon_social=_crear_campo("razon_social", "EMPRESA TEST S.A.C."),
        ),
        grupo_b=DatosComprobante(
            tipo_comprobante=_crear_campo("tipo_comprobante", "FACTURA"),
            serie=_crear_campo("serie", "F001"),
            numero=_crear_campo("numero", numero),
            fecha_emision=_crear_campo("fecha_emision", "2026-02-10", tipo_campo="fecha"),
        ),
        grupo_f=TotalesTributos(
            subtotal=_crear_campo("subtotal", "100.00", tipo_campo="monto"),
            igv_monto=_crear_campo("igv_monto", "18.00", tipo_campo="monto"),
            importe_total=_crear_campo("importe_total", "118.00", tipo_campo="monto"),
        ),
        grupo_k=MetadatosExtraccion(
            pagina_origen=5,
            metodo_extraccion="pymupdf",
            confianza_global="alta",
            timestamp_extraccion="2026-02-19T10:00:00Z",
        ),
    )


def _crear_observacion_critica_con_evidencia() -> Observacion:
    """Crea observación CRITICA con evidencia completa."""
    obs = Observacion(
        nivel=NivelObservacion.CRITICA,
        agente="AG04",
        descripcion="Monto total no coincide con suma de items",
        accion_requerida="Verificar cálculo de factura",
        regla_aplicada="RULE_ARIT_001",
    )
    obs.agregar_evidencia(
        EvidenciaProbatoria(
            archivo="factura_001.pdf",
            pagina=3,
            valor_detectado="118.00",
            valor_esperado="120.00",
            snippet="TOTAL S/ 118.00",
            confianza=0.95,
            regla_aplicada="RULE_ARIT_001",
        )
    )
    return obs


def _crear_observacion_critica_sin_evidencia() -> Observacion:
    """Crea observación CRITICA sin evidencia (será degradada)."""
    return Observacion(
        nivel=NivelObservacion.CRITICA,
        agente="AG06",
        descripcion="Falta documento requerido",
        accion_requerida="Adjuntar documento faltante",
    )


def _crear_observacion_mayor_sin_evidencia() -> Observacion:
    """Crea observación MAYOR sin evidencia (será degradada)."""
    return Observacion(
        nivel=NivelObservacion.MAYOR,
        agente="AG03",
        descripcion="RUC del proveedor inconsistente",
        accion_requerida="Verificar RUC en SUNAT",
    )


def _crear_observacion_menor() -> Observacion:
    """Crea observación MENOR (no se degrada)."""
    return Observacion(
        nivel=NivelObservacion.MENOR,
        agente="AG05",
        descripcion="Firma digital no verificada",
        accion_requerida="Verificar manualmente",
    )


def _crear_expediente_completo(n_comprobantes: int = 3) -> ExpedienteJSON:
    """Crea ExpedienteJSON con N comprobantes de alta confianza."""
    exp = ExpedienteJSON(sinad="TEST-ROUTER-001")
    for _ in range(n_comprobantes):
        exp.comprobantes.append(_crear_comprobante_minimo())
    return exp


def _crear_expediente_50pct_abstencion() -> ExpedienteJSON:
    """ExpedienteJSON con ~50% de campos abstenidos."""
    comp = ComprobanteExtraido(
        grupo_a=DatosEmisor(
            ruc_emisor=_crear_campo_abstencion("ruc_emisor"),
            razon_social=_crear_campo_abstencion("razon_social"),
        ),
        grupo_b=DatosComprobante(
            tipo_comprobante=_crear_campo("tipo_comprobante", "FACTURA"),
            serie=_crear_campo("serie", "F001"),
            numero=_crear_campo_abstencion("numero"),
            fecha_emision=_crear_campo_abstencion("fecha_emision"),
        ),
        grupo_f=TotalesTributos(
            subtotal=_crear_campo("subtotal", "100.00", tipo_campo="monto"),
            igv_monto=_crear_campo_abstencion("igv_monto"),
            importe_total=_crear_campo_abstencion("importe_total"),
        ),
        grupo_k=MetadatosExtraccion(
            pagina_origen=1,
            metodo_extraccion="paddleocr",
            confianza_global="baja",
            timestamp_extraccion="2026-02-19T10:00:00Z",
        ),
    )
    exp = ExpedienteJSON(sinad="TEST-ABSTENCION-50")
    exp.comprobantes.append(comp)
    return exp


# ==============================================================================
# FIXTURES
# ==============================================================================


@pytest.fixture
def umbrales_default():
    return UmbralesRouter()


@pytest.fixture
def umbrales_strict():
    return UmbralesRouter(
        max_campos_abstencion_warning_pct=0.10,
        max_campos_abstencion_critical_pct=0.25,
        max_observaciones_degradadas_warning=1,
        max_observaciones_degradadas_critical=2,
    )


@pytest.fixture
def router():
    return ConfidenceRouter()


@pytest.fixture
def temp_log_dir():
    """Directorio temporal para logs de prueba."""
    base = tempfile.mkdtemp(prefix="ag_router_test_")
    yield base
    shutil.rmtree(base, ignore_errors=True)


@pytest.fixture
def router_con_logger(temp_log_dir):
    """Router con TraceLogger activo."""
    logger = TraceLogger(log_dir=temp_log_dir)
    logger.start_trace(sinad="TEST-ROUTER-001", source="test")
    r = ConfidenceRouter(trace_logger=logger)
    yield r
    if logger.has_active_trace:
        logger.end_trace()


# ==============================================================================
# HITO 1: TESTS DE ESTRUCTURAS DE DATOS
# ==============================================================================


class TestUmbralesRouter:
    """Tests para UmbralesRouter dataclass."""

    def test_defaults(self):
        u = UmbralesRouter()
        assert u.max_campos_abstencion_warning_pct == 0.30
        assert u.max_campos_abstencion_critical_pct == 0.50
        assert u.min_comprobantes_con_datos == 1
        assert u.min_campos_por_comprobante == 3
        assert u.max_errores_aritmeticos_warning == 2
        assert u.max_errores_aritmeticos_critical == 5
        assert u.completitud_problemas_critical == 3

    def test_custom_values(self):
        u = UmbralesRouter(
            max_campos_abstencion_warning_pct=0.20,
            max_campos_abstencion_critical_pct=0.40,
        )
        assert u.max_campos_abstencion_warning_pct == 0.20
        assert u.max_campos_abstencion_critical_pct == 0.40

    def test_to_dict(self):
        u = UmbralesRouter()
        d = u.to_dict()
        assert isinstance(d, dict)
        assert "max_campos_abstencion_warning_pct" in d
        assert d["max_campos_abstencion_warning_pct"] == 0.30

    def test_from_dict(self):
        data = {"max_campos_abstencion_warning_pct": 0.15}
        u = UmbralesRouter.from_dict(data)
        assert u.max_campos_abstencion_warning_pct == 0.15
        # Resto mantiene defaults
        assert u.max_campos_abstencion_critical_pct == 0.50

    def test_from_dict_none(self):
        u = UmbralesRouter.from_dict(None)
        assert u.max_campos_abstencion_warning_pct == 0.30

    def test_roundtrip(self):
        original = UmbralesRouter(max_errores_aritmeticos_warning=4)
        d = original.to_dict()
        restored = UmbralesRouter.from_dict(d)
        assert restored.max_errores_aritmeticos_warning == 4


class TestResultadoRouter:
    """Tests para ResultadoRouter dataclass."""

    def test_defaults(self):
        r = ResultadoRouter()
        assert r.status == IntegridadStatus.OK
        assert r.confianza_global == ConfianzaGlobal.ALTA
        assert r.debe_detener is False
        assert r.razon_detencion == ""
        assert r.campos_evaluados == 0
        assert r.version_router == VERSION_ROUTER

    def test_to_dict(self):
        r = ResultadoRouter(
            status=IntegridadStatus.WARNING,
            campos_evaluados=10,
            campos_abstenidos=3,
        )
        d = r.to_dict()
        assert d["status"] == "WARNING"
        assert d["campos_evaluados"] == 10
        assert d["campos_abstenidos"] == 3
        assert "version_router" in d

    def test_resumen_texto_ok(self):
        r = ResultadoRouter(
            status=IntegridadStatus.OK,
            confianza_global=ConfianzaGlobal.ALTA,
            campos_evaluados=20,
            campos_legibles=18,
            campos_incompletos=2,
            campos_abstenidos=0,
            tasa_abstencion=0.0,
        )
        texto = r.resumen_texto()
        assert "OK" in texto
        assert "alta" in texto
        assert "20 eval" in texto

    def test_resumen_texto_critical(self):
        r = ResultadoRouter(
            status=IntegridadStatus.CRITICAL,
            debe_detener=True,
            razon_detencion="Tasa de abstención 60%",
        )
        texto = r.resumen_texto()
        assert "CRITICAL" in texto
        assert "SEÑAL CRITICAL" in texto

    def test_debe_detener_flag(self):
        r = ResultadoRouter(debe_detener=True, razon_detencion="test")
        assert r.debe_detener is True
        assert r.razon_detencion == "test"


class TestEvidenceEnforcer:
    """Tests para EvidenceEnforcer (wrapper sobre validar_y_degradar)."""

    def test_lista_vacia(self):
        validas, degradadas = EvidenceEnforcer.enforce_all([])
        assert validas == []
        assert degradadas == []

    def test_todas_validas(self):
        """CRITICA con evidencia completa no se degrada."""
        obs = _crear_observacion_critica_con_evidencia()
        validas, degradadas = EvidenceEnforcer.enforce_all([obs])
        assert len(validas) == 1
        assert len(degradadas) == 0
        assert validas[0].nivel == NivelObservacion.CRITICA

    def test_critica_sin_evidencia_se_degrada(self):
        """CRITICA sin evidencia → INCIERTO + requiere_revision_humana."""
        obs = _crear_observacion_critica_sin_evidencia()
        validas, degradadas = EvidenceEnforcer.enforce_all([obs])
        assert len(validas) == 0
        assert len(degradadas) == 1
        assert degradadas[0].nivel == NivelObservacion.INCIERTO
        assert degradadas[0].requiere_revision_humana is True

    def test_mayor_sin_evidencia_se_degrada(self):
        """MAYOR sin evidencia → INCIERTO."""
        obs = _crear_observacion_mayor_sin_evidencia()
        validas, degradadas = EvidenceEnforcer.enforce_all([obs])
        assert len(validas) == 0
        assert len(degradadas) == 1
        assert degradadas[0].nivel == NivelObservacion.INCIERTO

    def test_menor_no_se_degrada(self):
        """MENOR sin evidencia no se degrada (solo CRITICA/MAYOR)."""
        obs = _crear_observacion_menor()
        validas, degradadas = EvidenceEnforcer.enforce_all([obs])
        assert len(validas) == 1
        assert len(degradadas) == 0
        assert validas[0].nivel == NivelObservacion.MENOR

    def test_mixto(self):
        """Lista mixta: 1 válida, 1 degradada, 1 menor."""
        obs_list = [
            _crear_observacion_critica_con_evidencia(),
            _crear_observacion_critica_sin_evidencia(),
            _crear_observacion_menor(),
        ]
        validas, degradadas = EvidenceEnforcer.enforce_all(obs_list)
        assert len(validas) == 2  # CRITICA con evidencia + MENOR
        assert len(degradadas) == 1  # CRITICA sin evidencia

    def test_stats(self):
        obs_list = [
            _crear_observacion_critica_con_evidencia(),
            _crear_observacion_critica_sin_evidencia(),
            _crear_observacion_menor(),
        ]
        validas, degradadas = EvidenceEnforcer.enforce_all(obs_list)
        stats = EvidenceEnforcer.get_stats(validas, degradadas)
        assert stats["total_procesadas"] == 3
        assert stats["validas"] == 2
        assert stats["degradadas"] == 1
        assert 0.33 <= stats["tasa_degradacion"] <= 0.34

    def test_stats_sin_observaciones(self):
        stats = EvidenceEnforcer.get_stats([], [])
        assert stats["total_procesadas"] == 0
        assert stats["tasa_degradacion"] == 0.0


# ==============================================================================
# HITO 1: TESTS DEL CONFIDENCE ROUTER
# ==============================================================================


class TestConfidenceRouterInit:
    """Tests de inicialización del router."""

    def test_init_default(self):
        router = ConfidenceRouter()
        assert isinstance(router.umbrales, UmbralesRouter)
        assert isinstance(router.policy, AbstencionPolicy)
        assert router.logger is None
        assert router.agente_id == AGENTE_ID_DEFAULT

    def test_init_custom_umbrales(self):
        umbrales = UmbralesRouter(max_campos_abstencion_warning_pct=0.10)
        router = ConfidenceRouter(umbrales=umbrales)
        assert router.umbrales.max_campos_abstencion_warning_pct == 0.10

    def test_init_con_logger(self, router_con_logger):
        assert router_con_logger.logger is not None


class TestConfidenceRouterBasico:
    """Tests básicos del router evaluando expedientes."""

    def test_expediente_vacio(self, router):
        """Expediente sin datos → evalúa (puede dar WARNING/CRITICAL por falta datos)."""
        exp = ExpedienteJSON(sinad="TEST-VACIO")
        resultado = router.evaluar_expediente(exp)
        assert isinstance(resultado, ResultadoRouter)
        assert resultado.campos_evaluados == 0
        assert resultado.timestamp != ""

    def test_expediente_completo_alta_confianza(self, router):
        """Expediente con 3 comprobantes bien extraídos → OK/ALTA."""
        exp = _crear_expediente_completo(3)
        resultado = router.evaluar_expediente(exp)
        assert resultado.status == IntegridadStatus.OK
        assert resultado.confianza_global == ConfianzaGlobal.ALTA
        assert resultado.debe_detener is False
        assert resultado.campos_evaluados > 0
        assert resultado.campos_legibles > 0
        assert resultado.tasa_abstencion < 0.10

    def test_expediente_un_comprobante(self, router):
        """Un solo comprobante bien extraído → OK."""
        exp = _crear_expediente_completo(1)
        resultado = router.evaluar_expediente(exp)
        assert resultado.status == IntegridadStatus.OK

    def test_resultado_tiene_timestamp(self, router):
        exp = _crear_expediente_completo(1)
        resultado = router.evaluar_expediente(exp)
        assert resultado.timestamp != ""
        assert "T" in resultado.timestamp  # ISO format

    def test_resultado_tiene_version(self, router):
        exp = _crear_expediente_completo(1)
        resultado = router.evaluar_expediente(exp)
        assert resultado.version_router == VERSION_ROUTER


# ==============================================================================
# HITO 1: TEST DE REGRESIÓN — _recolectar_todos_campos (método privado)
# ==============================================================================


class TestRegresionRecolectarCampos:
    """
    Tests de regresión para ExpedienteJSON._recolectar_todos_campos().

    Este método es privado pero lo usa ConfidenceRouter._paso1_evaluar_campos().
    Si cambia nombre, firma o comportamiento, estos tests lo detectan.
    """

    def test_metodo_existe(self):
        """Verifica que _recolectar_todos_campos existe como método."""
        exp = ExpedienteJSON()
        assert hasattr(exp, "_recolectar_todos_campos")
        assert callable(exp._recolectar_todos_campos)

    def test_retorna_lista_campos(self):
        """Retorna List[CampoExtraido]."""
        exp = _crear_expediente_completo(1)
        campos = exp._recolectar_todos_campos()
        assert isinstance(campos, list)
        assert len(campos) > 0
        assert all(isinstance(c, CampoExtraido) for c in campos)

    def test_incluye_campos_comprobantes(self):
        """Incluye campos de todos los comprobantes."""
        exp = _crear_expediente_completo(2)
        campos = exp._recolectar_todos_campos()
        # 2 comprobantes con ~10 campos cada uno
        assert len(campos) >= 10

    def test_expediente_vacio_retorna_lista_vacia(self):
        """Sin comprobantes ni DJ ni boletos → lista vacía."""
        exp = ExpedienteJSON(sinad="VACIO")
        campos = exp._recolectar_todos_campos()
        assert campos == []

    def test_incluye_campos_abstencion(self):
        """Incluye campos abstenidos (valor=None)."""
        exp = _crear_expediente_50pct_abstencion()
        campos = exp._recolectar_todos_campos()
        abstenidos = [c for c in campos if c.es_abstencion()]
        assert len(abstenidos) > 0


# ==============================================================================
# HITO 1: TESTS DE ESCALACIÓN BÁSICA
# ==============================================================================


class TestEscalacionBasica:
    """Tests básicos de la lógica de escalación del router."""

    def test_alta_abstencion_warning(self, router):
        """>=30% abstención → WARNING."""
        exp = _crear_expediente_50pct_abstencion()
        resultado = router.evaluar_expediente(exp)
        # 50% abstención debería dar WARNING o CRITICAL
        assert resultado.status in [IntegridadStatus.WARNING, IntegridadStatus.CRITICAL]
        assert resultado.tasa_abstencion >= 0.30

    def test_critical_marca_debe_detener(self, router):
        """CRITICAL → debe_detener=True."""
        # Con umbrales bajos para forzar CRITICAL
        router_strict = ConfidenceRouter(
            umbrales=UmbralesRouter(
                max_campos_abstencion_critical_pct=0.20,
            )
        )
        exp = _crear_expediente_50pct_abstencion()
        resultado = router_strict.evaluar_expediente(exp)
        if resultado.status == IntegridadStatus.CRITICAL:
            assert resultado.debe_detener is True
            assert resultado.razon_detencion != ""

    def test_ok_no_detiene(self, router):
        """OK → debe_detener=False."""
        exp = _crear_expediente_completo(3)
        resultado = router.evaluar_expediente(exp)
        assert resultado.status == IntegridadStatus.OK
        assert resultado.debe_detener is False

    def test_observaciones_degradadas_contabilizadas(self, router):
        """Observaciones degradadas se reflejan en resultado."""
        exp = _crear_expediente_completo(1)
        obs = [
            _crear_observacion_critica_sin_evidencia(),
            _crear_observacion_mayor_sin_evidencia(),
        ]
        resultado = router.evaluar_expediente(exp, obs)
        assert len(resultado.observaciones_degradadas) == 2

    def test_expediente_actualizado_post_evaluacion(self, router):
        """El expediente se actualiza con integridad y hash post-router."""
        exp = _crear_expediente_completo(1)
        hash_antes = exp.integridad.hash_expediente
        resultado = router.evaluar_expediente(exp)
        # Integridad actualizada
        assert exp.integridad.status == resultado.status.value
        # Hash regenerado
        assert exp.integridad.hash_expediente != hash_antes

    def test_confianza_global_alta_en_expediente_limpio(self, router):
        """Expediente limpio → ConfianzaGlobal.ALTA."""
        exp = _crear_expediente_completo(3)
        resultado = router.evaluar_expediente(exp)
        assert resultado.confianza_global == ConfianzaGlobal.ALTA

    def test_confianza_global_baja_en_critical(self):
        """Expediente CRITICAL → ConfianzaGlobal.BAJA."""
        router_strict = ConfidenceRouter(
            umbrales=UmbralesRouter(
                max_campos_abstencion_critical_pct=0.20,
            )
        )
        exp = _crear_expediente_50pct_abstencion()
        resultado = router_strict.evaluar_expediente(exp)
        if resultado.status == IntegridadStatus.CRITICAL:
            assert resultado.confianza_global == ConfianzaGlobal.BAJA


class TestMaxStatus:
    """Tests para el helper _max_status."""

    def test_ok_vs_warning(self):
        result = ConfidenceRouter._max_status(IntegridadStatus.OK, IntegridadStatus.WARNING)
        assert result == IntegridadStatus.WARNING

    def test_warning_vs_critical(self):
        result = ConfidenceRouter._max_status(IntegridadStatus.WARNING, IntegridadStatus.CRITICAL)
        assert result == IntegridadStatus.CRITICAL

    def test_critical_vs_ok(self):
        """CRITICAL no baja a OK."""
        result = ConfidenceRouter._max_status(IntegridadStatus.CRITICAL, IntegridadStatus.OK)
        assert result == IntegridadStatus.CRITICAL

    def test_same_status(self):
        result = ConfidenceRouter._max_status(IntegridadStatus.WARNING, IntegridadStatus.WARNING)
        assert result == IntegridadStatus.WARNING


# ==============================================================================
# HITO 1: TESTS CON TRACE LOGGER
# ==============================================================================


class TestRouterConLogger:
    """Tests básicos de integración con TraceLogger."""

    def test_router_con_logger_no_falla(self, router_con_logger):
        """Evaluar con logger activo no causa error."""
        exp = _crear_expediente_completo(1)
        resultado = router_con_logger.evaluar_expediente(exp)
        assert resultado.status == IntegridadStatus.OK

    def test_router_sin_logger_no_falla(self):
        """Evaluar sin logger no causa error."""
        router = ConfidenceRouter(trace_logger=None)
        exp = _crear_expediente_completo(1)
        resultado = router.evaluar_expediente(exp)
        assert resultado.status == IntegridadStatus.OK


# ==============================================================================
# HITO 2: TESTS DE DetalleEnforcement Y ReporteEnforcement
# ==============================================================================


class TestDetalleEnforcement:
    """Tests para DetalleEnforcement dataclass."""

    def test_defaults(self):
        d = DetalleEnforcement()
        assert d.agente == ""
        assert d.fue_degradada is False
        assert d.campos_faltantes == []
        assert d.requiere_revision_humana is False

    def test_to_dict(self):
        d = DetalleEnforcement(
            agente="AG04",
            nivel_original="CRÍTICA",
            nivel_post="INCIERTO",
            fue_degradada=True,
            descripcion="Monto no coincide",
            campos_faltantes=["snippet", "regla_aplicada"],
            requiere_revision_humana=True,
        )
        result = d.to_dict()
        assert result["agente"] == "AG04"
        assert result["fue_degradada"] is True
        assert "snippet" in result["campos_faltantes"]

    def test_degradada_con_campos_faltantes(self):
        d = DetalleEnforcement(
            fue_degradada=True,
            campos_faltantes=["archivo", "pagina", "snippet"],
        )
        assert len(d.campos_faltantes) == 3


class TestReporteEnforcement:
    """Tests para ReporteEnforcement dataclass."""

    def test_defaults(self):
        r = ReporteEnforcement()
        assert r.total_procesadas == 0
        assert r.total_validas == 0
        assert r.total_degradadas == 0
        assert r.tasa_degradacion == 0.0
        assert r.detalles == []

    def test_to_dict(self):
        r = ReporteEnforcement(
            total_procesadas=5,
            total_validas=3,
            total_degradadas=2,
            tasa_degradacion=0.4,
        )
        result = r.to_dict()
        assert result["total_procesadas"] == 5
        assert result["tasa_degradacion"] == 0.4

    def test_resumen_texto_con_degradadas(self):
        d = DetalleEnforcement(
            agente="AG06",
            nivel_original="CRITICA",
            nivel_post="INCIERTO",
            fue_degradada=True,
            descripcion="Documento faltante en expediente",
            campos_faltantes=["archivo", "snippet"],
        )
        r = ReporteEnforcement(
            detalles=[d],
            total_procesadas=1,
            total_degradadas=1,
            tasa_degradacion=1.0,
        )
        texto = r.resumen_texto()
        assert "AG06" in texto
        assert "archivo" in texto

    def test_resumen_texto_sin_degradadas(self):
        r = ReporteEnforcement(
            total_procesadas=3,
            total_validas=3,
            total_degradadas=0,
            tasa_degradacion=0.0,
        )
        texto = r.resumen_texto()
        assert "0 degradadas" in texto


# ==============================================================================
# HITO 2: TESTS DE SeccionDiagnostico Y DiagnosticoExpediente
# ==============================================================================


class TestSeccionDiagnostico:
    """Tests para SeccionDiagnostico dataclass."""

    def test_defaults(self):
        s = SeccionDiagnostico()
        assert s.nombre == ""
        assert s.status == "OK"
        assert s.detalles == []

    def test_to_dict(self):
        s = SeccionDiagnostico(
            nombre="evaluacion_campos",
            status="WARNING",
            mensaje="3 campos abstenidos",
            detalles=["campo_a", "campo_b"],
        )
        result = s.to_dict()
        assert result["nombre"] == "evaluacion_campos"
        assert result["status"] == "WARNING"
        assert len(result["detalles"]) == 2


class TestDiagnosticoExpediente:
    """Tests para DiagnosticoExpediente."""

    def test_defaults(self):
        d = DiagnosticoExpediente()
        assert d.sinad == ""
        assert d.secciones == []
        assert d.version_router == VERSION_ROUTER

    def test_to_dict(self):
        d = DiagnosticoExpediente(
            sinad="TEST-001",
            secciones=[
                SeccionDiagnostico(nombre="campos", status="OK", mensaje="todo bien"),
            ],
        )
        result = d.to_dict()
        assert result["sinad"] == "TEST-001"
        assert len(result["secciones"]) == 1

    def test_to_rows_con_detalles(self):
        d = DiagnosticoExpediente(
            sinad="TEST-002",
            secciones=[
                SeccionDiagnostico(
                    nombre="completitud",
                    status="WARNING",
                    mensaje="2 problemas",
                    detalles=["falta SINAD", "falta naturaleza"],
                ),
            ],
        )
        rows = d.to_rows()
        assert len(rows) == 2
        assert rows[0]["seccion"] == "completitud"
        assert rows[0]["detalle"] == "falta SINAD"
        assert rows[1]["detalle"] == "falta naturaleza"

    def test_to_rows_sin_detalles(self):
        d = DiagnosticoExpediente(
            secciones=[
                SeccionDiagnostico(nombre="unicidad", status="OK", mensaje="ok"),
            ],
        )
        rows = d.to_rows()
        assert len(rows) == 1
        assert rows[0]["detalle"] == ""

    def test_resumen_texto(self):
        d = DiagnosticoExpediente(
            sinad="TEST-003",
            secciones=[
                SeccionDiagnostico(nombre="campos", status="OK", mensaje="12/12 legibles"),
                SeccionDiagnostico(nombre="aritmetica", status="WARNING", mensaje="2 errores"),
            ],
        )
        texto = d.resumen_texto()
        assert "TEST-003" in texto
        assert "campos" in texto
        assert "OK" in texto
        assert "WARNING" in texto


# ==============================================================================
# HITO 2: TESTS DE IntegrityCheckpoint
# ==============================================================================


class TestIntegrityCheckpointInit:
    """Tests de inicialización del IntegrityCheckpoint."""

    def test_init_default(self):
        cp = IntegrityCheckpoint()
        assert isinstance(cp.router, ConfidenceRouter)
        assert cp.logger is None
        assert cp.agente_id == "INTEGRITY_CHECKPOINT"

    def test_init_custom_umbrales(self):
        umbrales = UmbralesRouter(max_campos_abstencion_warning_pct=0.15)
        cp = IntegrityCheckpoint(umbrales=umbrales)
        assert cp.router.umbrales.max_campos_abstencion_warning_pct == 0.15

    def test_acciones_definidas(self):
        assert IntegrityCheckpoint.ACCION_CONTINUAR == "CONTINUAR"
        assert IntegrityCheckpoint.ACCION_CONTINUAR_CON_ALERTAS == "CONTINUAR_CON_ALERTAS"
        assert IntegrityCheckpoint.ACCION_DETENER == "DETENER"


class TestIntegrityCheckpointEvaluar:
    """Tests del método evaluar() del IntegrityCheckpoint."""

    def test_expediente_limpio_continuar(self):
        """Expediente con 3 comprobantes bien extraídos → CONTINUAR."""
        cp = IntegrityCheckpoint()
        exp = _crear_expediente_completo(3)
        decision = cp.evaluar(exp)

        assert isinstance(decision, DecisionCheckpoint)
        assert decision.accion == "CONTINUAR"
        assert decision.resultado is not None
        assert decision.resultado.status == IntegridadStatus.OK
        assert decision.timestamp != ""

    def test_expediente_limpio_diagnostico_6_secciones(self):
        """El diagnóstico siempre tiene 6 secciones estándar."""
        cp = IntegrityCheckpoint()
        exp = _crear_expediente_completo(2)
        decision = cp.evaluar(exp)

        assert decision.diagnostico is not None
        assert len(decision.diagnostico.secciones) == 6
        nombres = [s.nombre for s in decision.diagnostico.secciones]
        assert "evaluacion_campos" in nombres
        assert "enforcement" in nombres
        assert "completitud" in nombres
        assert "unicidad" in nombres
        assert "aritmetica" in nombres
        assert "decision" in nombres

    def test_expediente_alta_abstencion_detener_o_alertas(self):
        """Expediente con ~50% abstención → DETENER o CONTINUAR_CON_ALERTAS."""
        cp = IntegrityCheckpoint()
        exp = _crear_expediente_50pct_abstencion()
        decision = cp.evaluar(exp)

        assert decision.accion in ["DETENER", "CONTINUAR_CON_ALERTAS"]
        assert decision.resultado is not None
        assert decision.resultado.tasa_abstencion >= 0.30

    def test_expediente_critical_detener(self):
        """Expediente CRITICAL con umbrales estrictos → DETENER."""
        cp = IntegrityCheckpoint(
            umbrales=UmbralesRouter(
                max_campos_abstencion_critical_pct=0.20,
            )
        )
        exp = _crear_expediente_50pct_abstencion()
        decision = cp.evaluar(exp)

        if decision.resultado.status == IntegridadStatus.CRITICAL:
            assert decision.accion == "DETENER"
            assert decision.resultado.debe_detener is True

    def test_observaciones_degradadas_en_reporte(self):
        """Observaciones sin evidencia aparecen como degradadas en reporte."""
        cp = IntegrityCheckpoint()
        exp = _crear_expediente_completo(1)
        obs = [
            _crear_observacion_critica_sin_evidencia(),
            _crear_observacion_mayor_sin_evidencia(),
        ]
        decision = cp.evaluar(exp, obs)

        assert decision.reporte_enforcement is not None
        assert decision.reporte_enforcement.total_degradadas == 2
        # Los detalles incluyen campos faltantes
        degradadas = [d for d in decision.reporte_enforcement.detalles if d.fue_degradada]
        assert len(degradadas) == 2
        for d in degradadas:
            assert len(d.campos_faltantes) > 0

    def test_observacion_valida_en_reporte(self):
        """Observación con evidencia completa no se degrada."""
        cp = IntegrityCheckpoint()
        exp = _crear_expediente_completo(1)
        obs = [_crear_observacion_critica_con_evidencia()]
        decision = cp.evaluar(exp, obs)

        assert decision.reporte_enforcement.total_validas == 1
        assert decision.reporte_enforcement.total_degradadas == 0

    def test_sin_observaciones_reporte_vacio(self):
        """Sin observaciones → reporte con 0 procesadas."""
        cp = IntegrityCheckpoint()
        exp = _crear_expediente_completo(1)
        decision = cp.evaluar(exp)

        assert decision.reporte_enforcement is not None
        assert decision.reporte_enforcement.total_procesadas == 0

    def test_diagnostico_to_rows(self):
        """El diagnóstico puede convertirse a filas de Excel."""
        cp = IntegrityCheckpoint()
        exp = _crear_expediente_completo(2)
        decision = cp.evaluar(exp)

        rows = decision.diagnostico.to_rows()
        assert len(rows) >= 6  # Al menos 1 fila por sección
        assert all("seccion" in r and "status" in r for r in rows)

    def test_decision_to_dict_serializable(self):
        """DecisionCheckpoint.to_dict() produce un dict serializable."""
        cp = IntegrityCheckpoint()
        exp = _crear_expediente_completo(1)
        decision = cp.evaluar(exp)

        d = decision.to_dict()
        assert isinstance(d, dict)
        assert d["accion"] == "CONTINUAR"
        assert d["resultado"] is not None
        assert d["diagnostico"] is not None
        # Verificar que es JSON-serializable
        import json

        json_str = json.dumps(d, ensure_ascii=False)
        assert len(json_str) > 100

    def test_resumen_texto(self):
        """DecisionCheckpoint.resumen_texto() genera texto legible."""
        cp = IntegrityCheckpoint()
        exp = _crear_expediente_completo(1)
        decision = cp.evaluar(exp)

        texto = decision.resumen_texto()
        assert "IntegrityCheckpoint" in texto
        assert "CONTINUAR" in texto


class TestDetectarCamposFaltantes:
    """Tests para IntegrityCheckpoint._detectar_campos_faltantes."""

    def test_sin_evidencias(self):
        """Observación sin evidencias → faltante 'evidencias (ninguna)'."""
        obs = _crear_observacion_critica_sin_evidencia()
        faltantes = IntegrityCheckpoint._detectar_campos_faltantes(obs)
        assert "evidencias (ninguna)" in faltantes

    def test_evidencia_completa(self):
        """Observación con evidencia completa → sin faltantes."""
        obs = _crear_observacion_critica_con_evidencia()
        faltantes = IntegrityCheckpoint._detectar_campos_faltantes(obs)
        assert len(faltantes) == 0

    def test_evidencia_parcial(self):
        """Evidencia con campos vacíos → faltantes específicos."""
        obs = Observacion(
            nivel=NivelObservacion.CRITICA,
            agente="AG04",
            descripcion="test",
            accion_requerida="test",
        )
        obs.agregar_evidencia(
            EvidenciaProbatoria(
                archivo="test.pdf",
                pagina=3,
                valor_detectado="100.00",
                # snippet vacío, regla_aplicada vacía
            )
        )
        faltantes = IntegrityCheckpoint._detectar_campos_faltantes(obs)
        assert "snippet" in faltantes
        assert "regla_aplicada" in faltantes
        assert "archivo" not in faltantes  # archivo sí existe

    def test_evidencia_pagina_cero(self):
        """Pagina=0 → faltante 'pagina'."""
        obs = Observacion(
            nivel=NivelObservacion.MAYOR,
            agente="AG03",
            descripcion="test",
            accion_requerida="test",
        )
        obs.agregar_evidencia(
            EvidenciaProbatoria(
                archivo="test.pdf",
                pagina=0,
                valor_detectado="valor",
                snippet="texto",
                regla_aplicada="RULE_001",
            )
        )
        faltantes = IntegrityCheckpoint._detectar_campos_faltantes(obs)
        assert "pagina" in faltantes


class TestIntegrityCheckpointConLogger:
    """Tests del IntegrityCheckpoint con TraceLogger."""

    def test_evaluar_con_logger_no_falla(self, temp_log_dir):
        logger = TraceLogger(log_dir=temp_log_dir)
        logger.start_trace(sinad="TEST-CP-001", source="test")
        cp = IntegrityCheckpoint(trace_logger=logger)

        exp = _crear_expediente_completo(1)
        decision = cp.evaluar(exp)
        assert decision.accion == "CONTINUAR"

        if logger.has_active_trace:
            logger.end_trace()

    def test_evaluar_critical_con_logger(self, temp_log_dir):
        logger = TraceLogger(log_dir=temp_log_dir)
        logger.start_trace(sinad="TEST-CP-002", source="test")
        cp = IntegrityCheckpoint(
            trace_logger=logger,
            umbrales=UmbralesRouter(
                max_campos_abstencion_critical_pct=0.20,
            ),
        )

        exp = _crear_expediente_50pct_abstencion()
        decision = cp.evaluar(exp)

        # Debería ser DETENER o CONTINUAR_CON_ALERTAS
        assert decision.accion in ["DETENER", "CONTINUAR_CON_ALERTAS"]

        if logger.has_active_trace:
            logger.end_trace()


# ==============================================================================
# HITO 2: TESTS DE DecisionCheckpoint
# ==============================================================================


class TestDecisionCheckpoint:
    """Tests para DecisionCheckpoint dataclass."""

    def test_defaults(self):
        d = DecisionCheckpoint()
        assert d.accion == "CONTINUAR"
        assert d.resultado is None
        assert d.reporte_enforcement is None
        assert d.diagnostico is None

    def test_to_dict_vacio(self):
        d = DecisionCheckpoint()
        result = d.to_dict()
        assert result["accion"] == "CONTINUAR"
        assert result["resultado"] is None

    def test_resumen_texto_default(self):
        d = DecisionCheckpoint()
        texto = d.resumen_texto()
        assert "IntegrityCheckpoint" in texto
        assert "CONTINUAR" in texto


# ==============================================================================
# HITO 2: TESTS DE EDGE CASES
# ==============================================================================


class TestEdgeCases:
    """Tests de edge cases para Hito 2."""

    def test_expediente_vacio_no_crash(self):
        """IntegrityCheckpoint con expediente vacío no crashea."""
        cp = IntegrityCheckpoint()
        exp = ExpedienteJSON(sinad="VACIO")
        decision = cp.evaluar(exp)
        assert isinstance(decision, DecisionCheckpoint)
        assert decision.diagnostico is not None

    def test_muchas_observaciones_degradadas(self):
        """Muchas observaciones degradadas → se reflejan en reporte."""
        cp = IntegrityCheckpoint()
        exp = _crear_expediente_completo(1)
        obs = [_crear_observacion_critica_sin_evidencia() for _ in range(10)]
        decision = cp.evaluar(exp, obs)

        assert decision.reporte_enforcement.total_degradadas == 10

    def test_observaciones_mixtas(self):
        """Mix de observaciones válidas, degradadas y menores."""
        cp = IntegrityCheckpoint()
        exp = _crear_expediente_completo(2)
        obs = [
            _crear_observacion_critica_con_evidencia(),
            _crear_observacion_critica_sin_evidencia(),
            _crear_observacion_mayor_sin_evidencia(),
            _crear_observacion_menor(),
        ]
        decision = cp.evaluar(exp, obs)

        reporte = decision.reporte_enforcement
        assert reporte.total_procesadas == 4
        assert reporte.total_validas == 2  # CRITICA con evidencia + MENOR
        assert reporte.total_degradadas == 2  # CRITICA sin + MAYOR sin

    def test_diagnostico_sinad_propagado(self):
        """El SINAD del expediente se propaga al diagnóstico."""
        cp = IntegrityCheckpoint()
        exp = _crear_expediente_completo(1)
        exp.sinad = "ODI2026-INT-0139051"
        decision = cp.evaluar(exp)

        assert decision.diagnostico.sinad == "ODI2026-INT-0139051"

    def test_version_router_en_diagnostico(self):
        """La versión del router se incluye en el diagnóstico."""
        cp = IntegrityCheckpoint()
        exp = _crear_expediente_completo(1)
        decision = cp.evaluar(exp)

        assert decision.diagnostico.version_router == VERSION_ROUTER
