#!/usr/bin/env python3
"""
Benchmark PaddleOCR-VL-1.5 via Docker (vLLM backend, sm_120).

Envía 5 páginas de expedientes reales al servidor PaddleOCR-VL en localhost:8118
y mide tiempo + campos extraídos.

Uso:
    python scripts/benchmark_paddleocr_vl_docker.py
"""

import base64
import json
import os
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
DPI = 300  # Resolución de renderizado

# 5 páginas diversas para benchmark
# Mezcla: facturas, boletas, comprobantes de diferentes expedientes
TEST_PAGES = [
    {
        "pdf": "data/expedientes/pruebas/viaticos_2026/comprobantes_revision/F001-881_PIRIS_41.pdf",
        "page": 0,
        "label": "Factura F001-881 (escaneada, restaurante)",
        "expected_fields": ["RUC", "serie_numero", "fecha", "total", "IGV"],
    },
    {
        "pdf": "data/expedientes/pruebas/viaticos_2026/comprobantes_revision/E001-5438_LopezCampos_60.pdf",
        "page": 0,
        "label": "Boleta E001-5438 (escaneada, hotel)",
        "expected_fields": ["RUC", "serie_numero", "fecha", "total", "IGV"],
    },
    {
        "pdf": "data/expedientes/pruebas/viaticos_2026/comprobantes_revision/E001-5447_LopezCampos_70.pdf",
        "page": 0,
        "label": "Boleta E001-5447 (escaneada)",
        "expected_fields": ["RUC", "serie_numero", "fecha", "total"],
    },
    {
        "pdf": "data/expedientes/pruebas/caja_chica_2026/OT2026-INT-0179550_CAJA_CHICA_JAQUELINE/20260212174439SUSTENTOLIQUIDACION03.pdf",
        "page": 0,
        "label": "Sustento liquidación caja chica (digital)",
        "expected_fields": ["fecha", "monto"],
    },
    {
        "pdf": "data/expedientes/pruebas/ordenes_servicio_2026/AEC2026-INT-0063838/20260202124424OS202627.pdf",
        "page": 0,
        "label": "Orden de servicio (digital)",
        "expected_fields": ["numero", "fecha", "monto"],
    },
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent


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
        "max_tokens": 2048,
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


def count_fields(text: str, expected: list[str]) -> dict:
    """Cuenta campos encontrados en el texto extraído."""
    text_lower = text.lower()
    found = {}
    # Patrones simples de detección
    import re

    if "RUC" in expected:
        rucs = re.findall(r'\b(10|20)\d{9}\b', text)
        found["RUC"] = rucs[0] if rucs else None

    if "serie_numero" in expected:
        series = re.findall(r'[A-Z]\d{3}-\d{3,8}', text)
        found["serie_numero"] = series[0] if series else None

    if "fecha" in expected:
        fechas = re.findall(r'\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}', text)
        found["fecha"] = fechas[0] if fechas else None

    if "total" in expected or "monto" in expected:
        montos = re.findall(r'[\d,]+\.\d{2}', text)
        key = "total" if "total" in expected else "monto"
        found[key] = montos[-1] if montos else None  # último monto suele ser el total

    if "IGV" in expected:
        igv_match = re.findall(r'(?:IGV|I\.G\.V).*?([\d,]+\.\d{2})', text, re.IGNORECASE)
        found["IGV"] = igv_match[0] if igv_match else None

    if "numero" in expected:
        nums = re.findall(r'(?:N[°ºo]|Nro)\s*[:\.]?\s*(\d[\d-]+)', text)
        found["numero"] = nums[0] if nums else None

    return found


def main():
    print("=" * 70)
    print("BENCHMARK: PaddleOCR-VL-1.5 via Docker (vLLM backend, sm_120)")
    print("=" * 70)
    print(f"Server: {SERVER_URL}")
    print(f"DPI: {DPI}")
    print(f"Páginas a evaluar: {len(TEST_PAGES)}")
    print()

    # Verificar servidor
    print("Verificando servidor...", end=" ")
    if not check_server():
        print("OFFLINE — abortando.")
        sys.exit(1)

    # Mostrar modelos
    r = requests.get(f"{SERVER_URL}/v1/models", timeout=5)
    print(f"OK — modelos: {json.dumps(r.json(), indent=2)}")
    print()

    results = []

    for i, test in enumerate(TEST_PAGES, 1):
        pdf_path = PROJECT_ROOT / test["pdf"]
        print(f"[{i}/5] {test['label']}")
        print(f"  PDF: {test['pdf']} (page {test['page']})")

        if not pdf_path.exists():
            print(f"  ⚠ PDF NO ENCONTRADO — saltando")
            results.append({"label": test["label"], "error": "PDF not found"})
            continue

        # Renderizar
        t0 = time.time()
        img_b64 = render_page_to_base64(str(pdf_path), test["page"], DPI)
        render_time = time.time() - t0
        img_size_kb = len(img_b64) * 3 / 4 / 1024
        print(f"  Render: {render_time:.1f}s, {img_size_kb:.0f} KB")

        # Enviar al servidor
        print(f"  Enviando a PaddleOCR-VL...", end=" ", flush=True)
        result = send_to_paddleocr_vl(img_b64)

        if result.get("error"):
            print(f"ERROR {result.get('status')}: {result['error'][:200]}")
            results.append({"label": test["label"], "error": result["error"][:500], "elapsed": result["elapsed"]})
            continue

        print(f"{result['elapsed']:.1f}s, {result['tokens_completion']} tokens")

        # Mostrar output (primeros 500 chars)
        content = result["content"]
        print(f"  Output ({len(content)} chars):")
        for line in content[:500].split("\n"):
            print(f"    {line}")
        if len(content) > 500:
            print(f"    ... ({len(content) - 500} chars más)")

        # Detectar campos
        fields = count_fields(content, test["expected_fields"])
        found_count = sum(1 for v in fields.values() if v is not None)
        total_expected = len(test["expected_fields"])
        print(f"  Campos: {found_count}/{total_expected} — {fields}")

        results.append({
            "label": test["label"],
            "elapsed": result["elapsed"],
            "tokens_prompt": result["tokens_prompt"],
            "tokens_completion": result["tokens_completion"],
            "content_length": len(content),
            "fields_found": found_count,
            "fields_expected": total_expected,
            "fields": fields,
            "render_time": render_time,
        })
        print()

    # Resumen
    print("=" * 70)
    print("RESUMEN")
    print("=" * 70)

    valid = [r for r in results if "error" not in r]
    if valid:
        avg_time = sum(r["elapsed"] for r in valid) / len(valid)
        avg_tokens = sum(r["tokens_completion"] for r in valid) / len(valid)
        total_fields = sum(r["fields_found"] for r in valid)
        total_expected = sum(r["fields_expected"] for r in valid)

        print(f"Páginas procesadas: {len(valid)}/{len(results)}")
        print(f"Tiempo promedio: {avg_time:.1f}s/página")
        print(f"Tokens promedio: {avg_tokens:.0f}/página")
        print(f"Campos extraídos: {total_fields}/{total_expected} ({100*total_fields/total_expected:.0f}%)")
        print()

        print("| Página | Tiempo | Tokens | Campos | Detalle |")
        print("|--------|--------|--------|--------|---------|")
        for r in valid:
            print(f"| {r['label'][:40]} | {r['elapsed']:.1f}s | {r['tokens_completion']} | {r['fields_found']}/{r['fields_expected']} | {r['fields']} |")
    else:
        print("NINGUNA página procesada exitosamente.")

    # Guardar JSON
    output_path = PROJECT_ROOT / "output" / "benchmark_paddleocr_vl_docker.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nResultados guardados en: {output_path}")


if __name__ == "__main__":
    main()
