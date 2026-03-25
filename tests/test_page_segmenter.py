# -*- coding: utf-8 -*-
"""
Tests — page_segmenter (layout OCR, golden DIRI2026, N regiones sin límite fijo).
"""

from __future__ import annotations

import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.extraction.page_classifier import TipoPagina, clasificar_pagina
from src.extraction.page_segmenter import VERSION_PAGE_SEGMENTER, segmentar_pagina
from src.ocr.core import LineaOCR


def _ln(
    texto: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> LineaOCR:
    return LineaOCR(
        texto=texto,
        bbox=(x0, y0, x1, y1),
        confianza=0.95,
        motor="test",
    )


def test_p21_dos_regiones_golden_layout() -> None:
    """Dos columnas (Braserito izq + Yululu der) — DIRI p21."""
    lineas = [
        _ln("FACTURA DE VENTA ELECTRONICA", 40, 20, 320, 40),
        _ln("F001-017009", 40, 45, 200, 65),
        _ln("RUC 20393685361", 40, 70, 280, 90),
        _ln("IMPORTE TOTAL 46.00", 40, 240, 280, 260),
        _ln("FACTURA ELECTRONICA", 540, 20, 880, 42),
        _ln("F001-00001640", 540, 48, 750, 68),
        _ln("RUC 10104259249", 540, 75, 780, 95),
        _ln("TOTAL 22.00", 540, 250, 720, 270),
    ]
    regs = segmentar_pagina(lineas)
    assert len(regs) == 2
    ids_scores = sorted((r.id, r.score_comprobante) for r in regs)
    assert all(s >= 2 for _, s in ids_scores)


def test_p34_dos_regiones_golden_layout() -> None:
    """Dos columnas (Tarapoto + Cremy) — DIRI p34."""
    lineas = [
        _ln("FACTURA FF15-0002179", 30, 18, 330, 38),
        _ln("RUC 20572278779", 30, 45, 300, 65),
        _ln("IMPORTE TOTAL 47.80", 30, 230, 300, 250),
        _ln("FACTURA F002-00000489", 520, 18, 890, 40),
        _ln("RUC 20612548804", 520, 50, 780, 70),
        _ln("TOTAL 30.00", 520, 235, 700, 255),
    ]
    regs = segmentar_pagina(lineas)
    assert len(regs) == 2


def test_p37_ticket_una_region() -> None:
    """Ticket térmico estrecho — DIRI p37."""
    lineas = [
        _ln("CREMY SAC", 120, 15, 350, 35),
        _ln("F002-00000493", 120, 50, 350, 72),
        _ln("RUC 20612548804", 120, 80, 380, 100),
        _ln("Desayuno Cremy 25.00", 120, 130, 380, 150),
        _ln("IMPORTE TOTAL 25.00", 120, 280, 400, 300),
    ]
    regs = segmentar_pagina(lineas)
    assert len(regs) == 1
    assert regs[0].score_comprobante >= 2


def test_sunat_texto_clasificador_cero_regiones_segmenter() -> None:
    """Página validez SUNAT: el clasificador es SUNAT; líneas sin patrón fiscal fuerte → 0 regiones."""
    texto_sunat = """SUNAT Consulta de comprobante
Resultado de la consulta
Estado: VÁLIDO
"""
    assert clasificar_pagina(texto_sunat).tipo is TipoPagina.SUNAT_VALIDACION
    lineas = [
        _ln("SUNAT", 100, 20, 200, 40),
        _ln("Consulta de comprobante", 100, 50, 500, 72),
        _ln("Resultado de la consulta", 100, 90, 520, 112),
        _ln("Estado: VALIDO", 100, 130, 350, 150),
    ]
    regs = segmentar_pagina(lineas)
    assert regs == []


def test_sintetico_tres_columnas_tres_comprobantes() -> None:
    """N>=3 sin hardcode: tres franjas X separadas."""
    lineas = []
    cols = [
        (20, "F001-11111", "20111111111", 0),
        (420, "E001-22222", "20222222222", 1),
        (820, "FW01-33333", "20333333333", 2),
    ]
    for x0, serie, ruc, idx in cols:
        lineas.append(_ln("FACTURA", x0, 10, x0 + 200, 30))
        lineas.append(_ln(serie, x0, 40, x0 + 220, 60))
        lineas.append(_ln(f"RUC {ruc}", x0, 70, x0 + 280, 90))
        lineas.append(_ln("IMPORTE TOTAL 10.00", x0, 200, x0 + 300, 220))
    regs = segmentar_pagina(lineas)
    assert len(regs) >= 3
    assert all(r.score_comprobante >= 2 for r in regs)


def test_sin_bbox_retorna_vacio() -> None:
    ln = LineaOCR(texto="F001-99999", bbox=None, confianza=0.9, motor="t")
    assert segmentar_pagina([ln]) == []


def test_version_segmenter() -> None:
    assert VERSION_PAGE_SEGMENTER == "1.0.0"
