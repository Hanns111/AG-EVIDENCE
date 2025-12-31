# -*- coding: utf-8 -*-
"""Script para ver detalle de por qué no procede"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import json

output_dir = 'output'
jsons = [f for f in os.listdir(output_dir) if f.endswith('.json')]
jsons.sort(reverse=True)
ruta = os.path.join(output_dir, jsons[0])

with open(ruta, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Extraer datos de la nueva estructura
meta = data.get('metadata', {})
decision_data = data.get('decision', {})
stats = data.get('estadisticas', {})
rec = data.get('recomendacion', {})
hallazgos = data.get('hallazgos', [])

sinad = meta.get('expediente_sinad', 'N/A')
decision = decision_data.get('resultado', 'N/A')
bloquea = decision_data.get('bloquea_pago', False)

print("=" * 70)
print("📋 ANÁLISIS DETALLADO: ¿POR QUÉ NO PROCEDE ESTE EXPEDIENTE?")
print("=" * 70)
print(f"📌 SINAD: {sinad}")
print(f"🔴 DECISIÓN: {decision}")
print(f"🚫 Bloquea pago: {'SÍ' if bloquea else 'NO'}")
print()
print(f"📊 Total observaciones: {stats.get('total_observaciones', 0)}")
print(f"   🔴 Críticas: {stats.get('criticas', 0)}")
print(f"   🟡 Mayores: {stats.get('mayores', 0)}")
print(f"   🟢 Menores: {stats.get('menores', 0)}")
print()

# Filtrar por severidad (considerar variantes con/sin tilde)
criticas = [h for h in hallazgos if h.get('severidad', '').upper() in ['CRITICA', 'CRÍTICA']]
mayores = [h for h in hallazgos if h.get('severidad', '').upper() in ['MAYOR', 'INCIERTO']]
menores = [h for h in hallazgos if h.get('severidad', '').upper() in ['MENOR', 'INFORMATIVA', 'INFORMATIVO']]

print("=" * 70)
print("🔴 OBSERVACIONES CRÍTICAS - ESTAS BLOQUEAN EL PAGO")
print("=" * 70)

for i, h in enumerate(criticas, 1):
    print()
    print(f"━━━ CRÍTICA #{i} ━━━")
    agente = h.get('agente', '')
    hallazgo = h.get('hallazgo', '')
    impacto = h.get('impacto', '')
    accion = h.get('accion', '')
    
    print(f"🔍 Agente: {agente}")
    print(f"📝 Hallazgo: {hallazgo}")
    print(f"💥 Impacto: {impacto}")
    print(f"⚡ Acción requerida: {accion}")
    
    ev = h.get('evidencia', {})
    if isinstance(ev, dict) and ev:
        print("📎 Evidencia documental:")
        for k, v in ev.items():
            if v:
                val_str = str(v)[:200]
                print(f"   • {k}: {val_str}")
    elif ev:
        print(f"📎 Evidencia: {str(ev)[:200]}")

print()
print("=" * 70)
print("🟡 OBSERVACIONES MAYORES - SUBSANABLES PERO IMPORTANTES")
print("=" * 70)

for i, h in enumerate(mayores, 1):
    print()
    print(f"━━━ MAYOR #{i} ━━━")
    agente = h.get('agente', '')
    hallazgo = h.get('hallazgo', '')
    accion = h.get('accion', '')
    
    print(f"🔍 Agente: {agente}")
    print(f"📝 Hallazgo: {hallazgo}")
    if accion:
        print(f"⚡ Acción: {accion}")
    
    ev = h.get('evidencia', {})
    if isinstance(ev, dict) and ev:
        print("📎 Evidencia:")
        for k, v in list(ev.items())[:3]:
            if v:
                val_str = str(v)[:150]
                print(f"   • {k}: {val_str}")

print()
print("=" * 70)
print("📋 RESUMEN EJECUTIVO")
print("=" * 70)
print()
if criticas:
    print(f"❌ El expediente SINAD {sinad} NO PROCEDE por {len(criticas)} observación(es) CRÍTICA(s):")
    print()
    for i, h in enumerate(criticas, 1):
        hallazgo = h.get('hallazgo', '')[:100]
        print(f"  {i}. {hallazgo}")
else:
    print(f"✅ No hay observaciones críticas")

print()
if mayores:
    print(f"⚠️ Además tiene {len(mayores)} observaciones MAYORES que deben subsanarse.")
print()

print("=" * 70)
print("💡 RECOMENDACIÓN")
print("=" * 70)
print(rec.get('texto', ''))
print()
accion_req = rec.get('accion_requerida', '')
area_resp = rec.get('area_responsable', '')
if accion_req:
    print(f"⚡ Acción: {accion_req}")
if area_resp:
    print(f"👤 Área responsable: {area_resp}")
print("=" * 70)

