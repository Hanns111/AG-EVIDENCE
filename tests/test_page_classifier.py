# -*- coding: utf-8 -*-
"""
Tests — pageClassifier v2 (scoring auditable, golden DIRI2026-INT-0196314).

Validación obligatoria:
- Páginas validez SUNAT (22,23,25,27,29,31,33,35,36,38,40,42) → SUNAT_VALIDACION
- Páginas comprobante (21,24,26,28,30,32,34,37,39,41) → COMPROBANTE (página completa; p21/p34 con 2 comprobantes físicos quedan un solo texto).
- Caso ticket térmico p37 (Cremy), negativo administrativo, p43 no comprobante.
"""

from __future__ import annotations

import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.extraction.page_classifier import VERSION_PAGE_CLASSIFIER, TipoPagina, clasificar_pagina

# Plantilla SUNAT alineada a consultas de validez (DIRI golden)
_TEXTO_SUNAT = """SUNAT — Consulta de comprobantes de pago
Resultado de la consulta
RUC del emisor: {ruc}
Tipo: Factura Electrónica
Serie - Número: {serie_num}
Importe total consultado: {monto}
Estado: VÁLIDO
Comprobante registrado ante SUNAT.
"""


@pytest.mark.parametrize(
    "pagina_golden,serie_ref,ruc,monto",
    [
        (22, "F001-017009", "20393685361", "46.00"),
        (23, "F001-00001640", "10104259249", "22.00"),
        (25, "E001-4206", "20607903744", "70.00"),
        (27, "F001-017020", "20393685361", "51.00"),
        (29, "FW01-00001421", "20607201243", "47.00"),
        (31, "F003-00000426", "20612548804", "22.00"),
        (33, "E001-250", "20614519755", "380.00"),
        (35, "FF15-0002179", "20572278779", "47.80"),
        (36, "F002-00000489", "20612548804", "30.00"),
        (38, "F002-00000493", "20612548804", "25.00"),
        (40, "E001-4234", "20607903744", "70.00"),
        (42, "E001-2666", "10001248061", "20.00"),
    ],
)
def test_golden_paginas_sunat_100_sunat_validacion(
    pagina_golden: int,
    serie_ref: str,
    ruc: str,
    monto: str,
) -> None:
    texto = _TEXTO_SUNAT.format(ruc=ruc, serie_num=serie_ref, monto=monto)
    c = clasificar_pagina(texto)
    assert c.tipo is TipoPagina.SUNAT_VALIDACION, (
        f"p{pagina_golden}: esperado SUNAT, got {c.tipo} "
        f"sunat={c.score_sunat} comp={c.score_comprobante} {c.senales_activadas}"
    )
    assert c.pasa_a_extraccion is False
    assert c.score_sunat >= 3
    assert c.score_comprobante >= 1  # la página repite serie; el umbral SUNAT debe ganar


_PAG21_DOBLE = """FACTURA DE VENTA ELECTRÓNICA
Representación impresa — F001-017009
RUC 20393685361 PARRILLADAS EL BRASERITO S.R.L.
Cliente MINISTERIO DE EDUCACION RUC 20131370998
OP. EXONERADAS 46.00 IGV 0.00
IMPORTE TOTAL 46.00

FACTURA ELECTRÓNICA F001-00001640
R.U.C. 10104259249 BAUTISTA ZEREMELCO — YULULU HELADOS
Comprador MINISTERIO DE EDUCACION 20131370998
Detalle CAFE AMERICANO 6.00 NIU TRIPLE 8.00
OP EXONERADAS 22.00
Total 22.00
"""

_TEXTO_COMP_POR_PAGINA = {
    21: _PAG21_DOBLE,
    24: """FACTURA ELECTRÓNICA E001-4206
RUC 20607903744 AERO TRANSPORTES CALLAO S.A.C.
MINISTERIO DE EDUCACION 20131370998
SERVICIO TAXI 70.00
VALOR VENTA 70.00 IMPORTE TOTAL 70.00""",
    26: """FACTURA DE VENTA ELECTRÓNICA F001-017020
RUC 20393685361 PARRILLADAS EL BRASERITO
Cant. 1 LOMO SALTADO 40.00 Cant. 1 JARRA 11.00
OP. EXONERADAS 51.00
SUBTOTAL VENTAS 51.00 IMPORTE TOTAL 51.00""",
    28: """FACTURA ELECTRÓNICA FW01-00001421
RUC 20607201243 PAPA CHOLO RESTAURANTE E.I.R.L.
POLLO ORIENTAL 34.00 LIMONADA 13.00
OP EXONERADAS 47.00 IMPORTE TOTAL 47.00""",
    30: """FACTURA DE VENTA ELECTRÓNICA F003-00000426
RUC 20612548804 CREMY S.A.C.
Descripcion Power cant 1 unid importe 22.00
OP EXONERADAS 22.00 IMPORTE TOTAL 22.00""",
    32: """FACTURA ELECTRÓNICA E001-250
RUC 20614519755 GRUPO ALIANZA TOTAL E.I.R.L.
SERVICIO DE ALOJAMIENTO 360.00 LATE CHECK OUT 20.00
SUBTOTAL VENTAS 380.00 IMPORTE TOTAL 380.00""",
    34: """FACTURA ELECTRÓNICA FF15-0002179
RUC 20572278779 INVERSIONES INMOBILIARIAS TARAPOTO SAC
COSTILLA BBQ 38.90 CHICHA 10.00
OP NO GRAVADA 47.80 IMPORTE TOTAL 47.80

FACTURA DE VENTA ELECTRÓNICA F002-00000489
RUC 20612548804 CREMY S.A.C.
Jugo de mango 12.00 Sandwich pollo 18.00
OP EXONERADAS 30.00 TOTAL 30.00""",
    37: """CREMY SAC
FACTURA DE VENTA ELECTRÓNICA F002-00000493
RUC 20612548804
Desayuno Cremy 25.00
OP EXONERADAS 25.00
IMPORTE TOTAL 25.00
EFECTIVO 30.00
VUELTO -5.00
""",
    39: """FACTURA ELECTRÓNICA E001-4234
RUC 20607903744 AERO TRANSPORTES CALLAO S.A.C.
MINISTERIO DE EDUCACION 20131370998
TAXI AEROPUERTO 70.00
VALOR VENTA 70.00 IMPORTE TOTAL 70.00""",
    41: """FACTURA ELECTRÓNICA E001-2666
RUC 10001248061 CACERES ESPINOZA LUDOVICO
MOVILIDAD HOTEL AEROPUERTO 20.00
SUBTOTAL VENTAS 20.00 IMPORTE TOTAL 20.00""",
}


@pytest.mark.parametrize("pagina_golden", sorted(_TEXTO_COMP_POR_PAGINA.keys()))
def test_golden_paginas_comprobante_100_comprobante(pagina_golden: int) -> None:
    texto = _TEXTO_COMP_POR_PAGINA[pagina_golden]
    c = clasificar_pagina(texto)
    assert c.tipo is TipoPagina.COMPROBANTE, (
        f"p{pagina_golden}: esperado COMPROBANTE, got {c.tipo} "
        f"sunat={c.score_sunat} comp={c.score_comprobante} {c.senales_activadas}"
    )
    assert c.pasa_a_extraccion is True
    assert c.score_comprobante >= 2
    assert c.score_sunat < 3


def test_ticket_termico_p37_senales_termico_o_estructura() -> None:
    c = clasificar_pagina(_TEXTO_COMP_POR_PAGINA[37])
    assert c.tipo is TipoPagina.COMPROBANTE
    labels = " ".join(c.senales_activadas)
    assert "comprobante.serie_valida(+2)" in labels
    assert (
        "comprobante.ticket_termico(+1)" in labels
        or "comprobante.estructura_items_totales(+1)" in labels
        or "comprobante.ruc_y_total(+1)" in labels
    )


def test_negativo_administrativo_anexo3_es_otros() -> None:
    texto = """ANEXO N° 3
RENDICION DE CUENTAS POR VIATICOS
DIRECCION DE RELACIONES INTERGUBERNAMENTALES
Comisionado: ADRIANZEN CHINGA JOSE MANUEL
Destino: UCAYALI
Monto recibido 1700.00 Total gastado 936.80
"""
    c = clasificar_pagina(texto)
    assert c.tipo is TipoPagina.OTROS
    assert c.pasa_a_extraccion is False


def test_p43_devolucion_no_es_comprobante() -> None:
    texto = """RECIBO DE INGRESO — BANCO DE LA NACION
Devolucion de saldos viaticos
Ordenante ADRIANZEN CHINGA JOSE MANUEL DNI 08623419
Monto 763.20
"""
    c = clasificar_pagina(texto)
    assert c.tipo is not TipoPagina.COMPROBANTE
    assert c.pasa_a_extraccion is False


def test_clasificacion_auditable_expone_scores() -> None:
    c = clasificar_pagina(
        "consulta de comprobante\nSUNAT\nResultado de la consulta\nEstado: valido"
    )
    assert isinstance(c.senales_activadas, list)
    assert c.score_sunat >= 3
    assert isinstance(c.score_comprobante, int)


def test_version_modulo() -> None:
    assert VERSION_PAGE_CLASSIFIER == "2.0.0"
