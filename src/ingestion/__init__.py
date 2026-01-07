# -*- coding: utf-8 -*-
"""
Módulo de Ingestión — Extracción de texto desde PDFs
=====================================================
Implementa gating automático: PDF nativo vs OCR vs fallback_manual.
"""

from .pdf_text_extractor import extract_text_with_gating

__all__ = ["extract_text_with_gating"]
