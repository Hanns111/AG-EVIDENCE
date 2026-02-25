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

from .detraccion_spot import SPOTValidator, spot_aplica
from .field_validators import (
    ValidationFlag,
    ValidationResult,
    validar_consistencia_aritmetica,
    validar_fecha,
    validar_monto,
    validar_ruc,
    validar_serie_numero,
)
from .tdr_requirements import (
    TDRRequirementExtractor,
    extraer_requisitos_tdr,
    validar_requisitos_tdr,
)

__all__ = [
    "spot_aplica",
    "SPOTValidator",
    "extraer_requisitos_tdr",
    "validar_requisitos_tdr",
    "TDRRequirementExtractor",
    "ValidationResult",
    "ValidationFlag",
    "validar_ruc",
    "validar_serie_numero",
    "validar_monto",
    "validar_fecha",
    "validar_consistencia_aritmetica",
]
