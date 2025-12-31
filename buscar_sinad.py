# -*- coding: utf-8 -*-
"""Buscar ubicación exacta de números SINAD"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import re
import fitz

# Buscar en Downloads directamente
carpeta = 'C:\\Users\\hanns\\Downloads'
pdfs = [os.path.join(carpeta, f) for f in os.listdir(carpeta) if f.endswith('.pdf') and os.path.getsize(os.path.join(carpeta, f)) > 1000]

print(f'Analizando {len(pdfs)} documentos...')
print('=' * 70)

# Valores SINAD a buscar
valores_buscar = ['1079322', '54719']
sinad_encontrados = []

for pdf_path in pdfs:
    nombre = os.path.basename(pdf_path)
    try:
        doc = fitz.open(pdf_path)
        for num_pag in range(len(doc)):
            page = doc[num_pag]
            texto = page.get_text()
            
            # Buscar cada valor
            for valor in valores_buscar:
                if valor in texto:
                    # Encontrar todas las ocurrencias
                    for match in re.finditer(re.escape(valor), texto):
                        pos = match.start()
                        
                        # Extraer contexto amplio
                        start = max(0, pos - 80)
                        end = min(len(texto), pos + len(valor) + 80)
                        contexto = texto[start:end].strip()
                        contexto = re.sub(r'\s+', ' ', contexto)  # Normalizar espacios
                        
                        # Detectar tipo de documento por contexto
                        tipo_ref = "N/A"
                        texto_lower = texto.lower()
                        if "proveído" in texto_lower or "proveido" in texto_lower:
                            tipo_ref = "PROVEÍDO"
                        elif "informe" in texto_lower:
                            tipo_ref = "INFORME"
                        elif "memorandum" in texto_lower or "memorando" in texto_lower:
                            tipo_ref = "MEMORANDUM"
                        elif "conformidad" in texto_lower:
                            tipo_ref = "CONFORMIDAD"
                        elif "orden" in texto_lower and "servicio" in texto_lower:
                            tipo_ref = "ORDEN DE SERVICIO"
                        elif "cotizacion" in texto_lower or "cotización" in texto_lower:
                            tipo_ref = "COTIZACIÓN"
                        
                        sinad_encontrados.append({
                            'valor': valor,
                            'archivo': nombre,
                            'pagina': num_pag + 1,
                            'tipo_doc': tipo_ref,
                            'contexto': contexto
                        })
        doc.close()
    except Exception as e:
        print(f'Error en {nombre}: {e}')

# Agrupar por valor
print()
print('=' * 70)
print('📍 UBICACIÓN EXACTA DE LOS NÚMEROS SINAD')
print('=' * 70)

valores_agrupados = {}
for s in sinad_encontrados:
    val = s['valor']
    if val not in valores_agrupados:
        valores_agrupados[val] = []
    # Evitar duplicados exactos
    key = (s['archivo'], s['pagina'])
    if not any(x['archivo'] == s['archivo'] and x['pagina'] == s['pagina'] for x in valores_agrupados[val]):
        valores_agrupados[val].append(s)

for valor, ocurrencias in sorted(valores_agrupados.items()):
    print()
    print(f"{'='*70}")
    print(f"🔢 SINAD: {valor}")
    print(f"{'='*70}")
    
    for i, ocu in enumerate(ocurrencias, 1):
        print()
        print(f"  📄 Ocurrencia #{i}")
        print(f"  ─────────────────────────────────────────────────")
        print(f"  📁 Archivo: {ocu['archivo']}")
        print(f"  📃 Página: {ocu['pagina']}")
        print(f"  📋 Tipo documento: {ocu['tipo_doc']}")
        print(f"  📝 Contexto literal:")
        print(f"     \"{ocu['contexto']}\"")

print()
print('=' * 70)
print('📊 RESUMEN DE LA INCONSISTENCIA')
print('=' * 70)
print()
for valor, ocurrencias in sorted(valores_agrupados.items()):
    archivos = [o['archivo'] for o in ocurrencias]
    print(f"  SINAD {valor} aparece en:")
    for o in ocurrencias:
        print(f"    → {o['archivo']} (pág. {o['pagina']})")
print()
print('⚠️ CONCLUSIÓN: Hay DOS números SINAD diferentes en el expediente.')
print('   Esto impide la trazabilidad correcta del expediente.')
print('=' * 70)

