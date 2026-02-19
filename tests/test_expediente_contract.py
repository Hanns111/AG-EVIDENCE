# -*- coding: utf-8 -*-
"""
Tests para expediente_contract.py — Contrato de Datos Tipado (Tarea #17)
=========================================================================

Cobertura:
  1. Enumeraciones (6 enums)
  2. Serialización roundtrip to_dict/from_dict para cada dataclass
  3. Listas vacías y campos opcionales (None)
  4. Integración con CampoExtraido de abstencion.py
  5. Validaciones de completitud
  6. Unicidad de comprobantes
  7. Hash SHA-256
  8. Resumen de extracción
  9. DocumentosConvenio (Pautas 5.1.11)
  10. ExpedienteJSON completo (to_json/from_json)

≥50 tests requeridos por criterio de aceptación de Tarea #17.
"""

import json
import sys
import os
import pytest
from copy import deepcopy

# Asegurar path del proyecto
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.settings import MetodoExtraccion
from src.extraction.abstencion import (
    CampoExtraido,
    EvidenceStatus,
    AbstencionPolicy,
    FUENTE_ABSTENCION,
)
from src.extraction.expediente_contract import (
    # Constantes
    VERSION_CONTRATO,
    TOLERANCIA_ARITMETICA,
    # Enums
    TipoComprobante,
    CategoriaGasto,
    MetodoExtraccionContrato,
    TipoBoleto,
    ConfianzaGlobal,
    IntegridadStatus,
    # Grupos A-K
    DatosEmisor,
    DatosComprobante,
    DatosAdquirente,
    CondicionesComerciales,
    ItemDetalle,
    TotalesTributos,
    ClasificacionGasto,
    DatosHospedaje,
    DatosMovilidad,
    ValidacionesAritmeticas,
    MetadatosExtraccion,
    # Contenedores
    ComprobanteExtraido,
    GastoDeclaracionJurada,
    BoletoTransporte,
    ItemAnexo3,
    DatosAnexo3,
    DocumentosConvenio,
    ArchivoFuente,
    ResumenExtraccion,
    IntegridadExpediente,
    # Top-level
    ExpedienteJSON,
)


# ==============================================================================
# FIXTURES
# ==============================================================================

def _crear_campo(nombre: str, valor: str, confianza: float = 0.92) -> CampoExtraido:
    """Helper para crear CampoExtraido con datos mínimos."""
    return CampoExtraido(
        nombre_campo=nombre,
        valor=valor,
        archivo="test.pdf",
        pagina=1,
        confianza=confianza,
        metodo=MetodoExtraccion.OCR,
        snippet=f"{nombre}: {valor}",
        tipo_campo="texto",
    )


def _crear_campo_abstencion(nombre: str) -> CampoExtraido:
    """Helper para crear un campo en abstención formal."""
    return CampoExtraido(
        nombre_campo=nombre,
        valor=None,
        archivo="test.pdf",
        pagina=0,
        confianza=0.0,
        metodo=MetodoExtraccion.MANUAL,
        snippet="",
        tipo_campo="texto",
        regla_aplicada="ABSTENCION",
    )


def _crear_comprobante_minimo() -> ComprobanteExtraido:
    """Helper para crear un comprobante con datos mínimos."""
    return ComprobanteExtraido(
        grupo_a=DatosEmisor(
            ruc_emisor=_crear_campo("ruc_emisor", "20100039207"),
            razon_social=_crear_campo("razon_social", "EMPRESA TEST S.A.C."),
        ),
        grupo_b=DatosComprobante(
            tipo_comprobante=_crear_campo("tipo_comprobante", "FACTURA"),
            serie=_crear_campo("serie", "F001"),
            numero=_crear_campo("numero", "00000468"),
            fecha_emision=_crear_campo("fecha_emision", "2026-02-10"),
        ),
        grupo_f=TotalesTributos(
            subtotal=_crear_campo("subtotal", "100.00"),
            igv_monto=_crear_campo("igv_monto", "18.00"),
            importe_total=_crear_campo("importe_total", "118.00"),
        ),
        grupo_k=MetadatosExtraccion(
            pagina_origen=5,
            metodo_extraccion="pymupdf",
            confianza_global="alta",
            timestamp_extraccion="2026-02-19T10:00:00Z",
        ),
    )


def _crear_expediente_completo() -> ExpedienteJSON:
    """Helper para crear un ExpedienteJSON completo para tests."""
    comp1 = _crear_comprobante_minimo()
    comp2 = ComprobanteExtraido(
        grupo_b=DatosComprobante(
            serie=_crear_campo("serie", "B001"),
            numero=_crear_campo("numero", "00005678"),
        ),
    )
    dj = GastoDeclaracionJurada(
        fecha=_crear_campo("fecha", "2026-02-10"),
        monto=_crear_campo("monto", "15.00"),
        descripcion=_crear_campo("descripcion", "Taxi aeropuerto"),
    )
    boleto = BoletoTransporte(
        tipo=_crear_campo("tipo", "AEREO"),
        empresa=_crear_campo("empresa", "LATAM"),
        ruta=_crear_campo("ruta", "LIM-PIU"),
        fecha=_crear_campo("fecha", "2026-02-07"),
    )
    archivo = ArchivoFuente(
        nombre="expediente.pdf",
        ruta_relativa="data/expedientes/exp001.pdf",
        hash_sha256="abc123def",
        tamaño_bytes=1024000,
        total_paginas=50,
        fecha_procesamiento="2026-02-19T10:00:00Z",
    )
    return ExpedienteJSON(
        sinad="OT2026-INT-0179550",
        naturaleza="VIÁTICOS",
        categoria="VIATICOS",
        extraido_por="pipeline_test_v1",
        timestamp_generacion="2026-02-19T10:00:00Z",
        archivos_fuente=[archivo],
        comprobantes=[comp1, comp2],
        declaracion_jurada=[dj],
        boletos=[boleto],
    )


# ==============================================================================
# 1. ENUMERACIONES
# ==============================================================================

class TestEnumeraciones:
    """Tests para las 6 enumeraciones del contrato."""

    def test_tipo_comprobante_valores(self):
        assert TipoComprobante.FACTURA.value == "FACTURA"
        assert TipoComprobante.BOLETA.value == "BOLETA"
        assert TipoComprobante.RECIBO_HONORARIOS.value == "RECIBO_HONORARIOS"
        assert len(TipoComprobante) == 8

    def test_categoria_gasto_valores(self):
        assert CategoriaGasto.ALIMENTACION.value == "ALIMENTACION"
        assert CategoriaGasto.HOSPEDAJE.value == "HOSPEDAJE"
        assert len(CategoriaGasto) == 5

    def test_metodo_extraccion_contrato(self):
        assert MetodoExtraccionContrato.PYMUPDF.value == "pymupdf"
        assert MetodoExtraccionContrato.QWEN_VL.value == "qwen_vl"
        assert MetodoExtraccionContrato.PADDLEOCR_GPU.value == "paddleocr_gpu"

    def test_tipo_boleto(self):
        assert TipoBoleto.AEREO.value == "AEREO"
        assert TipoBoleto.TERRESTRE.value == "TERRESTRE"
        assert TipoBoleto.BOARDING_PASS.value == "BOARDING_PASS"

    def test_confianza_global(self):
        assert ConfianzaGlobal.ALTA.value == "alta"
        assert ConfianzaGlobal.MEDIA.value == "media"
        assert ConfianzaGlobal.BAJA.value == "baja"

    def test_integridad_status(self):
        assert IntegridadStatus.OK.value == "OK"
        assert IntegridadStatus.WARNING.value == "WARNING"
        assert IntegridadStatus.CRITICAL.value == "CRITICAL"


# ==============================================================================
# 2. GRUPO A — DatosEmisor
# ==============================================================================

class TestDatosEmisor:
    """Tests para Grupo A."""

    def test_vacio(self):
        emisor = DatosEmisor()
        assert emisor.ruc_emisor is None
        assert emisor.razon_social is None

    def test_con_campos(self):
        emisor = DatosEmisor(
            ruc_emisor=_crear_campo("ruc_emisor", "20100039207"),
            razon_social=_crear_campo("razon_social", "EMPRESA S.A.C."),
        )
        assert emisor.ruc_emisor.valor == "20100039207"

    def test_roundtrip(self):
        emisor = DatosEmisor(
            ruc_emisor=_crear_campo("ruc_emisor", "20100039207"),
            razon_social=_crear_campo("razon_social", "EMPRESA S.A.C."),
            direccion_emisor=_crear_campo("direccion", "Av. Javier Prado 123"),
        )
        d = emisor.to_dict()
        reconstruido = DatosEmisor.from_dict(d)
        assert reconstruido.ruc_emisor.valor == "20100039207"
        assert reconstruido.razon_social.valor == "EMPRESA S.A.C."
        assert reconstruido.direccion_emisor.valor == "Av. Javier Prado 123"

    def test_from_dict_none(self):
        emisor = DatosEmisor.from_dict(None)
        assert emisor.ruc_emisor is None

    def test_campos_list(self):
        emisor = DatosEmisor(
            ruc_emisor=_crear_campo("ruc", "20100039207"),
        )
        campos = emisor.campos_list()
        assert len(campos) == 1
        assert campos[0].valor == "20100039207"

    def test_campos_list_vacia(self):
        emisor = DatosEmisor()
        assert len(emisor.campos_list()) == 0


# ==============================================================================
# 3. GRUPO B — DatosComprobante
# ==============================================================================

class TestDatosComprobante:
    """Tests para Grupo B."""

    def test_roundtrip(self):
        comp = DatosComprobante(
            tipo_comprobante=_crear_campo("tipo", "FACTURA"),
            serie=_crear_campo("serie", "F001"),
            numero=_crear_campo("numero", "00000468"),
            fecha_emision=_crear_campo("fecha", "2026-02-10"),
            moneda=_crear_campo("moneda", "PEN"),
        )
        d = comp.to_dict()
        reconstruido = DatosComprobante.from_dict(d)
        assert reconstruido.serie.valor == "F001"
        assert reconstruido.numero.valor == "00000468"
        assert reconstruido.moneda.valor == "PEN"

    def test_from_dict_vacio(self):
        comp = DatosComprobante.from_dict({})
        assert comp.serie is None
        assert comp.numero is None

    def test_campos_list_parcial(self):
        comp = DatosComprobante(
            serie=_crear_campo("serie", "F001"),
            numero=_crear_campo("numero", "468"),
        )
        assert len(comp.campos_list()) == 2


# ==============================================================================
# 4. GRUPO C — DatosAdquirente
# ==============================================================================

class TestDatosAdquirente:
    """Tests para Grupo C."""

    def test_roundtrip(self):
        adq = DatosAdquirente(
            ruc_adquirente=_crear_campo("ruc_adq", "20131370998"),
            razon_social_adquirente=_crear_campo("rs_adq", "MINEDU"),
        )
        d = adq.to_dict()
        r = DatosAdquirente.from_dict(d)
        assert r.ruc_adquirente.valor == "20131370998"
        assert r.razon_social_adquirente.valor == "MINEDU"


# ==============================================================================
# 5. GRUPO D — CondicionesComerciales
# ==============================================================================

class TestCondicionesComerciales:
    """Tests para Grupo D."""

    def test_roundtrip(self):
        cc = CondicionesComerciales(
            condicion_pago=_crear_campo("cond", "CONTADO"),
            observaciones=_crear_campo("obs", "Pie de página informativo"),
        )
        d = cc.to_dict()
        r = CondicionesComerciales.from_dict(d)
        assert r.condicion_pago.valor == "CONTADO"
        assert r.observaciones.valor == "Pie de página informativo"


# ==============================================================================
# 6. GRUPO E — ItemDetalle
# ==============================================================================

class TestItemDetalle:
    """Tests para Grupo E."""

    def test_roundtrip(self):
        item = ItemDetalle(
            cantidad=_crear_campo("cant", "2"),
            descripcion=_crear_campo("desc", "Almuerzo menú ejecutivo"),
            valor_unitario=_crear_campo("vu", "25.00"),
            importe=_crear_campo("imp", "50.00"),
        )
        d = item.to_dict()
        r = ItemDetalle.from_dict(d)
        assert r.cantidad.valor == "2"
        assert r.importe.valor == "50.00"

    def test_item_vacio(self):
        item = ItemDetalle()
        assert len(item.campos_list()) == 0


# ==============================================================================
# 7. GRUPO F — TotalesTributos
# ==============================================================================

class TestTotalesTributos:
    """Tests para Grupo F."""

    def test_roundtrip_completo(self):
        tt = TotalesTributos(
            subtotal=_crear_campo("subtotal", "100.00"),
            igv_tasa=_crear_campo("igv_tasa", "18"),
            igv_monto=_crear_campo("igv", "18.00"),
            importe_total=_crear_campo("total", "118.00"),
            total_exonerado=_crear_campo("exonerado", "0.00"),
        )
        d = tt.to_dict()
        r = TotalesTributos.from_dict(d)
        assert r.subtotal.valor == "100.00"
        assert r.igv_monto.valor == "18.00"
        assert r.importe_total.valor == "118.00"
        assert r.total_exonerado.valor == "0.00"
        # Campo None no reconstruido
        assert r.total_inafecto is None


# ==============================================================================
# 8. GRUPO G — ClasificacionGasto
# ==============================================================================

class TestClasificacionGasto:
    """Tests para Grupo G."""

    def test_roundtrip(self):
        cg = ClasificacionGasto(
            categoria_gasto=_crear_campo("cat", "ALIMENTACION"),
            subcategoria=_crear_campo("sub", "ALMUERZO"),
        )
        d = cg.to_dict()
        r = ClasificacionGasto.from_dict(d)
        assert r.categoria_gasto.valor == "ALIMENTACION"


# ==============================================================================
# 9. GRUPO H — DatosHospedaje
# ==============================================================================

class TestDatosHospedaje:
    """Tests para Grupo H."""

    def test_roundtrip(self):
        h = DatosHospedaje(
            fecha_checkin=_crear_campo("checkin", "2026-02-07"),
            fecha_checkout=_crear_campo("checkout", "2026-02-10"),
            numero_noches=_crear_campo("noches", "3"),
            nombre_huesped=_crear_campo("huesped", "MARTINEZ LOPEZ"),
        )
        d = h.to_dict()
        r = DatosHospedaje.from_dict(d)
        assert r.fecha_checkin.valor == "2026-02-07"
        assert r.numero_noches.valor == "3"

    def test_optional_none(self):
        """Grupo H es opcional — None es válido."""
        comp = ComprobanteExtraido()
        assert comp.grupo_h is None


# ==============================================================================
# 10. GRUPO I — DatosMovilidad
# ==============================================================================

class TestDatosMovilidad:
    """Tests para Grupo I."""

    def test_roundtrip(self):
        m = DatosMovilidad(
            origen=_crear_campo("origen", "Lima"),
            destino=_crear_campo("destino", "Piura"),
            placa_vehiculo=_crear_campo("placa", "ABC-123"),
        )
        d = m.to_dict()
        r = DatosMovilidad.from_dict(d)
        assert r.origen.valor == "Lima"
        assert r.destino.valor == "Piura"


# ==============================================================================
# 11. GRUPO J — ValidacionesAritmeticas
# ==============================================================================

class TestValidacionesAritmeticas:
    """Tests para Grupo J — Python calcula, no la IA."""

    def test_todas_ok_cuando_todas_pasan(self):
        va = ValidacionesAritmeticas(
            suma_items_ok=True,
            igv_ok=True,
            total_ok=True,
        )
        assert va.todas_ok() is True

    def test_todas_ok_cuando_una_falla(self):
        va = ValidacionesAritmeticas(
            suma_items_ok=True,
            igv_ok=False,
            total_ok=True,
        )
        assert va.todas_ok() is False

    def test_todas_ok_cuando_ninguna_ejecutada(self):
        va = ValidacionesAritmeticas()
        # Sin checks ejecutados, se considera OK
        assert va.todas_ok() is True

    def test_roundtrip(self):
        va = ValidacionesAritmeticas(
            suma_items_ok=True,
            igv_ok=True,
            total_ok=False,
            noches_ok=None,
            errores_detalle=["Total no coincide: 118.00 vs 117.98"],
        )
        d = va.to_dict()
        r = ValidacionesAritmeticas.from_dict(d)
        assert r.suma_items_ok is True
        assert r.total_ok is False
        assert r.noches_ok is None
        assert len(r.errores_detalle) == 1

    def test_tolerancia_default(self):
        va = ValidacionesAritmeticas()
        assert va.tolerancia_usada == TOLERANCIA_ARITMETICA


# ==============================================================================
# 12. GRUPO K — MetadatosExtraccion
# ==============================================================================

class TestMetadatosExtraccion:
    """Tests para Grupo K."""

    def test_roundtrip(self):
        mk = MetadatosExtraccion(
            pagina_origen=5,
            metodo_extraccion="pymupdf",
            confianza_global="alta",
            campos_no_encontrados=["ruc_emisor", "igv_tasa"],
            timestamp_extraccion="2026-02-19T10:00:00Z",
        )
        d = mk.to_dict()
        r = MetadatosExtraccion.from_dict(d)
        assert r.pagina_origen == 5
        assert r.metodo_extraccion == "pymupdf"
        assert len(r.campos_no_encontrados) == 2

    def test_defaults(self):
        mk = MetadatosExtraccion()
        assert mk.pagina_origen == 0
        assert mk.confianza_global == "baja"


# ==============================================================================
# 13. ComprobanteExtraido
# ==============================================================================

class TestComprobanteExtraido:
    """Tests para el comprobante completo (Grupos A-K)."""

    def test_comprobante_vacio(self):
        comp = ComprobanteExtraido()
        assert len(comp.todos_los_campos()) == 0

    def test_comprobante_minimo_roundtrip(self):
        comp = _crear_comprobante_minimo()
        d = comp.to_dict()
        r = ComprobanteExtraido.from_dict(d)
        assert r.grupo_a.ruc_emisor.valor == "20100039207"
        assert r.grupo_b.serie.valor == "F001"
        assert r.grupo_f.importe_total.valor == "118.00"
        assert r.grupo_k.pagina_origen == 5

    def test_get_serie_numero(self):
        comp = _crear_comprobante_minimo()
        assert comp.get_serie_numero() == "F001-00000468"

    def test_get_serie_numero_sin_datos(self):
        comp = ComprobanteExtraido()
        assert comp.get_serie_numero() == "SIN_IDENTIFICAR"

    def test_grupo_e_items_roundtrip(self):
        """Grupo E es una lista de items."""
        items = [
            ItemDetalle(
                cantidad=_crear_campo("cant", "2"),
                descripcion=_crear_campo("desc", "Almuerzo"),
                importe=_crear_campo("imp", "50.00"),
            ),
            ItemDetalle(
                cantidad=_crear_campo("cant", "1"),
                descripcion=_crear_campo("desc", "Café"),
                importe=_crear_campo("imp", "8.00"),
            ),
        ]
        comp = ComprobanteExtraido(grupo_e=items)
        d = comp.to_dict()
        r = ComprobanteExtraido.from_dict(d)
        assert len(r.grupo_e) == 2
        assert r.grupo_e[0].descripcion.valor == "Almuerzo"
        assert r.grupo_e[1].importe.valor == "8.00"

    def test_grupos_opcionales_h_i(self):
        """Grupos H e I son opcionales."""
        comp = ComprobanteExtraido(
            grupo_h=DatosHospedaje(
                fecha_checkin=_crear_campo("checkin", "2026-02-07"),
            ),
        )
        d = comp.to_dict()
        r = ComprobanteExtraido.from_dict(d)
        assert r.grupo_h.fecha_checkin.valor == "2026-02-07"
        assert r.grupo_i is None

    def test_todos_los_campos_cuenta(self):
        comp = _crear_comprobante_minimo()
        campos = comp.todos_los_campos()
        # grupo_a: 2 campos (ruc_emisor, razon_social)
        # grupo_b: 4 campos (tipo, serie, numero, fecha)
        # grupo_f: 3 campos (subtotal, igv, total)
        assert len(campos) == 9


# ==============================================================================
# 14. GastoDeclaracionJurada
# ==============================================================================

class TestGastoDeclaracionJurada:
    """Tests para DJ de movilidad."""

    def test_roundtrip(self):
        dj = GastoDeclaracionJurada(
            fecha=_crear_campo("fecha", "2026-02-10"),
            descripcion=_crear_campo("desc", "Taxi aeropuerto"),
            monto=_crear_campo("monto", "15.00"),
        )
        d = dj.to_dict()
        r = GastoDeclaracionJurada.from_dict(d)
        assert r.fecha.valor == "2026-02-10"
        assert r.monto.valor == "15.00"

    def test_campos_list(self):
        dj = GastoDeclaracionJurada(
            fecha=_crear_campo("fecha", "2026-02-10"),
        )
        assert len(dj.campos_list()) == 1


# ==============================================================================
# 15. BoletoTransporte
# ==============================================================================

class TestBoletoTransporte:
    """Tests para boletos de transporte."""

    def test_roundtrip(self):
        boleto = BoletoTransporte(
            tipo=_crear_campo("tipo", "AEREO"),
            empresa=_crear_campo("empresa", "LATAM"),
            ruta=_crear_campo("ruta", "LIM-PIU"),
            fecha=_crear_campo("fecha", "2026-02-07"),
            pasajero=_crear_campo("pasajero", "MARTINEZ LOPEZ"),
        )
        d = boleto.to_dict()
        r = BoletoTransporte.from_dict(d)
        assert r.tipo.valor == "AEREO"
        assert r.empresa.valor == "LATAM"
        assert r.pasajero.valor == "MARTINEZ LOPEZ"


# ==============================================================================
# 16. DatosAnexo3
# ==============================================================================

class TestDatosAnexo3:
    """Tests para Anexo 3 de rendición."""

    def test_roundtrip_basico(self):
        anexo = DatosAnexo3(
            sinad=_crear_campo("sinad", "OT2026-INT-0179550"),
            comisionado=_crear_campo("comisionado", "LOPEZ GARCIA JUAN"),
            dni=_crear_campo("dni", "12345678"),
            viatico_otorgado=_crear_campo("viatico", "1280.00"),
            total_gastado=_crear_campo("gastado", "1100.00"),
        )
        d = anexo.to_dict()
        r = DatosAnexo3.from_dict(d)
        assert r.sinad.valor == "OT2026-INT-0179550"
        assert r.comisionado.valor == "LOPEZ GARCIA JUAN"

    def test_con_items(self):
        items = [
            ItemAnexo3(
                nro=_crear_campo("nro", "1"),
                fecha=_crear_campo("fecha", "2026-02-08"),
                importe=_crear_campo("importe", "120.00"),
            ),
            ItemAnexo3(
                nro=_crear_campo("nro", "2"),
                fecha=_crear_campo("fecha", "2026-02-09"),
                importe=_crear_campo("importe", "85.00"),
            ),
        ]
        anexo = DatosAnexo3(items=items)
        d = anexo.to_dict()
        r = DatosAnexo3.from_dict(d)
        assert len(r.items) == 2
        assert r.items[0].nro.valor == "1"
        assert r.items[1].importe.valor == "85.00"

    def test_from_dict_none(self):
        r = DatosAnexo3.from_dict(None)
        assert r.sinad is None
        assert len(r.items) == 0


# ==============================================================================
# 17. DocumentosConvenio (Pautas 5.1.11)
# ==============================================================================

class TestDocumentosConvenio:
    """Tests para convenios interinstitucionales."""

    def test_documentos_minimos_presentes_ok(self):
        dc = DocumentosConvenio(
            convenio_vigente=_crear_campo("convenio", "CONV-001-2026"),
            documento_cobranza=_crear_campo("cobranza", "LIQ-001"),
            detalle_consumo=_crear_campo("detalle", "Consumo Feb 2026"),
            informe_tecnico=_crear_campo("informe", "INF-001-2026"),
            certificacion_presupuestal=_crear_campo("ccp", "CCP-001"),
            derivacion_sinad=_crear_campo("sinad", "ESINAD-001"),
        )
        assert dc.documentos_minimos_presentes() is True

    def test_documentos_minimos_falta_uno(self):
        dc = DocumentosConvenio(
            convenio_vigente=_crear_campo("convenio", "CONV-001-2026"),
            documento_cobranza=_crear_campo("cobranza", "LIQ-001"),
            # Falta detalle_consumo
            informe_tecnico=_crear_campo("informe", "INF-001-2026"),
            certificacion_presupuestal=_crear_campo("ccp", "CCP-001"),
            derivacion_sinad=_crear_campo("sinad", "ESINAD-001"),
        )
        assert dc.documentos_minimos_presentes() is False

    def test_apto_para_devengado_ok(self):
        dc = DocumentosConvenio(
            convenio_vigente=_crear_campo("convenio", "CONV-001-2026"),
            documento_cobranza=_crear_campo("cobranza", "LIQ-001"),
            detalle_consumo=_crear_campo("detalle", "Consumo Feb 2026"),
            informe_tecnico=_crear_campo("informe", "INF-001-2026"),
            certificacion_presupuestal=_crear_campo("ccp", "CCP-001"),
            derivacion_sinad=_crear_campo("sinad", "ESINAD-001"),
            coherencia_economica=True,
        )
        assert dc.apto_para_devengado() is True

    def test_apto_para_devengado_sin_coherencia(self):
        dc = DocumentosConvenio(
            convenio_vigente=_crear_campo("convenio", "CONV-001-2026"),
            documento_cobranza=_crear_campo("cobranza", "LIQ-001"),
            detalle_consumo=_crear_campo("detalle", "Consumo Feb 2026"),
            informe_tecnico=_crear_campo("informe", "INF-001-2026"),
            certificacion_presupuestal=_crear_campo("ccp", "CCP-001"),
            derivacion_sinad=_crear_campo("sinad", "ESINAD-001"),
            coherencia_economica=False,
        )
        assert dc.apto_para_devengado() is False

    def test_roundtrip(self):
        dc = DocumentosConvenio(
            convenio_vigente=_crear_campo("convenio", "CONV-001-2026"),
            entidad_contraparte=_crear_campo("entidad", "RENIEC"),
            conformidad_funcional=True,
            coherencia_economica=True,
        )
        d = dc.to_dict()
        r = DocumentosConvenio.from_dict(d)
        assert r.convenio_vigente.valor == "CONV-001-2026"
        assert r.entidad_contraparte.valor == "RENIEC"
        assert r.conformidad_funcional is True
        assert r.coherencia_economica is True


# ==============================================================================
# 18. ArchivoFuente
# ==============================================================================

class TestArchivoFuente:
    """Tests para archivo fuente con hash."""

    def test_roundtrip(self):
        af = ArchivoFuente(
            nombre="exp001.pdf",
            ruta_relativa="data/expedientes/exp001.pdf",
            hash_sha256="abcdef1234567890",
            tamaño_bytes=2048000,
            total_paginas=100,
        )
        d = af.to_dict()
        r = ArchivoFuente.from_dict(d)
        assert r.nombre == "exp001.pdf"
        assert r.hash_sha256 == "abcdef1234567890"
        assert r.total_paginas == 100


# ==============================================================================
# 19. ResumenExtraccion
# ==============================================================================

class TestResumenExtraccion:
    """Tests para estadísticas."""

    def test_roundtrip(self):
        re = ResumenExtraccion(
            total_campos=100,
            campos_ok=85,
            campos_abstencion=10,
            campos_incompletos=5,
            tasa_extraccion=0.85,
            comprobantes_procesados=16,
        )
        d = re.to_dict()
        r = ResumenExtraccion.from_dict(d)
        assert r.total_campos == 100
        assert r.campos_ok == 85
        assert r.tasa_extraccion == 0.85


# ==============================================================================
# 20. IntegridadExpediente
# ==============================================================================

class TestIntegridadExpediente:
    """Tests para integridad."""

    def test_roundtrip(self):
        ie = IntegridadExpediente(
            status="WARNING",
            hash_expediente="sha256abc",
            cadena_custodia_verificada=True,
            alertas=["Comprobante #3 sin RUC"],
        )
        d = ie.to_dict()
        r = IntegridadExpediente.from_dict(d)
        assert r.status == "WARNING"
        assert r.cadena_custodia_verificada is True
        assert len(r.alertas) == 1


# ==============================================================================
# 21. ExpedienteJSON — Serialización
# ==============================================================================

class TestExpedienteJSONSerializacion:
    """Tests de serialización to_dict/from_dict y to_json/from_json."""

    def test_to_dict_minimo(self):
        exp = ExpedienteJSON(sinad="TEST-001")
        d = exp.to_dict()
        assert d["sinad"] == "TEST-001"
        assert d["comprobantes"] == []
        assert d["documentos_convenio"] is None

    def test_roundtrip_completo(self):
        exp = _crear_expediente_completo()
        d = exp.to_dict()
        r = ExpedienteJSON.from_dict(d)
        assert r.sinad == "OT2026-INT-0179550"
        assert r.naturaleza == "VIÁTICOS"
        assert len(r.comprobantes) == 2
        assert len(r.declaracion_jurada) == 1
        assert len(r.boletos) == 1
        assert len(r.archivos_fuente) == 1
        assert r.comprobantes[0].grupo_a.ruc_emisor.valor == "20100039207"

    def test_to_json_from_json(self):
        exp = _crear_expediente_completo()
        json_str = exp.to_json()
        r = ExpedienteJSON.from_json(json_str)
        assert r.sinad == exp.sinad
        assert len(r.comprobantes) == len(exp.comprobantes)
        assert r.comprobantes[0].get_serie_numero() == "F001-00000468"

    def test_json_es_utf8(self):
        exp = ExpedienteJSON(sinad="OT2026-INT-0179550", naturaleza="VIÁTICOS")
        json_str = exp.to_json()
        # Verificar que tildes NO están escapadas
        assert "VIÁTICOS" in json_str
        assert "\\u00ed" not in json_str  # No debe escapar UTF-8

    def test_version_contrato(self):
        exp = ExpedienteJSON()
        assert exp.version_contrato == VERSION_CONTRATO

    def test_repr(self):
        exp = _crear_expediente_completo()
        r = repr(exp)
        assert "OT2026-INT-0179550" in r
        assert "comprobantes=2" in r


# ==============================================================================
# 22. ExpedienteJSON — Validación
# ==============================================================================

class TestExpedienteJSONValidacion:
    """Tests de validación de completitud."""

    def test_validar_completitud_ok(self):
        exp = _crear_expediente_completo()
        problemas = exp.validar_completitud()
        assert len(problemas) == 0

    def test_validar_sinad_vacio(self):
        exp = ExpedienteJSON()
        problemas = exp.validar_completitud()
        assert "SINAD vacío" in problemas

    def test_validar_naturaleza_vacia(self):
        exp = ExpedienteJSON(sinad="TEST-001")
        problemas = exp.validar_completitud()
        assert "Naturaleza no determinada" in problemas

    def test_validar_sin_archivos_fuente(self):
        exp = ExpedienteJSON(sinad="TEST-001", naturaleza="VIATICOS")
        problemas = exp.validar_completitud()
        assert "Sin archivos fuente registrados" in problemas

    def test_validar_sin_datos_extraidos(self):
        exp = ExpedienteJSON(
            sinad="TEST-001",
            naturaleza="VIATICOS",
            archivos_fuente=[ArchivoFuente(nombre="test.pdf")],
        )
        problemas = exp.validar_completitud()
        assert any("Sin datos extraídos" in p for p in problemas)

    def test_validar_comprobante_sin_serie_numero(self):
        comp = ComprobanteExtraido()  # Sin serie ni número
        exp = ExpedienteJSON(
            sinad="TEST-001",
            naturaleza="VIATICOS",
            archivos_fuente=[ArchivoFuente(nombre="test.pdf")],
            comprobantes=[comp],
        )
        problemas = exp.validar_completitud()
        assert any("sin serie ni número" in p for p in problemas)


# ==============================================================================
# 23. ExpedienteJSON — Unicidad
# ==============================================================================

class TestExpedienteJSONUnicidad:
    """Tests de verificación de unicidad de comprobantes."""

    def test_sin_duplicados(self):
        exp = _crear_expediente_completo()
        duplicados = exp.verificar_unicidad_comprobantes()
        assert len(duplicados) == 0

    def test_con_duplicados(self):
        comp1 = _crear_comprobante_minimo()  # F001-00000468
        comp2 = _crear_comprobante_minimo()  # F001-00000468 (duplicado)
        exp = ExpedienteJSON(comprobantes=[comp1, comp2])
        duplicados = exp.verificar_unicidad_comprobantes()
        assert len(duplicados) == 1
        assert "F001-00000468" in duplicados[0]

    def test_sin_identificar_no_marca_duplicado(self):
        """SIN_IDENTIFICAR no se considera duplicado."""
        comp1 = ComprobanteExtraido()  # SIN_IDENTIFICAR
        comp2 = ComprobanteExtraido()  # SIN_IDENTIFICAR
        exp = ExpedienteJSON(comprobantes=[comp1, comp2])
        duplicados = exp.verificar_unicidad_comprobantes()
        assert len(duplicados) == 0


# ==============================================================================
# 24. ExpedienteJSON — Hash
# ==============================================================================

class TestExpedienteJSONHash:
    """Tests para hash SHA-256."""

    def test_generar_hash(self):
        exp = _crear_expediente_completo()
        h = exp.generar_hash()
        assert len(h) == 64  # SHA-256 hex
        assert exp.integridad.hash_expediente == h

    def test_hash_determinista(self):
        exp1 = _crear_expediente_completo()
        exp2 = _crear_expediente_completo()
        h1 = exp1.generar_hash()
        h2 = exp2.generar_hash()
        assert h1 == h2

    def test_hash_cambia_con_datos(self):
        exp1 = _crear_expediente_completo()
        exp2 = _crear_expediente_completo()
        exp2.sinad = "OTRO-SINAD"
        h1 = exp1.generar_hash()
        h2 = exp2.generar_hash()
        assert h1 != h2


# ==============================================================================
# 25. ExpedienteJSON — Resumen de Extracción
# ==============================================================================

class TestExpedienteJSONResumen:
    """Tests para generar_resumen()."""

    def test_resumen_basico(self):
        exp = _crear_expediente_completo()
        resumen = exp.generar_resumen()
        assert resumen.comprobantes_procesados == 2
        assert resumen.gastos_dj == 1
        assert resumen.boletos == 1
        assert resumen.total_campos > 0
        assert resumen.tasa_extraccion > 0.0

    def test_resumen_expediente_vacio(self):
        exp = ExpedienteJSON()
        resumen = exp.generar_resumen()
        assert resumen.total_campos == 0
        assert resumen.tasa_extraccion == 0.0


# ==============================================================================
# 26. Integración con AbstencionPolicy
# ==============================================================================

class TestIntegracionAbstencion:
    """Tests de integración con CampoExtraido y AbstencionPolicy."""

    def test_campo_abstencion_en_comprobante(self):
        """Un comprobante con campos en abstención."""
        comp = ComprobanteExtraido(
            grupo_a=DatosEmisor(
                ruc_emisor=_crear_campo_abstencion("ruc_emisor"),
                razon_social=_crear_campo("razon_social", "EMPRESA X"),
            ),
            grupo_b=DatosComprobante(
                serie=_crear_campo("serie", "F001"),
                numero=_crear_campo("numero", "468"),
            ),
        )
        campos = comp.todos_los_campos()
        abstenciones = [c for c in campos if c.es_abstencion()]
        assert len(abstenciones) == 1
        assert abstenciones[0].nombre_campo == "ruc_emisor"

    def test_get_campos_abstencion_expediente(self):
        """Expediente con algunos campos en abstención."""
        comp = ComprobanteExtraido(
            grupo_a=DatosEmisor(
                ruc_emisor=_crear_campo_abstencion("ruc_emisor"),
            ),
            grupo_f=TotalesTributos(
                importe_total=_crear_campo_abstencion("total"),
            ),
        )
        exp = ExpedienteJSON(comprobantes=[comp])
        abstenciones = exp.get_campos_abstencion()
        assert len(abstenciones) == 2

    def test_get_campos_por_confianza(self):
        """Filtrar campos con confianza baja."""
        comp = ComprobanteExtraido(
            grupo_a=DatosEmisor(
                ruc_emisor=_crear_campo("ruc", "20100039207", confianza=0.55),
                razon_social=_crear_campo("rs", "EMPRESA", confianza=0.95),
            ),
        )
        exp = ExpedienteJSON(comprobantes=[comp])
        bajos = exp.get_campos_por_confianza(0.60)
        assert len(bajos) == 1
        assert bajos[0].valor == "20100039207"


# ==============================================================================
# 27. DocumentosConvenio en ExpedienteJSON
# ==============================================================================

class TestConvenioEnExpediente:
    """Tests de DocumentosConvenio integrado en ExpedienteJSON."""

    def test_expediente_con_convenio(self):
        dc = DocumentosConvenio(
            convenio_vigente=_crear_campo("convenio", "CONV-001"),
            entidad_contraparte=_crear_campo("entidad", "RENIEC"),
        )
        exp = ExpedienteJSON(
            sinad="CONV-2026-001",
            naturaleza="CONVENIO INTERINSTITUCIONAL",
            documentos_convenio=dc,
        )
        d = exp.to_dict()
        r = ExpedienteJSON.from_dict(d)
        assert r.documentos_convenio is not None
        assert r.documentos_convenio.convenio_vigente.valor == "CONV-001"
        assert r.documentos_convenio.entidad_contraparte.valor == "RENIEC"

    def test_expediente_sin_convenio(self):
        exp = ExpedienteJSON(sinad="VIA-001")
        d = exp.to_dict()
        r = ExpedienteJSON.from_dict(d)
        assert r.documentos_convenio is None

    def test_convenio_roundtrip_json(self):
        dc = DocumentosConvenio(
            convenio_vigente=_crear_campo("convenio", "CONV-001"),
            documento_cobranza=_crear_campo("cobranza", "LIQ-FEB"),
            conformidad_funcional=True,
            coherencia_economica=True,
        )
        exp = ExpedienteJSON(
            sinad="CONV-2026-001",
            documentos_convenio=dc,
        )
        json_str = exp.to_json()
        r = ExpedienteJSON.from_json(json_str)
        assert r.documentos_convenio.conformidad_funcional is True
        assert r.documentos_convenio.coherencia_economica is True


# ==============================================================================
# 28. Constantes y versión
# ==============================================================================

class TestConstantes:
    """Tests para constantes del módulo."""

    def test_version_contrato(self):
        assert VERSION_CONTRATO == "1.0.0"

    def test_tolerancia_aritmetica(self):
        assert TOLERANCIA_ARITMETICA == 0.02


# ==============================================================================
# 29. Edge Cases
# ==============================================================================

class TestEdgeCases:
    """Tests de casos borde."""

    def test_from_dict_con_campos_extra(self):
        """from_dict debe ignorar campos no reconocidos."""
        data = {
            "ruc_emisor": _crear_campo("ruc", "20100039207").to_dict(),
            "campo_futuro_v2": "valor_nuevo",  # Campo no existente
        }
        emisor = DatosEmisor.from_dict(data)
        assert emisor.ruc_emisor.valor == "20100039207"
        # No debe fallar por el campo extra

    def test_campo_extraido_con_bbox(self):
        """CampoExtraido con bbox se serializa correctamente."""
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor="20100039207",
            archivo="test.pdf",
            pagina=1,
            confianza=0.95,
            metodo=MetodoExtraccion.OCR,
            bbox=(100.0, 200.0, 300.0, 250.0),
            motor_ocr="paddleocr_gpu",
        )
        emisor = DatosEmisor(ruc_emisor=campo)
        d = emisor.to_dict()
        r = DatosEmisor.from_dict(d)
        assert r.ruc_emisor.bbox == (100.0, 200.0, 300.0, 250.0)
        assert r.ruc_emisor.motor_ocr == "paddleocr_gpu"

    def test_json_grande_no_falla(self):
        """Un expediente con muchos comprobantes serializa correctamente."""
        comps = [_crear_comprobante_minimo() for _ in range(50)]
        # Cambiar serie/número para evitar duplicados en test
        for i, comp in enumerate(comps):
            comp.grupo_b.numero = _crear_campo("numero", f"{i+1:08d}")
        exp = ExpedienteJSON(
            sinad="BULK-TEST",
            naturaleza="CAJA CHICA",
            comprobantes=comps,
        )
        json_str = exp.to_json()
        r = ExpedienteJSON.from_json(json_str)
        assert len(r.comprobantes) == 50

    def test_expediente_from_dict_vacio(self):
        """from_dict con diccionario vacío no falla."""
        exp = ExpedienteJSON.from_dict({})
        assert exp.sinad == ""
        assert len(exp.comprobantes) == 0
