# -*- coding: utf-8 -*-
"""
Clasificación auditable de páginas (sin IA) — scoring determinístico.

Corrige falsos positivos del golden DIRI2026: páginas de validez/consulta SUNAT
no se promueven a extracción de comprobantes.

Fase 5: umbrales score_sunat >= 3 → SUNAT_VALIDACION; score_comprobante >= 2
(sin duda SUNAT) → COMPROBANTE; en caso contrario → OTROS (abstención > invención).

VERSION: 2.0.0 — motor de puntuación auditable
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple

VERSION_PAGE_CLASSIFIER = "2.0.0"


class TipoPagina(str, Enum):
    COMPROBANTE = "COMPROBANTE"
    SUNAT_VALIDACION = "SUNAT_VALIDACION"
    OTROS = "OTROS"


@dataclass(frozen=True)
class ClasificacionPagina:
    tipo: TipoPagina
    pasa_a_extraccion: bool
    score_sunat: int
    score_comprobante: int
    senales_activadas: List[str] = field(default_factory=list)


# --- Normalización -----------------------------------------------------------


def normalizar_para_clasificar(texto: str) -> str:
    if not texto:
        return ""
    s = unicodedata.normalize("NFKC", texto).casefold()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _sin_tildes(s: str) -> str:
    nk = unicodedata.normalize("NFD", s)
    return "".join(c for c in nk if unicodedata.category(c) != "Mn")


def _norm_clave(texto: str) -> str:
    return _sin_tildes(normalizar_para_clasificar(texto))


def _contar_lineas_significativas(texto: str) -> int:
    if not texto.strip():
        return 0
    return sum(1 for ln in texto.splitlines() if ln.strip())


# --- Patrones auxiliares (solo para scoring; no alteran escribano_fiel) -------

_RE_ESTADO_VALIDO = re.compile(
    r"estado\s*[:.\-]?\s*(valido|válido)\b",
    re.IGNORECASE,
)

# Serie SUNAT típica (perfil amplio: F001-, E001-, FW01-, FF15-, etc.)
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


def _tiene_estructura_items_totales(norm: str) -> bool:
    """Indicios de detalle fiscal/tablas típicas de comprobante (no exclusivo)."""
    hits = 0
    if "cant" in norm and ("unid" in norm or "und" in norm):
        hits += 1
    if "descripcion" in norm or "descripc" in norm:
        hits += 1
    if (
        "op. gravada" in norm
        or "op gravada" in norm
        or "op.exonerada" in norm
        or "op exonerada" in norm
        or "op inafecta" in norm
    ):
        hits += 1
    if "importe total" in norm or "subtotal" in norm:
        hits += 1
    if "valor venta" in norm:
        hits += 1
    return hits >= 2


def _monto_cerca_de_total(norm: str) -> bool:
    return bool(
        re.search(
            r"(importe\s+total|total\s+a\s+pagar)\s*[:]?\s*s/?\s*\d+[.,]\d{2}\b",
            norm,
            re.IGNORECASE,
        )
        or re.search(r"\btotal\s+[:]?\s*\d+[.,]\d{2}\b", norm, re.IGNORECASE)
    )


def _es_ticket_termico(norm: str, n_lineas: int) -> bool:
    if n_lineas > 28 or n_lineas < 3:
        return False
    if _PATRON_SERIE_VALIDA.search(norm) is None:
        return False
    if not (_RE_TOTAL_CONTEXT.search(norm) or _monto_cerca_de_total(norm)):
        return False
    return True


def _score_sunat(norm: str) -> Tuple[int, List[str]]:
    score = 0
    senales: List[str] = []

    if "consulta de comprobante" in norm:
        score += 2
        senales.append("sunat.consulta_de_comprobante(+2)")
    elif "consulta" in norm and "comprobante" in norm:
        score += 1
        senales.append("sunat.consulta_y_comprobante_separados(+1)")

    if "resultado de la consulta" in norm:
        score += 2
        senales.append("sunat.resultado_de_la_consulta(+2)")

    if "sunat" in norm and _RE_ESTADO_VALIDO.search(norm):
        score += 2
        senales.append("sunat.sunat_y_estado_valido(+2)")

    if not _tiene_estructura_items_totales(norm):
        score += 1
        senales.append("sunat.ausencia_estructura_comprobante(+1)")

    # Refuerzo portal: "SUNAT" + frase fuerte de consulta suele bastar para ≥3 aunque falte ausencia.
    if "sunat" in norm and (
        "resultado de la consulta" in norm or "consulta de comprobante" in norm
    ):
        score += 1
        senales.append("sunat.presencia_portal(+1)")

    return score, senales


def _score_comprobante(texto: str, norm: str) -> Tuple[int, List[str]]:
    score = 0
    senales: List[str] = []
    n_lineas = _contar_lineas_significativas(texto)

    if _PATRON_SERIE_VALIDA.search(norm):
        score += 2
        senales.append("comprobante.serie_valida(+2)")

    tiene_ruc = _RE_RUC_MARCADOR.search(texto) is not None
    tiene_total = _RE_TOTAL_CONTEXT.search(norm) is not None or _monto_cerca_de_total(norm)
    if tiene_ruc and tiene_total:
        score += 1
        senales.append("comprobante.ruc_y_total(+1)")

    if _tiene_estructura_items_totales(norm):
        score += 1
        senales.append("comprobante.estructura_items_totales(+1)")

    if _es_ticket_termico(norm, n_lineas):
        score += 1
        senales.append("comprobante.ticket_termico(+1)")

    return score, senales


def _decidir_tipo(
    score_sunat: int,
    score_comprobante: int,
) -> Tuple[TipoPagina, bool]:
    """
    SUNAT gana si llega al umbral. COMPROBANTE solo si comprobante >= 2 y no hay
    duda SUNAT (score_sunat >= 2 sin llegar a 3 se considera zona de conflicto → OTROS).
    """
    if score_sunat >= 3:
        return TipoPagina.SUNAT_VALIDACION, False

    if score_comprobante >= 2 and score_sunat < 2:
        return TipoPagina.COMPROBANTE, True

    # Duda: comprobante débil, o señales SUNAT intermedias sin certeza suficiente
    return TipoPagina.OTROS, False


def clasificar_pagina(texto: str) -> ClasificacionPagina:
    """
    Clasifica el texto de una página ya extraído (OCR o capa digital).

    pasa_a_extraccion es True únicamente para COMPROBANTE.
    """
    if not (texto or "").strip():
        return ClasificacionPagina(
            tipo=TipoPagina.OTROS,
            pasa_a_extraccion=False,
            score_sunat=0,
            score_comprobante=0,
            senales_activadas=["vacio.sin_texto"],
        )

    norm = _norm_clave(texto)
    ss, sen_s = _score_sunat(norm)
    sc, sen_c = _score_comprobante(texto, norm)
    tipo, pasa = _decidir_tipo(ss, sc)
    senales = [*sen_s, *sen_c]
    return ClasificacionPagina(
        tipo=tipo,
        pasa_a_extraccion=pasa,
        score_sunat=ss,
        score_comprobante=sc,
        senales_activadas=senales,
    )
