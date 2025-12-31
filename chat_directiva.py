# -*- coding: utf-8 -*-
"""
CHAT DE DIRECTIVAS - ESTÁNDAR PROBATORIO ESTRICTO
=================================================
Consulta interactiva de directivas y pautas normativas.

POLÍTICA ANTI-ALUCINACIÓN:
- Solo responde con información LITERAL de los PDFs
- Cita obligatoria: archivo + página + snippet
- Si no encuentra: "No consta en la directiva cargada"

USO:
    python chat_directiva.py --pdf directiva1.pdf --pdf directiva2.pdf
    python chat_directiva.py --pdf "C:\\ruta\\directiva.pdf" --backend llm
    python chat_directiva.py --carpeta "C:\\directivas" --backend regex
    
OPCIONES:
    --pdf, -p       Ruta a un PDF (puede repetirse)
    --carpeta, -c   Carpeta con PDFs a cargar
    --backend, -b   Backend: auto, llm, regex (default: auto)
"""

import os
import sys
import argparse
import glob

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agentes.agente_directivas import AgenteDirectivas, MENSAJE_NO_CONSTA


def buscar_pdfs_en_carpeta(carpeta: str) -> list:
    """Busca todos los PDFs en una carpeta"""
    if not os.path.exists(carpeta):
        return []
    
    pdfs = glob.glob(os.path.join(carpeta, "*.pdf"))
    pdfs.extend(glob.glob(os.path.join(carpeta, "*.PDF")))
    
    return pdfs


def mostrar_banner(info: dict):
    """Muestra el banner de inicio"""
    docs = info['documentos_cargados']
    paginas = info['total_paginas']
    backend = info['backend'].upper()
    
    if info['llm_disponible']:
        backend_texto = f"LLM ({info['modelo']})"
    else:
        backend_texto = "REGEX"
    
    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║        📚 CHAT DE DIRECTIVAS - ESTÁNDAR PROBATORIO v1.0              ║
╠══════════════════════════════════════════════════════════════════════╣
║  ⚖️  POLÍTICA ANTI-ALUCINACIÓN ACTIVA                               ║
║     • Solo información literal de los PDFs                           ║
║     • Cita obligatoria: archivo + página + snippet                   ║
║     • Sin información → "No consta en la directiva"                  ║
╠══════════════════════════════════════════════════════════════════════╣
║  📄 Documentos: {docs:<3} | 📃 Páginas: {paginas:<5} | 🔧 Backend: {backend_texto:<12} ║
╠══════════════════════════════════════════════════════════════════════╣
║  Comandos: salir | ayuda | listar | buscar <término>                 ║
╚══════════════════════════════════════════════════════════════════════╝
""")


def mostrar_ayuda():
    """Muestra ayuda"""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                        📖 AYUDA                                      ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  PREGUNTAS DE EJEMPLO:                                               ║
║    • ¿Cuál es el plazo para rendir viáticos?                         ║
║    • ¿Qué documentos se requieren para el pago?                      ║
║    • ¿Cuándo corresponde aplicar penalidad?                          ║
║    • ¿Quién es el responsable de aprobar?                            ║
║    • ¿Cuál es el monto máximo para caja chica?                       ║
║                                                                      ║
║  COMANDOS:                                                           ║
║    listar        - Muestra los documentos cargados                   ║
║    buscar <X>    - Busca término exacto en documentos                ║
║    ayuda         - Muestra esta ayuda                                ║
║    salir         - Termina la sesión                                 ║
║                                                                      ║
║  NOTA: Las respuestas SIEMPRE citan archivo + página + texto         ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")


def mostrar_documentos(agente: AgenteDirectivas):
    """Muestra los documentos cargados"""
    print("\n📋 **DOCUMENTOS CARGADOS:**\n")
    
    for doc in agente.documentos:
        print(f"  📄 {doc.nombre}")
        print(f"     Ruta: {doc.ruta}")
        print(f"     Páginas: {doc.total_paginas}")
        print()


def buscar_termino(agente: AgenteDirectivas, termino: str):
    """Busca un término específico"""
    print(f"\n🔍 Buscando: '{termino}'...\n")
    
    evidencias = agente.buscar_en_documentos([termino], max_resultados=10)
    
    if not evidencias:
        print(f"❌ No se encontró '{termino}' en los documentos.")
        return
    
    print(f"✅ {len(evidencias)} resultado(s):\n")
    
    for i, ev in enumerate(evidencias, 1):
        print(f"  [{i}] {ev.archivo} - Pág. {ev.pagina}")
        print(f"      \"{ev.snippet[:100]}...\"")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Chat de Directivas - Consulta normativas con estándar probatorio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python chat_directiva.py --pdf directiva_viaticos.pdf
  python chat_directiva.py --pdf dir1.pdf --pdf dir2.pdf --backend llm
  python chat_directiva.py --carpeta "C:\\directivas"
        """
    )
    
    parser.add_argument(
        "--pdf", "-p",
        action="append",
        default=[],
        help="Ruta a un PDF (puede repetirse para múltiples PDFs)"
    )
    
    parser.add_argument(
        "--carpeta", "-c",
        help="Carpeta con PDFs a cargar"
    )
    
    parser.add_argument(
        "--backend", "-b",
        choices=["auto", "llm", "regex"],
        default="auto",
        help="Backend a usar: auto (default), llm, regex"
    )
    
    args = parser.parse_args()
    
    # Recopilar PDFs
    pdfs = list(args.pdf)
    
    if args.carpeta:
        pdfs_carpeta = buscar_pdfs_en_carpeta(args.carpeta)
        if pdfs_carpeta:
            print(f"📁 Encontrados {len(pdfs_carpeta)} PDFs en {args.carpeta}")
            pdfs.extend(pdfs_carpeta)
    
    if not pdfs:
        print("⚠️ No se especificaron PDFs.")
        print("\nUso:")
        print("  python chat_directiva.py --pdf <ruta.pdf>")
        print("  python chat_directiva.py --carpeta <carpeta_con_pdfs>")
        print("\nEjemplo:")
        print("  python chat_directiva.py --pdf directiva_viaticos.pdf --backend llm")
        return
    
    # Crear agente
    print("⏳ Cargando documentos...")
    agente = AgenteDirectivas(backend=args.backend)
    
    cargados = 0
    for pdf in pdfs:
        if os.path.exists(pdf):
            if agente.cargar_pdf(pdf):
                cargados += 1
                print(f"   ✅ {os.path.basename(pdf)}")
            else:
                print(f"   ❌ Error cargando: {pdf}")
        else:
            print(f"   ⚠️ No existe: {pdf}")
    
    if cargados == 0:
        print("\n❌ No se pudo cargar ningún documento.")
        return
    
    # Mostrar banner
    info = agente.get_info()
    mostrar_banner(info)
    
    print("📋 Archivos cargados:")
    for nombre in info['archivos']:
        print(f"   • {nombre}")
    
    print("\n" + "─" * 70)
    print("💬 Escribe tu pregunta sobre las directivas...\n")
    
    # Loop principal
    while True:
        try:
            entrada = input("🧑 Tú: ").strip()
            
            if not entrada:
                continue
            
            # Comandos especiales
            if entrada.lower() in ["salir", "exit", "q"]:
                print("\n👋 ¡Hasta luego!")
                break
            
            if entrada.lower() in ["ayuda", "help", "?"]:
                mostrar_ayuda()
                continue
            
            if entrada.lower() == "listar":
                mostrar_documentos(agente)
                continue
            
            if entrada.lower().startswith("buscar "):
                termino = entrada[7:].strip()
                if termino:
                    buscar_termino(agente, termino)
                continue
            
            # Procesar pregunta
            respuesta = agente.preguntar(entrada)
            
            print(f"\n🤖 Agente:\n{respuesta.texto}")
            
            # Metadata
            if respuesta.evidencias:
                print(f"\n   📎 {len(respuesta.evidencias)} fuente(s) citada(s)")
            
            if not respuesta.tiene_sustento:
                pass  # Ya se mostró el mensaje
            elif not respuesta.cumple_estandar:
                print("   ⚠️ [Respuesta sin estándar probatorio completo]")
            
            print()
            
        except KeyboardInterrupt:
            print("\n\n👋 ¡Hasta luego!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()



