"""E2E Pipeline Verification Script — Fase 1+2 formal check."""

import json
import os
import sys
import time

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import NaturalezaExpediente
from src.extraction.escribano_fiel import procesar_expediente

PDF_PATH = "/mnt/c/Users/Hans/Proyectos/AG-EVIDENCE/data/expedientes/pruebas/viaticos_2026/OPRE2026-INT-0131766_12.FEB.2026_/20260212144251EXPEDIENTE202602RENDICIONPARAREVI.pdf"
SINAD = "OPRE2026-INT-0131766"


def main():
    print("=" * 60)
    print("E2E PIPELINE VERIFICATION — AG-EVIDENCE")
    print("=" * 60)
    print(f"PDF: {PDF_PATH}")
    print(f"SINAD: {SINAD}")
    print("Naturaleza: VIATICOS")
    print()

    t0 = time.time()
    resultado = procesar_expediente(
        pdf_path=PDF_PATH,
        sinad=SINAD,
        naturaleza=NaturalezaExpediente.VIATICOS,
    )
    elapsed = time.time() - t0

    print(f"\n{'=' * 60}")
    print(f"RESULTADO E2E ({elapsed:.1f}s total)")
    print(f"{'=' * 60}")
    print(f"Exito: {resultado.exito}")
    print(f"Detenido: {resultado.detenido}")
    if resultado.razon_detencion:
        print(f"Razon detencion: {resultado.razon_detencion}")
    print(f"Duracion total: {resultado.duracion_total_ms:.0f}ms")

    # Pasos
    print(f"\nPasos ejecutados: {len(resultado.pasos)}")
    for paso in resultado.pasos:
        status = "OK" if paso.exito else "FAIL"
        print(f"  [{status}] {paso.paso} — {paso.duracion_ms:.0f}ms — {paso.mensaje}")

    # Custody
    if resultado.custody_record:
        cr = resultado.custody_record
        sha = cr.sha256 if hasattr(cr, "sha256") else str(cr)
        print(f"\nCustodia: SHA-256 = {sha[:32]}...")

    # Expediente
    if resultado.expediente:
        exp = resultado.expediente
        print(f"\nExpediente: {exp.sinad}")
        if hasattr(exp, "paginas_ocr") and exp.paginas_ocr:
            print(f"  Paginas OCR: {len(exp.paginas_ocr)}")
            total_words = sum(
                len(p.texto.split()) if hasattr(p, "texto") and p.texto else 0
                for p in exp.paginas_ocr
            )
            print(f"  Palabras totales: {total_words}")
        if hasattr(exp, "comprobantes") and exp.comprobantes:
            print(f"  Comprobantes: {len(exp.comprobantes)}")
        else:
            print("  Comprobantes: 0 (esperado — parseo profundo es Fase 3)")

    # Router
    if resultado.resultado_router:
        rr = resultado.resultado_router
        ist = getattr(rr, "integrity_status", None)
        ist_val = ist.value if hasattr(ist, "value") else str(ist)
        print(f"\nRouter: integrity_status = {ist_val}")

    # Decision
    if resultado.decision:
        d = resultado.decision
        st = getattr(d, "status", None)
        st_val = st.value if hasattr(st, "value") else str(st)
        accion = getattr(d, "accion_recomendada", "N/A")
        print(f"\nDecision: status = {st_val}")
        print(f"  Accion recomendada: {accion}")

    # Excel
    if resultado.ruta_excel:
        print(f"\nExcel generado: {resultado.ruta_excel}")
        if os.path.exists(resultado.ruta_excel):
            size_kb = os.path.getsize(resultado.ruta_excel) / 1024
            print(f"  Tamano: {size_kb:.1f} KB")

    # Observaciones
    if resultado.observaciones:
        print(f"\nObservaciones: {len(resultado.observaciones)}")
        for obs in resultado.observaciones[:5]:
            sev = obs.severidad if hasattr(obs, "severidad") else "?"
            desc = obs.descripcion if hasattr(obs, "descripcion") else str(obs)
            print(f"  - [{sev}] {desc[:100]}")

    # Summary
    print(f"\n{'=' * 60}")
    pasos_ok = sum(1 for p in resultado.pasos if p.exito)
    pasos_total = len(resultado.pasos)
    print(f"RESUMEN: {pasos_ok}/{pasos_total} pasos exitosos, {elapsed:.1f}s total")
    if resultado.detenido:
        print(f"NOTA: Pipeline detenido — {resultado.razon_detencion}")
        print("Esto es ESPERADO si parseo profundo no esta implementado (Fase 3)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
