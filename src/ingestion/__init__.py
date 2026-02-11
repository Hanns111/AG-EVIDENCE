# -*- coding: utf-8 -*-
"""
Módulo de Ingestión — Extracción y Custodia de PDFs
=====================================================
- Gating automático: PDF nativo vs OCR vs fallback_manual
- Cadena de custodia: copia inmutable + hash SHA-256 + registro JSONL
"""

from .pdf_text_extractor import extract_text_with_gating, get_texto_extraido
from .custody_chain import CustodyChain, CustodyRecord, VerificationResult, compute_sha256

__all__ = [
    "extract_text_with_gating",
    "get_texto_extraido",
    "CustodyChain",
    "CustodyRecord",
    "VerificationResult",
    "compute_sha256",
]
