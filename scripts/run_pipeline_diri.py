#!/usr/bin/env python3
"""
E2E test: pipeline escribano_fiel v3.0.0 con expediente DIRI2026-INT-0196314.

Mide métricas ADR-011 Nivel 2 (OCR-first):
- Páginas resueltas sin VLM vs escaladas a VLM
- Score promedio OCR por tipo
- Tiempo total vs baseline anterior
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import NaturalezaExpediente
from src.extraction.escribano_fiel import VERSION_ESCRIBANO, ConfigPipeline, EscribanoFiel

PDF = "data/expedientes/pruebas/viaticos_2026/DIRI2026-INT-0196314/2026031211199PV0086JOSEADRIANZENRENDICION.pdf"
SINAD = "DIRI2026-INT-0196314"

# Baseline anterior (sesión 2026-03-12, v2.0.0, pipeline 6 pasos)
BASELINE = {
    "version": "2.0.0",
    "comprobantes": 19,
    "digital": 13,
    "imagen": 8,
    "dedup": 2,
    "duracion_s": 2700,  # ~45 min estimado (VLM en todas las páginas)
    "paginas_vlm": 21,  # Todas iban al VLM
}

print("=" * 70)
print(f"AG-EVIDENCE — Pipeline v{VERSION_ESCRIBANO} (ADR-011 Nivel 2: OCR-first)")
print(f"Expediente: {SINAD}")
print(f"PDF: {os.path.basename(PDF)}")
print(
    f"Baseline v{BASELINE['version']}: {BASELINE['comprobantes']} comprobantes, "
    f"{BASELINE['paginas_vlm']} páginas al VLM, ~{BASELINE['duracion_s'] // 60} min"
)
print("=" * 70)

if not os.path.exists(PDF):
    print(f"\nERROR: PDF no encontrado: {PDF}")
    sys.exit(1)

# Directorios temporales para no ensuciar registros
tmpdir = tempfile.mkdtemp(prefix="ag_evidence_e2e_v3_")
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

print("\n" + "=" * 70)
print("RESULTADO DEL PIPELINE")
print("=" * 70)
print(f"Exito: {resultado.exito}")
print(f"Detenido: {resultado.detenido}")
dur_s = resultado.duracion_total_ms / 1000
print(f"Duracion total: {resultado.duracion_total_ms:.0f} ms ({dur_s:.1f}s / {dur_s / 60:.1f} min)")

if resultado.ruta_excel:
    print(f"Excel generado: {resultado.ruta_excel}")
    if os.path.exists(resultado.ruta_excel):
        size_kb = os.path.getsize(resultado.ruta_excel) / 1024
        print(f"  Tamaño: {size_kb:.1f} KB")
if resultado.razon_detencion:
    print(f"Razon detencion: {resultado.razon_detencion}")

# Pasos del pipeline
print(f"\nPasos ({len(resultado.pasos)}):")
ocr_first_data = None
dispatcher_data = None
for paso in resultado.pasos:
    status = "OK" if paso.exito else "FAIL"
    print(f"  [{status}] {paso.paso}: {paso.duracion_ms:.0f} ms ({paso.duracion_ms / 1000:.1f}s)")
    if paso.mensaje:
        print(f"         {paso.mensaje}")
    if paso.error:
        print(f"         ERROR: {paso.error}")
    # Extraer datos OCR-first del paso parseo_profundo
    if paso.paso == "parseo_profundo" and paso.datos:
        ocr_first_data = paso.datos.get("ocr_first")
        dispatcher_data = paso.datos.get("dispatcher")

# Métricas OCR-first (ADR-011 Nivel 2)
print("\n" + "=" * 70)
print("MÉTRICAS ADR-011 NIVEL 2: OCR-FIRST")
print("=" * 70)
if ocr_first_data:
    print(f"  Páginas resueltas sin VLM:  {ocr_first_data['paginas_resueltas_sin_vlm']}")
    print(f"  Páginas escaladas a VLM:    {ocr_first_data['paginas_escaladas_vlm']}")
    print(f"  Score promedio OCR:          {ocr_first_data['score_promedio_ocr']:.3f}")
    print(f"  Scores por página:           {ocr_first_data['scores_por_pagina']}")
else:
    print("  (Sin datos OCR-first — posiblemente 0 páginas comprobante)")

if dispatcher_data:
    print("\n  Dispatcher:")
    print(f"    Total páginas PDF:         {dispatcher_data['total_paginas_pdf']}")
    print(f"    Páginas comprobante:       {dispatcher_data['paginas_comprobante']}")
    print(f"    Páginas digitales:         {dispatcher_data['paginas_digitales']}")
    print(f"    Páginas imagen:            {dispatcher_data['paginas_imagen']}")
    print(f"    Páginas enviadas al VLM:   {dispatcher_data['paginas_enviadas_vlm']}")
    print(f"    Tipos detectados:          {dispatcher_data['tipos_detectados']}")
    print(f"    Tiempo VLM total:          {dispatcher_data['tiempo_vlm_total_s']:.1f}s")
    print(f"    Tiempo VLM promedio/pág:   {dispatcher_data['tiempo_vlm_promedio_s']:.1f}s")

# Comprobantes extraídos
n_comp = 0
if resultado.expediente:
    exp = resultado.expediente
    n_comp = len(exp.comprobantes) if exp.comprobantes else 0
    print(f"\nComprobantes extraídos: {n_comp}")
    if n_comp > 0:
        for i, c in enumerate(exp.comprobantes[:25]):
            # Acceder a campos via grupos del contrato
            tipo_val = c.grupo_b.tipo_comprobante.valor if c.grupo_b.tipo_comprobante else "?"
            serie_val = c.grupo_b.serie.valor if c.grupo_b.serie else "?"
            num_val = c.grupo_b.numero.valor if c.grupo_b.numero else "?"
            ruc_val = c.grupo_a.ruc_emisor.valor if c.grupo_a.ruc_emisor else "?"
            total_val = c.grupo_f.importe_total.valor if c.grupo_f.importe_total else "?"
            fecha_val = c.grupo_b.fecha_emision.valor if c.grupo_b.fecha_emision else "?"
            metodo = c.grupo_k.metodo_extraccion if c.grupo_k else "?"
            pag = c.grupo_k.pagina_origen if c.grupo_k else "?"
            print(
                f"    [{i + 1:2d}] p{pag:>2} {tipo_val:<10} {serie_val}-{num_val:<10} "
                f"RUC:{ruc_val} Total:{total_val} Fecha:{fecha_val} [{metodo}]"
            )

# Decision del router
if resultado.decision:
    d = resultado.decision
    status_val = d.resultado.status.value if d.resultado else "N/A"
    print("\nDecision del Router:")
    print(f"  Status: {status_val}")
    print(f"  Accion: {d.accion}")

# Observaciones
print(f"\nObservaciones ({len(resultado.observaciones)}):")
for obs in resultado.observaciones[:20]:
    nivel = getattr(obs, "nivel", "?")
    print(f"  - [{nivel}] {obs.descripcion[:120]}")

# COMPARACIÓN CON BASELINE
print("\n" + "=" * 70)
print("COMPARACIÓN v3.0.0 (OCR-first) vs BASELINE v2.0.0")
print("=" * 70)

paginas_vlm_ahora = dispatcher_data["paginas_enviadas_vlm"] if dispatcher_data else "?"
ocr_resueltas = ocr_first_data["paginas_resueltas_sin_vlm"] if ocr_first_data else 0
score_prom = ocr_first_data["score_promedio_ocr"] if ocr_first_data else 0
vlm_time = dispatcher_data["tiempo_vlm_total_s"] if dispatcher_data else "?"

print(f"  {'Métrica':<35} {'Baseline v2.0':<20} {'v3.0.0 OCR-first':<20}")
print(f"  {'-' * 35} {'-' * 20} {'-' * 20}")
print(f"  {'Comprobantes extraídos':<35} {BASELINE['comprobantes']:<20} {n_comp:<20}")
print(f"  {'Páginas enviadas al VLM':<35} {BASELINE['paginas_vlm']:<20} {paginas_vlm_ahora!s:<20}")
print(f"  {'Páginas resueltas sin VLM':<35} {'0':<20} {ocr_resueltas!s:<20}")
print(f"  {'Tiempo total':<35} {'~45 min':<20} {f'{dur_s:.0f}s ({dur_s / 60:.1f} min)':<20}")
print(f"  {'Tiempo VLM':<35} {'~45 min':<20} {f'{vlm_time}s'!s:<20}")
print(f"  {'Score promedio OCR':<35} {'N/A':<20} {score_prom!s:<20}")

if isinstance(paginas_vlm_ahora, int) and BASELINE["paginas_vlm"] > 0:
    reduccion_vlm = (1 - paginas_vlm_ahora / BASELINE["paginas_vlm"]) * 100
    print(f"\n  >> Reducción llamadas VLM: {reduccion_vlm:.0f}%")
if dur_s > 0 and BASELINE["duracion_s"] > 0:
    speedup = BASELINE["duracion_s"] / dur_s
    print(f"  >> Speedup vs baseline: {speedup:.1f}x más rápido")

print("=" * 70)
