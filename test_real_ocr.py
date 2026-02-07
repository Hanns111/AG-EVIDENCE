# -*- coding: utf-8 -*-
"""
Prueba real del adaptador OCR con expediente de viáticos
=========================================================
"""

import sys
from src.tools.ocr_preprocessor import preprocesar_expediente

if __name__ == "__main__":
    print("=" * 80)
    print("PRUEBA REAL DEL ADAPTADOR OCR")
    print("=" * 80)
    print()
    
    resultados = preprocesar_expediente(
        carpeta_expediente=r"C:\Users\Hans\Proyectos\AG-EVIDENCE\data\expedientes\pruebas\viaticos_2026\DIGC2026-INT-0072851",
        directorio_salida=r"C:\Users\Hans\Proyectos\AG-EVIDENCE\output\ocr_temp"
    )
    
    print(f"Total PDFs procesados: {len(resultados)}")
    print()
    
    for r in resultados:
        print(f"{r.archivo_original}")
        print(f"  Tipo: {r.tipo_detectado}")
        print(f"  OCR: {r.requirio_ocr}")
        print(f"  Éxito: {r.exito}")
        print(f"  Tiempo: {r.tiempo_proceso_ms}ms")
        print(f"  Páginas: {r.paginas_total}")
        print(f"  Tamaño original: {r.tamanio_original_bytes:,} bytes")
        print(f"  Tamaño procesado: {r.tamanio_procesado_bytes:,} bytes")
        if r.error:
            print(f"  Error: {r.error}")
        print(f"  Comando: {r.comando_ejecutado[:100]}..." if len(r.comando_ejecutado) > 100 else f"  Comando: {r.comando_ejecutado}")
        print(f"  Versión ocrmypdf: {r.version_ocrmypdf}")
        print()
