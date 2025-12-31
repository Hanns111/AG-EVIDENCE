# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              AG-EVIDENCE — Sistema de Análisis Probatorio                   ║
║                    Ministerio de Educación del Perú                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Este script ejecuta el análisis completo de Control Previo sobre los       ║
║  expedientes ubicados en la carpeta de Descargas.                           ║
║                                                                              ║
║  MODO DE USO:                                                                ║
║    python ejecutar_control_previo.py                                         ║
║    python ejecutar_control_previo.py --carpeta "C:\ruta\expediente"         ║
║    python ejecutar_control_previo.py --silencioso                           ║
║                                                                              ║
║  AGENTES INCLUIDOS:                                                          ║
║    01. Clasificador de Naturaleza                                           ║
║    02. OCR Avanzado                                                         ║
║    03. Coherencia Documental                                                ║
║    04. Legal / Directivas                                                   ║
║    05. Firmas y Competencia                                                 ║
║    06. Integridad del Expediente                                            ║
║    07. Penalidades                                                          ║
║    08. SUNAT Público (Experimental)                                         ║
║    09. Decisor Final                                                        ║
║                                                                              ║
║  RESTRICCIONES SUNAT:                                                        ║
║    - NO usa Clave SOL                                                       ║
║    - NO integra SIRE autenticado                                            ║
║    - Solo consultas públicas / APIs gratuitas                               ║
║    - Todos los resultados SUNAT son INFORMATIVOS                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import argparse
from datetime import datetime

# Configurar encoding para Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Agregar ruta del proyecto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orquestador import OrquestadorControlPrevio, ejecutar_control_previo
from config.settings import DOWNLOADS_DIR, OUTPUT_DIR


def main():
    """Función principal de ejecución"""
    
    # Parser de argumentos
    parser = argparse.ArgumentParser(
        description="AG-EVIDENCE — Sistema de Análisis Probatorio de Expedientes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python ejecutar_control_previo.py
  python ejecutar_control_previo.py --carpeta "C:\\expedientes\\2025"
  python ejecutar_control_previo.py --silencioso --guardar
        """
    )
    
    parser.add_argument(
        '--carpeta', '-c',
        type=str,
        default=None,
        help='Carpeta con los documentos del expediente (default: Downloads)'
    )
    
    parser.add_argument(
        '--silencioso', '-s',
        action='store_true',
        help='Ejecutar sin imprimir progreso (solo resultado final)'
    )
    
    parser.add_argument(
        '--guardar', '-g',
        action='store_true',
        help='Guardar informe automáticamente en carpeta output'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Ruta específica para guardar el informe'
    )
    
    args = parser.parse_args()
    
    # Determinar carpeta
    carpeta = args.carpeta or DOWNLOADS_DIR
    
    # Verificar que existe
    if not os.path.exists(carpeta):
        print(f"❌ Error: La carpeta no existe: {carpeta}")
        sys.exit(1)
    
    # Banner
    if not args.silencioso:
        print_banner()
    
    # Ejecutar análisis
    try:
        orquestador = OrquestadorControlPrevio(carpeta)
        informe = orquestador.ejecutar(verbose=not args.silencioso)
        
        if informe is None:
            print("❌ No se pudo generar el informe. Verifique que haya PDFs en la carpeta.")
            sys.exit(1)
        
        # Guardar si se solicitó
        if args.guardar or args.output:
            ruta = orquestador.guardar_informe(args.output)
            print(f"\n✅ Informe guardado en: {ruta}")
        
        # Retornar código según decisión
        from config.settings import DecisionFinal
        if informe.decision == DecisionFinal.NO_PROCEDE:
            sys.exit(2)  # Código especial para NO PROCEDE
        elif informe.decision == DecisionFinal.PROCEDE_CON_OBSERVACIONES:
            sys.exit(1)  # Código especial para OBSERVACIONES
        else:
            sys.exit(0)  # PROCEDE
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Análisis cancelado por el usuario")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error durante el análisis: {e}")
        if not args.silencioso:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def print_banner():
    """Imprime el banner del sistema"""
    banner = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ██████╗ ██████╗ ███╗   ██╗████████╗██████╗  ██████╗ ██╗                    ║
║  ██╔════╝██╔═══██╗████╗  ██║╚══██╔══╝██╔══██╗██╔═══██╗██║                    ║
║  ██║     ██║   ██║██╔██╗ ██║   ██║   ██████╔╝██║   ██║██║                    ║
║  ██║     ██║   ██║██║╚██╗██║   ██║   ██╔══██╗██║   ██║██║                    ║
║  ╚██████╗╚██████╔╝██║ ╚████║   ██║   ██║  ██║╚██████╔╝███████╗               ║
║   ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝               ║
║                                                                              ║
║  ██████╗ ██████╗ ███████╗██╗   ██╗██╗ ██████╗                                ║
║  ██╔══██╗██╔══██╗██╔════╝██║   ██║██║██╔═══██╗                               ║
║  ██████╔╝██████╔╝█████╗  ██║   ██║██║██║   ██║                               ║
║  ██╔═══╝ ██╔══██╗██╔══╝  ╚██╗ ██╔╝██║██║   ██║                               ║
║  ██║     ██║  ██║███████╗ ╚████╔╝ ██║╚██████╔╝                               ║
║  ╚═╝     ╚═╝  ╚═╝╚══════╝  ╚═══╝  ╚═╝ ╚═════╝                                ║
║                                                                              ║
║                    SISTEMA MULTI-AGENTE DE CONTROL PREVIO                   ║
║                         Ministerio de Educación                              ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  9 Agentes Especializados | OCR Avanzado | Validación SUNAT (Informativa)   ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """
    print(banner)


if __name__ == "__main__":
    main()



