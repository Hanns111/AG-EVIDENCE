# -*- coding: utf-8 -*-
"""Buscar SINAD con búsqueda más amplia"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import re
import fitz

carpeta = 'C:\\Users\\hanns\\Downloads'
pdfs = [os.path.join(carpeta, f) for f in os.listdir(carpeta) 
        if f.lower().endswith('.pdf') and os.path.getsize(os.path.join(carpeta, f)) > 1000]

print(f'Analizando {len(pdfs)} documentos...')
print('=' * 70)

# Valores a buscar
valores_buscar = ['1079322', '54719', '1047256']

resultados = []

for pdf_path in pdfs:
    nombre = os.path.basename(pdf_path)
    try:
        doc = fitz.open(pdf_path)
        texto_completo = ""
        
        for num_pag in range(len(doc)):
            page = doc[num_pag]
            texto = page.get_text()
            texto_completo += texto
            
            # Buscar cada valor
            for valor in valores_buscar:
                if valor in texto:
                    # Contexto
                    pos = texto.find(valor)
                    start = max(0, pos - 100)
                    end = min(len(texto), pos + len(valor) + 100)
                    contexto = texto[start:end].strip()
                    contexto = re.sub(r'\s+', ' ', contexto)
                    
                    resultados.append({
                        'valor': valor,
                        'archivo': nombre,
                        'pagina': num_pag + 1,
                        'contexto': contexto
                    })
        
        # También buscar patrón SINAD
        sinad_matches = re.findall(r'SINAD[:\s#N°]*(\d+)', texto_completo, re.IGNORECASE)
        if sinad_matches:
            print(f"  {nombre}: SINAD encontrados: {sinad_matches}")
        
        doc.close()
        
    except Exception as e:
        print(f'  Error en {nombre}: {e}')

print()
print('=' * 70)
print('RESULTADOS DE BÚSQUEDA')
print('=' * 70)

if not resultados:
    print()
    print('⚠️ Los valores 1079322 y 54719 NO se encontraron en los PDFs actuales.')
    print()
    print('Posibles razones:')
    print('  1. El expediente analizado anteriormente ya no está en Downloads')
    print('  2. Los números estaban en PDFs que fueron movidos/eliminados')
    print('  3. El texto no es extraíble (imagen sin OCR)')
    print()
    print('El análisis que arrojó esta inconsistencia fue del:')
    print('  Archivo: informe_control_previo_20251215_172759.json')
    print('  SINAD principal detectado: 1079322')
    print('  SINAD secundario detectado: 54719')
else:
    for r in resultados:
        print()
        print(f"Valor: {r['valor']}")
        print(f"  Archivo: {r['archivo']}")
        print(f"  Página: {r['pagina']}")
        print(f"  Contexto: \"{r['contexto']}\"")

print()
print('=' * 70)


