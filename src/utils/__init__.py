# -*- coding: utf-8 -*-
"""
Modulo de Utilidades — AG-EVIDENCE
===================================
Funciones transversales de seguridad, validacion y helpers.

Componentes:
  - security: Validacion de paths, limpieza de temporales, constantes
"""

from .security import (
    validar_ruta_segura,
    RutaInseguraError,
    DirectorioTemporalSeguro,
    TAMANIO_MAX_JSON_BYTES,
    EXTENSIONES_PDF_PERMITIDAS,
    EXTENSIONES_IMAGEN_PERMITIDAS,
    validar_json_tamano,
)

__all__ = [
    "validar_ruta_segura",
    "RutaInseguraError",
    "DirectorioTemporalSeguro",
    "TAMANIO_MAX_JSON_BYTES",
    "EXTENSIONES_PDF_PERMITIDAS",
    "EXTENSIONES_IMAGEN_PERMITIDAS",
    "validar_json_tamano",
]
