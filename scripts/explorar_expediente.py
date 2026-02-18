#!/usr/bin/env python3
"""Explorar PDFs de un expediente: páginas, texto embebido, preview."""
import fitz  # PyMuPDF
import os
import sys

base = sys.argv[1] if len(sys.argv) > 1 else '/mnt/c/Users/Hans/Proyectos/AG-EVIDENCE/data/expedientes/pruebas/viaticos_2026/DIRI2026-INT-0068815'

for f in sorted(os.listdir(base)):
    if not f.lower().endswith('.pdf'):
        continue
    path = os.path.join(base, f)
    doc = fitz.open(path)
    print(f'\n=== {f} ===')
    print(f'  Paginas: {len(doc)}')

    pages_with_text = 0
    pages_image_only = 0

    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if len(text) > 50:
            pages_with_text += 1
        else:
            pages_image_only += 1

        if i < 3 or i == len(doc) - 1:
            label = f'  p{i+1}'
            has = 'TEXTO' if len(text) > 50 else 'IMAGEN'
            preview = text[:120].replace('\n', ' | ') if text else '(vacio)'
            print(f'{label} [{has}]: {preview}')

    print(f'  Resumen: {pages_with_text} con texto, {pages_image_only} solo imagen')
    doc.close()

print('\n--- Exploracion completada ---')
