# -*- coding: utf-8 -*-
"""
Módulo OCR — Funciones core reutilizables
==========================================
Extraído de tools/ocr_smoke_test.py para reutilización.
"""

from .core import (
    renderizar_pagina,
    ejecutar_ocr,
    preprocesar_rotacion,
    calcular_metricas_imagen,
    verificar_tesseract,
    ensure_lang_available,
    CV2_DISPONIBLE,
    TESSERACT_DISPONIBLE,
)

__all__ = [
    "renderizar_pagina",
    "ejecutar_ocr",
    "preprocesar_rotacion",
    "calcular_metricas_imagen",
    "verificar_tesseract",
    "ensure_lang_available",
    "CV2_DISPONIBLE",
    "TESSERACT_DISPONIBLE",
]
