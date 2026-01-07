# -*- coding: utf-8 -*-
"""
Demo de Gating de Extracción PDF
================================
Herramienta para demostrar la lógica de decisión entre:
1. Extracción Directa (Nativo)
2. OCR (Tesseract)
3. Fallback Manual

Uso:
    python tools/run_gating_demo.py --pdf <ruta_al_pdf>
"""

import sys
import argparse
import json
from pathlib import Path

# Agregar el directorio raíz al path para poder importar src
sys.path.append(str(Path(__file__).parent.parent))

try:
    from src.ingestion import extract_text_with_gating, get_texto_extraido
except ImportError as e:
    print(f"Error al importar módulos: {e}")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Demo de Gating de Extracción PDF")
    parser.add_argument("--pdf", type=str, required=True, help="Ruta al archivo PDF")
    parser.add_argument("--lang", type=str, default="spa", help="Idioma para OCR (default: spa)")
    parser.add_argument("--full", action="store_true", help="Mostrar JSON completo de resultados")
    
    args = parser.parse_args()
    
    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: El archivo '{pdf_path}' no existe.")
        sys.exit(1)
        
    print(f"\n{'='*60}")
    print(f" PROCESANDO: {pdf_path.name}")
    print(f"{'='*60}")
    
    # Ejecutar gating
    resultado = extract_text_with_gating(pdf_path, lang=args.lang)
    
    decision = resultado["decision"]
    metodo = decision["metodo"]
    razon = decision["razon"]
    
    print(f"\nDECISIÓN FINAL: {metodo.upper()}")
    print(f"RAZÓN: {razon}")
    
    if args.full:
        print(f"\nRESULTADO COMPLETO (JSON):")
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
    else:
        # Resumen de métricas
        print(f"\n{' METRICAS ':-^60}")
        
        # Direct Text
        dt = resultado.get("direct_text", {})
        print(f"Direct Text:  {dt.get('num_chars', 0)} chars, {dt.get('num_words', 0)} words, {dt.get('tiempo_ms', 0)}ms")
        if dt.get("error"):
            print(f"  Error: {dt['error']}")
            
        # OCR
        ocr = resultado.get("ocr", {})
        print(f"OCR (Tess):   {ocr.get('num_words', 0)} words, {ocr.get('confianza_promedio', 0)*100:.1f}% confianza, {ocr.get('tiempo_ms', 0)}ms")
        if ocr.get("error"):
            print(f"  Error: {ocr['error']}")
            
        # Texto Extraído
        texto = get_texto_extraido(resultado)
        print(f"\n{' SNIPPET EXTRAÍDO ':-^60}")
        if texto:
            snippet = texto.replace('\n', ' ')[:300]
            # Usar encode/decode para evitar errores en consolas con encoding limitado
            try:
                print(f"{snippet}...")
            except UnicodeEncodeError:
                print(f"{snippet.encode('ascii', errors='replace').decode('ascii')}...")
        else:
            print("[NINGÚN TEXTO EXTRAÍDO - REQUIERE REVISIÓN MANUAL]")
            
    print(f"\n{'='*60}")

if __name__ == "__main__":
    main()
