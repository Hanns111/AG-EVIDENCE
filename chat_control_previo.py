# -*- coding: utf-8 -*-
"""
CHAT DE CONTROL PREVIO - ESTÁNDAR PROBATORIO ESTRICTO
=====================================================
v3.0 - Sistema conversacional con política anti-alucinación

POLÍTICA ANTI-ALUCINACIÓN:
- El agente SOLO responde con información literal del JSON
- Si no hay evidencia → "No consta información suficiente"
- Toda respuesta debe citar: observación, severidad, archivo, página, snippet

USO:
    python chat_control_previo.py                    # Auto
    python chat_control_previo.py --backend regex   # Solo regex
    python chat_control_previo.py informe.json      # JSON específico
"""

import os
import sys
import argparse

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agentes.agente_10_conversacional import (
    AgenteConversacional, 
    BackendMode,
    MENSAJE_INSUFICIENCIA
)


def buscar_json_reciente() -> str:
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    if not os.path.exists(output_dir):
        return None
    jsons = [f for f in os.listdir(output_dir) if f.endswith('.json')]
    if not jsons:
        return None
    jsons.sort(reverse=True)
    return os.path.join(output_dir, jsons[0])


def mostrar_banner(backend_info: dict):
    if backend_info["llm_disponible"]:
        backend_texto = f"LLM ({backend_info['modelo']})"
    else:
        backend_texto = "REGEX"
    
    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║      🤖 CHAT DE CONTROL PREVIO - ESTÁNDAR PROBATORIO v3.0           ║
╠══════════════════════════════════════════════════════════════════════╣
║  ⚖️  POLÍTICA ANTI-ALUCINACIÓN ACTIVA                               ║
║     • Solo respuestas con evidencia documental                       ║
║     • Sin interpretaciones ni inferencias                            ║
║     • Cita obligatoria: archivo, página, snippet                     ║
╠══════════════════════════════════════════════════════════════════════╣
║  🔧 Backend: {backend_texto:<54} ║
╠══════════════════════════════════════════════════════════════════════╣
║  Comandos: salir | ayuda | test                                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")


def mostrar_ayuda():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                     📖 PREGUNTAS PERMITIDAS                          ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  ✅ SOBRE OBSERVACIONES:                                             ║
║    • ¿Por qué no procede?                                            ║
║    • ¿Cuál es la observación más grave?                              ║
║    • Lista las críticas                                              ║
║    • Detalle de la observación 1                                     ║
║                                                                      ║
║  ✅ BÚSQUEDA DE EVIDENCIA:                                           ║
║    • ¿En qué archivo aparece el 54719?                               ║
║    • ¿Dónde está la inconsistencia del SINAD?                        ║
║                                                                      ║
║  ✅ FILTROS:                                                         ║
║    • Resume solo firmas                                              ║
║    • Resume solo coherencia                                          ║
║                                                                      ║
║  ❌ PREGUNTAS PROHIBIDAS (retornan insuficiencia):                   ║
║    • ¿Qué opinas?                                                    ║
║    • ¿Qué harías tú?                                                 ║
║    • ¿Esto está bien o mal?                                          ║
║    • ¿Qué quiso decir el proveedor?                                  ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")


def main():
    parser = argparse.ArgumentParser(
        description="Chat de Control Previo - Estándar Probatorio Estricto"
    )
    parser.add_argument("json_path", nargs="?", help="Ruta al JSON")
    parser.add_argument("--backend", "-b", choices=["auto", "llm", "regex"], default="auto")
    args = parser.parse_args()
    
    ruta_json = args.json_path or buscar_json_reciente()
    
    if not ruta_json:
        print("⚠️ No hay JSON. Ejecuta: python ejecutar_control_previo.py --guardar")
        return
    
    if not os.path.exists(ruta_json):
        print(f"❌ No existe: {ruta_json}")
        return
    
    print(f"📂 Cargando: {os.path.basename(ruta_json)}")
    agente = AgenteConversacional(ruta_json, backend=args.backend)
    
    if not agente.datos:
        print("❌ No se pudo cargar el JSON.")
        return
    
    backend_info = agente.get_backend_info()
    mostrar_banner(backend_info)
    
    # Info del expediente
    sinad = agente.metadata.get("expediente_sinad", "N/A")
    decision = agente.decision.get("resultado", "N/A")
    total = len(agente.hallazgos)
    criticas = len([h for h in agente.hallazgos if h.get("severidad") == "CRÍTICA"])
    
    print(f"""
┌────────────────────────────────────────────────────────────────────┐
│  📋 SINAD: {sinad:<56} │
│  📌 Decisión: {decision:<52} │
│  📊 Hallazgos: {total} total ({criticas} críticas)                         │
└────────────────────────────────────────────────────────────────────┘
""")
    
    print("💬 Escribe tu pregunta...\n" + "─" * 70)
    
    while True:
        try:
            pregunta = input("\n🧑 Tú: ").strip()
            
            if not pregunta:
                continue
            
            if pregunta.lower() in ["salir", "exit", "q"]:
                print("\n👋 ¡Hasta luego!")
                break
            
            if pregunta.lower() in ["ayuda", "help", "?"]:
                mostrar_ayuda()
                continue
            
            if pregunta.lower() == "test":
                # Ejecutar test rápido
                print("\n🧪 Ejecutando test de estándar probatorio...")
                os.system("python tests/test_estandar_probatorio.py")
                continue
            
            # Procesar pregunta
            respuesta = agente.preguntar(pregunta)
            
            print(f"\n🤖 Agente:")
            print(respuesta.texto)
            
            # Mostrar metadata
            meta = []
            if respuesta.evidencias_citadas:
                meta.append(f"📎 {len(respuesta.evidencias_citadas)} evidencia(s)")
            if not respuesta.cumple_estandar_probatorio:
                meta.append("⚠️ Sin estándar probatorio")
            if respuesta.backend_usado == "llm":
                meta.append("🧠 LLM")
            
            if meta:
                print(f"\n   {' | '.join(meta)}")
            
        except KeyboardInterrupt:
            print("\n\n👋 ¡Hasta luego!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
