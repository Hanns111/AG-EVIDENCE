#!/usr/bin/env python3
"""
Benchmark PaddleOCR-VL-1.5 via Docker (vLLM backend, sm_120).

Procesa TODAS las páginas del expediente DIRI2026-INT-0196314 (44 páginas)
contra el servidor PaddleOCR-VL en localhost:8118.

Mide: tiempo por página, campos extraídos (RUC, serie/número, fecha, monto, IGV).
Compara contra baseline qwen2.5vl:7b (pipeline v4.1.0).

Uso:
    python scripts/benchmark_paddleocr_vl_docker.py
"""

import base64
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

try:
    import fitz  # PyMuPDF
except ImportError:
    print("pip install pymupdf")
    sys.exit(1)

# ── Config ──────────────────────────────────────────────────────────────────
SERVER_URL = "http://localhost:8118"
DPI = 300
PROJECT_ROOT = Path(__file__).resolve().parent.parent

PDF_PATH = PROJECT_ROOT / "data/expedientes/pruebas/viaticos_2026/DIRI2026-INT-0196314_12.03.2026/2026031211199PV0086JOSEADRIANZENRENDICION.pdf"
SINAD = "DIRI2026-INT-0196314"

# Baseline qwen2.5vl:7b (pipeline v4.1.0, run_pipeline_diri.py)
BASELINE_QWEN = {
    "version": "qwen2.5vl:7b via Ollama v4.1.0",
    "total_pages": 44,
    "comprobantes": 19,
    "paginas_vlm": 13,
    "paginas_ocr_first": 8,  # resueltas sin VLM
    "duracion_total_s": 168,  # 2.8 min
    "vlm_promedio_s": 20.0,
    "json_fallos": 0,
    "vram_gb": 14.3,
    "model_size_gb": 6.0,
}


def render_page_to_base64(pdf_path: str, page_num: int, dpi: int = 300) -> str:
    """Renderiza una página de PDF como PNG base64."""
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    png_bytes = pix.tobytes("png")
    doc.close()
    return base64.b64encode(png_bytes).decode("utf-8")


def check_server() -> bool:
    """Verifica que el servidor esté listo."""
    try:
        r = requests.get(f"{SERVER_URL}/v1/models", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def send_to_paddleocr_vl(image_b64: str, prompt: str = "Read all the text in this image.") -> dict:
    """Envía imagen al servidor PaddleOCR-VL via API OpenAI-compatible."""
    payload = {
        "model": "PaddleOCR-VL-1.5-0.9B",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}"
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
        "max_tokens": 4096,
        "temperature": 0.0,
    }

    start = time.time()
    r = requests.post(
        f"{SERVER_URL}/v1/chat/completions",
        json=payload,
        timeout=300,
    )
    elapsed = time.time() - start

    if r.status_code != 200:
        return {"error": r.text, "elapsed": elapsed, "status": r.status_code}

    data = r.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage = data.get("usage", {})
    return {
        "content": content,
        "elapsed": elapsed,
        "tokens_prompt": usage.get("prompt_tokens", 0),
        "tokens_completion": usage.get("completion_tokens", 0),
        "status": 200,
    }


def extract_fields(text: str) -> dict:
    """Extrae campos clave de un comprobante desde texto OCR."""
    # Limpiar tokens de posición
    clean = re.sub(r'<\|LOC_\d+\|>', '', text)

    fields = {}

    # RUC (11 dígitos, empieza con 10 o 20)
    rucs = re.findall(r'\b((?:10|20)\d{9})\b', clean)
    # Filtrar RUCs conocidos del Estado (pagador)
    rucs_estado = {"20131370998", "20380795907", "20304634781"}
    rucs_proveedor = [r for r in rucs if r not in rucs_estado]
    fields["RUC"] = rucs_proveedor[0] if rucs_proveedor else (rucs[0] if rucs else None)

    # Serie/Número
    series = re.findall(r'([A-Z]\w?\d{2,3}-\d{3,8})', clean)
    fields["serie_numero"] = series[0] if series else None

    # Fecha (dd/mm/yyyy o dd-mm-yyyy o dd.mm.yyyy)
    fechas = re.findall(r'(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})', clean)
    fields["fecha"] = fechas[0] if fechas else None

    # Montos (S/ o números con decimales)
    montos = re.findall(r'S/?\.?\s*([\d,]+\.\d{2})', clean)
    if not montos:
        montos = re.findall(r'([\d,]+\.\d{2})', clean)
    fields["total"] = montos[-1] if montos else None

    # IGV
    igv_match = re.findall(r'(?:I\.?G\.?V\.?|IGV)[^0-9]*([\d,]+\.\d{2})', clean, re.IGNORECASE)
    fields["IGV"] = igv_match[0] if igv_match else None

    # Subtotal / Op. Gravada
    sub_match = re.findall(r'(?:OP\.?\s*GRAVADA|SUBTOTAL|VALOR\s*VENTA)[^0-9]*([\d,]+\.\d{2})', clean, re.IGNORECASE)
    fields["subtotal"] = sub_match[0] if sub_match else None

    return fields


def classify_page(text: str) -> str:
    """Clasifica el tipo de página basándose en el contenido."""
    clean = re.sub(r'<\|LOC_\d+\|>', '', text).lower()
    if re.search(r'factura\s*electr[oó]nica', clean):
        return "FACTURA"
    if re.search(r'boleta\s*de\s*venta', clean):
        return "BOLETA"
    if re.search(r'nota\s*de\s*cr[eé]dito', clean):
        return "NOTA_CREDITO"
    if re.search(r'boarding\s*pass|tarjeta\s*de\s*embarque', clean):
        return "BOARDING_PASS"
    if re.search(r'anexo\s*n', clean):
        return "ANEXO"
    if re.search(r'declaraci[oó]n\s*jurada', clean):
        return "DJ"
    if re.search(r'planilla\s*de\s*vi[aá]ticos', clean):
        return "PLANILLA"
    if re.search(r'consulta\s*de\s*validez|sunat', clean):
        return "VALIDEZ_SUNAT"
    if re.search(r'ticket|boleto', clean):
        return "TICKET"
    if re.search(r'ruc.*\d{11}', clean) and re.search(r'[\d,]+\.\d{2}', clean):
        return "COMPROBANTE"
    return "OTRO"


def main():
    print("=" * 70)
    print("BENCHMARK COMPLETO: PaddleOCR-VL-1.5 vs qwen2.5vl:7b")
    print(f"Expediente: {SINAD}")
    print("=" * 70)

    if not PDF_PATH.exists():
        print(f"ERROR: PDF no encontrado: {PDF_PATH}")
        sys.exit(1)

    doc = fitz.open(str(PDF_PATH))
    total_pages = len(doc)
    doc.close()
    print(f"PDF: {PDF_PATH.name} ({total_pages} páginas)")
    print(f"Server: {SERVER_URL}")
    print(f"DPI: {DPI}")
    print()

    # Verificar servidor
    print("Verificando servidor...", end=" ", flush=True)
    if not check_server():
        print("OFFLINE")
        sys.exit(1)
    print("OK")

    # Warmup (primera inferencia compila CUDA graphs)
    print("Warmup (primera inferencia)...", end=" ", flush=True)
    warmup_b64 = render_page_to_base64(str(PDF_PATH), 0, DPI)
    warmup_result = send_to_paddleocr_vl(warmup_b64)
    warmup_time = warmup_result.get("elapsed", 0)
    print(f"{warmup_time:.1f}s")
    print()

    # Procesar todas las páginas
    results = []
    t_total_start = time.time()

    for page_num in range(total_pages):
        t0 = time.time()
        img_b64 = render_page_to_base64(str(PDF_PATH), page_num, DPI)
        render_time = time.time() - t0

        result = send_to_paddleocr_vl(img_b64)

        if result.get("error"):
            print(f"  [p{page_num+1:02d}] ERROR: {result['error'][:100]}")
            results.append({
                "page": page_num + 1,
                "error": result["error"][:500],
                "elapsed": result["elapsed"],
            })
            continue

        content = result["content"]
        fields = extract_fields(content)
        page_type = classify_page(content)
        elapsed = result["elapsed"]

        has_ruc = fields["RUC"] is not None
        has_serie = fields["serie_numero"] is not None
        has_fecha = fields["fecha"] is not None
        has_total = fields["total"] is not None
        has_igv = fields["IGV"] is not None

        campos_found = sum([has_ruc, has_serie, has_fecha, has_total])
        tag = f"RUC={'Y' if has_ruc else '-'} SER={'Y' if has_serie else '-'} FEC={'Y' if has_fecha else '-'} TOT={'Y' if has_total else '-'} IGV={'Y' if has_igv else '-'}"

        print(
            f"  [p{page_num+1:02d}] {elapsed:5.1f}s | {result['tokens_completion']:4d}tok | "
            f"{page_type:<15} | {tag} | "
            f"{fields.get('serie_numero') or ''}"
        )

        results.append({
            "page": page_num + 1,
            "elapsed": elapsed,
            "render_time": render_time,
            "tokens_prompt": result["tokens_prompt"],
            "tokens_completion": result["tokens_completion"],
            "content_length": len(content),
            "page_type": page_type,
            "fields": fields,
            "campos_found": campos_found,
        })

    t_total = time.time() - t_total_start

    # ═══ RESUMEN ═══
    print()
    print("=" * 70)
    print("RESUMEN PaddleOCR-VL-1.5")
    print("=" * 70)

    valid = [r for r in results if "error" not in r]
    comprobantes = [r for r in valid if r["page_type"] in ("FACTURA", "BOLETA", "COMPROBANTE", "NOTA_CREDITO")]
    otros = [r for r in valid if r not in comprobantes]

    avg_time = sum(r["elapsed"] for r in valid) / len(valid) if valid else 0
    avg_tokens = sum(r["tokens_completion"] for r in valid) / len(valid) if valid else 0

    print(f"Páginas procesadas:    {len(valid)}/{total_pages}")
    print(f"Tiempo total:          {t_total:.1f}s ({t_total/60:.1f} min)")
    print(f"Tiempo promedio/pág:   {avg_time:.1f}s")
    print(f"Tokens promedio/pág:   {avg_tokens:.0f}")
    print(f"Warmup (primera):      {warmup_time:.1f}s")
    print()

    # Clasificación
    type_counts = {}
    for r in valid:
        t = r["page_type"]
        type_counts[t] = type_counts.get(t, 0) + 1
    print("Tipos de página detectados:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t:<20} {c}")
    print()

    # Campos en comprobantes
    if comprobantes:
        ruc_ok = sum(1 for r in comprobantes if r["fields"]["RUC"])
        serie_ok = sum(1 for r in comprobantes if r["fields"]["serie_numero"])
        fecha_ok = sum(1 for r in comprobantes if r["fields"]["fecha"])
        total_ok = sum(1 for r in comprobantes if r["fields"]["total"])
        igv_ok = sum(1 for r in comprobantes if r["fields"]["IGV"])
        n = len(comprobantes)

        print(f"Comprobantes detectados: {n}")
        print(f"  RUC:          {ruc_ok}/{n} ({100*ruc_ok/n:.0f}%)")
        print(f"  Serie/Número: {serie_ok}/{n} ({100*serie_ok/n:.0f}%)")
        print(f"  Fecha:        {fecha_ok}/{n} ({100*fecha_ok/n:.0f}%)")
        print(f"  Total:        {total_ok}/{n} ({100*total_ok/n:.0f}%)")
        print(f"  IGV:          {igv_ok}/{n} ({100*igv_ok/n:.0f}%)")
        print()

    # ═══ COMPARATIVA ═══
    print("=" * 70)
    print("COMPARATIVA: PaddleOCR-VL-1.5 vs qwen2.5vl:7b")
    print("=" * 70)

    bl = BASELINE_QWEN
    vram_bl = f"{bl['vram_gb']}GB"
    dur_bl = f"{bl['duracion_total_s']}s"
    dur_new = f"{t_total:.0f}s"
    speedup_total = f"{bl['duracion_total_s']/t_total:.1f}x" if t_total > 0 else "?"
    vlm_bl = f"{bl['vlm_promedio_s']}s"
    vlm_new = f"{avg_time:.1f}s"
    speedup_page = f"{bl['vlm_promedio_s']/avg_time:.1f}x" if avg_time > 0 else "?"

    hdr = f"  {'Métrica':<30} {'qwen2.5vl:7b':<20} {'PaddleOCR-VL-1.5':<20} {'Delta':<15}"
    sep = f"  {'-'*30} {'-'*20} {'-'*20} {'-'*15}"
    print(hdr)
    print(sep)
    print(f"  {'Modelo':<30} {'7B (6.0GB Q4)':<20} {'0.9B (1.89GB bf16)':<20} {'8x menor':<15}")
    print(f"  {'VRAM':<30} {vram_bl:<20} {'~4-5GB':<20} {'3x menor':<15}")
    print(f"  {'Tiempo total':<30} {dur_bl:<20} {dur_new:<20} {speedup_total:<15}")
    print(f"  {'Tiempo/pag (promedio)':<30} {vlm_bl:<20} {vlm_new:<20} {speedup_page:<15}")
    print(f"  {'Comprobantes detectados':<30} {bl['comprobantes']:<20} {len(comprobantes):<20}")
    print(f"  {'JSON nativo':<30} {'Si':<20} {'No (texto)':<20}")
    print(f"  {'Tokens posicionales':<30} {'No':<20} {'Si (<|LOC|>)':<20}")

    # ═══ DETALLE POR PÁGINA ═══
    print()
    print("=" * 70)
    print("DETALLE POR PÁGINA (comprobantes)")
    print("=" * 70)
    print(f"  {'Pág':>3} | {'Tipo':<15} | {'Tiempo':>6} | {'Tokens':>5} | {'RUC':<13} | {'Serie/Num':<15} | {'Fecha':<12} | {'Total':<10} | {'IGV':<8}")
    print(f"  {'-'*3}-+-{'-'*15}-+-{'-'*6}-+-{'-'*5}-+-{'-'*13}-+-{'-'*15}-+-{'-'*12}-+-{'-'*10}-+-{'-'*8}")
    for r in valid:
        f = r["fields"]
        print(
            f"  {r['page']:3d} | {r['page_type']:<15} | {r['elapsed']:5.1f}s | {r['tokens_completion']:5d} | "
            f"{(f['RUC'] or '-'):<13} | {(f['serie_numero'] or '-'):<15} | "
            f"{(f['fecha'] or '-'):<12} | {(f['total'] or '-'):<10} | {(f['IGV'] or '-'):<8}"
        )

    # Guardar JSON
    output = {
        "expediente": SINAD,
        "pdf": str(PDF_PATH.name),
        "total_pages": total_pages,
        "dpi": DPI,
        "warmup_s": warmup_time,
        "total_time_s": t_total,
        "avg_time_per_page_s": avg_time,
        "avg_tokens_per_page": avg_tokens,
        "comprobantes_detected": len(comprobantes),
        "type_counts": type_counts,
        "pages": results,
        "baseline": BASELINE_QWEN,
    }
    output_path = PROJECT_ROOT / "output" / "benchmark_paddleocr_vl_diri2026.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fp:
        json.dump(output, fp, indent=2, ensure_ascii=False, default=str)
    print(f"\nResultados guardados en: {output_path}")


if __name__ == "__main__":
    main()
