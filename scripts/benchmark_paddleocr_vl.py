# -*- coding: utf-8 -*-
"""
Benchmark: PaddleOCR-VL-1.5 vs Pipeline actual (qwen2.5vl:7b)
==============================================================
ADR-012: Evaluar PaddleOCR-VL-1.5 como reemplazo del VLM actual.

Métricas:
  - Tiempo por página (s)
  - Campos extraídos: RUC, fecha, serie/número, total, IGV, subtotal
  - Markdown output quality
  - GPU memory usage

Uso (desde WSL2):
    cd /mnt/c/Users/Hans/Proyectos/AG-EVIDENCE
    python scripts/benchmark_paddleocr_vl.py

Versión: 1.0.0
Fecha: 2026-03-24
"""

import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

# Proyecto root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Expediente de referencia
EXPEDIENTE_DIR = (
    PROJECT_ROOT
    / "data"
    / "expedientes"
    / "pruebas"
    / "viaticos_2026"
    / "DIRI2026-INT-0196314_12.03.2026"
)
RENDICION_PDF = EXPEDIENTE_DIR / "2026031211199PV0086JOSEADRIANZENRENDICION.pdf"

# Output
OUTPUT_DIR = PROJECT_ROOT / "output" / "benchmark_adr012"


@dataclass
class PageResult:
    """Resultado de una página individual."""

    page_num: int
    time_seconds: float
    markdown_length: int
    fields_found: Dict[str, Optional[str]] = field(default_factory=dict)
    raw_markdown: str = ""


@dataclass
class BenchmarkResult:
    """Resultado completo del benchmark."""

    model_name: str
    pdf_file: str
    total_pages: int
    pages_processed: int
    total_time_seconds: float
    avg_time_per_page: float
    model_load_time: float
    gpu_memory_gb: float
    page_results: List[PageResult] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ==============================================================================
# Extracción de campos desde Markdown
# ==============================================================================

# Patrones para campos de comprobantes peruanos
FIELD_PATTERNS = {
    "ruc": [
        r"R\.?U\.?C\.?\s*:?\s*(\d{11})",
        r"(\d{11})",  # fallback: cualquier secuencia de 11 dígitos
    ],
    "fecha": [
        r"(?:FECHA|F\.\s*EMISI[OÓ]N|FECHA\s*DE\s*EMISI[OÓ]N)\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
    ],
    "serie_numero": [
        r"([FBE]\d{3}-\d+)",
        r"(F\w+-\d+)",
    ],
    "total": [
        r"(?:TOTAL|IMPORTE\s*TOTAL|OP\.\s*GRAVADA)\s*:?\s*S/\.?\s*([\d,]+\.?\d*)",
        r"(?:TOTAL)\s*:?\s*([\d,]+\.\d{2})",
    ],
    "igv": [
        r"(?:I\.?G\.?V\.?|IGV\s*18%?)\s*:?\s*S/\.?\s*([\d,]+\.?\d*)",
    ],
    "subtotal": [
        r"(?:SUB\s*TOTAL|SUBTOTAL|VALOR\s*VENTA)\s*:?\s*S/\.?\s*([\d,]+\.?\d*)",
    ],
}


def extract_fields(markdown: str) -> Dict[str, Optional[str]]:
    """Extrae campos de comprobante desde texto markdown."""
    fields = {}
    for field_name, patterns in FIELD_PATTERNS.items():
        found = None
        for pattern in patterns:
            match = re.search(pattern, markdown, re.IGNORECASE)
            if match:
                found = match.group(1).strip()
                break
        fields[field_name] = found
    return fields


# ==============================================================================
# Benchmark PaddleOCR-VL-1.5
# ==============================================================================


def benchmark_paddleocr_vl(
    pdf_path: Path,
    max_pages: Optional[int] = None,
) -> BenchmarkResult:
    """Ejecuta benchmark de PaddleOCR-VL-1.5 sobre un PDF."""
    import paddle
    from paddleocr import PaddleOCRVL

    print(f"\n{'='*60}")
    print("BENCHMARK: PaddleOCR-VL-1.5 (0.9B)")
    print(f"{'='*60}")
    print(f"PDF: {pdf_path.name}")
    print(f"GPU: {paddle.device.cuda.get_device_name(0)}")
    print(f"VRAM total: ~24 GB")

    # Load model
    print("\nLoading model...")
    t_load_start = time.time()
    model = PaddleOCRVL(pipeline_version="v1.5")
    t_load_end = time.time()
    load_time = t_load_end - t_load_start
    print(f"Model loaded in {load_time:.1f}s")

    # Count pages
    import fitz

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    doc.close()

    pages_to_process = min(total_pages, max_pages) if max_pages else total_pages
    print(f"Pages: {total_pages} total, processing {pages_to_process}")

    # Process pages
    page_results = []
    total_start = time.time()

    for i, result in enumerate(model.predict(str(pdf_path))):
        page_time = time.time() - (
            total_start if i == 0 else page_results[-1].time_seconds + total_start
        )

        # Extract markdown
        if isinstance(result, dict):
            md = result.get("markdown", "")
        else:
            md = getattr(result, "markdown", "")
            if not md and hasattr(result, "text"):
                md = str(result.text)

        # Extract fields
        fields = extract_fields(md)
        fields_count = sum(1 for v in fields.values() if v is not None)

        page_result = PageResult(
            page_num=i + 1,
            time_seconds=round(time.time() - total_start, 2),
            markdown_length=len(md),
            fields_found=fields,
            raw_markdown=md[:2000],  # Truncate for storage
        )
        page_results.append(page_result)

        print(
            f"  Page {i+1:2d}/{pages_to_process}: "
            f"{page_result.time_seconds:6.1f}s cumulative | "
            f"md={len(md):5d} chars | "
            f"fields={fields_count}/6 | "
            f"{', '.join(f'{k}={v}' for k, v in fields.items() if v)}"
        )

        if i + 1 >= pages_to_process:
            break

    total_time = time.time() - total_start
    gpu_mem = paddle.device.cuda.max_memory_allocated(0) / 1e9

    avg_time = total_time / len(page_results) if page_results else 0

    print(f"\n{'─'*60}")
    print(f"Total time: {total_time:.1f}s ({len(page_results)} pages)")
    print(f"Avg time/page: {avg_time:.1f}s")
    print(f"GPU memory peak: {gpu_mem:.2f} GB")

    return BenchmarkResult(
        model_name="PaddleOCR-VL-1.5 (0.9B)",
        pdf_file=pdf_path.name,
        total_pages=total_pages,
        pages_processed=len(page_results),
        total_time_seconds=round(total_time, 2),
        avg_time_per_page=round(avg_time, 2),
        model_load_time=round(load_time, 2),
        gpu_memory_gb=round(gpu_mem, 2),
        page_results=page_results,
    )


# ==============================================================================
# Main
# ==============================================================================


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not RENDICION_PDF.exists():
        print(f"ERROR: PDF not found: {RENDICION_PDF}")
        sys.exit(1)

    # Run benchmark — process first 10 pages for speed
    result = benchmark_paddleocr_vl(RENDICION_PDF, max_pages=10)

    # Save results
    output_file = OUTPUT_DIR / "benchmark_paddleocr_vl_1.5.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(asdict(result), f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {output_file}")

    # Summary comparison with current pipeline
    print(f"\n{'='*60}")
    print("COMPARISON vs CURRENT PIPELINE (qwen2.5vl:7b via Ollama)")
    print(f"{'='*60}")
    print(f"{'Metric':<30} {'Current':>15} {'PaddleOCR-VL':>15}")
    print(f"{'─'*60}")
    print(f"{'Model size':<30} {'7B':>15} {'0.9B':>15}")
    print(
        f"{'Avg time/page':<30} {'~28s':>15} {f'{result.avg_time_per_page:.1f}s':>15}"
    )
    print(
        f"{'Total ({result.pages_processed} pages)':<30} {f'~{result.pages_processed * 28}s':>15} {f'{result.total_time_seconds:.0f}s':>15}"
    )
    print(f"{'GPU memory':<30} {'~14 GB':>15} {f'{result.gpu_memory_gb:.1f} GB':>15}")
    print(f"{'Model load':<30} {'~5s':>15} {f'{result.model_load_time:.0f}s':>15}")

    # Field extraction summary
    total_fields = 0
    found_fields = 0
    for pr in result.page_results:
        for v in pr.fields_found.values():
            total_fields += 1
            if v is not None:
                found_fields += 1

    pct = (found_fields / total_fields * 100) if total_fields > 0 else 0
    print(f"\nFields extracted: {found_fields}/{total_fields} ({pct:.0f}%)")


if __name__ == "__main__":
    main()
