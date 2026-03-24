#!/usr/bin/env python3
"""Script temporal para probar el pipeline escribano_fiel con expediente real."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.extraction.escribano_fiel import procesar_expediente
from config.settings import NaturalezaExpediente

PDF = "data/expedientes/pruebas/viaticos_2026/DIGC2026-INT-0073285/20260209151142RendicionJoseLuisHuaman.pdf"
SINAD = "DIGC2026-INT-0073285"

print("=" * 60)
print("AG-EVIDENCE — Pipeline Test")
print(f"Expediente: {SINAD}")
print(f"PDF: {os.path.basename(PDF)}")
print("=" * 60)

resultado = procesar_expediente(
    pdf_path=PDF,
    sinad=SINAD,
    naturaleza=NaturalezaExpediente.VIATICOS,
)

print("\n" + "=" * 60)
print("RESULTADO DEL PIPELINE")
print("=" * 60)
print(f"Exito: {resultado.exito}")
print(f"Detenido: {resultado.detenido}")
print(f"Duracion total: {resultado.duracion_total_ms:.0f} ms ({resultado.duracion_total_ms / 1000:.1f}s)")

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
    if paso.error:
        print(f"         ERROR: {paso.error}")

if resultado.decision:
    d = resultado.decision
    print(f"\nDecision del Router:")
    print(f"  Integrity status: {d.integrity_status}")
    print(f"  Accion: {d.accion}")
    if hasattr(d, "confianza_global"):
        print(f"  Confianza global: {d.confianza_global}")

if resultado.custody_record:
    cr = resultado.custody_record
    print(f"\nCustodia:")
    print(f"  SHA-256: {cr.sha256[:32]}...")
    print(f"  Timestamp: {cr.timestamp}")

if resultado.expediente:
    exp = resultado.expediente
    print(f"\nExpedienteJSON:")
    print(f"  SINAD: {exp.sinad}")
    if hasattr(exp, "paginas_procesadas"):
        print(f"  Paginas: {exp.paginas_procesadas}")

print(f"\nObservaciones ({len(resultado.observaciones)}):")
for obs in resultado.observaciones[:10]:
    print(f"  - [{obs.severidad}] {obs.descripcion[:80]}")

print("=" * 60)
