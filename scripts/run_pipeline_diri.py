#!/usr/bin/env python3
"""E2E test: pipeline escribano_fiel con expediente DIRI2026-INT-0196314."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import NaturalezaExpediente
from src.extraction.escribano_fiel import ConfigPipeline, EscribanoFiel

PDF = "data/expedientes/pruebas/viaticos_2026/DIRI2026-INT-0196314_12.03.2026/2026031211199PV0086JOSEADRIANZENRENDICION.pdf"
SINAD = "DIRI2026-INT-0196314"

print("=" * 70)
print("AG-EVIDENCE — E2E Pipeline Test (Fase 3 Integration)")
print(f"Expediente: {SINAD}")
print(f"PDF: {os.path.basename(PDF)}")
print("Baseline: 0 comprobantes, CRITICAL")
print("=" * 70)

# Usar directorios temporales para evitar conflicto con custody existente
tmpdir = tempfile.mkdtemp(prefix="ag_evidence_e2e_")
config = ConfigPipeline(
    vault_dir=os.path.join(tmpdir, "vault"),
    registry_dir=os.path.join(tmpdir, "registry"),
    output_dir="output",
    log_dir=os.path.join(tmpdir, "logs"),
    generar_excel=True,
    detener_en_critical=False,  # No detener, queremos ver el resultado completo
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
print(
    f"Duracion total: {resultado.duracion_total_ms:.0f} ms ({resultado.duracion_total_ms / 1000:.1f}s)"
)

if resultado.ruta_excel:
    print(f"Excel generado: {resultado.ruta_excel}")
    if os.path.exists(resultado.ruta_excel):
        size_kb = os.path.getsize(resultado.ruta_excel) / 1024
        print(f"  Tamaño: {size_kb:.1f} KB")
if resultado.razon_detencion:
    print(f"Razon detencion: {resultado.razon_detencion}")

print(f"\nPasos ({len(resultado.pasos)}):")
for paso in resultado.pasos:
    status = "OK" if paso.exito else "FAIL"
    print(f"  [{status}] {paso.paso}: {paso.duracion_ms:.0f} ms")
    if paso.mensaje:
        print(f"         {paso.mensaje}")
    if paso.datos:
        for k, v in paso.datos.items():
            if k != "vlm_stats":
                print(f"         {k}: {v}")
    if paso.error:
        print(f"         ERROR: {paso.error}")

if resultado.decision:
    d = resultado.decision
    print("\nDecision del Router:")
    print(f"  Integrity status: {d.integrity_status}")
    print(f"  Accion: {d.accion}")
    if hasattr(d, "confianza_global"):
        print(f"  Confianza global: {d.confianza_global}")

if resultado.expediente:
    exp = resultado.expediente
    n_comp = len(exp.comprobantes) if exp.comprobantes else 0
    print("\nExpedienteJSON:")
    print(f"  SINAD: {exp.sinad}")
    print(f"  Comprobantes extraidos: {n_comp}")
    if n_comp > 0:
        print("  Detalle comprobantes:")
        for i, c in enumerate(exp.comprobantes[:10]):
            tipo = getattr(c, "tipo_comprobante", "?")
            serie = getattr(c, "serie_numero", "?")
            ruc = getattr(c, "ruc_emisor", "?")
            total = getattr(c, "importe_total", "?")
            print(f"    [{i + 1}] {tipo} {serie} | RUC: {ruc} | Total: {total}")

print(f"\nObservaciones ({len(resultado.observaciones)}):")
for obs in resultado.observaciones[:15]:
    nivel = getattr(obs, "nivel", getattr(obs, "severidad", "?"))
    print(f"  - [{nivel}] {obs.descripcion[:100]}")

# Comparar con baseline
print("\n" + "=" * 70)
print("COMPARACION CON BASELINE")
print("=" * 70)
n_comp = (
    len(resultado.expediente.comprobantes)
    if resultado.expediente and resultado.expediente.comprobantes
    else 0
)
integrity = resultado.decision.integrity_status if resultado.decision else "N/A"
print("  Baseline:  0 comprobantes, CRITICAL")
print(f"  Ahora:     {n_comp} comprobantes, {integrity}")
if n_comp > 0:
    print(f"  >> MEJORA: +{n_comp} comprobantes extraidos por VLM")
else:
    print("  >> SIN CAMBIO: VLM no extrajo comprobantes")
print("=" * 70)
