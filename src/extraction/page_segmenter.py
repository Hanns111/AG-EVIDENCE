# -*- coding: utf-8 -*-
"""
Segmentación multi-comprobante por layout OCR (sin IA).

Parte páginas en N regiones candidatas usando huecos en X (columnas) y en Y
(sub-bloques por columna). Filtra regiones con score_comprobante < 2.

VERSION: 1.0.0
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Tuple

from src.ocr.core import LineaOCR

VERSION_PAGE_SEGMENTER = "1.0.0"

# Umbrales relativos al tamaño de página en píxeles (bbox OCR, típ. mismo DPI que render)
_FRAC_GAP_X = 0.045
_MIN_GAP_X = 14.0
_FRAC_GAP_Y = 0.085
_MIN_GAP_Y = 22.0

_PATRON_SERIE_VALIDA = re.compile(
    r"\b(F|E|B|BV|FE|FC|FP|FW|FF)[A-Z0-9]{0,4}\s*[-]?\s*\d{3,9}\b",
    re.IGNORECASE,
)
_RE_RUC_MARCADOR = re.compile(
    r"(?:r[.\s]*u[.\s]*c|n[°o]?\s*ruc)\s*[:]?\s*(\d{11})|\b(\d{11})\b",
    re.IGNORECASE,
)
_RE_TOTAL_CONTEXT = re.compile(
    r"(importe\s+total|total\s+a\s+pagar|total\s+venta|valor\s+venta|"
    r"subtotal\s+ventas|op\.?\s*exoneradas|op\.?\s*gravadas)\b",
    re.IGNORECASE,
)
_RE_DECIMAL_IMPORTE = re.compile(r"\b\d+[.,]\d{2}\b")


@dataclass
class Region:
    id: str
    bbox: Tuple[float, float, float, float]
    lineas: List[LineaOCR]
    score_comprobante: int
    senales_activadas: List[str] = field(default_factory=list)


def _norm_texto(s: str) -> str:
    if not s:
        return ""
    t = unicodedata.normalize("NFKC", s).casefold()
    return re.sub(r"\s+", " ", t).strip()


def _xc(linea: LineaOCR) -> float:
    assert linea.bbox is not None
    return (linea.bbox[0] + linea.bbox[2]) * 0.5


def _union_bbox(lineas: List[LineaOCR]) -> Tuple[float, float, float, float]:
    x0 = min(l.bbox[0] for l in lineas if l.bbox)
    y0 = min(l.bbox[1] for l in lineas if l.bbox)
    x1 = max(l.bbox[2] for l in lineas if l.bbox)
    y1 = max(l.bbox[3] for l in lineas if l.bbox)
    return (x0, y0, x1, y1)


def _texto_union(lineas: List[LineaOCR]) -> str:
    ordered = sorted(
        lineas,
        key=lambda ln: (ln.bbox[1] if ln.bbox else 0.0, ln.bbox[0] if ln.bbox else 0.0),
    )
    return "\n".join(ln.texto for ln in ordered if (ln.texto or "").strip())


def _split_by_x_gaps(lineas: List[LineaOCR], page_w: float) -> List[List[LineaOCR]]:
    """Agrupa líneas en columnas por huecos grandes en X (sin k fijo)."""
    if len(lineas) <= 1:
        return [lineas]
    thr = max(_FRAC_GAP_X * page_w, _MIN_GAP_X)
    sorted_l = sorted(lineas, key=_xc)
    grupos: List[List[LineaOCR]] = []
    actual: List[LineaOCR] = [sorted_l[0]]
    for i in range(1, len(sorted_l)):
        cur = sorted_l[i]
        prev = actual[-1]
        assert prev.bbox and cur.bbox
        gap_borde = max(0.0, cur.bbox[0] - prev.bbox[2])
        gap_xc = _xc(cur) - _xc(prev)
        if gap_borde >= thr or gap_xc >= thr:
            grupos.append(actual)
            actual = [cur]
        else:
            actual.append(cur)
    grupos.append(actual)
    return grupos


def _split_by_y_gaps(lineas: List[LineaOCR], page_h: float) -> List[List[LineaOCR]]:
    """Subdivide una columna en bloques por huecos en Y."""
    if len(lineas) <= 1:
        return [lineas]
    thr = max(_FRAC_GAP_Y * page_h, _MIN_GAP_Y)
    sorted_l = sorted(lineas, key=lambda l: l.bbox[1] if l.bbox else 0.0)
    grupos: List[List[LineaOCR]] = []
    actual: List[LineaOCR] = [sorted_l[0]]
    for i in range(1, len(sorted_l)):
        cur_sorted = sorted_l[i]
        prev = actual[-1]
        assert prev.bbox and cur_sorted.bbox
        gap_borde = max(0.0, cur_sorted.bbox[1] - prev.bbox[3])
        gap_yc = (cur_sorted.bbox[1] + cur_sorted.bbox[3]) * 0.5 - (
            prev.bbox[1] + prev.bbox[3]
        ) * 0.5
        if gap_borde >= thr or gap_yc >= thr:
            grupos.append(actual)
            actual = [cur_sorted]
        else:
            actual.append(cur_sorted)
    grupos.append(actual)
    return grupos


def _multiples_importes(norm: str) -> bool:
    return len(_RE_DECIMAL_IMPORTE.findall(norm)) >= 3


def _score_region(lineas: List[LineaOCR]) -> Tuple[int, List[str]]:
    texto = _texto_union(lineas)
    norm = _norm_texto(texto)
    score = 0
    senales: List[str] = []

    if _PATRON_SERIE_VALIDA.search(norm):
        score += 2
        senales.append("comp.serie_valida(+2)")
    if _RE_TOTAL_CONTEXT.search(norm) or _RE_DECIMAL_IMPORTE.search(norm):
        score += 1
        senales.append("comp.total_o_importes(+1)")
    if _RE_RUC_MARCADOR.search(texto):
        score += 1
        senales.append("comp.ruc(+1)")
    if _multiples_importes(norm):
        score += 1
        senales.append("comp.multiples_importes(+1)")

    return score, senales


def segmentar_pagina(lineas_ocr: List[LineaOCR]) -> List[Region]:
    """
    Devuelve 0..N regiones candidatas (solo las que pasan score >= 2).

    Requiere bboxes en líneas; si no hay líneas con bbox, retorna [].
    """
    lineas = [ln for ln in lineas_ocr if ln.bbox and (ln.texto or "").strip()]
    if not lineas:
        return []

    page_x0 = min(ln.bbox[0] for ln in lineas)
    page_x1 = max(ln.bbox[2] for ln in lineas)
    page_y0 = min(ln.bbox[1] for ln in lineas)
    page_y1 = max(ln.bbox[3] for ln in lineas)
    page_w = max(1.0, page_x1 - page_x0)
    page_h = max(1.0, page_y1 - page_y0)

    columnas = _split_by_x_gaps(lineas, page_w)
    candidatos: List[List[LineaOCR]] = []
    for col in columnas:
        candidatos.extend(_split_by_y_gaps(col, page_h))

    regiones: List[Region] = []
    rid = 0
    for cand in candidatos:
        if not cand:
            continue
        sc, sen = _score_region(cand)
        if sc < 2:
            continue
        bbox = _union_bbox(cand)
        regiones.append(
            Region(
                id=f"r{rid}",
                bbox=bbox,
                lineas=list(cand),
                score_comprobante=sc,
                senales_activadas=list(sen),
            )
        )
        rid += 1

    return regiones
