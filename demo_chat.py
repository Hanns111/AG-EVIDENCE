# -*- coding: utf-8 -*-
"""Demo del Chat Asistente"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os

from chat_asistente import ChatAsistente

# Crear asistente
asistente = ChatAsistente(backend='auto')

# Cargar directivas
print("📂 Cargando directivas...")
asistente.cargar_carpeta(r'C:\Users\hanns\Downloads\DIRECITVAS VIGENTES AL 26.11.2025', recursivo=True)

# Cargar JSON del expediente
output_dir = 'output'
jsons = sorted([f for f in os.listdir(output_dir) if f.endswith('.json')], reverse=True)
if jsons:
    print("📋 Cargando expediente JSON...")
    asistente.cargar_expediente_json(os.path.join(output_dir, jsons[0]))

info = asistente.get_info()
print()
print("=" * 70)
print("🤖 CHAT ASISTENTE LISTO")
print("=" * 70)
print(f"🔧 Backend: {info['backend'].upper()}")
if info.get('modelo'):
    print(f"🧠 Modelo: {info['modelo']}")
print(f"📄 PDFs: {info['pdfs_cargados']} ({info['paginas_totales']} páginas)")
print(f"📋 Expediente: {'Sí' if info['expediente_json'] else 'No'} ({info['hallazgos_json']} hallazgos)")
print()
print("📁 Directivas cargadas:")
for a in info['archivos']:
    print(f"   • {a}")
print()

# Consultas de ejemplo
preguntas = [
    "¿Qué documentos debe tener un expediente de pago según las pautas?",
    "¿Cuál es el error más grave del expediente analizado?",
    "¿Qué dice la directiva sobre el plazo de rendición de viáticos?",
]

for pregunta in preguntas:
    print("=" * 70)
    print(f"❓ PREGUNTA: {pregunta}")
    print("-" * 70)
    respuesta = asistente.preguntar(pregunta)
    
    # Mostrar respuesta (máximo 900 caracteres)
    texto = respuesta.texto[:900]
    print(f"💬 RESPUESTA:")
    print(texto)
    print()
    print(f"   ✅ Sustento: {respuesta.tiene_sustento} | 📎 Evidencias: {len(respuesta.evidencias)}")
    print()

print("=" * 70)
print("💡 Para iniciar chat interactivo ejecute:")
print('   python chat_asistente.py --carpeta "C:\\Users\\hanns\\Downloads\\DIRECITVAS VIGENTES AL 26.11.2025" --backend llm')
print("=" * 70)


