# -*- coding: utf-8 -*-
"""
Capa C — Analista Local (IA opcional y confinada)
==================================================
Interfaz para IA local como analista de evidencia.

PRINCIPIO FUNDAMENTAL:
La IA local NUNCA escribe valores probatorios.
Solo produce notas, tags de riesgo y sugerencias de revision humana.

Si la IA intenta proponer valores probatorios (RUC, montos, serie/numero,
fechas, razones sociales), el sistema los bloquea automaticamente con
"NO_AUTORIZADO" y registra un WARNING en TraceLogger.

Uso:
    from src.extraction.local_analyst import analyze_evidence, AnalysisNotes

    notes = analyze_evidence(
        records=[campo1, campo2],
        flags=["RUC_CHECKSUM_FAIL"],
    )
    # notes.notas -> ["Posible error en RUC del gasto #3"]
    # notes.tags_riesgo -> ["RUC_SOSPECHOSO"]
    # notes.sugerencias_revision -> ["ruc_proveedor"]

Feature flag:
    LOCAL_ANALYST_CONFIG["enabled"] en config/settings.py
    Si False (default), analyze_evidence() retorna AnalysisNotes vacio.
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

# Asegurar path del proyecto
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


logger = logging.getLogger(__name__)


# ==============================================================================
# CAMPOS PROBATORIOS BLOQUEADOS
# ==============================================================================

CAMPOS_PROBATORIOS: Set[str] = {
    "ruc",
    "monto",
    "serie_numero",
    "fecha",
    "razon_social",
    "igv",
    "valor_venta",
    "base_imponible",
    "total",
    "subtotal",
    "numero_documento",
    "ruc_proveedor",
    "ruc_emisor",
    "monto_total",
    "monto_parcial",
    "fecha_emision",
    "fecha_pago",
    "serie",
    "numero",
}


# ==============================================================================
# DATACLASSES
# ==============================================================================


@dataclass
class AnalysisNotes:
    """
    Resultado del analisis de la IA local.

    Contiene SOLO informacion no-probatoria:
    - Notas textuales libres
    - Tags de riesgo categoricos
    - Sugerencias de campos a revisar manualmente

    NUNCA contiene valores de campos probatorios.
    """

    notas: List[str] = field(default_factory=list)
    tags_riesgo: List[str] = field(default_factory=list)
    sugerencias_revision: List[str] = field(default_factory=list)
    confianza_analisis: float = 0.0
    bloqueados: List[Dict[str, str]] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Indica si el analisis esta vacio (feature flag deshabilitado)."""
        return (
            not self.notas
            and not self.tags_riesgo
            and not self.sugerencias_revision
            and not self.bloqueados
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario para JSON."""
        return {
            "notas": self.notas,
            "tags_riesgo": self.tags_riesgo,
            "sugerencias_revision": self.sugerencias_revision,
            "confianza_analisis": self.confianza_analisis,
            "bloqueados": self.bloqueados,
        }


# ==============================================================================
# FUNCION GUARDIAN — BLOQUEO DE CAMPOS PROBATORIOS
# ==============================================================================


def _bloquear_valores_probatorios(
    output: Dict[str, Any],
    trace_logger: Any = None,
) -> Dict[str, Any]:
    """
    Filtra la salida de la IA local. Si detecta que intento escribir
    un campo probatorio, lo reemplaza con 'NO_AUTORIZADO' y registra.

    Args:
        output: Diccionario libre devuelto por la IA.
        trace_logger: TraceLogger opcional (duck typing).

    Returns:
        Diccionario limpio con campos probatorios bloqueados.
    """
    clean = {}
    bloqueados = []

    for key, value in output.items():
        key_lower = key.lower().strip()

        # Verificar si la clave coincide con un campo probatorio
        es_probatorio = False
        for campo in CAMPOS_PROBATORIOS:
            if campo in key_lower or key_lower in campo:
                es_probatorio = True
                break

        if es_probatorio:
            clean[key] = "NO_AUTORIZADO"
            bloqueados.append(
                {
                    "campo": key,
                    "valor_bloqueado": str(value)[:100],
                    "razon": "CAMPO_PROBATORIO_EN_CAPA_C",
                }
            )
            logger.warning(
                "IA local intento escribir campo probatorio: %s = %s -> NO_AUTORIZADO",
                key,
                str(value)[:50],
            )
            # Registrar en TraceLogger si disponible (duck typing)
            if trace_logger is not None:
                try:
                    trace_logger.warning(
                        f"IA local intento escribir campo probatorio: {key}",
                        agent_id="CAPA_C",
                        operation="bloqueo_probatorio",
                        context={
                            "campo": key,
                            "valor_bloqueado": str(value)[:100],
                        },
                    )
                except Exception:
                    pass  # TraceLogger nunca rompe el pipeline
        else:
            clean[key] = value

    return clean, bloqueados


# ==============================================================================
# FUNCION PRINCIPAL — INTERFAZ DE ANALISIS
# ==============================================================================


def analyze_evidence(
    records: List[Any],
    flags: Optional[List[str]] = None,
    raw_ocr_text: str = "",
    trace_logger: Any = None,
) -> AnalysisNotes:
    """
    Punto de entrada para la Capa C: analisis de IA local.

    Si LOCAL_ANALYST_ENABLED es False (default), retorna AnalysisNotes vacio.
    Si es True, envia los records y flags al motor de IA local y filtra
    la respuesta para bloquear cualquier campo probatorio.

    Args:
        records: Lista de CampoExtraido con datos extraidos.
        flags: Lista de flags de validacion (ej: ["RUC_CHECKSUM_FAIL"]).
        raw_ocr_text: Texto OCR crudo para contexto (opcional).
        trace_logger: TraceLogger opcional para auditoria.

    Returns:
        AnalysisNotes con notas, tags y sugerencias.
        Vacio si feature flag deshabilitado.
    """
    if flags is None:
        flags = []

    # Verificar feature flag
    try:
        from config.settings import LOCAL_ANALYST_CONFIG

        enabled = LOCAL_ANALYST_CONFIG.get("enabled", False)
    except (ImportError, AttributeError):
        enabled = False

    if not enabled:
        logger.debug("LOCAL_ANALYST_ENABLED=False, retornando analisis vacio")
        return AnalysisNotes()

    # Motor de IA no implementado aun (Fase 3, Tareas #22-26)
    # Por ahora retornamos vacio con log informativo
    logger.info(
        "analyze_evidence llamado con %d records, %d flags. Motor IA no implementado aun (Fase 3).",
        len(records),
        len(flags),
    )

    return AnalysisNotes(
        notas=["Motor de IA local no implementado aun (Fase 3, Tareas #22-26)"],
        confianza_analisis=0.0,
    )


def _process_ia_output(
    raw_output: Dict[str, Any],
    trace_logger: Any = None,
) -> AnalysisNotes:
    """
    Procesa la salida cruda de la IA local y la convierte en AnalysisNotes.

    Esta funcion se usara cuando el motor de IA este implementado (Fase 3).
    Aplica el bloqueo de campos probatorios antes de construir el resultado.

    Args:
        raw_output: Diccionario libre devuelto por la IA.
        trace_logger: TraceLogger opcional.

    Returns:
        AnalysisNotes limpio con campos probatorios bloqueados.
    """
    clean_output, bloqueados = _bloquear_valores_probatorios(raw_output, trace_logger)

    return AnalysisNotes(
        notas=clean_output.get("notas", []) if isinstance(clean_output.get("notas"), list) else [],
        tags_riesgo=clean_output.get("tags_riesgo", [])
        if isinstance(clean_output.get("tags_riesgo"), list)
        else [],
        sugerencias_revision=clean_output.get("sugerencias_revision", [])
        if isinstance(clean_output.get("sugerencias_revision"), list)
        else [],
        confianza_analisis=float(clean_output.get("confianza_analisis", 0.0)),
        bloqueados=bloqueados,
    )
