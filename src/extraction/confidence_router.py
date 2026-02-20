# -*- coding: utf-8 -*-
"""
Confidence Router + Integrity Checkpoint
==========================================
Tarea #18 del Plan de Desarrollo (Fase 2: Contrato + Router)

Evalúa la calidad e integridad de un ExpedienteJSON post-extracción
y determina si cumple los estándares mínimos para continuar el pipeline.

Opera como nodo de evaluación standalone. NO modifica el flujo AG01→AG09.
La integración como nodo LangGraph se realiza en Tarea #21.

Pipeline interno:
  1. Recolectar todos los CampoExtraido del expediente
  2. Evaluar cada campo con AbstencionPolicy (umbral por tipo)
  3. Aplicar EvidenceEnforcer a observaciones existentes (Art. 4-5)
  4. Verificar completitud estructural
  5. Verificar unicidad de comprobantes
  6. Recoger errores aritméticos (Grupo J)
  7. Computar IntegridadStatus agregado (OK/WARNING/CRITICAL)

Principios:
  - Reutiliza Observacion.validar_y_degradar() (no duplica lógica probatoria)
  - Reutiliza AbstencionPolicy.evaluar_lote() (no reimplementa umbrales)
  - CRITICAL marca debe_detener=True como señal; la detención real
    la ejecuta el orquestador (Art. 2.2/2.3 de Gobernanza)
  - Todos los umbrales son configurables para calibración (Tarea #19)

Uso:
    from src.extraction.confidence_router import ConfidenceRouter

    router = ConfidenceRouter()
    resultado = router.evaluar_expediente(expediente, observaciones)

    if resultado.debe_detener:
        print(f"SEÑAL CRITICAL: {resultado.razon_detencion}")
        # Orquestador decide si detener pipeline (Art. 2.2)
    else:
        print(f"Status: {resultado.status.value}")

Gobernanza:
  - Art. 2: Flujo AG01→AG09 intacto (este módulo es standalone)
  - Art. 3: Anti-alucinación (delega a AbstencionPolicy)
  - Art. 4: Estándar probatorio (EvidenceEnforcer)
  - Art. 5: Degradación automática (Observacion.validar_y_degradar)
  - Art. 17: Trazabilidad (TraceLogger)
  - ADR-005: No es módulo monolítico; preparado para nodo LangGraph
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

from config.settings import (
    Observacion,
    NivelObservacion,
    EvidenciaProbatoria,
)
from src.extraction.abstencion import (
    CampoExtraido,
    EvidenceStatus,
    UmbralesAbstencion,
    AbstencionPolicy,
    ResultadoAbstencion,
)
from src.extraction.expediente_contract import (
    ExpedienteJSON,
    IntegridadStatus,
    IntegridadExpediente,
    ConfianzaGlobal,
)


# ==============================================================================
# CONSTANTES
# ==============================================================================

VERSION_ROUTER = "1.0.0"
"""Versión del módulo confidence_router."""

AGENTE_ID_DEFAULT = "ROUTER"
"""ID de agente por defecto para logging."""


# ==============================================================================
# UMBRALES DEL ROUTER
# ==============================================================================

@dataclass
class UmbralesRouter:
    """
    Umbrales configurables para decisiones del ConfidenceRouter.

    Controla los puntos de corte para escalar el status de integridad
    de OK a WARNING a CRITICAL. Todos los defaults son conservadores
    para calibrar con datos reales en Tarea #19.

    Porcentajes como fracciones (0.0 a 1.0).
    """
    # --- Abstención ---
    max_campos_abstencion_warning_pct: float = 0.30
    """>=30% campos abstenidos → WARNING."""

    max_campos_abstencion_critical_pct: float = 0.50
    """>=50% campos abstenidos → CRITICAL."""

    # --- Evidence enforcement ---
    max_observaciones_degradadas_warning: int = 2
    """>2 observaciones degradadas → WARNING."""

    max_observaciones_degradadas_critical: int = 5
    """>5 observaciones degradadas → CRITICAL."""

    # --- Datos mínimos ---
    min_comprobantes_con_datos: int = 1
    """Al menos 1 comprobante con datos extraídos."""

    min_campos_por_comprobante: int = 3
    """Mínimo de campos por comprobante para considerarlo válido."""

    # --- Errores aritméticos ---
    max_errores_aritmeticos_warning: int = 2
    """>2 errores aritméticos → WARNING."""

    max_errores_aritmeticos_critical: int = 5
    """>5 errores aritméticos → CRITICAL."""

    # --- Completitud ---
    completitud_problemas_critical: int = 3
    """>=3 problemas de completitud → CRITICAL."""

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "UmbralesRouter":
        """Crea desde diccionario."""
        if not data:
            return cls()
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ==============================================================================
# EVIDENCE ENFORCER
# ==============================================================================

class EvidenceEnforcer:
    """
    Ejecuta enforcement del estándar probatorio (Art. 4-5 Gobernanza)
    sobre una lista de Observaciones.

    NO reimplementa la lógica de degradación — delega a
    Observacion.validar_y_degradar() que ya existe en config/settings.py.

    Proporciona:
      - Procesamiento en lote
      - Separación válidas vs degradadas
      - Estadísticas de enforcement
    """

    @staticmethod
    def enforce_all(
        observaciones: List[Observacion],
    ) -> Tuple[List[Observacion], List[Observacion]]:
        """
        Aplica enforcement a todas las observaciones.

        Para cada observación CRITICA o MAYOR sin evidencia completa,
        llama validar_y_degradar() que la degrada a INCIERTO con
        requiere_revision_humana=True.

        Observaciones MENOR, INFORMATIVA e INCIERTO pasan sin cambio.

        Args:
            observaciones: Lista de observaciones a procesar.

        Returns:
            Tupla (validas, degradadas) donde:
              - validas: observaciones que mantuvieron su nivel original
              - degradadas: observaciones degradadas a INCIERTO
        """
        validas: List[Observacion] = []
        degradadas: List[Observacion] = []

        for obs in observaciones:
            nivel_original = obs.nivel
            obs.validar_y_degradar()

            if obs.nivel != nivel_original:
                degradadas.append(obs)
            else:
                validas.append(obs)

        return validas, degradadas

    @staticmethod
    def get_stats(
        validas: List[Observacion],
        degradadas: List[Observacion],
    ) -> Dict[str, Any]:
        """
        Genera estadísticas del enforcement.

        Args:
            validas: Lista de observaciones válidas.
            degradadas: Lista de observaciones degradadas.

        Returns:
            Dict con conteos por nivel y tasas.
        """
        total = len(validas) + len(degradadas)
        por_nivel: Dict[str, int] = {}

        for obs in validas:
            key = obs.nivel.value
            por_nivel[key] = por_nivel.get(key, 0) + 1

        return {
            "total_procesadas": total,
            "validas": len(validas),
            "degradadas": len(degradadas),
            "tasa_degradacion": len(degradadas) / total if total > 0 else 0.0,
            "por_nivel_post_enforcement": por_nivel,
        }


# ==============================================================================
# RESULTADO DEL ROUTER
# ==============================================================================

@dataclass
class ResultadoRouter:
    """
    Resultado completo de la evaluación del ConfidenceRouter.

    Contiene:
      - El expediente actualizado (integridad, resumen)
      - La decisión de status (OK/WARNING/CRITICAL)
      - Datos de diagnóstico para hoja DIAGNOSTICO del Excel (Tarea #20)
      - Flag debe_detener como señal al orquestador (Art. 2.2/2.3)

    El campo debe_detener es una SEÑAL, no una acción directa.
    La detención real del pipeline la ejecuta el orquestador.
    """
    # --- Decisión core ---
    expediente: Optional[ExpedienteJSON] = None
    status: IntegridadStatus = IntegridadStatus.OK
    confianza_global: ConfianzaGlobal = ConfianzaGlobal.ALTA
    debe_detener: bool = False
    razon_detencion: str = ""

    # --- Métricas de campos ---
    campos_evaluados: int = 0
    campos_abstenidos: int = 0
    campos_incompletos: int = 0
    campos_legibles: int = 0
    tasa_abstencion: float = 0.0

    # --- Evidence enforcement ---
    observaciones_validas: List[Observacion] = field(default_factory=list)
    observaciones_degradadas: List[Observacion] = field(default_factory=list)

    # --- Abstención ---
    resultados_abstencion: List[ResultadoAbstencion] = field(default_factory=list)

    # --- Completitud y duplicados ---
    problemas_completitud: List[str] = field(default_factory=list)
    comprobantes_duplicados: List[str] = field(default_factory=list)

    # --- Errores aritméticos ---
    errores_aritmeticos: List[str] = field(default_factory=list)

    # --- Alertas agregadas ---
    alertas: List[str] = field(default_factory=list)

    # --- Metadata ---
    timestamp: str = ""
    version_router: str = VERSION_ROUTER

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario para JSON/diagnóstico."""
        return {
            "status": self.status.value,
            "confianza_global": self.confianza_global.value,
            "debe_detener": self.debe_detener,
            "razon_detencion": self.razon_detencion,
            "campos_evaluados": self.campos_evaluados,
            "campos_abstenidos": self.campos_abstenidos,
            "campos_incompletos": self.campos_incompletos,
            "campos_legibles": self.campos_legibles,
            "tasa_abstencion": round(self.tasa_abstencion, 4),
            "observaciones_validas": len(self.observaciones_validas),
            "observaciones_degradadas": len(self.observaciones_degradadas),
            "problemas_completitud": self.problemas_completitud,
            "comprobantes_duplicados": self.comprobantes_duplicados,
            "errores_aritmeticos": self.errores_aritmeticos,
            "alertas": self.alertas,
            "timestamp": self.timestamp,
            "version_router": self.version_router,
        }

    def resumen_texto(self) -> str:
        """Genera resumen legible para logging y reportes."""
        lineas = [
            f"=== Resultado ConfidenceRouter v{self.version_router} ===",
            f"Status: {self.status.value} | Confianza: {self.confianza_global.value}",
            f"Campos: {self.campos_evaluados} eval, "
            f"{self.campos_legibles} OK, "
            f"{self.campos_incompletos} incompletos, "
            f"{self.campos_abstenidos} abstenidos "
            f"({self.tasa_abstencion:.1%})",
        ]

        if self.observaciones_degradadas:
            lineas.append(
                f"Observaciones degradadas: {len(self.observaciones_degradadas)}"
            )

        if self.errores_aritmeticos:
            lineas.append(
                f"Errores aritméticos: {len(self.errores_aritmeticos)}"
            )

        if self.problemas_completitud:
            lineas.append(
                f"Problemas completitud: {len(self.problemas_completitud)}"
            )

        if self.debe_detener:
            lineas.append(f"⚠ SEÑAL CRITICAL: {self.razon_detencion}")

        if self.alertas:
            lineas.append(f"Alertas: {len(self.alertas)}")

        return "\n".join(lineas)


# ==============================================================================
# CONFIDENCE ROUTER — Clase principal
# ==============================================================================

class ConfidenceRouter:
    """
    Router de Confianza + Integrity Checkpoint para ExpedienteJSON.

    Tarea #18 del Plan de Desarrollo (Fase 2: Contrato + Router).

    Opera como nodo de evaluación post-extracción. Recibe un
    ExpedienteJSON ya poblado y determina si la extracción cumple
    con los estándares mínimos de calidad e integridad.

    NO modifica el flujo AG01→AG09 (Art. 2 Gobernanza).
    CRITICAL es una señal; la detención la ejecuta el orquestador (Art. 2.2).

    Preparado para integración como nodo LangGraph en Tarea #21.

    Uso:
        router = ConfidenceRouter()
        resultado = router.evaluar_expediente(expediente)

        if resultado.debe_detener:
            # Orquestador decide acción (Art. 2.2/2.3)
            print(f"SEÑAL CRITICAL: {resultado.razon_detencion}")
        else:
            print(f"Status: {resultado.status.value}")
    """

    def __init__(
        self,
        umbrales: Optional[UmbralesRouter] = None,
        umbrales_abstencion: Optional[UmbralesAbstencion] = None,
        trace_logger: Optional[Any] = None,
        agente_id: str = AGENTE_ID_DEFAULT,
    ):
        """
        Inicializa el ConfidenceRouter.

        Args:
            umbrales: Umbrales del router para escalación de status.
            umbrales_abstencion: Umbrales de abstención por tipo de campo.
            trace_logger: Instancia de TraceLogger (opcional).
            agente_id: ID de agente para logging.
        """
        self.umbrales = umbrales or UmbralesRouter()
        self.policy = AbstencionPolicy(
            umbrales=umbrales_abstencion,
            agente_id=agente_id,
            trace_logger=trace_logger,
        )
        self.logger = trace_logger
        self.agente_id = agente_id

    def evaluar_expediente(
        self,
        expediente: ExpedienteJSON,
        observaciones: Optional[List[Observacion]] = None,
    ) -> ResultadoRouter:
        """
        Evalúa un expediente completo post-extracción.

        Args:
            expediente: ExpedienteJSON ya poblado con datos de extracción.
            observaciones: Lista opcional de observaciones existentes
                          (de agentes previos). Si None, se usa lista vacía.

        Returns:
            ResultadoRouter con decisión y diagnóstico completo.

        Nota:
            Este es el método principal. La implementación completa
            se activa en Hito 2 (Tarea #18). Hito 1 retorna status OK
            con métricas básicas del expediente.
        """
        obs = observaciones or []
        timestamp = datetime.now(timezone.utc).isoformat()

        # --- Paso 1: Recolectar y evaluar campos ---
        resultados_abs, stats = self._paso1_evaluar_campos(expediente)

        # --- Paso 2: Enforce evidencia ---
        validas, degradadas = self._paso2_enforce_evidencia(obs)

        # --- Paso 3-5: Verificaciones estructurales ---
        problemas = self._paso3_verificar_completitud(expediente)
        duplicados = self._paso4_verificar_unicidad(expediente)
        errores_arit = self._paso5_recoger_errores_aritmeticos(expediente)

        # --- Paso 6: Computar status agregado ---
        status, confianza, debe_detener, razon, alertas = (
            self._paso6_computar_status(
                stats, degradadas, problemas, duplicados,
                errores_arit, expediente,
            )
        )

        # --- Paso 7: Actualizar expediente ---
        self._paso7_actualizar_expediente(expediente, status, alertas)

        # --- Construir resultado ---
        resultado = ResultadoRouter(
            expediente=expediente,
            status=status,
            confianza_global=confianza,
            debe_detener=debe_detener,
            razon_detencion=razon,
            campos_evaluados=stats["total"],
            campos_abstenidos=stats["abstenidos"],
            campos_incompletos=stats["incompletos"],
            campos_legibles=stats["legibles"],
            tasa_abstencion=(
                stats["abstenidos"] / stats["total"]
                if stats["total"] > 0 else 0.0
            ),
            observaciones_validas=validas,
            observaciones_degradadas=degradadas,
            resultados_abstencion=resultados_abs,
            problemas_completitud=problemas,
            comprobantes_duplicados=duplicados,
            errores_aritmeticos=errores_arit,
            alertas=alertas,
            timestamp=timestamp,
        )

        # --- Logging (Hito 3 amplía esto) ---
        self._log_resultado(resultado)

        return resultado

    # ------------------------------------------------------------------
    # PASOS INTERNOS
    # ------------------------------------------------------------------

    def _paso1_evaluar_campos(
        self, expediente: ExpedienteJSON,
    ) -> Tuple[List[ResultadoAbstencion], Dict[str, int]]:
        """
        Recolecta todos los campos y evalúa con AbstencionPolicy.

        Usa ExpedienteJSON._recolectar_todos_campos() — método privado
        del contrato. Test de regresión dedicado en test_confidence_router.py
        para detectar roturas futuras si cambia el nombre o firma.
        """
        todos_campos = expediente._recolectar_todos_campos()
        resultados = self.policy.evaluar_lote(todos_campos)

        stats: Dict[str, int] = {
            "total": len(todos_campos),
            "legibles": 0,
            "incompletos": 0,
            "abstenidos": 0,
        }

        for campo in todos_campos:
            status = campo.clasificar_status()
            if status == EvidenceStatus.LEGIBLE:
                stats["legibles"] += 1
            elif status == EvidenceStatus.INCOMPLETO:
                stats["incompletos"] += 1
            elif status == EvidenceStatus.ILEGIBLE:
                stats["abstenidos"] += 1

        return resultados, stats

    def _paso2_enforce_evidencia(
        self, observaciones: List[Observacion],
    ) -> Tuple[List[Observacion], List[Observacion]]:
        """Aplica EvidenceEnforcer. Delega a Observacion.validar_y_degradar()."""
        return EvidenceEnforcer.enforce_all(observaciones)

    def _paso3_verificar_completitud(
        self, expediente: ExpedienteJSON,
    ) -> List[str]:
        """Delega a ExpedienteJSON.validar_completitud()."""
        return expediente.validar_completitud()

    def _paso4_verificar_unicidad(
        self, expediente: ExpedienteJSON,
    ) -> List[str]:
        """Delega a ExpedienteJSON.verificar_unicidad_comprobantes()."""
        return expediente.verificar_unicidad_comprobantes()

    def _paso5_recoger_errores_aritmeticos(
        self, expediente: ExpedienteJSON,
    ) -> List[str]:
        """Recolecta errores aritméticos de Grupo J de cada comprobante."""
        errores: List[str] = []
        for i, comp in enumerate(expediente.comprobantes):
            if comp.grupo_j and not comp.grupo_j.todas_ok():
                serie_num = comp.get_serie_numero() or f"#{i + 1}"
                for err in comp.grupo_j.errores_detalle:
                    errores.append(f"Comprobante {serie_num}: {err}")
                if comp.grupo_j.suma_items_ok is False:
                    errores.append(
                        f"Comprobante {serie_num}: suma de items no cuadra"
                    )
                if comp.grupo_j.igv_ok is False:
                    errores.append(
                        f"Comprobante {serie_num}: IGV no cuadra"
                    )
                if comp.grupo_j.total_ok is False:
                    errores.append(
                        f"Comprobante {serie_num}: total no cuadra"
                    )
        return errores

    def _paso6_computar_status(
        self,
        stats_campos: Dict[str, int],
        degradadas: List[Observacion],
        problemas: List[str],
        duplicados: List[str],
        errores_arit: List[str],
        expediente: ExpedienteJSON,
    ) -> Tuple[IntegridadStatus, ConfianzaGlobal, bool, str, List[str]]:
        """
        Computa IntegridadStatus agregado basado en todas las señales.

        Escalación: OK < WARNING < CRITICAL.
        Cada check puede escalar. El status final es el máximo.
        CRITICAL marca debe_detener=True como SEÑAL al orquestador.

        Duplicados → WARNING (nunca CRITICAL). Per Hans:
        "Hotel con múltiples noches en 1 factura = válido."
        """
        status = IntegridadStatus.OK
        alertas: List[str] = []
        razon_detencion = ""

        total = stats_campos["total"]

        # --- Check 1: Tasa de abstención ---
        if total > 0:
            tasa = stats_campos["abstenidos"] / total
            if tasa >= self.umbrales.max_campos_abstencion_critical_pct:
                status = IntegridadStatus.CRITICAL
                msg = (
                    f"Tasa de abstención {tasa:.0%} >= "
                    f"{self.umbrales.max_campos_abstencion_critical_pct:.0%}"
                )
                alertas.append(msg)
                razon_detencion = msg
            elif tasa >= self.umbrales.max_campos_abstencion_warning_pct:
                status = self._max_status(status, IntegridadStatus.WARNING)
                alertas.append(
                    f"Tasa de abstención {tasa:.0%} >= "
                    f"{self.umbrales.max_campos_abstencion_warning_pct:.0%}"
                )

        # --- Check 2: Datos mínimos ---
        n_comp_con_datos = sum(
            1 for c in expediente.comprobantes
            if len(c.todos_los_campos()) >= self.umbrales.min_campos_por_comprobante
        )
        if n_comp_con_datos < self.umbrales.min_comprobantes_con_datos:
            status = self._max_status(status, IntegridadStatus.CRITICAL)
            msg = (
                f"Solo {n_comp_con_datos} comprobantes con datos "
                f"(mínimo: {self.umbrales.min_comprobantes_con_datos})"
            )
            alertas.append(msg)
            if not razon_detencion:
                razon_detencion = msg

        # --- Check 3: Observaciones degradadas ---
        n_degradadas = len(degradadas)
        if n_degradadas > self.umbrales.max_observaciones_degradadas_critical:
            status = self._max_status(status, IntegridadStatus.CRITICAL)
            msg = (
                f"{n_degradadas} observaciones degradadas "
                f"(máximo critical: {self.umbrales.max_observaciones_degradadas_critical})"
            )
            alertas.append(msg)
            if not razon_detencion:
                razon_detencion = msg
        elif n_degradadas > self.umbrales.max_observaciones_degradadas_warning:
            status = self._max_status(status, IntegridadStatus.WARNING)
            alertas.append(
                f"{n_degradadas} observaciones degradadas "
                f"(máximo warning: {self.umbrales.max_observaciones_degradadas_warning})"
            )

        # --- Check 4: Completitud ---
        if len(problemas) >= self.umbrales.completitud_problemas_critical:
            status = self._max_status(status, IntegridadStatus.CRITICAL)
            msg = (
                f"{len(problemas)} problemas de completitud "
                f"(máximo: {self.umbrales.completitud_problemas_critical})"
            )
            alertas.append(msg)
            if not razon_detencion:
                razon_detencion = msg

        # --- Check 5: Duplicados → WARNING (nunca CRITICAL) ---
        if duplicados:
            status = self._max_status(status, IntegridadStatus.WARNING)
            alertas.append(
                f"{len(duplicados)} comprobantes posiblemente duplicados "
                f"(requiere revisión humana)"
            )

        # --- Check 6: Errores aritméticos ---
        n_arit = len(errores_arit)
        if n_arit > self.umbrales.max_errores_aritmeticos_critical:
            status = self._max_status(status, IntegridadStatus.CRITICAL)
            msg = (
                f"{n_arit} errores aritméticos "
                f"(máximo critical: {self.umbrales.max_errores_aritmeticos_critical})"
            )
            alertas.append(msg)
            if not razon_detencion:
                razon_detencion = msg
        elif n_arit > self.umbrales.max_errores_aritmeticos_warning:
            status = self._max_status(status, IntegridadStatus.WARNING)
            alertas.append(
                f"{n_arit} errores aritméticos "
                f"(máximo warning: {self.umbrales.max_errores_aritmeticos_warning})"
            )

        # --- Determinar ConfianzaGlobal ---
        debe_detener = (status == IntegridadStatus.CRITICAL)
        confianza = self._computar_confianza_global(
            status, stats_campos, n_degradadas,
        )

        return status, confianza, debe_detener, razon_detencion, alertas

    def _paso7_actualizar_expediente(
        self,
        expediente: ExpedienteJSON,
        status: IntegridadStatus,
        alertas: List[str],
    ) -> None:
        """Actualiza expediente.integridad y regenera resumen + hash."""
        expediente.integridad.status = status.value
        expediente.integridad.alertas = alertas
        expediente.generar_resumen()
        expediente.generar_hash()

    # ------------------------------------------------------------------
    # UTILIDADES INTERNAS
    # ------------------------------------------------------------------

    @staticmethod
    def _max_status(
        current: IntegridadStatus,
        new: IntegridadStatus,
    ) -> IntegridadStatus:
        """Retorna el status más severo. OK < WARNING < CRITICAL."""
        order = {
            IntegridadStatus.OK: 0,
            IntegridadStatus.WARNING: 1,
            IntegridadStatus.CRITICAL: 2,
        }
        if order.get(new, 0) > order.get(current, 0):
            return new
        return current

    @staticmethod
    def _computar_confianza_global(
        status: IntegridadStatus,
        stats: Dict[str, int],
        n_degradadas: int,
    ) -> ConfianzaGlobal:
        """
        Determina ConfianzaGlobal basada en métricas agregadas.

        - ALTA: status OK + abstención < 10% + 0 degradadas
        - MEDIA: status OK/WARNING con métricas moderadas
        - BAJA: status CRITICAL o métricas pobres
        """
        total = stats.get("total", 0)
        abstenidos = stats.get("abstenidos", 0)
        tasa = abstenidos / total if total > 0 else 1.0

        if status == IntegridadStatus.CRITICAL:
            return ConfianzaGlobal.BAJA

        if (
            status == IntegridadStatus.OK
            and tasa < 0.10
            and n_degradadas == 0
        ):
            return ConfianzaGlobal.ALTA

        if tasa < 0.30 and n_degradadas <= 2:
            return ConfianzaGlobal.MEDIA

        return ConfianzaGlobal.BAJA

    def _log_resultado(self, resultado: ResultadoRouter) -> None:
        """
        Registra resultado en TraceLogger.

        Hito 3 amplía esto con logging detallado por paso.
        """
        if not self.logger:
            return

        level = "info"
        if resultado.status == IntegridadStatus.WARNING:
            level = "warning"
        elif resultado.status == IntegridadStatus.CRITICAL:
            level = "error"

        context = {
            "status": resultado.status.value,
            "confianza_global": resultado.confianza_global.value,
            "campos_evaluados": resultado.campos_evaluados,
            "campos_abstenidos": resultado.campos_abstenidos,
            "tasa_abstencion": round(resultado.tasa_abstencion, 4),
            "observaciones_degradadas": len(resultado.observaciones_degradadas),
            "errores_aritmeticos": len(resultado.errores_aritmeticos),
            "debe_detener": resultado.debe_detener,
            "version_router": resultado.version_router,
        }

        log_method = getattr(self.logger, level, self.logger.info)
        log_method(
            f"ConfidenceRouter: {resultado.status.value}",
            agent_id=self.agente_id,
            operation="evaluar_expediente",
            context=context,
        )
