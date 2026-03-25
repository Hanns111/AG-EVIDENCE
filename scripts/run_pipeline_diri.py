#!/usr/bin/env python3
"""
E2E test: pipeline escribano_fiel v4.1.0 con expediente DIRI2026-INT-0196314.

Pipeline v4.1.0:
- qwen2.5vl:7b modelo primario (sin fallback)
- keep_alive=10m, format=json, ThreadPoolExecutor(2)
- OCR-first + ROI crop + telemetría detallada
- Objetivo: <3 min por expediente
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import VLM_CONFIG, NaturalezaExpediente
from src.extraction.escribano_fiel import VERSION_ESCRIBANO, ConfigPipeline, EscribanoFiel

PDF = "data/expedientes/pruebas/viaticos_2026/DIRI2026-INT-0196314_12.03.2026/2026031211199PV0086JOSEADRIANZENRENDICION.pdf"
SINAD = "DIRI2026-INT-0196314"

# Baseline: v4.0.0 (2026-03-13, antes de keep_alive + format=json)
BASELINE = {
    "version": "4.0.0",
    "comprobantes": 19,
    "duracion_s": 168,  # 2.8 min
    "paginas_vlm": 13,
    "vlm_promedio_s": 20.0,
    "json_fallos": 1,
}

print("=" * 70)
print(f"AG-EVIDENCE — Pipeline v{VERSION_ESCRIBANO}")
print(f"Expediente: {SINAD}")
print(f"PDF: {os.path.basename(PDF)}")
print(
    f"VLM: {VLM_CONFIG['model']} | format={VLM_CONFIG.get('format')} | "
    f"keep_alive={VLM_CONFIG.get('keep_alive')} | workers={VLM_CONFIG.get('vlm_workers')}"
)
print(
    f"Baseline v{BASELINE['version']}: {BASELINE['comprobantes']} comprobantes, "
    f"{BASELINE['duracion_s']}s, {BASELINE['json_fallos']} JSON fallos"
)
print("=" * 70)

if not os.path.exists(PDF):
    print(f"\nERROR: PDF no encontrado: {PDF}")
    sys.exit(1)

tmpdir = tempfile.mkdtemp(prefix="ag_e2e_v41_")
config = ConfigPipeline(
    vault_dir=os.path.join(tmpdir, "vault"),
    registry_dir=os.path.join(tmpdir, "registry"),
    output_dir="output",
    log_dir=os.path.join(tmpdir, "logs"),
    generar_excel=True,
    detener_en_critical=False,
    vlm_enabled=True,
)

escribano = EscribanoFiel(config=config)
resultado = escribano.procesar_expediente(
    pdf_path=PDF,
    sinad=SINAD,
    naturaleza=NaturalezaExpediente.VIATICOS,
)

# === RESULTADO ===
print("\n" + "=" * 70)
print("RESULTADO DEL PIPELINE")
print("=" * 70)
dur_s = resultado.duracion_total_ms / 1000
print(f"Exito: {resultado.exito}")
print(f"Duracion: {dur_s:.1f}s ({dur_s / 60:.1f} min)")

if resultado.ruta_excel:
    print(f"Excel: {resultado.ruta_excel}")
if resultado.razon_detencion:
    print(f"Detenido: {resultado.razon_detencion}")

# Pasos
print(f"\nPasos ({len(resultado.pasos)}):")
ocr_first_data = None
dispatcher_data = None
roi_crop_data = None
telemetry_data = None
for paso in resultado.pasos:
    status = "OK" if paso.exito else "FAIL"
    print(f"  [{status}] {paso.paso}: {paso.duracion_ms / 1000:.1f}s — {paso.mensaje or ''}")
    if paso.error:
        print(f"         ERROR: {paso.error}")
    if paso.paso == "parseo_profundo" and paso.datos:
        ocr_first_data = paso.datos.get("ocr_first")
        dispatcher_data = paso.datos.get("dispatcher")
        roi_crop_data = paso.datos.get("roi_crop")
        telemetry_data = paso.datos.get("telemetry")

# === MÉTRICAS ===
print("\n" + "=" * 70)
print("MÉTRICAS")
print("=" * 70)

if ocr_first_data:
    print(f"  OCR-first resueltas sin VLM: {ocr_first_data['paginas_resueltas_sin_vlm']}")
    print(f"  OCR-first escaladas a VLM:   {ocr_first_data['paginas_escaladas_vlm']}")
    print(f"  Score promedio OCR:           {ocr_first_data['score_promedio_ocr']:.3f}")

if roi_crop_data:
    print(f"  ROI crop aplicado:           {roi_crop_data.get('pages_with_crop', 0)} páginas")
    ratios = roi_crop_data.get("crop_area_ratios", [])
    if ratios:
        print(f"  Ratio área promedio:         {sum(ratios) / len(ratios):.3f}")

if dispatcher_data:
    print(f"  Páginas PDF total:           {dispatcher_data['total_paginas_pdf']}")
    print(f"  Páginas comprobante:         {dispatcher_data['paginas_comprobante']}")
    print(f"  Páginas enviadas VLM:        {dispatcher_data['paginas_enviadas_vlm']}")
    print(f"  Tiempo VLM total:            {dispatcher_data['tiempo_vlm_total_s']:.1f}s")
    print(f"  Tiempo VLM promedio/pág:     {dispatcher_data['tiempo_vlm_promedio_s']:.1f}s")
    print(f"  Tipos detectados:            {dispatcher_data['tipos_detectados']}")

# Telemetría VLM
if telemetry_data:
    print(f"\n  Telemetría VLM ({len(telemetry_data)} invocaciones):")
    for t in telemetry_data[:5]:
        print(
            f"    {t['tipo']} | {t['elapsed_s']:.1f}s | "
            f"prompt={t['prompt_eval_count']} tokens | "
            f"eval={t['eval_count']} tokens | "
            f"load={t['load_duration_ms']:.0f}ms"
        )
    if len(telemetry_data) > 5:
        print(f"    ... y {len(telemetry_data) - 5} más")

# === COMPROBANTES ===
n_comp = 0
if resultado.expediente:
    exp = resultado.expediente
    n_comp = len(exp.comprobantes) if exp.comprobantes else 0
    print(f"\nComprobantes extraídos: {n_comp}")
    if n_comp > 0:
        for i, c in enumerate(exp.comprobantes[:25]):
            tipo_val = c.grupo_b.tipo_comprobante.valor if c.grupo_b.tipo_comprobante else "?"
            serie_val = c.grupo_b.serie.valor if c.grupo_b.serie else "?"
            num_val = c.grupo_b.numero.valor if c.grupo_b.numero else "?"
            ruc_val = c.grupo_a.ruc_emisor.valor if c.grupo_a.ruc_emisor else "?"
            total_val = c.grupo_f.importe_total.valor if c.grupo_f.importe_total else "?"
            fecha_val = c.grupo_b.fecha_emision.valor if c.grupo_b.fecha_emision else "?"
            metodo = c.grupo_k.metodo_extraccion if c.grupo_k else "?"
            pag = c.grupo_k.pagina_origen if c.grupo_k else "?"
            print(
                f"    [{i + 1:2d}] p{pag or '?':>2} {tipo_val or '?':<10} "
                f"{serie_val or '?'}-{num_val or '?':<10} "
                f"RUC:{ruc_val or '?'} Total:{total_val or '?'} "
                f"Fecha:{fecha_val or '?'} [{metodo or '?'}]"
            )

# Router
if resultado.decision:
    d = resultado.decision
    status_val = d.resultado.status.value if d.resultado else "N/A"
    print(f"\nRouter: {status_val} → {d.accion}")

# Observaciones (resumen)
n_obs = len(resultado.observaciones)
if n_obs > 0:
    niveles = {}
    for obs in resultado.observaciones:
        nv = str(getattr(obs, "nivel", "?"))
        niveles[nv] = niveles.get(nv, 0) + 1
    print(f"\nObservaciones ({n_obs}): {niveles}")

# === COMPARACIÓN ===
print("\n" + "=" * 70)
print(f"COMPARACIÓN v{BASELINE['version']} vs v{VERSION_ESCRIBANO}")
print("=" * 70)

vlm_prom = dispatcher_data["tiempo_vlm_promedio_s"] if dispatcher_data else "?"
vlm_env = dispatcher_data["paginas_enviadas_vlm"] if dispatcher_data else "?"

bl_dur = BASELINE["duracion_s"]
bl_vlm = BASELINE["vlm_promedio_s"]
bl_comp = BASELINE["comprobantes"]
bl_json = BASELINE["json_fallos"]
comp_delta = "OK" if n_comp == bl_comp else "DIFF!"
time_str = f"{dur_s:.0f}s"
bl_time_str = f"{bl_dur}s"
vlm_str = f"{vlm_prom:.1f}s" if isinstance(vlm_prom, (int, float)) else str(vlm_prom)
speedup_str = f"{bl_dur / dur_s:.1f}x" if dur_s > 0 else "?"

print(f"  {'Métrica':<30} {'Baseline':<15} {'Actual':<15} {'Delta':<15}")
print(f"  {'-' * 30} {'-' * 15} {'-' * 15} {'-' * 15}")
print(f"  {'Comprobantes':<30} {bl_comp:<15} {n_comp:<15} {comp_delta:<15}")
print(f"  {'Tiempo total':<30} {bl_time_str:<15} {time_str:<15} {speedup_str:<15}")
print(f"  {'VLM promedio/pág':<30} {bl_vlm:<15} {vlm_str:<15}")
print(f"  {'JSON fallos':<30} {bl_json:<15} {'0':<15}")

if dur_s > 0 and bl_dur > 0:
    print(f"\n  Speedup: {bl_dur / dur_s:.1f}x")

print("=" * 70)
