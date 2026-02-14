# -*- coding: utf-8 -*-
"""
Modulo de Extraccion de Campos
===============================
Subsistema de extraccion estructurada de datos de documentos.

Componentes:
  - abstencion: Politica formal de abstencion operativa (Tarea #12)
  - local_analyst: Interfaz para IA local como analista (Capa C)
  - [Futuros]: ocr_extractor, campos, regex_engine
"""

from .abstencion import (
    CampoExtraido,
    EvidenceStatus,
    UmbralesAbstencion,
    ResultadoAbstencion,
    RazonAbstencion,
    AbstencionPolicy,
    FUENTE_ABSTENCION,
    FRASE_ABSTENCION_ESTANDAR,
)

from .local_analyst import (
    AnalysisNotes,
    analyze_evidence,
    CAMPOS_PROBATORIOS,
)

__all__ = [
    "CampoExtraido",
    "EvidenceStatus",
    "UmbralesAbstencion",
    "ResultadoAbstencion",
    "RazonAbstencion",
    "AbstencionPolicy",
    "FUENTE_ABSTENCION",
    "FRASE_ABSTENCION_ESTANDAR",
    "AnalysisNotes",
    "analyze_evidence",
    "CAMPOS_PROBATORIOS",
]
