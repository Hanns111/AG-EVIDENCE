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

VERSION_ROUTER = "2.0.0"
"""Versión del módulo confidence_router. Hito 2: IntegrityCheckpoint + Diagnóstico."""

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
# REPORTE DE ENFORCEMENT DETALLADO (Hito 2)
# ==============================================================================

@dataclass
class DetalleEnforcement:
    """
    Detalle de enforcement para UNA observación individual.

    Registra exactamente qué le faltó a una observación para cumplir
    el estándar probatorio (Art. 4-5 Gobernanza), permitiendo al
    usuario saber qué completar.
    """
    agente: str = ""
    nivel_original: str = ""
    nivel_post: str = ""
    fue_degradada: bool = False
    descripcion: str = ""
    campos_faltantes: List[str] = field(default_factory=list)
    """Lista de campos que faltan: 'archivo', 'pagina', 'snippet', etc."""
    requiere_revision_humana: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario."""
        return {
            "agente": self.agente,
            "nivel_original": self.nivel_original,
            "nivel_post": self.nivel_post,
            "fue_degradada": self.fue_degradada,
            "descripcion": self.descripcion,
            "campos_faltantes": self.campos_faltantes,
            "requiere_revision_humana": self.requiere_revision_humana,
        }


@dataclass
class ReporteEnforcement:
    """
    Reporte completo del enforcement probatorio (Hito 2).

    Agrega DetalleEnforcement por cada observación procesada,
    más estadísticas globales. Diseñado para alimentar la hoja
    DIAGNOSTICO del Excel (Tarea #20).
    """
    detalles: List[DetalleEnforcement] = field(default_factory=list)
    total_procesadas: int = 0
    total_validas: int = 0
    total_degradadas: int = 0
    tasa_degradacion: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario."""
        return {
            "total_procesadas": self.total_procesadas,
            "total_validas": self.total_validas,
            "total_degradadas": self.total_degradadas,
            "tasa_degradacion": round(self.tasa_degradacion, 4),
            "detalles": [d.to_dict() for d in self.detalles],
        }

    def resumen_texto(self) -> str:
        """Resumen legible para logging."""
        lineas = [
            f"Enforcement: {self.total_procesadas} procesadas, "
            f"{self.total_validas} válidas, "
            f"{self.total_degradadas} degradadas "
            f"({self.tasa_degradacion:.0%})",
        ]
        for d in self.detalles:
            if d.fue_degradada:
                lineas.append(
                    f"  ⚠ [{d.agente}] {d.nivel_original}→{d.nivel_post}: "
                    f"{d.descripcion[:60]}... "
                    f"Falta: {', '.join(d.campos_faltantes)}"
                )
        return "\n".join(lineas)


# ==============================================================================
# DIAGNOSTICO DEL EXPEDIENTE (Hito 2)
# ==============================================================================

@dataclass
class SeccionDiagnostico:
    """
    Una sección del diagnóstico con nombre, status y detalle.

    Cada sección corresponde a un paso del pipeline de evaluación
    (campos, enforcement, completitud, unicidad, aritmética).
    """
    nombre: str = ""
    status: str = "OK"  # OK, WARNING, CRITICAL, SKIP
    mensaje: str = ""
    detalles: List[str] = field(default_factory=list)
    metricas: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario."""
        return {
            "nombre": self.nombre,
            "status": self.status,
            "mensaje": self.mensaje,
            "detalles": self.detalles,
            "metricas": self.metricas,
        }


@dataclass
class DiagnosticoExpediente:
    """
    Diagnóstico completo del expediente para la hoja DIAGNOSTICO del Excel.

    Diseñado para Tarea #20. Cada sección corresponde a un paso
    del ConfidenceRouter. Serializable a JSON y a filas de Excel.

    Secciones estándar:
      1. evaluacion_campos — Resultado de AbstencionPolicy
      2. enforcement — Resultado del estándar probatorio
      3. completitud — Campos obligatorios faltantes
      4. unicidad — Comprobantes duplicados
      5. aritmetica — Errores de validación aritmética (Grupo J)
      6. decision — Status final y confianza global
    """
    sinad: str = ""
    timestamp: str = ""
    version_router: str = VERSION_ROUTER
    secciones: List[SeccionDiagnostico] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario."""
        return {
            "sinad": self.sinad,
            "timestamp": self.timestamp,
            "version_router": self.version_router,
            "secciones": [s.to_dict() for s in self.secciones],
        }

    def to_rows(self) -> List[Dict[str, str]]:
        """
        Convierte a filas planas para hoja Excel DIAGNOSTICO.

        Cada fila tiene: seccion, status, mensaje, detalle.
        Útil para openpyxl o pandas.
        """
        rows: List[Dict[str, str]] = []
        for s in self.secciones:
            if s.detalles:
                for detalle in s.detalles:
                    rows.append({
                        "seccion": s.nombre,
                        "status": s.status,
                        "mensaje": s.mensaje,
                        "detalle": detalle,
                    })
            else:
                rows.append({
                    "seccion": s.nombre,
                    "status": s.status,
                    "mensaje": s.mensaje,
                    "detalle": "",
                })
        return rows

    def resumen_texto(self) -> str:
        """Resumen legible para logging y consola."""
        lineas = [
            f"=== Diagnóstico {self.sinad} (v{self.version_router}) ===",
        ]
        for s in self.secciones:
            icon = {"OK": "✅", "WARNING": "⚠️", "CRITICAL": "🔴", "SKIP": "⏭️"}.get(
                s.status, "❓"
            )
            lineas.append(f"  {icon} {s.nombre}: {s.status} — {s.mensaje}")
            for d in s.detalles[:3]:
                lineas.append(f"      • {d}")
            if len(s.detalles) > 3:
                lineas.append(f"      ... +{len(s.detalles) - 3} más")
        return "\n".join(lineas)


# ==============================================================================
# INTEGRITY CHECKPOINT (Hito 2)
# ==============================================================================

class IntegrityCheckpoint:
    """
    Punto de control de integridad para el pipeline de extracción.

    Wrapper decisor sobre ConfidenceRouter que proporciona una interfaz
    limpia para el orquestador LangGraph (preparado para Tarea #21).

    Responsabilidades:
      - Ejecutar evaluación completa vía ConfidenceRouter
      - Generar ReporteEnforcement detallado
      - Generar DiagnosticoExpediente para Excel
      - Decidir acción: CONTINUAR, CONTINUAR_CON_ALERTAS, DETENER
      - NO ejecuta la detención (Art. 2.2) — solo emite señal

    Interfaz del orquestador:
        checkpoint = IntegrityCheckpoint()
        decision = checkpoint.evaluar(expediente, observaciones)

        if decision.accion == "DETENER":
            # Orquestador implementa la detención
            ...
        elif decision.accion == "CONTINUAR_CON_ALERTAS":
            # Orquestador registra alertas y continúa
            ...

    Gobernanza:
      - Art. 2: No modifica flujo AG01→AG09
      - Art. 2.2/2.3: DETENER es señal, no acción directa
      - Art. 4-5: EvidenceEnforcer integrado
      - ADR-005: Nodo preparado para LangGraph, no monolito
    """

    # Acciones posibles del checkpoint
    ACCION_CONTINUAR = "CONTINUAR"
    ACCION_CONTINUAR_CON_ALERTAS = "CONTINUAR_CON_ALERTAS"
    ACCION_DETENER = "DETENER"

    def __init__(
        self,
        umbrales: Optional[UmbralesRouter] = None,
        umbrales_abstencion: Optional[UmbralesAbstencion] = None,
        trace_logger: Optional[Any] = None,
        agente_id: str = "INTEGRITY_CHECKPOINT",
    ):
        """
        Inicializa el IntegrityCheckpoint.

        Args:
            umbrales: Umbrales del router para escalación.
            umbrales_abstencion: Umbrales de abstención por tipo de campo.
            trace_logger: Instancia de TraceLogger (opcional).
            agente_id: ID de agente para logging.
        """
        self.router = ConfidenceRouter(
            umbrales=umbrales,
            umbrales_abstencion=umbrales_abstencion,
            trace_logger=trace_logger,
            agente_id=agente_id,
        )
        self.logger = trace_logger
        self.agente_id = agente_id

    def evaluar(
        self,
        expediente: ExpedienteJSON,
        observaciones: Optional[List[Observacion]] = None,
    ) -> "DecisionCheckpoint":
        """
        Evalúa un expediente y emite decisión para el orquestador.

        Este es el método principal. Ejecuta:
          1. ConfidenceRouter.evaluar_expediente()
          2. Genera ReporteEnforcement detallado
          3. Genera DiagnosticoExpediente completo
          4. Determina acción (CONTINUAR / ALERTAS / DETENER)

        Args:
            expediente: ExpedienteJSON ya poblado.
            observaciones: Lista de observaciones previas (opcional).

        Returns:
            DecisionCheckpoint con todo el contexto decisorio.
        """
        obs = observaciones or []
        timestamp = datetime.now(timezone.utc).isoformat()

        # --- Paso 1: Evaluación completa ---
        resultado = self.router.evaluar_expediente(expediente, obs)

        # --- Paso 2: Reporte de enforcement detallado ---
        reporte = self._generar_reporte_enforcement(obs, resultado)

        # --- Paso 3: Diagnóstico para Excel ---
        diagnostico = self._generar_diagnostico(expediente, resultado, reporte)

        # --- Paso 4: Determinar acción ---
        accion = self._determinar_accion(resultado)

        # --- Paso 5: Log decisión ---
        self._log_decision(accion, resultado)

        return DecisionCheckpoint(
            accion=accion,
            resultado=resultado,
            reporte_enforcement=reporte,
            diagnostico=diagnostico,
            timestamp=timestamp,
        )

    def _generar_reporte_enforcement(
        self,
        observaciones_originales: List[Observacion],
        resultado: "ResultadoRouter",
    ) -> ReporteEnforcement:
        """
        Genera ReporteEnforcement con detalle por observación.

        Analiza cada observación original para determinar exactamente
        qué le faltó para cumplir el estándar probatorio.
        """
        detalles: List[DetalleEnforcement] = []

        # Procesar degradadas (las que fallaron enforcement)
        for obs in resultado.observaciones_degradadas:
            campos_faltantes = self._detectar_campos_faltantes(obs)
            detalles.append(DetalleEnforcement(
                agente=obs.agente,
                nivel_original="CRITICA/MAYOR",  # Fue degradada desde ahí
                nivel_post=obs.nivel.value,
                fue_degradada=True,
                descripcion=obs.descripcion,
                campos_faltantes=campos_faltantes,
                requiere_revision_humana=obs.requiere_revision_humana,
            ))

        # Procesar válidas (las que pasaron enforcement)
        for obs in resultado.observaciones_validas:
            detalles.append(DetalleEnforcement(
                agente=obs.agente,
                nivel_original=obs.nivel.value,
                nivel_post=obs.nivel.value,
                fue_degradada=False,
                descripcion=obs.descripcion,
                campos_faltantes=[],
                requiere_revision_humana=obs.requiere_revision_humana,
            ))

        total = len(detalles)
        n_degradadas = sum(1 for d in detalles if d.fue_degradada)

        return ReporteEnforcement(
            detalles=detalles,
            total_procesadas=total,
            total_validas=total - n_degradadas,
            total_degradadas=n_degradadas,
            tasa_degradacion=n_degradadas / total if total > 0 else 0.0,
        )

    @staticmethod
    def _detectar_campos_faltantes(obs: Observacion) -> List[str]:
        """
        Detecta qué campos probatorios le faltan a una observación.

        Según Art. 4, una observación CRITICA/MAYOR requiere:
          - archivo: Nombre del archivo fuente
          - pagina: Número de página (>0)
          - valor_detectado: Valor encontrado
          - snippet: Texto exacto extraído
          - regla_aplicada: ID de la regla

        Returns:
            Lista de nombres de campos faltantes.
        """
        faltantes: List[str] = []

        if not obs.evidencias:
            faltantes.append("evidencias (ninguna)")
            return faltantes

        # Verificar cada evidencia
        for i, ev in enumerate(obs.evidencias):
            prefix = f"evidencia[{i}]." if len(obs.evidencias) > 1 else ""
            if not ev.archivo:
                faltantes.append(f"{prefix}archivo")
            if ev.pagina <= 0:
                faltantes.append(f"{prefix}pagina")
            if not ev.valor_detectado:
                faltantes.append(f"{prefix}valor_detectado")
            if not ev.snippet:
                faltantes.append(f"{prefix}snippet")
            if not ev.regla_aplicada:
                faltantes.append(f"{prefix}regla_aplicada")

        return faltantes

    def _generar_diagnostico(
        self,
        expediente: ExpedienteJSON,
        resultado: "ResultadoRouter",
        reporte: ReporteEnforcement,
    ) -> DiagnosticoExpediente:
        """
        Genera DiagnosticoExpediente completo para hoja Excel.

        Crea una sección por cada paso de evaluación del router.
        """
        secciones: List[SeccionDiagnostico] = []

        # Sección 1: Evaluación de campos
        secciones.append(self._seccion_campos(resultado))

        # Sección 2: Enforcement probatorio
        secciones.append(self._seccion_enforcement(resultado, reporte))

        # Sección 3: Completitud
        secciones.append(self._seccion_completitud(resultado))

        # Sección 4: Unicidad
        secciones.append(self._seccion_unicidad(resultado))

        # Sección 5: Aritmética
        secciones.append(self._seccion_aritmetica(resultado))

        # Sección 6: Decisión final
        secciones.append(self._seccion_decision(resultado))

        return DiagnosticoExpediente(
            sinad=expediente.sinad,
            timestamp=resultado.timestamp,
            version_router=resultado.version_router,
            secciones=secciones,
        )

    @staticmethod
    def _seccion_campos(resultado: "ResultadoRouter") -> SeccionDiagnostico:
        """Sección 1: Evaluación de campos extraídos."""
        if resultado.campos_evaluados == 0:
            return SeccionDiagnostico(
                nombre="evaluacion_campos",
                status="SKIP",
                mensaje="Sin campos para evaluar",
                metricas={"total": 0},
            )

        status = "OK"
        if resultado.tasa_abstencion >= 0.50:
            status = "CRITICAL"
        elif resultado.tasa_abstencion >= 0.30:
            status = "WARNING"

        return SeccionDiagnostico(
            nombre="evaluacion_campos",
            status=status,
            mensaje=(
                f"{resultado.campos_legibles}/{resultado.campos_evaluados} "
                f"campos legibles ({1 - resultado.tasa_abstencion:.0%})"
            ),
            detalles=[
                f"Legibles: {resultado.campos_legibles}",
                f"Incompletos: {resultado.campos_incompletos}",
                f"Abstenidos: {resultado.campos_abstenidos}",
                f"Tasa abstención: {resultado.tasa_abstencion:.1%}",
            ],
            metricas={
                "total": resultado.campos_evaluados,
                "legibles": resultado.campos_legibles,
                "incompletos": resultado.campos_incompletos,
                "abstenidos": resultado.campos_abstenidos,
                "tasa_abstencion": round(resultado.tasa_abstencion, 4),
            },
        )

    @staticmethod
    def _seccion_enforcement(
        resultado: "ResultadoRouter",
        reporte: ReporteEnforcement,
    ) -> SeccionDiagnostico:
        """Sección 2: Enforcement del estándar probatorio."""
        if reporte.total_procesadas == 0:
            return SeccionDiagnostico(
                nombre="enforcement",
                status="SKIP",
                mensaje="Sin observaciones para evaluar",
                metricas={"total": 0},
            )

        status = "OK"
        if reporte.total_degradadas > 5:
            status = "CRITICAL"
        elif reporte.total_degradadas > 2:
            status = "WARNING"

        detalles: List[str] = []
        for d in reporte.detalles:
            if d.fue_degradada:
                detalles.append(
                    f"[{d.agente}] {d.descripcion[:80]} → "
                    f"Falta: {', '.join(d.campos_faltantes)}"
                )

        return SeccionDiagnostico(
            nombre="enforcement",
            status=status,
            mensaje=(
                f"{reporte.total_degradadas}/{reporte.total_procesadas} "
                f"observaciones degradadas"
            ),
            detalles=detalles,
            metricas=reporte.to_dict(),
        )

    @staticmethod
    def _seccion_completitud(resultado: "ResultadoRouter") -> SeccionDiagnostico:
        """Sección 3: Completitud estructural."""
        n = len(resultado.problemas_completitud)
        if n == 0:
            return SeccionDiagnostico(
                nombre="completitud",
                status="OK",
                mensaje="Estructura completa",
            )

        status = "CRITICAL" if n >= 3 else "WARNING"
        return SeccionDiagnostico(
            nombre="completitud",
            status=status,
            mensaje=f"{n} problemas de completitud",
            detalles=resultado.problemas_completitud,
        )

    @staticmethod
    def _seccion_unicidad(resultado: "ResultadoRouter") -> SeccionDiagnostico:
        """Sección 4: Unicidad de comprobantes."""
        n = len(resultado.comprobantes_duplicados)
        if n == 0:
            return SeccionDiagnostico(
                nombre="unicidad",
                status="OK",
                mensaje="Sin comprobantes duplicados",
            )

        return SeccionDiagnostico(
            nombre="unicidad",
            status="WARNING",  # Duplicados → WARNING (nunca CRITICAL)
            mensaje=f"{n} posibles duplicados (revisión humana)",
            detalles=resultado.comprobantes_duplicados,
        )

    @staticmethod
    def _seccion_aritmetica(resultado: "ResultadoRouter") -> SeccionDiagnostico:
        """Sección 5: Validaciones aritméticas (Grupo J)."""
        n = len(resultado.errores_aritmeticos)
        if n == 0:
            return SeccionDiagnostico(
                nombre="aritmetica",
                status="OK",
                mensaje="Validaciones aritméticas correctas",
            )

        status = "CRITICAL" if n > 5 else "WARNING" if n > 2 else "OK"
        return SeccionDiagnostico(
            nombre="aritmetica",
            status=status,
            mensaje=f"{n} errores aritméticos",
            detalles=resultado.errores_aritmeticos,
        )

    @staticmethod
    def _seccion_decision(resultado: "ResultadoRouter") -> SeccionDiagnostico:
        """Sección 6: Decisión final del checkpoint."""
        return SeccionDiagnostico(
            nombre="decision",
            status=resultado.status.value,
            mensaje=(
                f"Confianza: {resultado.confianza_global.value} | "
                f"Debe detener: {'SÍ' if resultado.debe_detener else 'NO'}"
            ),
            detalles=resultado.alertas,
            metricas={
                "status": resultado.status.value,
                "confianza_global": resultado.confianza_global.value,
                "debe_detener": resultado.debe_detener,
                "razon_detencion": resultado.razon_detencion,
            },
        )

    def _determinar_accion(self, resultado: "ResultadoRouter") -> str:
        """
        Determina la acción a tomar basada en el resultado.

        - DETENER: status CRITICAL (señal al orquestador, Art. 2.2)
        - CONTINUAR_CON_ALERTAS: status WARNING (pipeline continúa)
        - CONTINUAR: status OK (sin problemas)
        """
        if resultado.debe_detener:
            return self.ACCION_DETENER
        if resultado.status == IntegridadStatus.WARNING:
            return self.ACCION_CONTINUAR_CON_ALERTAS
        return self.ACCION_CONTINUAR

    def _log_decision(self, accion: str, resultado: "ResultadoRouter") -> None:
        """Registra la decisión del checkpoint en TraceLogger."""
        if not self.logger:
            return

        level = "info"
        if accion == self.ACCION_DETENER:
            level = "error"
        elif accion == self.ACCION_CONTINUAR_CON_ALERTAS:
            level = "warning"

        context = {
            "accion": accion,
            "status": resultado.status.value,
            "confianza_global": resultado.confianza_global.value,
            "debe_detener": resultado.debe_detener,
            "alertas": len(resultado.alertas),
        }

        log_method = getattr(self.logger, level, self.logger.info)
        log_method(
            f"IntegrityCheckpoint: {accion}",
            agent_id=self.agente_id,
            operation="evaluar",
            context=context,
        )


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
# DECISIÓN DEL CHECKPOINT (Hito 2)
# ==============================================================================

@dataclass
class DecisionCheckpoint:
    """
    Resultado completo del IntegrityCheckpoint.

    Contiene la decisión (acción), el resultado del router,
    el reporte de enforcement detallado y el diagnóstico
    para la hoja Excel.

    El orquestador LangGraph consume esta clase para decidir
    si continuar o detener el pipeline.
    """
    accion: str = "CONTINUAR"
    resultado: Optional[ResultadoRouter] = None
    reporte_enforcement: Optional[ReporteEnforcement] = None
    diagnostico: Optional[DiagnosticoExpediente] = None
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serializa completo a diccionario."""
        return {
            "accion": self.accion,
            "resultado": self.resultado.to_dict() if self.resultado else None,
            "reporte_enforcement": (
                self.reporte_enforcement.to_dict()
                if self.reporte_enforcement else None
            ),
            "diagnostico": (
                self.diagnostico.to_dict()
                if self.diagnostico else None
            ),
            "timestamp": self.timestamp,
        }

    def resumen_texto(self) -> str:
        """Resumen legible para logging y consola."""
        lineas = [f"=== IntegrityCheckpoint: {self.accion} ==="]
        if self.resultado:
            lineas.append(self.resultado.resumen_texto())
        if self.diagnostico:
            lineas.append(self.diagnostico.resumen_texto())
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
