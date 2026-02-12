# -*- coding: utf-8 -*-
"""
Modulo OCR — Motor OCR con PaddleOCR PP-OCRv5 + Tesseract Fallback
====================================================================
Funciones core reutilizables para OCR en AG-EVIDENCE v2.0.

Motor primario: PaddleOCR PP-OCRv5
Motor fallback: Tesseract via pytesseract
"""

from .core import (
    renderizar_pagina,
    ejecutar_ocr,
    preprocesar_rotacion,
    calcular_metricas_imagen,
    verificar_tesseract,
    verificar_paddleocr,
    verificar_ocr,
    ensure_lang_available,
    CV2_DISPONIBLE,
    TESSERACT_DISPONIBLE,
    PADDLEOCR_DISPONIBLE,
)

__all__ = [
    "renderizar_pagina",
    "ejecutar_ocr",
    "preprocesar_rotacion",
    "calcular_metricas_imagen",
    "verificar_tesseract",
    "verificar_paddleocr",
    "verificar_ocr",
    "ensure_lang_available",
    "CV2_DISPONIBLE",
    "TESSERACT_DISPONIBLE",
    "PADDLEOCR_DISPONIBLE",
]
