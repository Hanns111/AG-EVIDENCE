# -*- coding: utf-8 -*-
"""
AG-EVIDENCE — Sistema de Análisis Probatorio de Expedientes
===========================================================
Ministerio de Educación del Perú

Arquitectura de 9 agentes especializados para revisión
de expedientes administrativos del sector público.
"""

__version__ = "1.0.0"
__author__ = "AG-EVIDENCE MINEDU"

# Imports opcionales para evitar errores en pytest
try:
    from .orquestador import OrquestadorControlPrevio, ejecutar_control_previo
except ImportError:
    pass



