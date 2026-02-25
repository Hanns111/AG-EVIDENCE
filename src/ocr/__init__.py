# -*- coding: utf-8 -*-
"""
Modulo OCR — Motor OCR con PaddleOCR PP-OCRv5 + Tesseract Fallback
====================================================================
Funciones core reutilizables para OCR en AG-EVIDENCE v2.0.

Motor primario: PaddleOCR PP-OCRv5
Motor fallback: Tesseract via pytesseract
"""

from .core import (
    CV2_DISPONIBLE,
    PADDLEOCR_DISPONIBLE,
    TESSERACT_DISPONIBLE,
    LineaOCR,
    calcular_metricas_imagen,
    ejecutar_ocr,
    ensure_lang_available,
    preprocesar_rotacion,
    renderizar_pagina,
    verificar_ocr,
    verificar_paddleocr,
    verificar_tesseract,
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
    "LineaOCR",
    "CV2_DISPONIBLE",
    "TESSERACT_DISPONIBLE",
    "PADDLEOCR_DISPONIBLE",
]
