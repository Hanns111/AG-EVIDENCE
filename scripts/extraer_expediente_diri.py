#!/usr/bin/env python3
"""
Extraer texto completo del expediente DIRI2026-INT-0068815.
- Páginas con texto embebido: PyMuPDF directo
- Páginas solo imagen: PaddleOCR PP-OCRv5 GPU
"""

import json
import os
import sys

import fitz

BASE = "/mnt/c/Users/Hans/Proyectos/AG-EVIDENCE/data/expedientes/pruebas/viaticos_2026/DIRI2026-INT-0068815"
OUTPUT = "/mnt/c/Users/Hans/Proyectos/AG-EVIDENCE/data/expedientes/pruebas/viaticos_2026/DIRI2026-INT-0068815/extraccion"

os.makedirs(OUTPUT, exist_ok=True)

# Intentar importar PaddleOCR
try:
    sys.path.insert(0, "/mnt/c/Users/Hans/Proyectos/AG-EVIDENCE")
    from src.ocr.core import ejecutar_ocr

    HAS_OCR = True
    print("[OK] PaddleOCR importado")
except Exception as e:
    HAS_OCR = False
    print(f"[WARN] PaddleOCR no disponible: {e}")
    print("       Páginas imagen se marcarán como pendientes OCR")

resultados = {}

for pdf_name in sorted(os.listdir(BASE)):
    if not pdf_name.lower().endswith(".pdf"):
        continue

    pdf_path = os.path.join(BASE, pdf_name)
    doc = fitz.open(pdf_path)
    short_name = "PV" if "PIURA" in pdf_name.upper() else "RENDICION"

    print(f"\n{'=' * 70}")
    print(f"Procesando: {short_name} ({pdf_name})")
    print(f"Páginas: {len(doc)}")
    print(f"{'=' * 70}")

    pdf_result = {"archivo": pdf_name, "tipo": short_name, "paginas": len(doc), "contenido": []}

    for i, page in enumerate(doc):
        page_num = i + 1
        text = page.get_text().strip()
        metodo = "pymupdf"

        if len(text) < 50:
            # Página imagen — intentar OCR
            metodo = "ocr_pendiente"
            if HAS_OCR:
                try:
                    import io as _io

                    from PIL import Image as PILImage

                    # Renderizar página como imagen para OCR
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    pil_img = PILImage.open(_io.BytesIO(img_bytes))

                    # Guardar imagen para referencia
                    img_path = os.path.join(OUTPUT, f"{short_name}_p{page_num:02d}.png")
                    pil_img.save(img_path)

                    resultado_ocr = ejecutar_ocr(pil_img, lang="spa")
                    if resultado_ocr and resultado_ocr.get("texto_completo"):
                        text = resultado_ocr["texto_completo"]
                        metodo = "paddleocr_gpu"
                    elif resultado_ocr and isinstance(resultado_ocr, dict):
                        # Buscar texto en la estructura del resultado
                        text_parts = []
                        for key in ["texto_completo", "text", "resultado"]:
                            if key in resultado_ocr and resultado_ocr[key]:
                                text_parts.append(str(resultado_ocr[key]))
                        if not text_parts and "lineas" in resultado_ocr:
                            for linea in resultado_ocr["lineas"]:
                                if hasattr(linea, "texto"):
                                    text_parts.append(linea.texto)
                                elif isinstance(linea, dict) and "texto" in linea:
                                    text_parts.append(linea["texto"])
                        text = (
                            "\n".join(text_parts)
                            if text_parts
                            else f"[OCR sin texto - p{page_num}]"
                        )
                        metodo = "paddleocr_gpu" if text_parts else "ocr_vacio"
                    else:
                        text = f"[OCR sin resultado - página {page_num}]"
                        metodo = "ocr_vacio"
                except Exception as e:
                    text = f"[Error OCR: {e}]"
                    metodo = "ocr_error"
                    import traceback

                    traceback.print_exc()

        page_data = {"pagina": page_num, "metodo": metodo, "caracteres": len(text), "texto": text}
        pdf_result["contenido"].append(page_data)

        # Mostrar resumen por página
        preview = text[:100].replace("\n", " | ") if text else "(vacio)"
        status = "✓" if metodo == "pymupdf" else ("🔍" if "ocr" in metodo else "⚠")
        print(f"  p{page_num:02d} [{metodo:15s}] {len(text):5d} chars | {preview}...")

    doc.close()
    resultados[short_name] = pdf_result

# Guardar resultado completo
output_json = os.path.join(OUTPUT, "extraccion_completa.json")
with open(output_json, "w", encoding="utf-8") as f:
    json.dump(resultados, f, ensure_ascii=False, indent=2)

# Guardar texto plano concatenado para revisión
for key, data in resultados.items():
    txt_path = os.path.join(OUTPUT, f"{key}_texto_completo.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        for page in data["contenido"]:
            f.write(f"\n{'=' * 60}\n")
            f.write(f"PAGINA {page['pagina']} [{page['metodo']}]\n")
            f.write(f"{'=' * 60}\n")
            f.write(page["texto"])
            f.write("\n")

print(f"\n{'=' * 70}")
print("RESUMEN")
print(f"{'=' * 70}")
for key, data in resultados.items():
    total_chars = sum(p["caracteres"] for p in data["contenido"])
    metodos = {}
    for p in data["contenido"]:
        m = p["metodo"]
        metodos[m] = metodos.get(m, 0) + 1
    print(f"{key}: {data['paginas']} páginas, {total_chars} caracteres")
    for m, count in metodos.items():
        print(f"  {m}: {count} páginas")

print(f"\nArchivos generados en: {OUTPUT}")
print("  - extraccion_completa.json")
for key in resultados:
    print(f"  - {key}_texto_completo.txt")
