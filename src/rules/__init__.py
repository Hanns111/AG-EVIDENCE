# -*- coding: utf-8 -*-
"""
RULES — Reglas de Control Previo
================================
Módulos con candados de validación basados en normativa administrativa.

Módulos disponibles:
- detraccion_spot: Validación de SPOT según RS 183-2004/SUNAT
- tdr_requirements: Extracción y validación de requisitos del TDR
"""

from .detraccion_spot import spot_aplica, SPOTValidator
from .tdr_requirements import extraer_requisitos_tdr, validar_requisitos_tdr, TDRRequirementExtractor

__all__ = [
    'spot_aplica',
    'SPOTValidator',
    'extraer_requisitos_tdr',
    'validar_requisitos_tdr',
    'TDRRequirementExtractor',
]


