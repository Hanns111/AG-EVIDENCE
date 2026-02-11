# -*- coding: utf-8 -*-
"""
Módulo de Extracción de Campos
===============================
Subsistema de extracción estructurada de datos de documentos.

Componentes:
  - abstencion: Política formal de abstención operativa (Tarea #12)
  - [Futuros]: ocr_extractor (Tarea #13), campos, regex_engine
"""

from .abstencion import (
    CampoExtraido,
    UmbralesAbstencion,
    ResultadoAbstencion,
    RazonAbstencion,
    AbstencionPolicy,
    FUENTE_ABSTENCION,
    FRASE_ABSTENCION_ESTANDAR,
)

__all__ = [
    "CampoExtraido",
    "UmbralesAbstencion",
    "ResultadoAbstencion",
    "RazonAbstencion",
    "AbstencionPolicy",
    "FUENTE_ABSTENCION",
    "FRASE_ABSTENCION_ESTANDAR",
]
