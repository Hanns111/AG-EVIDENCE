# -*- coding: utf-8 -*-
"""
Configuración de umbrales para gating de extracción PDF
=======================================================
Valores por defecto para decidir: direct_text vs ocr vs fallback_manual.
"""

from dataclasses import dataclass


@dataclass
class GatingThresholds:
    """Umbrales para decisión de gating."""
    
    # Mínimo de caracteres para considerar direct_text válido
    direct_text_min_chars: int = 200
    
    # Mínimo de palabras para considerar direct_text válido
    direct_text_min_words: int = 30
    
    # Mínima confianza OCR para aceptar resultado
    ocr_min_confidence: float = 0.60
    
    # Mínimo de palabras OCR para aceptar resultado
    ocr_min_words: int = 20
    
    # Páginas de muestra para OCR (si el PDF tiene muchas páginas)
    sample_pages: int = 1
    
    # DPI para renderizado OCR
    ocr_dpi: int = 200
    
    # Idioma por defecto para OCR
    ocr_lang: str = "spa"


# Instancia global con valores por defecto
DEFAULT_THRESHOLDS = GatingThresholds()
