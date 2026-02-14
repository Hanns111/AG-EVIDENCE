# -*- coding: utf-8 -*-
"""
RULES — Reglas de Control Previo
================================
Modulos con candados de validacion basados en normativa administrativa.

Modulos disponibles:
- detraccion_spot: Validacion de SPOT segun RS 183-2004/SUNAT
- tdr_requirements: Extraccion y validacion de requisitos del TDR
- field_validators: Validadores deterministas por tipo de campo (Capa B)
"""

from .detraccion_spot import spot_aplica, SPOTValidator
from .tdr_requirements import extraer_requisitos_tdr, validar_requisitos_tdr, TDRRequirementExtractor
from .field_validators import (
    ValidationResult,
    ValidationFlag,
    validar_ruc,
    validar_serie_numero,
    validar_monto,
    validar_fecha,
    validar_consistencia_aritmetica,
)

__all__ = [
    'spot_aplica',
    'SPOTValidator',
    'extraer_requisitos_tdr',
    'validar_requisitos_tdr',
    'TDRRequirementExtractor',
    'ValidationResult',
    'ValidationFlag',
    'validar_ruc',
    'validar_serie_numero',
    'validar_monto',
    'validar_fecha',
    'validar_consistencia_aritmetica',
]


