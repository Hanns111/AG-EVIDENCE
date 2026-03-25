# -*- coding: utf-8 -*-
"""
Diagnóstico OCR + page_classifier (solo lectura / consola).

No modifica el pipeline ni src/. Replica el paso de OCR del escribano
(renderizar_pagina + ejecutar_ocr) e imprime métricas por página.

Uso:
  python tools/diagnose_ocr_expediente.py "C:\\Users\\Hans\\Downloads\\CMPA2026-INT-0305757"
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.extraction.page_classifier import TipoPagina, clasificar_pagina


def _first_pdf(carpeta: Path) -> Path | None:
    pdfs = sorted(p for p in carpeta.iterdir() if p.suffix.lower() == ".pdf")
    return pdfs[0] if pdfs else None


def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: python tools/diagnose_ocr_expediente.py RUTA_CARPETA", file=sys.stderr)
        return 1

    carpeta = Path(sys.argv[1]).expanduser()
    if not carpeta.is_dir():
        print(f"ERROR: no es carpeta: {carpeta}", file=sys.stderr)
        return 1

    pdf = _first_pdf(carpeta)
    if pdf is None:
        print(f"ERROR: sin PDFs en {carpeta}", file=sys.stderr)
        return 1

    print("=" * 72)
    print(f"Carpeta: {carpeta}")
    print(f"Primer PDF: {pdf.name}")
    print("=" * 72)

    try:
        import fitz
    except ImportError:
        print("ERROR: PyMuPDF (fitz) no instalado.")
        return 1

    from src.ocr.core import ejecutar_ocr, renderizar_pagina

    doc = fitz.open(str(pdf))
    num_paginas = len(doc)
    doc.close()

    dpi = 200
    idioma = "spa"

    for page_num in range(1, num_paginas + 1):
        img = renderizar_pagina(pdf, page_num, dpi=dpi)
        texto = ""
        lineas: list = []
        motor = "none"
        err = ""

        if img is None:
            err = "No se pudo renderizar página"
        else:
            res = ejecutar_ocr(img, lang=idioma, trace_logger=None)
            texto = (res.get("texto_completo") or "").strip()
            lineas = res.get("lineas") or []
            motor = res.get("motor_ocr") or "none"
            if res.get("error"):
                err = str(res.get("error"))

        cl = clasificar_pagina(texto)
        tipo = cl.tipo.value if hasattr(cl.tipo, "value") else str(cl.tipo)
        n_lineas = len(lineas)
        longitud = len(texto)
        preview = texto[:300].replace("\n", " ") + ("…" if longitud > 300 else "")

        print()
        print(f"--- Página {page_num}/{num_paginas} ---")
        print(f"  longitud texto OCR: {longitud}")
        print(f"  motor: {motor}  |  líneas OCR: {n_lineas}")
        if err:
            print(f"  error OCR: {err}")
        print(f"  primeras 300 chars: {preview!r}")
        print(
            f"  page_classifier: tipo={tipo}  "
            f"score_sunat={cl.score_sunat}  score_comprobante={cl.score_comprobante}"
        )

        if page_num <= 2:
            print()
            print(f"  [DETALLE págs 1-2] Texto OCR completo (pág {page_num}):")
            print("-" * 40)
            print(texto if texto else "(vacío)")
            print("-" * 40)
            print(f"  clasificar_pagina -> tipo={tipo}, pasa_extraccion={cl.pasa_a_extraccion}")
            print(
                f"  señales: {cl.senales_activadas[:12]}{'…' if len(cl.senales_activadas) > 12 else ''}"
            )

    print()
    print("=" * 72)
    print(f"Total páginas procesadas: {num_paginas}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
