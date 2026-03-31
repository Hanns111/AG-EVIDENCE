#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Herramienta independiente: extrae comprobantes de PDFs (MINEDU / expedientes).
Extensión forense: cabecera emisor/cliente, ítems, montos etiquetados, forma de
pago y señales para control previo.

Principio obligatorio (anti-alucinación): «Si un dato no es claramente visible para
un humano en el documento, el sistema NO debe inferirlo ni generarlo» — preferir NULL.
Visibilidad probatoria: solo se reporta lo extraíble del propio bloque; lo no visible
queda NULL y puede marcarse con error_detectado_documento_fuente en revisión.

Flujo v2 (extraer → clasificar): primero se extrae de cada bloque (NULL si no hay
evidencia); solo después se decide si es comprobante (veneno/scoring/tier).
Versionado en repo: scripts/extract_comprobantes_minedu.py (uso práctico: copiar junto a PDFs o ajustar rutas).

Uso:
  python extract_comprobantes_minedu.py
  python extract_comprobantes_minedu.py --debug

Requiere Poppler en PATH para pdf2image (Windows: descargar poppler-windows y añadir bin/).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Pattern, Set, Tuple

# -----------------------------------------------------------------------------
# Dependencias opcionales (mensajes claros si faltan)
# -----------------------------------------------------------------------------

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None  # type: ignore

try:
    import pdfplumber
except ImportError:
    pdfplumber = None  # type: ignore

try:
    import pytesseract
    from pdf2image import convert_from_path
except ImportError:
    pytesseract = None
    convert_from_path = None  # type: ignore

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore


# Trazabilidad cuando un campo queda NULL por falta de evidencia explícita
TAG_DATO_NO_VISIBLE = "dato_no_visible"
TAG_OCR_INCOMPLETO = "ocr_incompleto"
TAG_CAMPO_SIN_EVIDENCIA = "campo_no_extraido_por_falta_de_evidencia"
TAG_IGV_INCONSISTENTE_REGIMEN = "igv_inconsistente_posible_regimen_especial"
TAG_ITEMS_SIN_LIMPIEZA = "items_sin_limpieza"
TAG_DESGLOSE_INCONSISTENTE = "desglose_inconsistente"
TAG_NO_COMPLETAR_DESDE_ANEXO = "no_completar_desde_anexo"
TAG_CAMPO_NO_VISIBLE_EN_COMPROBANTE = "campo_no_visible_en_comprobante"
TAG_FRASE_PRIORIDAD_NULL = "Es preferible NULL que un dato incorrecto proveniente de otra fuente."
TAG_ERROR_DETECTADO_DOCUMENTO_FUENTE = "error_detectado_documento_fuente"
FRASE_VISIBILIDAD_PROBATORIA = (
    "El sistema solo reporta lo que se puede ver; lo demás se observa como error."
)

# -----------------------------------------------------------------------------
# Columnas de salida
# -----------------------------------------------------------------------------

COLUMNS = [
    "tipo",
    "serie",
    "numero",
    "serie_raw",
    "numero_raw",
    "serie_numero_normalizado",
    "ruc",
    "proveedor_ruc",
    "proveedor",
    "proveedor_nombre",
    "proveedor_direccion",
    "proveedor_telefono",
    "proveedor_web",
    "proveedor_email",
    "cliente_nombre",
    "cliente_ruc",
    "descripcion_items",
    "tipo_gasto_detectado",
    "posible_observacion",
    "valor_venta",
    "igv",
    "recargo_consumo",
    "cargo_servicio",
    "icbper",
    "otros_cargos",
    "forma_pago",
    "fecha",
    "monto_total",
    "moneda",
    "concepto",
    "estado",
    "confianza",
    "archivo_origen",
    "pagina",
    "tier_post_extraccion",
    "score_post_extraccion",
    "needs_review",
    "visible_en_documento",
    "parcial_ocr",
    "observaciones",
]

COLUMNS_DESCARTADOS = [
    "archivo_origen",
    "pagina",
    "bloque_indice",
    "bloques_total",
    "clasificacion_pagina",
    "motivo_descarte",
    "score_extraccion",
    "tier_si_no_veneno",
    "serie_numero_normalizado",
    "ruc",
    "monto_total",
    "tipo_doc",
    "chars_bloque",
]


RE_RUC = re.compile(r"\b(\d{11})\b")
RE_SERIE_NUM = re.compile(
    r"\b([FB][A-Z]?\d{3})\s*[-–—]\s*(\d{4,})\b",
    re.IGNORECASE,
)
RE_SERIE_NUM_LOOSE = re.compile(
    r"\b([FB]\d{3})\s*[-–—]?\s*(\d{4,})\b",
    re.IGNORECASE,
)
RE_FECHA = re.compile(
    r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b",
)
RE_FECHA_EMISION = re.compile(
    r"FECHA\s+D[EE]\s+EMISI[OÓ]N",
    re.IGNORECASE,
)
RE_F_EMISION = re.compile(
    r"F\.\s*EMISI[OÓ]N|F\.EMISI[OÓ]N|\bF\s+EMISI[OÓ]N\b",
    re.IGNORECASE,
)
RE_CONSULTA_RUC = re.compile(
    r"CONSULTA\s+RUC|CONSULTA\s+DEL\s+RUC",
    re.IGNORECASE,
)
RE_ESTADO_CONTRIBUYENTE = re.compile(
    r"ESTADO\s+DEL\s+CONTRIBUYENTE",
    re.IGNORECASE,
)
RE_MONTO = re.compile(
    r"(?:^|[^\d])(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})|\d+[.,]\d{2})\b",
)

# Prioridad montos: 1 TOTAL A PAGAR, 2 IMPORTE TOTAL, 3 TOTAL (no SUBTOTAL; evitar IGV)
RE_TOTAL_A_PAGAR = re.compile(
    r"TOTAL\s+A\s+PAGAR[^\d]{0,60}((?:\d{1,3}(?:[.,]\d{3})*[.,]\d{2})|\d+[.,]\d{2})",
    re.IGNORECASE,
)
RE_IMPORTE_TOTAL = re.compile(
    r"IMPORTE\s+TOTAL[^\d]{0,60}((?:\d{1,3}(?:[.,]\d{3})*[.,]\d{2})|\d+[.,]\d{2})",
    re.IGNORECASE,
)
RE_TOTAL_SOLO = re.compile(
    r"(?<!SUB)(?:^|[^\w])(TOTAL)\b[^\d]{0,60}((?:\d{1,3}(?:[.,]\d{3})*[.,]\d{2})|\d+[.,]\d{2})",
    re.IGNORECASE,
)

# Recuperación extendida (solo bloque; sin inferir desde anexo): moneda visible + monto, etc.
RE_SIMBOLO_MONEDA = re.compile(
    r"S\s*/\s*|(?<!\w)S/\s*|\bSOLES\b|(?<!\w)PEN\b",
    re.IGNORECASE,
)
RE_PROVEEDOR_ETIQUETA_VIS = re.compile(
    r"\b(RAZ[OÓ]N\s+SOCIAL|PROVEEDOR|EMISOR|NOMBRE\s+COMERCIAL)\b",
    re.IGNORECASE,
)

# --- Extracción forense (cabecera, cliente, ítems, montos etiquetados) ---
RE_EMAIL = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)
RE_URL = re.compile(
    r"(?:https?://[^\s\]>]+|www\.[^\s\]>]+)",
    re.IGNORECASE,
)
RE_TEL_PERU = re.compile(
    r"(?:\+51[\s\-]?)?(?:9\d{8}|[1-9]\d{6,7})\b",
)

RE_LINEA_DIRECCION = re.compile(
    r"\b(JR\.?|AV\.?|AVENIDA|CALLE|PSJ\.?|PROLONG\.?|URB\.?|URBANIZACION|"
    r"MZA\.?|LT\.?|DPTO\.?|NRO\.?|N°|PISO|OF\.?|LIMA|PROV\.?)\b",
    re.IGNORECASE,
)
RE_ETIQUETA_CLIENTE = re.compile(
    r"\b(ADQUIRIENTE|CLIENTE)\s*:\s*|SE[NÑ]OR(?:ES)?\s*:\s*",
    re.IGNORECASE,
)
RE_CLIENTE_RUC_LINE = re.compile(
    r"\bR\.?U\.?C\.?\s*:?\s*(\d{11})\b",
    re.IGNORECASE,
)
RE_FORMA_PAGO_TITULO = re.compile(
    r"FORMA\s+D[EE]\s+PAGO|CONDICI[OÓ]N\s+D[EE]\s+PAGO|CONDICI[OÓ]N\s+D[EE]\s+VENTA",
    re.IGNORECASE,
)

RE_VALOR_VENTA_LINE = re.compile(
    r"VALOR\s+DE\s+VENTA|VALOR\s+VENTA|OP\.?\s*GRAV|op\.\s*gravadas?",
    re.IGNORECASE,
)
RE_IGV_MONTO_LINE = re.compile(
    r"\bIGV\b|\bI\.?\s*G\.?\s*V\.?\b",
    re.IGNORECASE,
)
RE_RECARGO_CONSUMO = re.compile(
    r"RECARGO(\s+AL)?\s+CONSUMO|\bR\.?\s*C\.?\s*(?:%|:|\b)",
    re.IGNORECASE,
)
RE_CARGO_SERVICIO = re.compile(
    r"CARGO\s+POR\s+SERVICIO|%?\s*SERVICIO\b|\bSERVICIO\s*%",
    re.IGNORECASE,
)
RE_ICBPER_LINE = re.compile(r"\bICBPER\b", re.IGNORECASE)

RE_KW_ALIMENTACION = re.compile(
    r"\b(menu|desayuno|almuerzo|cena|consumo|alimento?s?|platos?|bebidas?\s*no\s*alcoholicas?)\b",
    re.IGNORECASE,
)
RE_KW_ALCOHOL = re.compile(
    r"\b(cervezas?|vinos?|whisky|whiskey|piscos?|rones?|licores?|champagne|champan)\b",
    re.IGNORECASE,
)
RE_KW_HOSPEDAJE = re.compile(
    r"\b(hospedaje|hotel|hostal|motel|alojamiento|noches?|habitaci|pernoct)\w*\b",
    re.IGNORECASE,
)
RE_KW_TRANSPORTE = re.compile(
    r"\b(taxi|pasajes?|transporte|movilidad|uber|colectivo|bus|encomienda\s*aerea)\b",
    re.IGNORECASE,
)


def _norm_num(s: str) -> str:
    """Normaliza montos tipo 1.234,56 o 1234.56 a forma comparable."""
    s = s.strip().replace(" ", "")
    if not s:
        return ""
    if s.count(",") == 1 and s.count(".") >= 1:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(",") > 0 and "." not in s:
        s = s.replace(",", ".")
    return s


def _line_es_igv_o_subtotal(line: str) -> bool:
    u = line.upper()
    if "SUBTOTAL" in u:
        return True
    if re.search(r"\bIGV\b", u) and "TOTAL" not in u:
        return True
    if re.match(r"^\s*IGV\b", u.strip()):
        return True
    return False


def extraer_texto_fitz(path: Path, page_index: int) -> str:
    if not fitz:
        return ""
    doc = fitz.open(str(path))
    try:
        if page_index < 0 or page_index >= len(doc):
            return ""
        return doc[page_index].get_text("text") or ""
    finally:
        doc.close()


def extraer_texto_plumber_page(path: Path, page_index: int) -> str:
    if not pdfplumber:
        return ""
    try:
        with pdfplumber.open(str(path)) as pdf:
            if page_index < 0 or page_index >= len(pdf.pages):
                return ""
            return pdf.pages[page_index].extract_text() or ""
    except Exception:
        return ""


def extraer_texto_ocr(path: Path, page_1based: int) -> str:
    if not convert_from_path or not pytesseract:
        return ""
    try:
        images = convert_from_path(
            str(path),
            first_page=page_1based,
            last_page=page_1based,
            dpi=200,
        )
        if not images:
            return ""
        return pytesseract.image_to_string(images[0], lang="spa") or ""
    except Exception as e:
        return f"[OCR_ERROR: {e}]"


def obtener_texto_pagina(path: Path, page_index: int) -> Tuple[str, str]:
    """Devuelve (texto, fuente)."""
    t = extraer_texto_fitz(path, page_index).strip()
    fuente = "pymupdf"
    t2 = extraer_texto_plumber_page(path, page_index).strip()
    if len(t2) > len(t):
        t = t2
        fuente = "pdfplumber"
    if len(t) >= 40:
        return t, fuente
    t_ocr = extraer_texto_ocr(path, page_index + 1).strip()
    if "[OCR_ERROR:" in t_ocr:
        return "", "error_ocr"
    if len(t_ocr) > len(t):
        return t_ocr, "ocr"
    return t, "debil" if t else "vacio"


def tiene_serie_numero_valido(texto: str) -> bool:
    s, n = primer_match_serie_num(texto)
    return bool(s and n)


def _es_pagina_sunat_consulta_ruc(texto: str) -> bool:
    """
    Constancia tipo consulta SUNAT: etiquetas típicas y sin serie-número de comprobante.
    """
    if tiene_serie_numero_valido(texto):
        return False
    if not RE_CONSULTA_RUC.search(texto):
        return False
    if not RE_ESTADO_CONTRIBUYENTE.search(texto):
        return False
    return True


def clasificar_pagina(texto: str) -> str:
    """
    Tipos: COMPROBANTE_REAL, SUNAT, ANEXO, DJ, OTRO.
    Orden de reglas para no solapar.
    """
    if not texto or len(texto.strip()) < 25:
        return "OTRO"
    u = texto.upper()
    head = u[:2000]

    if "DECLARACION" in head and "JURADA" in head:
        return "DJ"
    if re.search(r"\bANEXO\s*N", head) or u.lstrip().startswith("ANEXO"):
        return "ANEXO"
    if _es_pagina_sunat_consulta_ruc(texto):
        return "SUNAT"
    if _es_comprobante_real(texto):
        return "COMPROBANTE_REAL"
    return "OTRO"


def _es_comprobante_real(texto: str) -> bool:
    u = texto.upper()
    if "FACTURA" not in u and "BOLETA" not in u:
        return False
    if "RUC" not in u or "TOTAL" not in u:
        return False
    s, n = primer_match_serie_num(texto)
    if not s or not n:
        return False
    return True


RE_BLOQUE_RUIDO_TABLA = re.compile(
    r"\b(ANEXO|RELACI[OÓ]N|RELACION|LISTADO|LIQUIDACI[OÓ]N\s+DE\s+GASTOS|"
    r"CUADRO\s+DE\s+REQUISITOS|RELACI[OÓ]N\s+DE\s+DOCUMENTOS)\b",
    re.IGNORECASE,
)
RE_BLOQUE_RUIDO_TABLA_SIN_ANEXO = re.compile(
    r"\b(RELACI[OÓ]N|RELACION|LISTADO|LIQUIDACI[OÓ]N\s+DE\s+GASTOS|"
    r"CUADRO\s+DE\s+REQUISITOS|RELACI[OÓ]N\s+DE\s+DOCUMENTOS)\b",
    re.IGNORECASE,
)
RE_BLOQUE_RUIDO_SUNAT = re.compile(
    r"CONSULTA\s+(DEL\s+)?RUC|E-CONSULTARUC|SUNAT\s*-\s*CONSULTA|"
    r"FECHA\s+CONSULTA\s*:\s*\d|ESTADO\s+DEL\s+CONTRIBUYENTE",
    re.IGNORECASE,
)


def _bloque_parece_listado_varias_series(bloque: str) -> bool:
    """Varias series-número distintas en el mismo bloque → probable tabla / anexo."""
    norms: Set[str] = set()
    for rx in (RE_SERIE_NUM, RE_SERIE_NUM_LOOSE):
        for m in rx.finditer(bloque):
            sr, nr = m.group(1).upper(), m.group(2)
            _, _, sn_norm = normalizar_serie_numero(sr, nr)
            if sn_norm != "NULL":
                norms.add(sn_norm)
    return len(norms) >= 2


def _bloque_tiene_ruc_once_digitos(bloque: str) -> bool:
    return bool(RE_RUC.search(bloque))


def _bloque_tiene_indicio_monto_total(bloque: str) -> bool:
    u = bloque.upper()
    if re.search(r"\bTOTAL\b", u):
        return True
    if re.search(r"\bIMPORTE\b", u):
        return True
    if re.search(r"\bMONTO\b", u):
        return True
    return False


def _bloque_rechazo_patron_anexo_tabla_sunat(
    bloque: str,
    *,
    pagina_es_anexo: bool,
) -> Optional[str]:
    if RE_BLOQUE_RUIDO_SUNAT.search(bloque):
        return "patron_sunat_consulta"
    if _bloque_parece_listado_varias_series(bloque):
        return "multiples_series_tabla"
    if pagina_es_anexo:
        if RE_BLOQUE_RUIDO_TABLA_SIN_ANEXO.search(bloque):
            return "patron_anexo_listado"
    else:
        if RE_BLOQUE_RUIDO_TABLA.search(bloque):
            return "patron_anexo_listado"
    return None


def validar_bloque_para_comprobante(
    bloque: str,
    *,
    pagina_es_anexo: bool = False,
) -> Tuple[bool, str]:
    """
    Valida el BLOQUE aisladamente (no la página).
    (serie+RUC+indicio monto; sin patrones de listado/SUNAT/tabla).
    En página ANEXO no se rechaza solo por la palabra ANEXO en cabecera.
    """
    if len(bloque.strip()) < 30:
        return False, "bloque_muy_corto"
    patron = _bloque_rechazo_patron_anexo_tabla_sunat(bloque, pagina_es_anexo=pagina_es_anexo)
    if patron:
        return False, patron
    if not tiene_serie_numero_valido(bloque):
        return False, "sin_serie_numero_valida"
    if not _bloque_tiene_ruc_once_digitos(bloque):
        return False, "sin_ruc_11_digitos"
    if not _bloque_tiene_indicio_monto_total(bloque):
        return False, "sin_total_importe_o_monto"
    return True, "ok"


def _bloques_desde_cortes(texto: str, indices: List[int]) -> List[str]:
    if not indices:
        return []
    idx = sorted(set(indices))
    if idx[0] > 0:
        idx.insert(0, 0)
    out: List[str] = []
    for i in range(len(idx)):
        ini = idx[i]
        fin = idx[i + 1] if i + 1 < len(idx) else len(texto)
        bloque = texto[ini:fin].strip()
        if len(bloque) >= 15:
            out.append(bloque)
    return out


def detectar_bloques_comprobantes(texto: str) -> List[str]:
    """
    Segmenta la página por anclas fuertes (FACTURA/BOLETA/serie-número) y, si hay
    varias series distintas, por inicio de cada comprobante. Elige la partición
    con más bloques (recall).
    """
    if not texto or len(texto.strip()) < 30:
        return []
    # Anclas al inicio de línea: evita el pie "representación... factura electrónica" y SUNAT "FACTURA (desde...".
    patrones = [
        r"(?m)^\s*FACTURA\s+ELECTR[OÓ]NICA\b",
        r"(?m)^\s*BOLETA\s+DE\s+VENTA\b",
        r"(?m)^\s*BOLETA\s+ELECTR",
        r"(?m)^\s*FACTURA\s*:\s*$",
        r"(?m)^\s*FACTURA\s+DE\s+VENTA\b",
        r"\b[FBE][A-Z]?\d{3}\s*[-–—]\s*\d{4,}\b",
    ]
    indices_ancla: List[int] = []
    for patron in patrones:
        for match in re.finditer(patron, texto, re.IGNORECASE):
            indices_ancla.append(match.start())

    desde_anclas = _bloques_desde_cortes(texto, indices_ancla)

    indices_serie: List[int] = []
    vistos_norm: Set[str] = set()
    for rx in (RE_SERIE_NUM, RE_SERIE_NUM_LOOSE):
        for m in rx.finditer(texto):
            sr, nr = m.group(1).upper(), m.group(2)
            _, _, sn_norm = normalizar_serie_numero(sr, nr)
            if sn_norm == "NULL" or sn_norm in vistos_norm:
                continue
            vistos_norm.add(sn_norm)
            indices_serie.append(m.start())
    desde_series = _bloques_desde_cortes(texto, indices_serie)

    candidatos = [desde_anclas, desde_series]
    candidatos = [c for c in candidatos if c]
    if not candidatos:
        return []
    return max(candidatos, key=len)


def primer_match_serie_num(texto: str) -> Tuple[Optional[str], Optional[str]]:
    for rx in (RE_SERIE_NUM, RE_SERIE_NUM_LOOSE):
        m = rx.search(texto)
        if m:
            return m.group(1).upper(), m.group(2)
    return None, None


def normalizar_serie_numero(serie: Optional[str], numero: Optional[str]) -> Tuple[str, str, str]:
    """serie_raw, numero_raw, serie_numero_normalizado (número sin ceros a la izquierda)."""
    sr = (serie or "").strip().upper() or "NULL"
    nr_raw = (numero or "").strip() or "NULL"
    if sr == "NULL" or nr_raw == "NULL":
        return sr, nr_raw, "NULL"
    if nr_raw.isdigit():
        nr_norm = str(int(nr_raw))
    else:
        nr_norm = nr_raw.lstrip("0") or nr_raw
    norm = f"{sr}-{nr_norm}"
    return sr, nr_raw, norm


def ruc_contexto_cabecera(texto: str) -> Optional[str]:
    """RUC junto a etiqueta RUC o en cabecera (primeras líneas), no el primero global."""
    lines = [ln.strip() for ln in texto.splitlines() if ln.strip()]
    if not lines:
        return None
    header_n = min(35, len(lines))

    for i in range(header_n):
        ln = lines[i]
        if re.search(r"\bR\.?\s*U\.?\s*C\.?\b", ln, re.I):
            m = RE_RUC.search(ln)
            if m:
                return m.group(1)
            if i + 1 < len(lines):
                m = RE_RUC.search(lines[i + 1])
                if m:
                    return m.group(1)

    block = "\n".join(lines[:18])
    ms = RE_RUC.findall(block)
    return ms[0] if ms else None


def extraer_monto_prioritario(texto: str) -> str:
    """Prioridad: TOTAL A PAGAR > IMPORTE TOTAL > TOTAL; ignora SUBTOTAL / IGV."""
    one_line = re.sub(r"\s+", " ", texto)

    m = RE_TOTAL_A_PAGAR.search(one_line)
    if m:
        return _norm_num(m.group(1)) or "NULL"

    m = RE_IMPORTE_TOTAL.search(one_line)
    if m:
        return _norm_num(m.group(1)) or "NULL"

    for ln in texto.splitlines():
        if _line_es_igv_o_subtotal(ln):
            continue
        lu = ln.upper()
        if "SUBTOTAL" in lu:
            continue
        if not re.search(r"\bTOTAL\b", lu):
            continue
        nums = RE_MONTO.findall(ln)
        if nums:
            return _norm_num(nums[-1]) or "NULL"

    m = RE_TOTAL_SOLO.search(one_line)
    if m:
        return _norm_num(m.group(2)) or "NULL"

    return "NULL"


def inferir_tipo(texto: str) -> str:
    u = texto.upper()
    if "BOLETA" in u:
        return "BOLETA"
    if "FACTURA" in u:
        return "FACTURA"
    return "NULL"


def _format_fecha_match(m: re.Match) -> str:
    d, mth, y = m.group(1), m.group(2), m.group(3)
    yy = int("20" + y) if len(y) == 2 else int(y)
    return f"{int(d):02d}/{int(mth):02d}/{yy}"


def _contexto_fecha_ignorar(texto: str, start: int, end: int) -> bool:
    """Excluye fechas de consulta, impresión u otros contextos no emisión."""
    a = max(0, start - 90)
    b = min(len(texto), end + 50)
    c = texto[a:b].upper()
    if re.search(
        r"FECHA\s+D[EE]\s+CONSULTA|FECHA\s+CONSULTA|CONSULTA\s*:|"
        r"HORA\s+D[EE]\s+CONSULTA|D[EE]\s+CONSULTA",
        c,
    ):
        return True
    if re.search(
        r"FECHA\s+D[EE]\s+IMPRES|FECHA\s+IMPRES|IMPRES[IÍ]ON\s*:|"
        r"HORA\s+D[EE]\s+IMPRES|IMPRES[IÍ]O",
        c,
    ):
        return True
    return False


def _primera_fecha_tras_etiqueta(texto: str, etiqueta: Pattern[str]) -> Optional[str]:
    for ml in etiqueta.finditer(texto):
        ventana = texto[ml.end() : ml.end() + 160]
        for mf in RE_FECHA.finditer(ventana):
            abs_s = ml.end() + mf.start()
            abs_e = ml.end() + mf.end()
            if _contexto_fecha_ignorar(texto, abs_s, abs_e):
                continue
            return _format_fecha_match(mf)
    return None


def extraer_fecha_preferida(texto: str) -> str:
    """
    Prioridad: 1) Fecha de emisión, 2) F. EMISION, 3) primera fecha no ignorada.
    Ignora ventanas ligadas a consulta / impresión.
    """
    f = _primera_fecha_tras_etiqueta(texto, RE_FECHA_EMISION)
    if f:
        return f
    f = _primera_fecha_tras_etiqueta(texto, RE_F_EMISION)
    if f:
        return f
    for mf in RE_FECHA.finditer(texto):
        if _contexto_fecha_ignorar(texto, mf.start(), mf.end()):
            continue
        return _format_fecha_match(mf)
    return "NULL"


def inferir_moneda(texto: str) -> str:
    u = texto.upper()
    if "S/" in texto or "SOLES" in u or "PEN" in u:
        return "PEN"
    if "USD" in u or "DOLAR" in u:
        return "USD"
    return "NULL"


def concepto_heuristica(texto: str) -> str:
    lines = [ln.strip() for ln in texto.splitlines() if ln.strip()]
    for ln in lines:
        if re.match(r"^(DETALLE|CONCEPTO|DESCRIPCION|ITEM)\b", ln, re.I):
            return "NULL"
    return "NULL"


RE_PROVEEDOR_CALLE = re.compile(
    r"\b(AV\.?|JR\.?|CALLE|URB\.?|URBANIZACION|MZ\.?|MZA\.?|LT\.?)\b",
    re.IGNORECASE,
)
RE_DIRECCION_NUM_COMA = re.compile(r"\d+\s*,\s*\d+")


def _es_nombre_proveedor_aceptable(ln: str) -> bool:
    """Permite números en razón social; descarta solo si parece dirección explícita."""
    if len(ln) < 4:
        return False
    if RE_PROVEEDOR_CALLE.search(ln):
        return False
    if RE_DIRECCION_NUM_COMA.search(ln):
        return False
    if "RUC" in ln.upper()[:8]:
        return False
    u = ln.upper().strip()
    if u in ("FACTURA", "BOLETA", "BOLETA DE VENTA", "FACTURA DE VENTA"):
        return False
    if RE_SERIE_NUM.search(ln) or RE_SERIE_NUM_LOOSE.search(ln):
        return False
    if ln.isupper():
        return True
    words = [w for w in ln.split() if any(c.isalpha() for c in w)]
    if words and all((w[0].isupper() for w in words if w and w[0].isalpha())):
        return True
    return False


def _nombre_desde_linea_previa_a_ruc(
    lines_st: List[str],
    ruc_emisor: Optional[str],
) -> Optional[str]:
    lim = min(len(lines_st), 45)
    for i in range(1, lim):
        ln = lines_st[i]
        if not RE_RUC.search(ln):
            continue
        compact = re.sub(r"\s+", "", ln)
        if ruc_emisor:
            if ruc_emisor not in compact:
                continue
        elif not re.search(r"\bR\.?U\.?C\.?\b", ln, re.I):
            continue
        prev = lines_st[i - 1]
        if _es_nombre_proveedor_aceptable(prev):
            return prev[:300]
    return None


def extraer_proveedor_nombre_estricto(
    lines_st: List[str],
    ruc_emisor: Optional[str],
) -> str:
    """
    Prioridad: línea inmediatamente anterior al RUC del emisor (filtrada).
    Respaldo: etiqueta RAZÓN SOCIAL / DENOMINACIÓN.
    """
    prev_ruc = _nombre_desde_linea_previa_a_ruc(lines_st, ruc_emisor)
    if prev_ruc:
        return prev_ruc
    for i, ln in enumerate(lines_st[:45]):
        m = re.match(
            r"^(R[AE]Z[OÓ]N\s+SOCIAL|DENOMINACI[OÓ]N(?:\s+COMERCIAL)?)\s*:\s*(.+)$",
            ln,
            re.I,
        )
        if m and m.group(2).strip():
            v = m.group(2).strip()
            if RE_RUC.fullmatch(v):
                continue
            if _es_nombre_proveedor_aceptable(v):
                return v[:300]
            if (
                len(v) > 3
                and not RE_PROVEEDOR_CALLE.search(v)
                and not RE_DIRECCION_NUM_COMA.search(v)
            ):
                return v[:300]
        m2 = re.match(
            r"^(R[AE]Z[OÓ]N\s+SOCIAL|DENOMINACI[OÓ]N(?:\s+COMERCIAL)?)\s*:?\s*$",
            ln,
            re.I,
        )
        if m2 and i + 1 < len(lines_st):
            nxt = lines_st[i + 1].strip()
            if (
                len(nxt) > 2
                and not nxt.upper().startswith("RUC")
                and not RE_SERIE_NUM.search(nxt)
                and _es_nombre_proveedor_aceptable(nxt)
            ):
                return nxt[:300]
    return "NULL"


def extraer_proveedor_direccion_estricto(lines_st: List[str]) -> str:
    """Solo línea con etiqueta DIRECCIÓN (o valor inmediato tras etiqueta sola)."""
    for i, ln in enumerate(lines_st[:45]):
        m = re.match(r"^DIRECCI[OÓ]N(?:\s+FISCAL)?\s*:\s*(.+)$", ln, re.I)
        if m and m.group(1).strip():
            return m.group(1).strip()[:400]
        m2 = re.match(r"^DIRECCI[OÓ]N(?:\s+FISCAL)?\s*:?\s*$", ln, re.I)
        if m2 and i + 1 < len(lines_st):
            nxt = lines_st[i + 1].strip()
            if nxt and not re.match(r"^(RUC|TELEF|CORREO|EMAIL)\b", nxt, re.I):
                return nxt[:400]
    return "NULL"


def extraer_proveedor_telefono_estricto(lines_st: List[str]) -> str:
    """Teléfono solo si la línea indica explícitamente tel/cel (evita DNI u otros dígitos)."""
    for ln in lines_st[:40]:
        if not re.search(r"\b(TEL|CEL|T[EÉ]L|TFNO|T[EÉ]LF|MOVIL|PHONE)\b", ln, re.I):
            continue
        tm = RE_TEL_PERU.search(ln)
        if tm:
            return tm.group(0).strip()[:40]
    return "NULL"


def extraer_cabecera_proveedor_forense(texto: str, ruc_emisor: Optional[str]) -> Dict[str, str]:
    """
    Emisor: literales y regex; nombre prioriza línea previa al RUC del emisor cuando aplica.
    """
    out: Dict[str, str] = {
        "proveedor_nombre": "NULL",
        "proveedor_direccion": "NULL",
        "proveedor_telefono": "NULL",
        "proveedor_web": "NULL",
        "proveedor_email": "NULL",
    }
    lines_st = [ln.strip() for ln in texto.splitlines() if ln.strip()]
    if not lines_st:
        return out
    out["proveedor_nombre"] = extraer_proveedor_nombre_estricto(lines_st, ruc_emisor)
    out["proveedor_direccion"] = extraer_proveedor_direccion_estricto(lines_st)
    out["proveedor_telefono"] = extraer_proveedor_telefono_estricto(lines_st)
    cabezal_txt = "\n".join(lines_st[:32])
    emails = RE_EMAIL.findall(cabezal_txt)
    if emails:
        out["proveedor_email"] = emails[0][:120]
    urls = RE_URL.findall(cabezal_txt)
    if urls:
        out["proveedor_web"] = urls[0][:250]
    return out


def extraer_cliente_forense(texto: str) -> Tuple[str, str]:
    """Cliente: etiqueta + RUC explícito en línea; nombre solo con evidencia en la misma sección."""
    nombre, ruc_c = "NULL", "NULL"
    for m in RE_ETIQUETA_CLIENTE.finditer(texto):
        chunk = texto[m.end() : m.end() + 800]
        block: List[str] = []
        for x in [s.strip() for s in chunk.splitlines()]:
            if not x:
                continue
            ux = x.upper()
            if ux.startswith("DIRECCI") or ux.startswith("TIPO DE") or ux.startswith("FORMA DE"):
                break
            block.append(x)
            if len(block) >= 12:
                break
        prev: Optional[str] = None
        for ln in block:
            mcombo = re.match(
                r"^(.{2,180}?)\s+R\.?U\.?C\.?\s*:?\s*(\d{11})\s*$",
                ln,
                re.I,
            )
            if mcombo:
                nombre = mcombo.group(1).strip(": -_|")[:250]
                ruc_c = mcombo.group(2)
                break
            mr = RE_CLIENTE_RUC_LINE.search(ln)
            if mr:
                ruc_c = mr.group(1)
                if prev and nombre == "NULL":
                    pu = prev.upper()
                    if (
                        len(prev) > 3
                        and not RE_LINEA_DIRECCION.search(prev)
                        and "FACTURA" not in pu
                        and "BOLETA" not in pu
                    ):
                        nombre = prev[:250]
                break
            prev = ln
        if nombre != "NULL" or ruc_c != "NULL":
            break
    return nombre, ruc_c


def _mantener_linea_detalle_item(l: str) -> bool:
    s = l.strip()
    if len(s) < 3:
        return False
    u = s.upper()
    if re.search(r"\bTOTAL\b", u):
        return False
    if re.search(r"\bSUBTOTAL\b", u):
        return False
    if re.search(r"\bIGV\b", u) or re.search(r"\bI\.?\s*G\.?\s*V\.?\b", u):
        return False
    if re.match(r"^[\d\s.,\-]+$", s):
        return False
    return True


def extraer_bloque_items(texto: str) -> Tuple[str, bool]:
    """
    Devuelve (texto_items, usar_items_sin_limpieza).
    Si tras filtrar no queda nada pero había bloque → texto original y True.
    """
    lines_raw = texto.splitlines()
    start = -1
    for i, ln in enumerate(lines_raw):
        t = ln.strip()
        if re.search(
            r"^(DETALLE|DESCRIPCI[OÓ]N|ITEM(\s*S)?|CANT\.?)\b|\bDESCRIPCI[OÓ]N\s+DEL\s+",
            t,
            re.I,
        ):
            start = i + 1
            break
    if start < 0:
        return "NULL", False
    buf_raw: List[str] = []
    buf_clean: List[str] = []
    for j in range(start, min(start + 45, len(lines_raw))):
        l = lines_raw[j].strip()
        if not l:
            if len(buf_raw) > 12:
                break
            continue
        if re.search(
            r"^(SUBTOTAL|OP\.?\s*GRAV|IMPORTE\s+TOTAL|TOTAL\s+A\s+PAGAR|"
            r"IMPORTE\s+TOTAL|SON\s+:|GRACIAS)\b",
            l,
            re.I,
        ):
            break
        if re.match(r"^[-=_.]{4,}\s*$", l):
            continue
        buf_raw.append(l)
        if _mantener_linea_detalle_item(l):
            buf_clean.append(l)
    if not buf_raw:
        return "NULL", False
    if buf_clean:
        joined = " | ".join(buf_clean)
        return (joined[:5000] if len(joined) > 5000 else joined), False
    joined = " | ".join(buf_raw)
    return (joined[:5000] if len(joined) > 5000 else joined), True


def texto_zona_media_documento(texto: str) -> str:
    """Ventana ~20%%–80%% de líneas (evita cabecera y pie para tipo de gasto)."""
    lines = texto.splitlines()
    n = len(lines)
    if n < 10:
        return texto
    a = max(1, int(n * 0.20))
    b = min(n, int(n * 0.80))
    return "\n".join(lines[a:b])


def _monto_en_linea_etiqueta(ln: str, rx: Pattern[str]) -> Optional[str]:
    if not rx.search(ln):
        return None
    nums = RE_MONTO.findall(ln)
    if not nums:
        return None
    n = _norm_num(nums[-1])
    return n or None


def _primer_monto_en_linea_si_patron(ln: str, pat: Pattern[str]) -> Optional[str]:
    if not pat.search(ln):
        return None
    nums = RE_MONTO.findall(ln)
    if not nums:
        return None
    n = _norm_num(nums[-1])
    return n or None


def _linea_etiqueta_total_valor_igv(ln: str) -> bool:
    """Línea ya contabilizada como base, IGV o total (excluir de otros_cargos)."""
    u = ln.upper()
    if RE_VALOR_VENTA_LINE.search(ln):
        return True
    if RE_IGV_MONTO_LINE.search(ln) and "SUBTOTAL" not in u:
        return True
    if "SUBTOTAL" in u:
        return True
    if re.search(r"\bIMPORTE\s+TOTAL\b", u) or re.search(r"\bTOTAL\s+A\s+PAGAR\b", u):
        return True
    if re.search(r"\bTOTAL\b", u) and "SUBTOTAL" not in u:
        return True
    return False


def extraer_otros_cargos_desde_lineas(texto: str) -> str:
    """Líneas con monto explícito que no son valor venta / IGV / totales / cargos etiquetados."""
    fragmentos: List[str] = []
    for ln in texto.splitlines():
        lnst = ln.strip()
        if not lnst or len(lnst) < 4:
            continue
        if not RE_MONTO.search(lnst):
            continue
        if _linea_etiqueta_total_valor_igv(lnst):
            continue
        if RE_RECARGO_CONSUMO.search(lnst):
            continue
        if RE_CARGO_SERVICIO.search(lnst):
            continue
        if RE_ICBPER_LINE.search(lnst):
            continue
        fragmentos.append(lnst[:200])
        if len(fragmentos) >= 10:
            break
    if not fragmentos:
        return "NULL"
    out = " | ".join(fragmentos)
    return out[:2000] if len(out) > 2000 else out


def extraer_desglose_cargos_adicionales(texto: str) -> Dict[str, str]:
    out: Dict[str, str] = {
        "recargo_consumo": "NULL",
        "cargo_servicio": "NULL",
        "icbper": "NULL",
        "otros_cargos": "NULL",
    }
    rc_ok, cs_ok, icb_ok = False, False, False
    for ln in texto.splitlines():
        lnst = ln.strip()
        if not lnst:
            continue
        if not rc_ok and RE_RECARGO_CONSUMO.search(lnst):
            m = _primer_monto_en_linea_si_patron(lnst, RE_RECARGO_CONSUMO)
            if m:
                out["recargo_consumo"] = m
                rc_ok = True
            continue
        if not cs_ok and RE_CARGO_SERVICIO.search(lnst):
            m = _primer_monto_en_linea_si_patron(lnst, RE_CARGO_SERVICIO)
            if m:
                out["cargo_servicio"] = m
                cs_ok = True
            continue
        if not icb_ok and RE_ICBPER_LINE.search(lnst):
            m = _primer_monto_en_linea_si_patron(lnst, RE_ICBPER_LINE)
            if m:
                out["icbper"] = m
                icb_ok = True
    oc = extraer_otros_cargos_desde_lineas(texto)
    out["otros_cargos"] = oc
    return out


def extraer_valor_venta_igv(texto: str) -> Tuple[str, str]:
    """
    Solo montos en líneas con etiqueta explícita (no inferir % ni subtotales alternos).
    """
    valor_v, igv_v = "NULL", "NULL"
    for ln in texto.splitlines():
        if valor_v == "NULL":
            v = _monto_en_linea_etiqueta(ln, RE_VALOR_VENTA_LINE)
            if v:
                valor_v = v
        if igv_v == "NULL" and RE_IGV_MONTO_LINE.search(ln) and "SUBTOTAL" not in ln.upper():
            g = _monto_en_linea_etiqueta(ln, RE_IGV_MONTO_LINE)
            if g:
                igv_v = g
    if valor_v == "NULL":
        one = re.sub(r"\s+", " ", texto)
        m = re.search(
            r"(?:VALOR\s+DE\s+VENTA|VALOR\s+VENTA|OP\.?\s*GRAV)\s*[^:]?\s*("
            r"(?:\d{1,3}(?:[.,]\d{3})*[.,]\d{2})|\d+[.,]\d{2})",
            one,
            re.I,
        )
        if m:
            valor_v = _norm_num(m.group(1)) or "NULL"
    return valor_v, igv_v


def extraer_forma_pago(texto: str) -> str:
    """Solo si la palabra clave aparece en línea de forma/condición de pago (evita aciertos fortuitos)."""
    lines = texto.splitlines()
    for i, ln in enumerate(lines):
        if not RE_FORMA_PAGO_TITULO.search(ln):
            continue
        bloque = " ".join(lines[i : min(i + 3, len(lines))]).upper()
        orden = [
            ("CREDITO", "CREDITO"),
            ("TARJETA", "TARJETA"),
            ("EFECTIVO", "EFECTIVO"),
            ("YAPE", "YAPE"),
            ("PLIN", "PLIN"),
            ("CONTADO", "CONTADO"),
        ]
        for pat, val in orden:
            if re.search(rf"\b{pat}\b", bloque):
                return val
    return "NULL"


def _clasificar_tipo_gasto_desde_texto(blob: str) -> str:
    """Un solo tipo si hay una categoría clara; si hay varias o ninguna → NULL."""
    if not blob or blob == "NULL":
        return "NULL"
    found: List[str] = []
    if RE_KW_ALIMENTACION.search(blob):
        found.append("ALIMENTACION")
    if RE_KW_TRANSPORTE.search(blob):
        found.append("TRANSPORTE")
    if RE_KW_HOSPEDAJE.search(blob):
        found.append("HOSPEDAJE")
    if len(found) != 1:
        return "NULL"
    return found[0]


def tipo_gasto_y_observacion(
    descripcion_items: str,
    texto_completo: str,
) -> Tuple[str, str]:
    """Ítems primero; sin ítems → solo zona media del documento (no cabecera/pie)."""
    obs = "NULL"
    if descripcion_items != "NULL":
        if RE_KW_ALCOHOL.search(descripcion_items):
            obs = "GASTO NO PERMITIDO - POSIBLE ALCOHOL"
        tipo = _clasificar_tipo_gasto_desde_texto(descripcion_items)
        return tipo, obs
    zona = texto_zona_media_documento(texto_completo)
    tipo = _clasificar_tipo_gasto_desde_texto(zona)
    return tipo, obs


def igv_cuadra_con_base_18pct(
    valor_venta: str,
    igv: str,
    tol_rel: float = 0.035,
) -> bool:
    """True si no aplica, si no es legible o si IGV ≈ 18% de valor_venta (± tolerancia)."""
    if valor_venta == "NULL" or igv == "NULL":
        return True
    try:
        vv = float(valor_venta)
        ig = float(igv)
    except ValueError:
        return True
    if vv <= 0:
        return True
    esperado = vv * 0.18
    dif = abs(ig - esperado)
    if esperado < 0.01:
        return dif <= 0.01
    if dif <= 0.06:
        return True
    return (dif / esperado) <= tol_rel


def anexar_tag_igv_si_inconsistente(
    partes: List[str],
    valor_venta: str,
    igv: str,
) -> None:
    if not igv_cuadra_con_base_18pct(valor_venta, igv):
        partes.append(TAG_IGV_INCONSISTENTE_REGIMEN)


def anexar_tag_desglose_si_inconsistente(partes: List[str], fila: FilaComprobante) -> None:
    """Suma explícita (valor_venta + IGV + cargos + otros) vs monto_total."""
    if fila.monto_total == "NULL":
        return

    def _to_f(x: str) -> float:
        if x == "NULL" or not x:
            return 0.0
        try:
            return float(x)
        except ValueError:
            return 0.0

    s = (
        _to_f(fila.valor_venta)
        + _to_f(fila.igv)
        + _to_f(fila.recargo_consumo)
        + _to_f(fila.cargo_servicio)
        + _to_f(fila.icbper)
    )
    otros_s = 0.0
    if fila.otros_cargos != "NULL":
        for m in re.findall(
            r"(?:\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+[.,]\d{2})",
            fila.otros_cargos,
        ):
            otros_s += _to_f(_norm_num(m))
    s += otros_s

    n_componentes = sum(
        1
        for x in (
            fila.valor_venta,
            fila.igv,
            fila.recargo_consumo,
            fila.cargo_servicio,
            fila.icbper,
        )
        if x != "NULL"
    )
    if fila.otros_cargos != "NULL" and otros_s > 0:
        n_componentes += 1
    if n_componentes < 2:
        return
    try:
        mt = float(fila.monto_total)
    except ValueError:
        return
    if abs(mt) < 1e-9:
        return
    if abs(s - mt) > max(0.12, 0.018 * abs(mt)):
        partes.append(TAG_DESGLOSE_INCONSISTENTE)


def calcular_estado(
    ruc: str,
    serie_norm: str,
    monto: str,
    fecha: str,
    fuente: str,
) -> str:
    if fuente in ("ocr", "debil", "vacio", "error_ocr"):
        return "OCR_DUDOSO"
    ok_ruc = ruc != "NULL"
    ok_sn = serie_norm != "NULL"
    ok_monto = monto != "NULL"
    ok_fecha = fecha != "NULL"
    if ok_ruc and ok_sn and ok_monto and ok_fecha:
        return "COMPLETO"
    # Nativo/accesible pero casi sin datos fiscales recuperables
    if ok_sn and not ok_ruc and not ok_monto:
        return "DESCARTADO"
    return "PARCIAL"


def calcular_confianza(
    fuente: str,
    ruc: str,
    serie_norm: str,
    monto: str,
    fecha: str,
    estado: str,
) -> float:
    """
    Puntuación 0–1 heurística: campos completos + calidad de fuente de texto.
    """
    s = 0.0
    if ruc != "NULL":
        s += 0.22
    if serie_norm != "NULL":
        s += 0.22
    if monto != "NULL":
        s += 0.22
    if fecha != "NULL":
        s += 0.18
    if fuente in ("pymupdf", "pdfplumber"):
        s += 0.16
    elif fuente == "ocr":
        s += 0.10
    else:
        s += 0.06
    if estado == "COMPLETO":
        s += 0.08
    elif estado == "PARCIAL":
        s += 0.04
    elif estado == "OCR_DUDOSO":
        s *= 0.85
    elif estado == "DESCARTADO":
        s = min(s, 0.38)
    return round(min(1.0, s), 3)


@dataclass
class FilaComprobante:
    tipo: str = "NULL"
    serie: str = "NULL"
    numero: str = "NULL"
    serie_raw: str = "NULL"
    numero_raw: str = "NULL"
    serie_numero_normalizado: str = "NULL"
    ruc: str = "NULL"
    proveedor_ruc: str = "NULL"
    proveedor: str = "NULL"
    proveedor_nombre: str = "NULL"
    proveedor_direccion: str = "NULL"
    proveedor_telefono: str = "NULL"
    proveedor_web: str = "NULL"
    proveedor_email: str = "NULL"
    cliente_nombre: str = "NULL"
    cliente_ruc: str = "NULL"
    descripcion_items: str = "NULL"
    tipo_gasto_detectado: str = "NULL"
    posible_observacion: str = "NULL"
    valor_venta: str = "NULL"
    igv: str = "NULL"
    recargo_consumo: str = "NULL"
    cargo_servicio: str = "NULL"
    icbper: str = "NULL"
    otros_cargos: str = "NULL"
    forma_pago: str = "NULL"
    fecha: str = "NULL"
    monto_total: str = "NULL"
    moneda: str = "NULL"
    concepto: str = "NULL"
    estado: str = "PARCIAL"
    confianza: float = 0.0
    archivo_origen: str = ""
    pagina: int = 0
    bloque_indice_1based: int = 0
    observaciones: str = ""
    fuente_extraccion: str = ""
    tier_post_extraccion: str = ""
    score_post_extraccion: int = -1
    needs_review: bool = False
    visible_en_documento: bool = True
    parcial_ocr: bool = False

    def clave_dedup_normalizada(self) -> Tuple[str, str, str, int]:
        sin_clave_fiscal = self.serie_numero_normalizado == "NULL" and self.ruc == "NULL"
        sufijo = (self.pagina * 10_000 + self.bloque_indice_1based) if sin_clave_fiscal else 0
        return (self.archivo_origen, self.serie_numero_normalizado, self.ruc, sufijo)


@dataclass
class DecisionPostExtraccion:
    """Resultado de clasificar_bloque_post_extraccion (solo después de extraer)."""

    es_comprobante: bool
    descartado: bool
    motivo: str
    tier: str
    score: int
    detalle_scoring: str


@dataclass
class RegistroDescartado:
    archivo_origen: str
    pagina: int
    bloque_indice: int
    bloques_total: int
    clasificacion_pagina: str
    motivo_descarte: str
    score_extraccion: int
    tier_si_no_veneno: str
    serie_numero_normalizado: str
    ruc: str
    monto_total: str
    tipo_doc: str
    chars_bloque: int


def _consulta_sunat_en_bloque(bloque: str) -> bool:
    if RE_BLOQUE_RUIDO_SUNAT.search(bloque):
        return True
    u = re.sub(r"\s+", "", bloque.upper())
    if "CONSULTA" in bloque.upper() and (
        "SUNAT" in bloque.upper() or "E-CONSULTARUC" in u or "CONSULTARUC" in u
    ):
        return True
    return bool(re.search(r"\bCONSULTA\s+DE\s+COMPROBANTE\b", bloque, re.I))


def _bloque_anexo_y_estructura_tabla(bloque: str) -> bool:
    """ANEXO en texto + filas con aspecto de tabla (sin inferir datos de negocio)."""
    if not re.search(r"\bANEXO\b", bloque, re.I):
        return False
    lineas = [ln.strip() for ln in bloque.splitlines() if ln.strip()]
    if len(lineas) < 8:
        return False
    if _bloque_parece_listado_varias_series(bloque):
        return True
    fila_like = 0
    for ln in lineas:
        if re.search(r"(?:\d{1,3}[.,])+\d{2}\b|\b\d{11}\b", ln):
            fila_like += 1
    return fila_like >= 5


def _score_datos_extraidos(fila: FilaComprobante) -> int:
    s = 0
    if fila.serie_numero_normalizado != "NULL":
        s += 1
    if fila.ruc != "NULL":
        s += 1
    if fila.monto_total != "NULL":
        s += 1
    if fila.tipo in ("FACTURA", "BOLETA"):
        s += 1
    return s


def _tier_post_score(fila: FilaComprobante, score: int) -> str:
    if score >= 4:
        return "ALTA"
    if score == 3:
        if fila.fecha != "NULL" and fila.proveedor_nombre != "NULL":
            return "ALTA"
        return "MEDIA"
    if score == 2:
        return "BAJA"
    return "N/A"


def clasificar_bloque_post_extraccion(
    fila: FilaComprobante,
    texto_bloque: str,
) -> DecisionPostExtraccion:
    """
    Decide si el bloque es comprobante utilizable SOLO después de la extracción ciega.
    Veneno → descarte. Si no, scoring por campos extraídos y tier.
    """
    if _bloque_parece_listado_varias_series(texto_bloque):
        return DecisionPostExtraccion(
            False,
            True,
            "veneno_multiples_series_en_bloque",
            "N/A",
            0,
            "tabla_varias_series",
        )
    if _consulta_sunat_en_bloque(texto_bloque):
        return DecisionPostExtraccion(
            False,
            True,
            "veneno_consulta_sunat",
            "N/A",
            0,
            "consulta_o_constancia",
        )
    if _bloque_anexo_y_estructura_tabla(texto_bloque):
        return DecisionPostExtraccion(
            False,
            True,
            "veneno_anexo_tabla",
            "N/A",
            0,
            "anexo_y_estructura_tabular",
        )

    score = _score_datos_extraidos(fila)
    detalle = (
        f"pts_serie_ruc_monto_tipo={score} "
        f"(serie={'1' if fila.serie_numero_normalizado != 'NULL' else '0'},"
        f"ruc={'1' if fila.ruc != 'NULL' else '0'},"
        f"monto={'1' if fila.monto_total != 'NULL' else '0'},"
        f"tipo_doc={'1' if fila.tipo in ('FACTURA', 'BOLETA') else '0'})"
    )

    if score < 2:
        return DecisionPostExtraccion(
            False,
            True,
            "score_insuficiente_post_extraccion",
            "N/A",
            score,
            detalle,
        )

    tier = _tier_post_score(fila, score)
    return DecisionPostExtraccion(
        True,
        False,
        "comprobante_aceptado",
        tier,
        score,
        detalle,
    )


def _sin_veneno_en_bloque(bloque: str) -> bool:
    """Mismas señales que `clasificar_bloque_post_extraccion`; sin duplicar reglas distintas."""
    if _bloque_parece_listado_varias_series(bloque):
        return False
    if _consulta_sunat_en_bloque(bloque):
        return False
    if _bloque_anexo_y_estructura_tabla(bloque):
        return False
    return True


def _monto_parcial_en_bloque(bloque: str) -> bool:
    return bool(
        RE_MONTO.search(bloque)
        or RE_TOTAL_A_PAGAR.search(bloque)
        or RE_IMPORTE_TOTAL.search(bloque)
        or RE_TOTAL_SOLO.search(bloque)
    )


def _bloque_tiene_monto_con_simbolo_moneda(bloque: str) -> bool:
    if not RE_SIMBOLO_MONEDA.search(bloque):
        return False
    return _monto_parcial_en_bloque(bloque)


def _ruc_parcial_o_etiqueta_visible(bloque: str) -> bool:
    if RE_RUC.search(bloque):
        return True
    if re.search(
        r"\bR\.?\s*U\.?\s*C\.?\s*:?\s*\d{8,11}\b",
        bloque,
        re.IGNORECASE,
    ):
        return True
    if "RUC" in bloque.upper() and re.search(r"\b\d{9,11}\b", bloque):
        return True
    return False


def _bloque_estructura_ticket(bloque: str) -> bool:
    lineas = [ln for ln in bloque.splitlines() if ln.strip()]
    n = len(lineas)
    if n < 3 or n > 45:
        return False
    if not _monto_parcial_en_bloque(bloque):
        return False
    u = bloque.upper()
    if "TOTAL" not in u and "IMPORTE" not in u and "PAGO" not in u:
        return False
    return True


def _recuperacion_extendida_permitida(fila: FilaComprobante, bloque: str) -> bool:
    """
    Casos adicionales de aceptación SOLO si no hay veneno y hay evidencia visible en el bloque.
    No infiere: solo patrones de texto del propio segmento.
    """
    if not _sin_veneno_en_bloque(bloque):
        return False
    a = _bloque_tiene_monto_con_simbolo_moneda(bloque)
    b = (
        fila.ruc != "NULL" or _ruc_parcial_o_etiqueta_visible(bloque)
    ) and _monto_parcial_en_bloque(bloque)
    c = _bloque_estructura_ticket(bloque)
    return a or b or c


def _patron_serie_visible(bloque: str) -> bool:
    return bool(RE_SERIE_NUM.search(bloque) or RE_SERIE_NUM_LOOSE.search(bloque))


def _calcular_visible_y_parcial(
    fila: FilaComprobante, bloque: str, fuente: str
) -> Tuple[bool, bool]:
    critics: List[Tuple[bool, bool]] = [
        (fila.serie_numero_normalizado != "NULL", _patron_serie_visible(bloque)),
        (fila.ruc != "NULL", _ruc_parcial_o_etiqueta_visible(bloque)),
        (fila.monto_total != "NULL", _monto_parcial_en_bloque(bloque)),
        (fila.fecha != "NULL", bool(RE_FECHA.search(bloque))),
        (fila.proveedor_nombre != "NULL", bool(RE_PROVEEDOR_ETIQUETA_VIS.search(bloque))),
    ]
    has_any_val = any(v for v, _ in critics)
    n_pat = sum(1 for _, p in critics if p)
    parcial = fuente in ("ocr", "debil", "error_ocr")
    for v, p in critics:
        if not v and p:
            parcial = True
    vis_doc = has_any_val or n_pat >= 1
    return vis_doc, parcial


def _faltan_criticos_para_revisar(fila: FilaComprobante) -> bool:
    return any(
        x == "NULL"
        for x in (
            fila.serie_numero_normalizado,
            fila.ruc,
            fila.monto_total,
            fila.fecha,
            fila.proveedor_nombre,
        )
    )


def _anexar_tags_anti_alucinacion(
    partes: List[str],
    fuente: str,
    fila: FilaComprobante,
    n_chars: int,
) -> None:
    if fuente in ("ocr", "debil", "error_ocr"):
        partes.append(TAG_OCR_INCOMPLETO)
    forense_nulos = sum(
        1
        for x in (
            fila.proveedor_nombre,
            fila.proveedor_direccion,
            fila.cliente_ruc,
            fila.cliente_nombre,
            fila.descripcion_items,
            fila.valor_venta,
            fila.igv,
            fila.forma_pago,
            fila.tipo_gasto_detectado,
        )
        if x == "NULL"
    )
    if forense_nulos >= 7 and n_chars > 120:
        partes.append(TAG_CAMPO_SIN_EVIDENCIA)
    if fila.descripcion_items == "NULL" and n_chars > 100:
        partes.append(TAG_DATO_NO_VISIBLE)


def guardar_debug_texto(debug_dir: Path, pdf_name: str, page_1based: int, texto: str) -> None:
    debug_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w\-.]+", "_", pdf_name)[:120]
    fname = f"{safe}__p{page_1based:04d}.txt"
    (debug_dir / fname).write_text(texto or "", encoding="utf-8", errors="replace")


def extraer_fila_desde_bloque_texto(
    path: Path,
    page_index: int,
    texto_bloque: str,
    fuente: str,
    chars_pagina: int,
    indice_bloque: int,
    total_bloques: int,
    clasificacion_pagina: str,
    pagina_anexo: bool,
) -> FilaComprobante:
    """Una fila Excel solo desde texto_bloque (aislado); sin completar desde el resto de la página."""
    texto = texto_bloque
    s, n = primer_match_serie_num(texto)
    sr, nr_raw, sn_norm = normalizar_serie_numero(s, n)

    fila = FilaComprobante(archivo_origen=path.name, pagina=page_index + 1)
    fila.bloque_indice_1based = indice_bloque + 1
    fila.fuente_extraccion = fuente
    fila.tipo = inferir_tipo(texto)
    fila.serie = sr if sr != "NULL" else "NULL"
    fila.numero = nr_raw if nr_raw != "NULL" else "NULL"
    fila.serie_raw = sr if sr != "NULL" else "NULL"
    fila.numero_raw = nr_raw if nr_raw != "NULL" else "NULL"
    fila.serie_numero_normalizado = sn_norm

    r = ruc_contexto_cabecera(texto)
    fila.ruc = r if r else "NULL"
    fila.proveedor_ruc = fila.ruc

    cab = extraer_cabecera_proveedor_forense(texto, r)
    fila.proveedor_nombre = cab["proveedor_nombre"]
    fila.proveedor_direccion = cab["proveedor_direccion"]
    fila.proveedor_telefono = cab["proveedor_telefono"]
    fila.proveedor_web = cab["proveedor_web"]
    fila.proveedor_email = cab["proveedor_email"]

    fila.proveedor = fila.proveedor_nombre

    c_nom, c_ruc = extraer_cliente_forense(texto)
    fila.cliente_nombre = c_nom
    fila.cliente_ruc = c_ruc

    fila.descripcion_items, items_sin_limpieza = extraer_bloque_items(texto)
    fila.valor_venta, fila.igv = extraer_valor_venta_igv(texto)
    descargos = extraer_desglose_cargos_adicionales(texto)
    fila.recargo_consumo = descargos["recargo_consumo"]
    fila.cargo_servicio = descargos["cargo_servicio"]
    fila.icbper = descargos["icbper"]
    fila.otros_cargos = descargos["otros_cargos"]
    fila.forma_pago = extraer_forma_pago(texto)
    fila.tipo_gasto_detectado, fila.posible_observacion = tipo_gasto_y_observacion(
        fila.descripcion_items,
        texto,
    )

    fila.fecha = extraer_fecha_preferida(texto)
    fila.monto_total = extraer_monto_prioritario(texto)
    if fila.monto_total == "":
        fila.monto_total = "NULL"
    fila.moneda = inferir_moneda(texto)
    fila.concepto = concepto_heuristica(texto)

    fila.estado = calcular_estado(
        fila.ruc,
        fila.serie_numero_normalizado,
        fila.monto_total,
        fila.fecha,
        fuente,
    )
    fila.confianza = calcular_confianza(
        fuente,
        fila.ruc,
        fila.serie_numero_normalizado,
        fila.monto_total,
        fila.fecha,
        fila.estado,
    )

    obs_parts = [
        f"texto_fuente={fuente}",
        f"chars_pagina={chars_pagina}",
        f"chars_bloque={len(texto)}",
        f"segmento_bloque={indice_bloque + 1}/{total_bloques}",
        f"clasificacion_pagina={clasificacion_pagina}",
        "extraccion_solo_desde_bloque=1",
        "flujo=extraer_primero_clasificar_despues",
        TAG_FRASE_PRIORIDAD_NULL,
    ]
    if pagina_anexo:
        obs_parts.append(TAG_NO_COMPLETAR_DESDE_ANEXO)
    _anexar_tags_anti_alucinacion(obs_parts, fuente, fila, len(texto))
    if items_sin_limpieza:
        obs_parts.append(TAG_ITEMS_SIN_LIMPIEZA)
    anexar_tag_igv_si_inconsistente(obs_parts, fila.valor_venta, fila.igv)
    anexar_tag_desglose_si_inconsistente(obs_parts, fila)
    criticos_nulos = sum(
        1
        for x in (
            fila.ruc,
            fila.monto_total,
            fila.fecha,
            fila.proveedor_nombre,
            fila.descripcion_items,
        )
        if x == "NULL"
    )
    if criticos_nulos >= 2 and len(texto) > 60:
        obs_parts.append(TAG_CAMPO_NO_VISIBLE_EN_COMPROBANTE)
    fila.observaciones = " | ".join(obs_parts)
    return fila


def procesar_pagina(
    path: Path,
    page_index: int,
    debug_dir: Optional[Path],
) -> Tuple[List[FilaComprobante], List[RegistroDescartado], str, int]:
    """
    Extrae todos los bloques sin filtrar; clasificación solo después (clasificar_bloque_post_extraccion).
    Devuelve (filas comprobante, descartados, clasificación página, nº bloques).
    """
    texto, fuente = obtener_texto_pagina(path, page_index)
    clase = clasificar_pagina(texto) if texto else "OTRO"

    if debug_dir is not None:
        guardar_debug_texto(debug_dir, path.name, page_index + 1, texto)

    if not texto or len(texto.strip()) < 15:
        return [], [], clase, 0

    chars_pagina = len(texto)
    bloques = detectar_bloques_comprobantes(texto)
    if not bloques:
        bloques = [texto.strip()]
    pagina_anexo = clase == "ANEXO"

    filas: List[FilaComprobante] = []
    descartados: List[RegistroDescartado] = []

    for bi, bloque in enumerate(bloques):
        if len(bloque.strip()) < 8:
            continue
        fila = extraer_fila_desde_bloque_texto(
            path,
            page_index,
            bloque,
            fuente,
            chars_pagina,
            bi,
            len(bloques),
            clase,
            pagina_anexo,
        )
        dec = clasificar_bloque_post_extraccion(fila, bloque)
        score_ext = _score_datos_extraidos(fila)

        recuperar = (
            (not dec.es_comprobante or dec.descartado)
            and dec.motivo == "score_insuficiente_post_extraccion"
            and _recuperacion_extendida_permitida(fila, bloque)
        )

        if dec.es_comprobante and not dec.descartado:
            fila.tier_post_extraccion = dec.tier
            fila.score_post_extraccion = dec.score
            fila.needs_review = False
            vis, par = _calcular_visible_y_parcial(fila, bloque, fuente)
            fila.visible_en_documento = vis
            fila.parcial_ocr = par
            fila.observaciones += (
                f" | post_extraccion={dec.motivo} | tier={dec.tier} | "
                f"score_post={dec.score} | {dec.detalle_scoring}"
            )
            filas.append(fila)
        elif recuperar:
            fila.tier_post_extraccion = "BAJA"
            fila.score_post_extraccion = score_ext
            fila.needs_review = True
            vis, par = _calcular_visible_y_parcial(fila, bloque, fuente)
            fila.visible_en_documento = vis
            fila.parcial_ocr = par
            extra_obs: List[str] = [
                "post_extraccion=aceptacion_extendida_score_insuficiente | tier=BAJA | "
                f"score_post={score_ext} | {dec.detalle_scoring}",
                FRASE_VISIBILIDAD_PROBATORIA,
            ]
            if _faltan_criticos_para_revisar(fila):
                extra_obs.append(TAG_ERROR_DETECTADO_DOCUMENTO_FUENTE)
            fila.observaciones += " | " + " | ".join(extra_obs)
            filas.append(fila)
            print(
                f"[BLOQUE_RECUPERADO_POST_EXTRACCION] {path.name} p.{page_index + 1} "
                f"bloque={bi + 1}/{len(bloques)} score_ext={score_ext} needs_review=1"
            )
        else:
            descartados.append(
                RegistroDescartado(
                    archivo_origen=path.name,
                    pagina=page_index + 1,
                    bloque_indice=bi + 1,
                    bloques_total=len(bloques),
                    clasificacion_pagina=clase,
                    motivo_descarte=dec.motivo,
                    score_extraccion=score_ext,
                    tier_si_no_veneno=_tier_post_score(fila, score_ext),
                    serie_numero_normalizado=fila.serie_numero_normalizado,
                    ruc=fila.ruc,
                    monto_total=fila.monto_total,
                    tipo_doc=fila.tipo,
                    chars_bloque=len(bloque),
                )
            )
            print(
                f"[BLOQUE_DESCARTADO_POST_EXTRACCION] {path.name} p.{page_index + 1} "
                f"bloque={bi + 1}/{len(bloques)} motivo={dec.motivo} "
                f"score_ext={score_ext}"
            )

    print(
        f"[SEGMENTO] {path.name} p.{page_index + 1}: "
        f"bloques_detectados={len(bloques)}, comprobantes_aceptados_post_clasif={len(filas)}, "
        f"bloques_descartados={len(descartados)} (clasificacion_pagina={clase})"
    )
    return filas, descartados, clase, len(bloques)


def escribir_excel(
    path_xlsx: Path,
    filas: List[FilaComprobante],
    descartados: List[RegistroDescartado],
) -> None:
    df_main = pd.DataFrame([{c: getattr(f, c) for c in COLUMNS} for f in filas], columns=COLUMNS)
    rows_d: List[Dict[str, object]] = []
    for d in descartados:
        rows_d.append(
            {
                "archivo_origen": d.archivo_origen,
                "pagina": d.pagina,
                "bloque_indice": d.bloque_indice,
                "bloques_total": d.bloques_total,
                "clasificacion_pagina": d.clasificacion_pagina,
                "motivo_descarte": d.motivo_descarte,
                "score_extraccion": d.score_extraccion,
                "tier_si_no_veneno": d.tier_si_no_veneno,
                "serie_numero_normalizado": d.serie_numero_normalizado,
                "ruc": d.ruc,
                "monto_total": d.monto_total,
                "tipo_doc": d.tipo_doc,
                "chars_bloque": d.chars_bloque,
            }
        )
    df_d = pd.DataFrame(rows_d, columns=COLUMNS_DESCARTADOS)
    with pd.ExcelWriter(path_xlsx, engine="openpyxl") as writer:
        df_main.to_excel(writer, sheet_name="comprobantes", index=False)
        df_d.to_excel(writer, sheet_name="bloques_descartados", index=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extrae comprobantes a comprobantes.xlsx")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Guarda texto extraído por página en subcarpeta debug_extraccion/",
    )
    args = parser.parse_args()

    if pd is None:
        print("ERROR: instala pandas y openpyxl: pip install pandas openpyxl", file=sys.stderr)
        return 1
    if not fitz:
        print("ERROR: instala PyMuPDF: pip install pymupdf", file=sys.stderr)
        return 1

    base = Path(__file__).resolve().parent
    salida = base / "comprobantes.xlsx"
    debug_dir = base / "debug_extraccion" if args.debug else None

    pdfs = sorted(base.glob("*.pdf"))
    n_pdfs = len(pdfs)
    print(f"[INFO] PDFs encontrados: {n_pdfs}")
    if n_pdfs == 0:
        print("[AVISO] No hay archivos *.pdf en la carpeta del script.")
        print("[INFO] Se generará comprobantes.xlsx con 0 filas.")
        escribir_excel(salida, [], [])
        print(f"[OK] Excel guardado (vacío): {salida}")
        print("---")
        print("PDFs procesados: 0")
        print("Total de páginas: 0")
        print("Páginas clasificadas como COMPROBANTE_REAL: 0")
        print("Registros generados en Excel: 0")
        print("Excel generado listo para validación profesional")
        return 0

    for i, p in enumerate(pdfs, 1):
        print(f"  ({i}) {p.name}")

    filas: List[FilaComprobante] = []
    todos_descartados: List[RegistroDescartado] = []
    vistos_norm: Set[Tuple[str, str, str, int]] = set()
    conteo_clase: Dict[str, int] = {
        "COMPROBANTE_REAL": 0,
        "SUNAT": 0,
        "ANEXO": 0,
        "DJ": 0,
        "OTRO": 0,
    }
    total_paginas = 0
    suma_bloques_detectados = 0
    registros_pre_dedup = 0

    for pdf_path in pdfs:
        doc = fitz.open(str(pdf_path))
        n = len(doc)
        doc.close()
        total_paginas += n
        for pi in range(n):
            filas_pag, desc_pag, clase, n_bloques = procesar_pagina(pdf_path, pi, debug_dir)
            conteo_clase[clase] = conteo_clase.get(clase, 0) + 1
            suma_bloques_detectados += n_bloques
            todos_descartados.extend(desc_pag)
            for fila in filas_pag:
                registros_pre_dedup += 1
                key = fila.clave_dedup_normalizada()
                if key in vistos_norm:
                    continue
                vistos_norm.add(key)
                filas.append(fila)

    n_comp = conteo_clase.get("COMPROBANTE_REAL", 0)
    print(f"[INFO] Páginas procesadas (total): {total_paginas}")
    print(
        "[INFO] Páginas por clasificación: "
        f"COMPROBANTE_REAL={conteo_clase.get('COMPROBANTE_REAL', 0)}, "
        f"SUNAT={conteo_clase.get('SUNAT', 0)}, "
        f"ANEXO={conteo_clase.get('ANEXO', 0)}, "
        f"DJ={conteo_clase.get('DJ', 0)}, "
        f"OTRO={conteo_clase.get('OTRO', 0)}"
    )
    print(f"[INFO] Páginas clasificadas como COMPROBANTE_REAL: {n_comp}")
    print(f"[INFO] Bloques detectados (suma en todas las páginas): {suma_bloques_detectados}")
    print(f"[INFO] Comprobantes extraídos (antes de deduplicar): {registros_pre_dedup}")
    print(f"[INFO] Registros en Excel hoja comprobantes (tras deduplicar): {len(filas)}")
    print(f"[INFO] Bloques registrados en hoja descartados: {len(todos_descartados)}")
    print("---")
    print(f"PDFs procesados: {n_pdfs}")
    print(f"Total de páginas: {total_paginas}")
    print(f"Páginas clasificadas como COMPROBANTE_REAL: {n_comp}")
    print(f"Bloques detectados (total acumulado): {suma_bloques_detectados}")
    print(f"Comprobantes extraídos antes de deduplicar: {registros_pre_dedup}")
    print(f"Registros hoja comprobantes: {len(filas)}")
    print(f"Registros hoja bloques_descartados: {len(todos_descartados)}")

    if len(filas) == 0:
        print("[AVISO] Ningún bloque clasificado como comprobante tras post-extracción.")
        print("        Revise hoja bloques_descartados y PDFs.")

    escribir_excel(salida, filas, todos_descartados)
    print(f"[OK] Excel guardado: {salida} ({len(filas)} filas)")
    if debug_dir:
        print(f"[DEBUG] Textos por página en: {debug_dir}")
    print("Excel generado listo para validación profesional")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
