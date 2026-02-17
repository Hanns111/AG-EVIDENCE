"""
Prueba Empirica de Extraccion OCR — Caja Chica N.0000003
OT2026-INT-0179550

Compara los datos extraidos por el pipeline OCR contra el ground truth
(datos verificados manualmente en generar_excel_caja_chica_003.py).

Objetivo: medir tasa de error real del pipeline antes de construir
frameworks de validacion.

Metodo:
1. Renderiza cada pagina de comprobante como imagen (PyMuPDF 300 DPI)
2. Ejecuta OCR (PaddleOCR + Tesseract fallback) en cada pagina
3. Busca campos clave en el texto OCR via regex
4. Compara contra ground truth
5. Genera tabla comparativa + metricas + JSON de resultados

NO modifica ningun modulo existente. Solo mide.
"""

import json
import re
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Agregar raiz al path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import fitz  # PyMuPDF

# Pipeline OCR del proyecto
from src.ocr.core import ejecutar_ocr, renderizar_pagina

# ============================================================
# CONFIGURACION
# ============================================================

PDF_PATH = ROOT / "data" / "expedientes" / "pruebas" / "caja_chica_2026" / \
    "OT2026-INT-0179550_CAJA_CHICA_JAQUELINE" / \
    "20260212174439SUSTENTOLIQUIDACION03.pdf"

OUTPUT_DIR = ROOT / "data" / "evaluacion"
OUTPUT_JSON = OUTPUT_DIR / "prueba_empirica_cc003.json"

DPI = 300  # Resolucion de renderizado

# ============================================================
# GROUND TRUTH — Datos verificados manualmente por Hans
# Fuente: scripts/generar_excel_caja_chica_003.py
# ============================================================

GROUND_TRUTH = [
    {
        "gasto": 1,
        "pagina": 6,
        "serie_numero": "F001-1488",
        "ruc": None,  # Marcado ILEGIBLE en ground truth
        "razon_social": "CORPORACION IMPRESIONA S.A.C.",
        "tipo": "Factura",
        "total": 19.00,
        "igv": None,  # No desglosado en ground truth
        "fecha": "06/02/2026",
    },
    {
        "gasto": 2,
        "pagina": 12,  # Corregido: pag 11 es email Outlook, factura esta en pag 12
        "serie_numero": "E001-530",
        "ruc": "20610827171",
        "razon_social": "ASERVNT PERU S.A.C.",
        "tipo": "Factura",
        "total": 424.80,
        "igv": 64.80,
        "fecha": "03/02/2026",
    },
    {
        "gasto": 3,
        "pagina": 15,  # Corregido: keyword encontrado en pag 15 no 16
        "serie_numero": "0015171",
        "ruc": None,  # No aplica (tasa municipal)
        "razon_social": "MUNICIPALIDAD DISTRITAL DE ATE",
        "tipo": "Recibo",
        "total": 50.70,
        "igv": None,
        "fecha": "05/02/2026",
    },
    {
        "gasto": 4,
        "pagina": 23,
        "serie_numero": "0000-002",
        "ruc": None,  # DJ, no tiene RUC
        "razon_social": "VARGAS DEL RIO, VERONICA GRACE",
        "tipo": "Declaracion Jurada",
        "total": 42.90,
        "igv": None,
        "fecha": "27/01/2026",
    },
    {
        "gasto": 5,
        "pagina": 31,
        "serie_numero": "F002-00008351",
        "ruc": "20604955498",
        "razon_social": "JH METALINOX S.A.C.",
        "tipo": "Factura",
        "total": 70.00,
        "igv": 10.68,
        "fecha": "30/01/2026",
    },
    {
        "gasto": 6,
        "pagina": 35,
        "serie_numero": "F001-7369",
        "ruc": None,  # Marcado ILEGIBLE en ground truth
        "razon_social": "COMERCIAL VICKI E.I.R.L.",
        "tipo": "Factura",
        "total": 95.00,
        "igv": 14.49,  # Estimado en ground truth
        "fecha": "07/02/2026",
    },
    {
        "gasto": 7,
        "pagina": 38,
        "serie_numero": "E001-1094",
        "ruc": "20609780451",
        "razon_social": "RAYPEC S.A.C.",
        "tipo": "Factura",
        "total": 35.00,
        "igv": 5.34,
        "fecha": "07/02/2026",
    },
    {
        "gasto": 8,
        "pagina": 42,
        "serie_numero": "F001-2192",
        "ruc": "20606697091",
        "razon_social": "D&D SOLUCIONES ELECTRICAS E.I.R.L.",
        "tipo": "Factura",
        "total": 252.00,
        "igv": 38.44,
        "fecha": "08/02/2026",
    },
    {
        "gasto": 9,
        "pagina": 51,
        "serie_numero": "E001-2892",
        "ruc": "10701855406",
        "razon_social": "GSO DIGITAL",
        "tipo": "Factura",
        "total": 36.00,
        "igv": 5.49,
        "fecha": "06/02/2026",
    },
    {
        "gasto": 10,
        "pagina": 58,
        "serie_numero": "FQ01-00569",
        "ruc": "20440493781",
        "razon_social": "ITTSA",
        "tipo": "Factura",
        "total": 55.00,
        "igv": 8.39,
        "fecha": "07/02/2026",
    },
    {
        "gasto": 11,
        "pagina": 63,
        "serie_numero": "F001-00032196",
        "ruc": "20664646143",
        "razon_social": "HAO YUN LAI LAI S.A.C.",
        "tipo": "Factura",
        "total": 171.50,
        "igv": 26.16,  # Estimado en ground truth
        "fecha": "05/02/2026",
    },
    {
        "gasto": 12,
        "pagina": 65,
        "serie_numero": "FD1-00021821",
        "ruc": None,  # Marcado ILEGIBLE parcialmente
        "razon_social": "GOLDATI S.A.C.",
        "tipo": "Factura",
        "total": 188.50,
        "igv": 28.75,  # Estimado en ground truth
        "fecha": "05/02/2026",
    },
    {
        "gasto": 13,
        "pagina": 70,  # 70-71 (2 constancias)
        "serie_numero": "260001715589",
        "ruc": "20131370998",  # RUC del MINEDU (pagador)
        "razon_social": "RENIEC",
        "tipo": "Constancia de Pago",
        "total": 1028.70,
        "igv": None,
        "fecha": "09/02/2026",
    },
    {
        "gasto": 14,
        "pagina": 83,
        "serie_numero": "FD15-00502949",
        "ruc": "20508565934",
        "razon_social": "COMPANIA WONG DISCOUNT S.A.C.",
        "tipo": "Factura",
        "total": 158.90,
        "igv": None,  # Ilegible en ground truth
        "fecha": "09/02/2026",
    },
    {
        "gasto": 15,
        "pagina": 88,
        "serie_numero": "E001-499",
        "ruc": "20610827171",
        "razon_social": "ASERVNT PERU S.A.C.",
        "tipo": "Factura",
        "total": 424.80,
        "igv": 64.80,
        "fecha": "03/02/2026",
    },
    {
        "gasto": 16,
        "pagina": 90,  # Corregido: keyword LESCANO encontrado en pag 90
        "serie_numero": "EB01-6",
        "ruc": "10073775006",
        "razon_social": "LESCANO HIDALGO MARIO ARTURO",
        "tipo": "Boleta De Venta",
        "total": 38.00,
        "igv": None,
        "fecha": "10/02/2026",
    },
]


# ============================================================
# FUNCIONES DE EXTRACCION DESDE TEXTO OCR
# ============================================================

def buscar_ruc(texto):
    """Busca un RUC (11 digitos empezando con 10 o 20) en el texto."""
    # Patron: 10 o 20 seguido de 9 digitos
    matches = re.findall(r'\b((?:10|20)\d{9})\b', texto)
    if matches:
        # Filtrar RUCs conocidos del MINEDU/pagador
        rucs_pagador = {"20304634781", "20131370998"}
        for m in matches:
            if m not in rucs_pagador:
                return m
        # Si solo encontro RUCs del pagador, retornar el primero
        return matches[0]
    return None


def buscar_serie_numero(texto):
    """Busca serie-numero de comprobante en el texto."""
    # Patrones comunes: F001-1488, E001-530, FQ01-569, FD15-502949, EB01-6
    patrones = [
        r'([A-Z]{1,4}\d{1,4}[-]\d{1,10})',  # F001-1488, FQ01-569
        r'([A-Z]\d{3}[-]\d+)',  # F001-1488
    ]
    for patron in patrones:
        matches = re.findall(patron, texto)
        if matches:
            return matches[0]
    return None


def buscar_total(texto):
    """Busca monto total en el texto OCR."""
    # Buscar "TOTAL" o "IMPORTE TOTAL" seguido de monto
    patrones = [
        r'TOTAL\s*S/?\.?\s*(\d+[.,]\d{2})',
        r'IMPORTE\s+TOTAL\s*:?\s*S/?\.?\s*(\d+[.,]\d{2})',
        r'TOTAL\s*:?\s*(\d+[.,]\d{2})',
        r'SON\s*:.*?(\d+[.,]\d{2})',
    ]
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            valor = match.group(1).replace(',', '.')
            try:
                return float(valor)
            except ValueError:
                continue
    return None


def buscar_igv(texto):
    """Busca monto IGV en el texto OCR."""
    patrones = [
        r'I\.?G\.?V\.?\s*(?:\(?18%?\)?)?\s*:?\s*S/?\.?\s*(\d+[.,]\d{2})',
        r'IGV\s*:?\s*(\d+[.,]\d{2})',
        r'I\.G\.V\.\s*(\d+[.,]\d{2})',
    ]
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            valor = match.group(1).replace(',', '.')
            try:
                return float(valor)
            except ValueError:
                continue
    return None


def buscar_fecha(texto):
    """Busca fecha de emision en el texto OCR."""
    patrones = [
        r'(\d{2}/\d{2}/\d{4})',
        r'(\d{2}-\d{2}-\d{4})',
        r'(\d{2}\.\d{2}\.\d{4})',
    ]
    for patron in patrones:
        matches = re.findall(patron, texto)
        if matches:
            return matches[0].replace('-', '/').replace('.', '/')
    return None


def buscar_razon_social(texto):
    """Busca razon social despues de RUC o en las primeras lineas."""
    # Buscar despues de "RAZON SOCIAL" o "DENOMINACION"
    match = re.search(
        r'(?:RAZ[OÓ]N\s+SOCIAL|DENOMINACI[OÓ]N)\s*:?\s*(.+)',
        texto, re.IGNORECASE
    )
    if match:
        return match.group(1).strip()[:60]
    return None


def normalizar_serie(serie):
    """Normaliza serie-numero para comparacion flexible."""
    if serie is None:
        return None
    # Quitar ceros de relleno: F002-00008351 -> F002-8351
    match = re.match(r'([A-Z]+\d*)-0*(\d+)', serie)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return serie


def comparar_campo(extraido, esperado, tipo="texto"):
    """Compara un campo extraido contra el esperado."""
    if esperado is None:
        # Ground truth es ILEGIBLE/None — no evaluamos
        return "SKIP_GT_NULL"
    if extraido is None:
        return "NO_EXTRAIDO"

    if tipo == "monto":
        try:
            ext = float(extraido)
            esp = float(esperado)
            if abs(ext - esp) < 0.02:  # Tolerancia de centavos
                return "MATCH"
            else:
                return "ERROR"
        except (ValueError, TypeError):
            return "ERROR"

    elif tipo == "serie":
        # Comparacion flexible de serie-numero
        ext_norm = normalizar_serie(str(extraido))
        esp_norm = normalizar_serie(str(esperado))
        if ext_norm == esp_norm:
            return "MATCH"
        # Verificar si uno contiene al otro
        if ext_norm and esp_norm:
            if ext_norm in esp_norm or esp_norm in ext_norm:
                return "MATCH_PARCIAL"
        return "ERROR"

    elif tipo == "ruc":
        ext_str = str(extraido).strip()
        esp_str = str(esperado).strip()
        if ext_str == esp_str:
            return "MATCH"
        return "ERROR"

    elif tipo == "fecha":
        # Comparar fechas normalizadas
        ext_str = str(extraido).replace('-', '/').replace('.', '/')
        esp_str = str(esperado).replace('-', '/').replace('.', '/')
        if ext_str == esp_str:
            return "MATCH"
        return "ERROR"

    else:  # texto generico
        ext_str = str(extraido).upper().strip()
        esp_str = str(esperado).upper().strip()
        if ext_str == esp_str:
            return "MATCH"
        if esp_str in ext_str or ext_str in esp_str:
            return "MATCH_PARCIAL"
        return "ERROR"


# ============================================================
# MOTOR PRINCIPAL
# ============================================================

def procesar_pagina(doc, pagina_num):
    """Renderiza una pagina y ejecuta OCR usando el pipeline formal.

    Usa renderizar_pagina() del pipeline (incluye _validar_dimensiones, Regla 2)
    y ejecutar_ocr() que espera un objeto Image.Image (PIL), NO una ruta string.
    """
    page_idx = pagina_num - 1  # fitz usa 0-indexed

    if page_idx < 0 or page_idx >= doc.page_count:
        return {"error": f"Pagina {pagina_num} fuera de rango (max {doc.page_count})"}

    # Usar renderizar_pagina() del pipeline formal (incluye validacion Regla 2)
    img = renderizar_pagina(PDF_PATH, pagina_num, dpi=DPI)

    if img is None:
        return {
            "texto": "",
            "confianza": 0.0,
            "motor": "error_renderizado",
            "pagina": pagina_num,
            "chars": 0,
        }

    # Ejecutar OCR del pipeline — img es Image.Image (PIL), NO ruta string
    resultado = ejecutar_ocr(img, lang="spa")

    texto = resultado.get("texto_completo", resultado.get("texto", ""))
    confianza = resultado.get("confianza_promedio", 0.0)
    motor = resultado.get("motor_ocr", "desconocido")

    return {
        "texto": texto,
        "confianza": confianza,
        "motor": motor,
        "pagina": pagina_num,
        "chars": len(texto),
    }


def ejecutar_prueba():
    """Ejecuta la prueba empirica completa."""
    print("=" * 80)
    print("PRUEBA EMPIRICA DE EXTRACCION OCR")
    print("Expediente: Caja Chica N.0000003 (OT2026-INT-0179550)")
    print(f"PDF: {PDF_PATH.name}")
    print(f"Ground Truth: 16 comprobantes de generar_excel_caja_chica_003.py")
    print(f"DPI: {DPI}")
    print("=" * 80)

    if not PDF_PATH.exists():
        print(f"\n[ERROR] PDF no encontrado: {PDF_PATH}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(PDF_PATH))
    print(f"\nPDF abierto: {doc.page_count} paginas (todas escaneadas)")

    resultados = []

    for gt in GROUND_TRUTH:
        gasto_num = gt["gasto"]
        pagina = gt["pagina"]

        print(f"\n--- Gasto #{gasto_num} (pag. {pagina}) ---")

        # Procesar pagina con OCR
        ocr_result = procesar_pagina(doc, pagina)

        if "error" in ocr_result:
            print(f"  ERROR: {ocr_result['error']}")
            resultados.append({
                "gasto": gasto_num,
                "pagina": pagina,
                "error": ocr_result["error"],
                "campos": {},
            })
            continue

        texto = ocr_result["texto"]
        confianza = ocr_result["confianza"]
        motor = ocr_result["motor"]

        print(f"  Motor: {motor}, Confianza: {confianza:.2f}, Chars: {ocr_result['chars']}")

        # Extraer campos del texto OCR
        ruc_ext = buscar_ruc(texto)
        serie_ext = buscar_serie_numero(texto)
        total_ext = buscar_total(texto)
        igv_ext = buscar_igv(texto)
        fecha_ext = buscar_fecha(texto)
        razon_ext = buscar_razon_social(texto)

        # Comparar contra ground truth
        campos = {
            "ruc": {
                "extraido": ruc_ext,
                "esperado": gt["ruc"],
                "resultado": comparar_campo(ruc_ext, gt["ruc"], "ruc"),
            },
            "serie_numero": {
                "extraido": serie_ext,
                "esperado": gt["serie_numero"],
                "resultado": comparar_campo(serie_ext, gt["serie_numero"], "serie"),
            },
            "total": {
                "extraido": total_ext,
                "esperado": gt["total"],
                "resultado": comparar_campo(total_ext, gt["total"], "monto"),
            },
            "igv": {
                "extraido": igv_ext,
                "esperado": gt["igv"],
                "resultado": comparar_campo(igv_ext, gt["igv"], "monto"),
            },
            "fecha": {
                "extraido": fecha_ext,
                "esperado": gt["fecha"],
                "resultado": comparar_campo(fecha_ext, gt["fecha"], "fecha"),
            },
        }

        # Imprimir resultado por campo
        for campo_nombre, campo_data in campos.items():
            status = campo_data["resultado"]
            icon = {"MATCH": "OK", "MATCH_PARCIAL": "~", "ERROR": "X",
                    "NO_EXTRAIDO": "-", "SKIP_GT_NULL": "?"}
            icon_str = icon.get(status, "?")
            print(f"  [{icon_str}] {campo_nombre:15s}: "
                  f"extraido={campo_data['extraido']!s:25s} "
                  f"esperado={campo_data['esperado']!s:25s} "
                  f"-> {status}")

        resultados.append({
            "gasto": gasto_num,
            "pagina": pagina,
            "motor": motor,
            "confianza": confianza,
            "chars": ocr_result["chars"],
            "campos": campos,
            "texto_ocr_primeras_200": texto[:200],
        })

    doc.close()

    # ============================================================
    # METRICAS
    # ============================================================
    print("\n" + "=" * 80)
    print("METRICAS FINALES")
    print("=" * 80)

    total_campos = 0
    campos_match = 0
    campos_match_parcial = 0
    campos_error = 0
    campos_no_extraido = 0
    campos_skip = 0
    errores_detalle = []

    for res in resultados:
        if "error" in res and "campos" not in res:
            continue
        for campo_nombre, campo_data in res.get("campos", {}).items():
            status = campo_data["resultado"]
            if status == "SKIP_GT_NULL":
                campos_skip += 1
                continue
            total_campos += 1
            if status == "MATCH":
                campos_match += 1
            elif status == "MATCH_PARCIAL":
                campos_match_parcial += 1
            elif status == "ERROR":
                campos_error += 1
                errores_detalle.append({
                    "gasto": res["gasto"],
                    "campo": campo_nombre,
                    "extraido": campo_data["extraido"],
                    "esperado": campo_data["esperado"],
                })
            elif status == "NO_EXTRAIDO":
                campos_no_extraido += 1

    evaluables = total_campos
    correctos = campos_match + campos_match_parcial
    precision = (correctos / evaluables * 100) if evaluables > 0 else 0

    print(f"\nTotal campos evaluados:     {evaluables}")
    print(f"Campos con GT null (skip):  {campos_skip}")
    print(f"Match exacto:              {campos_match}")
    print(f"Match parcial:             {campos_match_parcial}")
    print(f"Error (dato incorrecto):   {campos_error}")
    print(f"No extraido (vacio):       {campos_no_extraido}")
    print(f"\nPRECISION: {precision:.1f}% ({correctos}/{evaluables})")

    if errores_detalle:
        print(f"\nDETALLE DE ERRORES ({len(errores_detalle)}):")
        for err in errores_detalle:
            print(f"  Gasto #{err['gasto']:2d} | {err['campo']:15s} | "
                  f"extraido: {err['extraido']!s:25s} | "
                  f"esperado: {err['esperado']!s:25s}")

    # ============================================================
    # GUARDAR JSON
    # ============================================================
    output = {
        "prueba": "empirica_cc003",
        "expediente": "OT2026-INT-0179550",
        "tipo": "Caja Chica N.0000003",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pipeline_version": "OCR core v3.1.0",
        "dpi": DPI,
        "total_paginas_pdf": 112,
        "total_comprobantes": len(GROUND_TRUTH),
        "metodo_extraccion": "100% OCR (todas las paginas son imagenes escaneadas)",
        "metricas": {
            "total_campos_evaluados": evaluables,
            "campos_gt_null_skip": campos_skip,
            "match_exacto": campos_match,
            "match_parcial": campos_match_parcial,
            "error": campos_error,
            "no_extraido": campos_no_extraido,
            "precision_pct": round(precision, 1),
        },
        "errores": errores_detalle,
        "resultados_por_comprobante": resultados,
        "criterio_exito": {
            "meta_texto_embebido": ">=95% (no aplica, todo es escaneado)",
            "meta_escaneado": ">=85%",
            "resultado": "PASS" if precision >= 85 else "FAIL",
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nResultados guardados en: {OUTPUT_JSON}")
    print(f"\nVERDICTO: {'PASS' if precision >= 85 else 'FAIL'} "
          f"(meta: >=85% para escaneados, obtenido: {precision:.1f}%)")

    return output


if __name__ == "__main__":
    ejecutar_prueba()
