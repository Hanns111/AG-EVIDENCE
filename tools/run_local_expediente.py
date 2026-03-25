# -*- coding: utf-8 -*-
"""
Ejecución local de expedientes → Excel (uso personal).

Importa el pipeline AG-EVIDENCE sin modificar src/. Itera PDFs en una carpeta,
acumula comprobantes y escribe una hoja resumen con columnas fijas.

Uso (desde la raíz del repo, o con PYTHONPATH):

  python tools/run_local_expediente.py "C:\\Users\\Hans\\Downloads\\CMPA2026-INT-0305757"

  python tools/run_local_expediente.py RUTA_CARPETA --output output/mi_expediente.xlsx

Por defecto el Excel se guarda en output/<slug>.xlsx donde slug sale del nombre
de la carpeta (ej. CMPA2026-INT-0305757 → cmpa2026_int_0305757.xlsx).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional

# Raíz del repositorio (tools/ -> padre)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.settings import OUTPUT_DIR, NaturalezaExpediente
from src.extraction.abstencion import CampoExtraido
from src.extraction.escribano_fiel import ConfigPipeline, EscribanoFiel, ResultadoPipeline
from src.extraction.expediente_contract import ComprobanteExtraido
from src.extraction.page_classifier import TipoPagina, clasificar_pagina

COLUMNS = [
    "expediente",
    "archivo_pdf",
    "pagina",
    "region_id",
    "ruc",
    "proveedor",
    "tipo_comprobante",
    "serie",
    "numero",
    "fecha",
    "total",
    "confianza",
    "observaciones",
]


def _slug_desde_carpeta(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "expediente"


def _cell_null(val: Optional[str]) -> str:
    """Representación explícita NULL para celdas sin dato probatorio."""
    if val is None or (isinstance(val, str) and not val.strip()):
        return "NULL"
    return str(val)


def _campo_valor(c: Optional[CampoExtraido]) -> Optional[str]:
    if c is None:
        return None
    if c.es_abstencion():
        return None
    return c.valor


def _archivo_pdf_comp(c: ComprobanteExtraido) -> str:
    for campo in c.todos_los_campos():
        if campo.archivo:
            return campo.archivo
    return ""


def _observaciones_comp(c: ComprobanteExtraido) -> str:
    parts: List[str] = []
    obs = c.grupo_d.observaciones if c.grupo_d else None
    v = _campo_valor(obs)
    if v:
        parts.append(v)
    if c.grupo_k and c.grupo_k.campos_no_encontrados:
        parts.append("faltantes: " + ", ".join(c.grupo_k.campos_no_encontrados))
    return " | ".join(parts) if parts else "NULL"


def _contar_paginas_sunat(resultado: ResultadoPipeline) -> int:
    for paso in resultado.pasos:
        if paso.paso != "extraccion_ocr" or not paso.datos:
            continue
        paginas = paso.datos.get("paginas") or []
        n = 0
        for p in paginas:
            texto = (p.get("texto") or "").strip()
            if not texto:
                continue
            if clasificar_pagina(texto).tipo == TipoPagina.SUNAT_VALIDACION:
                n += 1
        return n
    return 0


def _fila_desde_comprobante(expediente_id: str, c: ComprobanteExtraido) -> List[str]:
    rn = _campo_valor(c.grupo_a.razon_social if c.grupo_a else None)
    nc = _campo_valor(c.grupo_a.nombre_comercial if c.grupo_a else None)
    proveedor = rn or nc

    return [
        expediente_id,
        _archivo_pdf_comp(c) or "NULL",
        str(c.grupo_k.pagina_origen) if c.grupo_k and c.grupo_k.pagina_origen else "NULL",
        "NULL",  # el contrato actual no expone region_id por comprobante
        _cell_null(_campo_valor(c.grupo_a.ruc_emisor if c.grupo_a else None)),
        _cell_null(proveedor),
        _cell_null(_campo_valor(c.grupo_b.tipo_comprobante if c.grupo_b else None)),
        _cell_null(_campo_valor(c.grupo_b.serie if c.grupo_b else None)),
        _cell_null(_campo_valor(c.grupo_b.numero if c.grupo_b else None)),
        _cell_null(_campo_valor(c.grupo_b.fecha_emision if c.grupo_b else None)),
        _cell_null(_campo_valor(c.grupo_f.importe_total if c.grupo_f else None)),
        c.grupo_k.confianza_global if c.grupo_k and c.grupo_k.confianza_global else "NULL",
        _observaciones_comp(c),
    ]


def _escribir_excel(path: Path, filas: List[List[str]]) -> None:
    from openpyxl import Workbook

    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "comprobantes"
    ws.append(COLUMNS)
    for row in filas:
        ws.append(row)
    wb.save(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Procesar carpeta de PDFs con AG-EVIDENCE y generar Excel resumen.",
    )
    parser.add_argument(
        "carpeta",
        type=Path,
        help=r"Ruta a la carpeta del expediente (ej. C:\Users\...\CMPA2026-INT-0305757)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Ruta del .xlsx de salida (por defecto: output/<slug>.xlsx)",
    )
    parser.add_argument(
        "--sinad",
        type=str,
        default=None,
        help="Identificador SINAD/expediente (por defecto: nombre de la carpeta)",
    )
    args = parser.parse_args()

    carpeta: Path = args.carpeta.expanduser()
    if not carpeta.is_dir():
        print(f"ERROR: no es carpeta: {carpeta}", file=sys.stderr)
        return 1

    pdfs = sorted(p for p in carpeta.iterdir() if p.suffix.lower() == ".pdf")
    if not pdfs:
        print(f"ERROR: sin PDFs en {carpeta}", file=sys.stderr)
        return 1

    expediente_id = args.sinad or carpeta.name
    slug = _slug_desde_carpeta(carpeta.name)
    out_path = args.output
    if out_path is None:
        out_path = Path(OUTPUT_DIR) / f"{slug}.xlsx"
    else:
        out_path = out_path.expanduser()

    cfg = ConfigPipeline(
        generar_excel=False,
        detener_en_critical=False,
        vlm_enabled=True,
    )
    escribano = EscribanoFiel(config=cfg)

    filas: List[List[str]] = []
    total_sunat = 0
    errores: List[str] = []

    for pdf in pdfs:
        res = escribano.procesar_expediente(
            pdf_path=str(pdf.resolve()),
            sinad=expediente_id,
            naturaleza=NaturalezaExpediente.NO_DETERMINADO,
            ruta_excel=None,
        )
        total_sunat += _contar_paginas_sunat(res)
        if not res.expediente:
            errores.append(f"{pdf.name}: sin expediente en resultado")
            continue
        comprobantes = res.expediente.comprobantes or []
        print(
            f"[DIAG tool] {pdf.name} -> res.expediente.comprobantes: "
            f"len={len(comprobantes)} (iteracion fila a fila)",
            flush=True,
        )
        for c in comprobantes:
            filas.append(_fila_desde_comprobante(expediente_id, c))
        print(
            f"[DIAG tool] {pdf.name} filas añadidas al Excel: {len(comprobantes)} "
            f"| acumulado filas todas={len(filas)}",
            flush=True,
        )
        if not res.exito and res.razon_detencion:
            errores.append(f"{pdf.name}: pipeline {res.exito=} {res.razon_detencion}")

    _escribir_excel(out_path, filas)

    total_comp = len(filas)
    print("--- run_local_expediente ---")
    print(f"Carpeta: {carpeta}")
    print(f"Total PDFs: {len(pdfs)}")
    print(f"Total comprobantes detectados: {total_comp}")
    print(f"Páginas SUNAT (clasificador sobre texto OCR por página): {total_sunat}")
    print(f"Excel: {out_path.resolve()}")
    if errores:
        print("Avisos:")
        for e in errores:
            print(f"  - {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
