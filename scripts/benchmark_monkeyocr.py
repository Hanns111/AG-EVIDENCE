#!/usr/bin/env python3
"""
Benchmark: MonkeyOCR-pro-1.2B vs qwen3-vl:8b (via Ollama)
==========================================================
ADR-011 Nivel 4: evaluar modelo documental especializado.

Usa 5 páginas imagen del expediente DIRI2026-INT-0196314
para comparar tiempo y calidad de extracción.

Requisitos:
- MonkeyOCR instalado en /home/hans/tools/monkeyocr_env
- Ollama corriendo con qwen3-vl:8b
- Imágenes en output/benchmark_monkeyocr/page_*.png
"""

import json
import os
import re
import sys
import time

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

BENCHMARK_DIR = "output/benchmark_monkeyocr"
PAGES = [21, 24, 32, 34, 37]
MONKEYOCR_DIR = "/home/hans/tools/MonkeyOCR"
MONKEYOCR_ENV = "/home/hans/tools/monkeyocr_env"

# Campos que buscamos en la salida de cada motor
FIELDS_REGEX = {
    "ruc": re.compile(r"(\d{11})"),
    "fecha": re.compile(r"(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})"),
    "serie_numero": re.compile(r"([FBEP]\w{0,2}\d{2,3})\s*[-–]\s*(\d{3,10})", re.IGNORECASE),
    "total": re.compile(r"(?:TOTAL|IMPORTE)\s*[:.]?\s*S/?\.?\s*([\d,]+\.\d{2})", re.IGNORECASE),
}


def extract_fields_from_text(text):
    """Extrae campos estructurados del texto usando regex."""
    fields = {}
    m = FIELDS_REGEX["ruc"].search(text)
    if m:
        fields["ruc"] = m.group(1)
    m = FIELDS_REGEX["fecha"].search(text)
    if m:
        fields["fecha"] = m.group(1)
    m = FIELDS_REGEX["serie_numero"].search(text)
    if m:
        fields["serie_numero"] = f"{m.group(1)}-{m.group(2)}"
    m = FIELDS_REGEX["total"].search(text)
    if m:
        fields["total"] = m.group(1).replace(",", "")
    return fields


# ============================================================================
# BENCHMARK MonkeyOCR
# ============================================================================


def run_monkeyocr_benchmark():
    """Ejecuta MonkeyOCR sobre las 5 páginas."""
    print("\n" + "=" * 70)
    print("BENCHMARK: MonkeyOCR-pro-1.2B")
    print("=" * 70)

    results = []
    for pg in PAGES:
        img_path = os.path.join(BENCHMARK_DIR, f"page_{pg}.png")
        out_dir = os.path.join(BENCHMARK_DIR, f"monkey_p{pg}")
        os.makedirs(out_dir, exist_ok=True)

        print(f"\n  Procesando página {pg}...")
        t0 = time.perf_counter()

        # Ejecutar MonkeyOCR parse.py sobre la imagen
        cmd = (
            f"source {MONKEYOCR_ENV}/bin/activate && "
            f"cd {MONKEYOCR_DIR} && "
            f"python parse.py {os.path.abspath(img_path)} -o {os.path.abspath(out_dir)} "
            f"2>&1"
        )
        import subprocess

        proc = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True,
            timeout=300,
            env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"},
        )
        elapsed = time.perf_counter() - t0

        # Leer output markdown
        md_files = [f for f in os.listdir(out_dir) if f.endswith(".md")]
        text = ""
        if md_files:
            with open(os.path.join(out_dir, md_files[0])) as f:
                text = f.read()

        # Leer JSON si existe
        json_files = [f for f in os.listdir(out_dir) if f.endswith(".json")]
        json_data = None
        if json_files:
            with open(os.path.join(out_dir, json_files[0])) as f:
                json_data = json.load(f)

        fields = extract_fields_from_text(text)
        n_chars = len(text)

        result = {
            "page": pg,
            "time_s": round(elapsed, 1),
            "chars": n_chars,
            "fields": fields,
            "text_preview": text[:300].replace("\n", " "),
            "error": proc.stderr[-200:] if proc.returncode != 0 else None,
        }
        results.append(result)

        status = "OK" if n_chars > 0 else "EMPTY"
        print(f"    [{status}] {elapsed:.1f}s | {n_chars} chars | fields: {fields}")

    return results


# ============================================================================
# BENCHMARK qwen3-vl:8b (via Ollama)
# ============================================================================


def run_qwen_benchmark():
    """Ejecuta qwen3-vl:8b sobre las 5 páginas via Ollama."""
    print("\n" + "=" * 70)
    print("BENCHMARK: qwen3-vl:8b (via Ollama)")
    print("=" * 70)

    import base64
    import urllib.request

    results = []
    for pg in PAGES:
        img_path = os.path.join(BENCHMARK_DIR, f"page_{pg}.png")
        print(f"\n  Procesando página {pg}...")

        # Leer imagen como base64
        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        prompt = (
            "Extrae los datos de este comprobante de pago peruano en formato JSON. "
            "Campos: ruc_emisor, razon_social, fecha_emision, serie, numero, "
            "subtotal, igv, importe_total. Si no puedes leer un campo, pon null."
        )

        payload = json.dumps(
            {
                "model": "qwen3-vl:8b",
                "prompt": prompt,
                "images": [img_b64],
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 4096,
                    "num_ctx": 8192,
                },
            }
        ).encode("utf-8")

        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            elapsed = time.perf_counter() - t0
            text = data.get("response", "")
        except Exception as e:
            elapsed = time.perf_counter() - t0
            text = ""
            print(f"    ERROR: {e}")

        fields = extract_fields_from_text(text)
        n_chars = len(text)

        result = {
            "page": pg,
            "time_s": round(elapsed, 1),
            "chars": n_chars,
            "fields": fields,
            "text_preview": text[:300].replace("\n", " "),
        }
        results.append(result)

        status = "OK" if n_chars > 0 else "EMPTY"
        print(f"    [{status}] {elapsed:.1f}s | {n_chars} chars | fields: {fields}")

    return results


# ============================================================================
# COMPARACIÓN
# ============================================================================


def compare_results(monkey_results, qwen_results):
    """Imprime comparación lado a lado."""
    print("\n" + "=" * 70)
    print("COMPARACIÓN: MonkeyOCR-pro-1.2B vs qwen3-vl:8b")
    print("=" * 70)

    print(
        f"\n  {'Pág':<5} {'MonkeyOCR t(s)':<16} {'qwen3-vl t(s)':<16} "
        f"{'Monkey campos':<16} {'Qwen campos':<16} {'Speedup':<10}"
    )
    print(f"  {'-' * 5} {'-' * 16} {'-' * 16} {'-' * 16} {'-' * 16} {'-' * 10}")

    total_monkey = 0
    total_qwen = 0
    total_monkey_fields = 0
    total_qwen_fields = 0

    for mr, qr in zip(monkey_results, qwen_results):
        speedup = qr["time_s"] / mr["time_s"] if mr["time_s"] > 0 else 0
        n_mf = len(mr["fields"])
        n_qf = len(qr["fields"])
        print(
            f"  p{mr['page']:<4} {mr['time_s']:<16.1f} {qr['time_s']:<16.1f} "
            f"{n_mf:<16} {n_qf:<16} {speedup:<10.1f}x"
        )
        total_monkey += mr["time_s"]
        total_qwen += qr["time_s"]
        total_monkey_fields += n_mf
        total_qwen_fields += n_qf

    print(f"  {'-' * 5} {'-' * 16} {'-' * 16} {'-' * 16} {'-' * 16} {'-' * 10}")
    avg_monkey = total_monkey / len(monkey_results)
    avg_qwen = total_qwen / len(qwen_results)
    speedup_total = total_qwen / total_monkey if total_monkey > 0 else 0

    print(
        f"  {'TOTAL':<5} {total_monkey:<16.1f} {total_qwen:<16.1f} "
        f"{total_monkey_fields:<16} {total_qwen_fields:<16} {speedup_total:<10.1f}x"
    )
    print(f"  {'PROM':<5} {avg_monkey:<16.1f} {avg_qwen:<16.1f}")

    print("\n  Resumen:")
    print(
        f"    MonkeyOCR: {total_monkey:.1f}s total, {avg_monkey:.1f}s/pág, "
        f"{total_monkey_fields} campos encontrados"
    )
    print(
        f"    qwen3-vl:  {total_qwen:.1f}s total, {avg_qwen:.1f}s/pág, "
        f"{total_qwen_fields} campos encontrados"
    )
    print(f"    Speedup MonkeyOCR vs qwen3-vl: {speedup_total:.1f}x más rápido")

    # Detalle de campos por página
    print("\n  Detalle de campos extraídos:")
    for mr, qr in zip(monkey_results, qwen_results):
        print(f"\n    Página {mr['page']}:")
        print(f"      MonkeyOCR: {mr['fields']}")
        print(f"      qwen3-vl:  {qr['fields']}")

    return {
        "monkey_total_s": total_monkey,
        "qwen_total_s": total_qwen,
        "monkey_avg_s": avg_monkey,
        "qwen_avg_s": avg_qwen,
        "speedup": speedup_total,
        "monkey_fields": total_monkey_fields,
        "qwen_fields": total_qwen_fields,
    }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("ADR-011 Nivel 4: Benchmark MonkeyOCR-pro-1.2B vs qwen3-vl:8b")
    print("Expediente: DIRI2026-INT-0196314")
    print(f"Páginas benchmark: {PAGES}")
    print("=" * 70)

    # MonkeyOCR benchmark — DESCARTADO
    # MonkeyOCR-pro-1.2B no es viable en RTX 5090 Laptop (Blackwell sm_120):
    # - PyTorch 2.5.1 cu124 no soporta sm_120 (necesita nightly)
    # - Requiere PaddlePaddle (paddlex) que tampoco soporta sm_120 estándar
    # - Stack de dependencias complejo: PyTorch + PaddlePaddle + lmdeploy + paddlex
    # - Conflictos de versiones (numpy<2, PyMuPDF<=1.24.14, transformers==4.51.0)
    # Resultado: DESCARTADO para RTX 5090. Reevaluar cuando PyTorch soporte sm_120.
    print("\n[NOTA] MonkeyOCR-pro-1.2B DESCARTADO para RTX 5090 (sm_120).")
    print("  PyTorch 2.5.1 cu124 no soporta Blackwell. Necesita nightly builds.")
    print("  Ejecutando solo benchmark qwen3-vl:8b...\n")

    qwen_results = run_qwen_benchmark()

    print("\n" + "=" * 70)
    print("RESULTADO: solo qwen3-vl:8b (MonkeyOCR incompatible con hw)")
    print("=" * 70)
    total_time = sum(r["time_s"] for r in qwen_results)
    avg_time = total_time / len(qwen_results)
    total_fields = sum(len(r["fields"]) for r in qwen_results)
    print(f"  Total: {total_time:.1f}s, Promedio: {avg_time:.1f}s/pág")
    print(f"  Campos extraídos: {total_fields}")
    for r in qwen_results:
        print(f"    p{r['page']}: {r['time_s']:.1f}s | {r['fields']}")

    # Guardar resultados JSON
    output = {
        "benchmark": "ADR-011 Nivel 4",
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "pages": PAGES,
        "monkeyocr": {
            "status": "DESCARTADO",
            "reason": "RTX 5090 sm_120 incompatible con PyTorch 2.5.1 cu124",
            "action": "Reevaluar cuando PyTorch nightly soporte sm_120",
        },
        "qwen3_vl": qwen_results,
    }
    out_path = os.path.join(BENCHMARK_DIR, "benchmark_results.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResultados guardados en: {out_path}")
