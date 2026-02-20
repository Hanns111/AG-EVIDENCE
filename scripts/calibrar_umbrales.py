#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Calibración de Umbrales — Tarea #19
==============================================

Ejecuta la calibración de umbrales del ConfidenceRouter usando
los benchmarks empíricos disponibles en data/evaluacion/.

Genera:
  - data/normativa/umbrales_calibrados.json (perfiles calibrados)
  - Resumen en consola con estadísticas y perfiles

Uso:
    python scripts/calibrar_umbrales.py
    python scripts/calibrar_umbrales.py --benchmark data/evaluacion/prueba_empirica_cc003.json
    python scripts/calibrar_umbrales.py --output data/normativa/umbrales_custom.json
"""

import argparse
import sys
from pathlib import Path

# Agregar raíz del proyecto al path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.extraction.calibracion import (
    CalibradorUmbrales,
    PerfilCalibracion,
    VERSION_CALIBRACION,
)


def main():
    parser = argparse.ArgumentParser(
        description="Calibrar umbrales del ConfidenceRouter con benchmarks empíricos"
    )
    parser.add_argument(
        "--benchmark",
        type=str,
        nargs="+",
        default=None,
        help="Ruta(s) a archivos JSON de benchmark. Si no se especifica, "
             "busca todos los prueba_empirica_*.json en data/evaluacion/",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/normativa/umbrales_calibrados.json",
        help="Ruta de salida para el JSON de umbrales calibrados "
             "(default: data/normativa/umbrales_calibrados.json)",
    )
    parser.add_argument(
        "--perfil",
        type=str,
        choices=["conservador", "balanceado", "permisivo"],
        default=None,
        help="Mostrar solo un perfil específico (default: todos)",
    )
    parser.add_argument(
        "--solo-analisis",
        action="store_true",
        help="Solo analizar sin generar perfiles ni exportar",
    )

    args = parser.parse_args()

    print(f"=== Calibrador de Umbrales v{VERSION_CALIBRACION} ===\n")

    # Determinar benchmarks
    benchmark_paths = []
    if args.benchmark:
        benchmark_paths = [Path(b) for b in args.benchmark]
    else:
        eval_dir = ROOT / "data" / "evaluacion"
        if eval_dir.exists():
            benchmark_paths = sorted(eval_dir.glob("prueba_empirica_*.json"))

    if not benchmark_paths:
        print("ERROR: No se encontraron benchmarks.")
        print("  Especifique con --benchmark o coloque archivos en data/evaluacion/")
        sys.exit(1)

    # Cargar benchmarks
    calibrador = CalibradorUmbrales()
    for path in benchmark_paths:
        print(f"Cargando benchmark: {path}")
        calibrador.cargar_benchmark(str(path))

    print(f"\nBenchmarks cargados: {calibrador.num_benchmarks}")

    # Analizar
    print("\n--- Analizando ---")
    analisis = calibrador.analizar()

    print(f"Expediente: {analisis.expediente}")
    print(f"Comprobantes: {analisis.total_comprobantes}")
    print(f"Campos evaluados: {analisis.total_campos_evaluados}")
    print(f"Precisión global: {analisis.precision_pct}%")
    print(f"Tasa fallo global: {round(analisis.tasa_fallo_global * 100, 1)}%")
    print(f"Confianza OCR: {analisis.confianza_ocr_min:.3f} - "
          f"{analisis.confianza_ocr_max:.3f} (media {analisis.confianza_ocr_media:.3f})")

    print("\nEstadísticas por campo:")
    for campo, stat in analisis.stats_por_campo.items():
        if stat.evaluados > 0:
            print(f"  {campo:20s}: {stat.match}/{stat.evaluados} match "
                  f"({round(stat.tasa_acierto * 100, 1)}%), "
                  f"{stat.error} error, {stat.no_extraido} no extraído")

    if args.solo_analisis:
        print("\n--- Solo análisis (sin generar perfiles) ---")
        sys.exit(0)

    # Generar perfiles
    print("\n--- Generando perfiles ---")
    perfiles = calibrador.generar_perfiles()

    for perfil_enum, resultado in perfiles.items():
        if args.perfil and perfil_enum.value != args.perfil:
            continue

        print(f"\n  [{perfil_enum.value.upper()}]")
        ur = resultado.umbrales_router
        print(f"    abstención warning:    {ur['max_campos_abstencion_warning_pct']}")
        print(f"    abstención critical:   {ur['max_campos_abstencion_critical_pct']}")
        print(f"    obs degradadas warning: {ur['max_observaciones_degradadas_warning']}")
        print(f"    obs degradadas critical:{ur['max_observaciones_degradadas_critical']}")
        print(f"    min comprobantes:       {ur['min_comprobantes_con_datos']}")
        print(f"    min campos/comprobante: {ur['min_campos_por_comprobante']}")
        print(f"    errores arit warning:   {ur['max_errores_aritmeticos_warning']}")
        print(f"    errores arit critical:  {ur['max_errores_aritmeticos_critical']}")
        print(f"    completitud critical:   {ur['completitud_problemas_critical']}")

    # Exportar
    output_path = ROOT / args.output
    print(f"\n--- Exportando a {output_path} ---")
    ruta_real = calibrador.exportar_json(str(output_path))
    print(f"Archivo generado: {ruta_real}")

    # Validación cruzada con cc003
    tasa = analisis.tasa_fallo_global
    print("\n--- Validación cruzada con benchmark ---")
    for perfil_enum, resultado in perfiles.items():
        ur = resultado.umbrales_router
        critical_pct = ur["max_campos_abstencion_critical_pct"]
        warning_pct = ur["max_campos_abstencion_warning_pct"]

        if tasa >= critical_pct:
            status = "CRITICAL"
        elif tasa >= warning_pct:
            status = "WARNING"
        else:
            status = "OK"

        print(f"  {perfil_enum.value.upper():15s}: "
              f"tasa fallo {round(tasa * 100, 1)}% vs "
              f"warning {round(warning_pct * 100)}%/critical {round(critical_pct * 100)}% "
              f"→ {status}")

    print(f"\n=== Calibración completada ===")
    print(f"Perfil recomendado: BALANCEADO")


if __name__ == "__main__":
    main()
