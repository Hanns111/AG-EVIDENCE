# -*- coding: utf-8 -*-
"""
Módulo de Agentes del Sistema de Control Previo
"""

from .agente_01_clasificador import AgenteClasificador
from .agente_02_ocr import AgenteOCR
from .agente_03_coherencia import AgenteCoherencia
from .agente_04_legal import AgenteLegal
from .agente_05_firmas import AgenteFirmas
from .agente_06_integridad import AgenteIntegridad
from .agente_07_penalidades import AgentePenalidades
from .agente_08_sunat import AgenteSUNAT
from .agente_09_decisor import AgenteDecisor

__all__ = [
    'AgenteClasificador',
    'AgenteOCR', 
    'AgenteCoherencia',
    'AgenteLegal',
    'AgenteFirmas',
    'AgenteIntegridad',
    'AgentePenalidades',
    'AgenteSUNAT',
    'AgenteDecisor'
]



