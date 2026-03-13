# -*- coding: utf-8 -*-
"""
Tests para ReglasViaticos — Tarea #28 (Fase 4: Validaciones)

Cubre:
  - Documentos obligatorios (Anexo 3 + comprobantes)
  - Tope de viáticos por día (S/320.00/día)
  - Fechas de comprobantes dentro del periodo de comisión
  - Monto rendido vs viático otorgado
  - Cobertura de días con comprobantes
  - Boleta de venta — comprador debe ser institución
  - Casos edge: datos incompletos, fechas no parseables
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import NivelObservacion
from src.extraction.abstencion import CampoExtraido, MetodoExtraccion
from src.extraction.expediente_contract import (
    ComprobanteExtraido,
    DatosAdquirente,
    DatosAnexo3,
    DatosComprobante,
    DatosEmisor,
    ExpedienteJSON,
    MetadatosExtraccion,
    TotalesTributos,
    ValidacionesAritmeticas,
)
from src.validation.reglas_viaticos import (
    DIRECTIVA_VIGENTE,
    PLAZO_RENDICION_DIAS_HABILES,
    ReglasViaticos,
    ResultadoReglasViaticos,
    _parsear_fecha,
    validar_reglas_viaticos,
)

# ==============================================================================
# HELPERS
# ==============================================================================


def _campo(valor, archivo="test.pdf", pagina=1, nombre="test"):
    """Crea un CampoExtraido rápido."""
    return CampoExtraido(
        nombre_campo=nombre,
        valor=valor,
        archivo=archivo,
        pagina=pagina,
        confianza=0.9,
        metodo=MetodoExtraccion.PDF_TEXT,
        snippet=f"valor: {valor}",
        regla_aplicada="test",
    )


def _comprobante(
    total=None,
    serie="F001",
    numero="00001",
    tipo="FACTURA",
    fecha_emision=None,
    archivo="test.pdf",
    pagina=1,
):
    """Crea un ComprobanteExtraido rápido."""
    return ComprobanteExtraido(
        grupo_a=DatosEmisor(
            ruc_emisor=_campo("20123456789", archivo, pagina, "ruc_emisor"),
        ),
        grupo_b=DatosComprobante(
            tipo_comprobante=_campo(tipo, archivo, pagina, "tipo_comprobante"),
            serie=_campo(serie, archivo, pagina, "serie"),
            numero=_campo(numero, archivo, pagina, "numero"),
            fecha_emision=_campo(fecha_emision, archivo, pagina, "fecha_emision")
            if fecha_emision
            else None,
        ),
        grupo_f=TotalesTributos(
            importe_total=_campo(str(total), archivo, pagina, "importe_total")
            if total is not None
            else None,
        ),
        grupo_j=ValidacionesAritmeticas(),
        grupo_k=MetadatosExtraccion(pagina_origen=pagina),
    )


def _expediente_viaticos(
    comprobantes=None,
    comisionado=None,
    dni=None,
    fecha_salida=None,
    fecha_retorno=None,
    viatico_otorgado=None,
    total_gastado=None,
    devolucion=None,
):
    """Crea un ExpedienteJSON de viáticos para tests."""
    anexo3 = DatosAnexo3(
        sinad=_campo("TEST2026-INT-0000001"),
        comisionado=_campo(comisionado) if comisionado else None,
        dni=_campo(dni) if dni else None,
        fecha_salida=_campo(fecha_salida) if fecha_salida else None,
        fecha_regreso=_campo(fecha_retorno) if fecha_retorno else None,
        viatico_otorgado=_campo(str(viatico_otorgado)) if viatico_otorgado is not None else None,
        total_gastado=_campo(str(total_gastado)) if total_gastado is not None else None,
        devolucion=_campo(str(devolucion)) if devolucion is not None else None,
    )
    return ExpedienteJSON(
        sinad="TEST2026-INT-0000001",
        naturaleza="VIÁTICOS",
        comprobantes=comprobantes or [],
        anexo3=anexo3,
    )


# ==============================================================================
# TESTS: Parsear fecha
# ==============================================================================


class TestParsearFecha:
    def test_formato_dd_mm_yyyy(self):
        assert _parsear_fecha("15/02/2026") is not None
        assert _parsear_fecha("15/02/2026").day == 15

    def test_formato_dd_mm_yyyy_guion(self):
        assert _parsear_fecha("15-02-2026") is not None

    def test_formato_iso(self):
        assert _parsear_fecha("2026-02-15") is not None

    def test_none(self):
        assert _parsear_fecha(None) is None

    def test_vacio(self):
        assert _parsear_fecha("") is None

    def test_invalido(self):
        assert _parsear_fecha("no es fecha") is None

    def test_formato_corto(self):
        fecha = _parsear_fecha("15/02/26")
        assert fecha is not None


# ==============================================================================
# TESTS: Documentos obligatorios
# ==============================================================================


class TestDocumentosObligatorios:
    def setup_method(self):
        self.reglas = ReglasViaticos()

    def test_expediente_completo(self):
        comps = [_comprobante(total=100.0)]
        exp = _expediente_viaticos(comprobantes=comps, comisionado="JUAN PEREZ")
        resultado = self.reglas.validar(exp)
        docs_obs = [o for o in resultado.observaciones if "VIAT_DOC" in o.regla_aplicada]
        assert len(docs_obs) == 0

    def test_sin_comprobantes(self):
        exp = _expediente_viaticos(comisionado="JUAN PEREZ")
        resultado = self.reglas.validar(exp)
        docs_obs = [
            o for o in resultado.observaciones if "VIAT_DOC_COMPROBANTES" in o.regla_aplicada
        ]
        assert len(docs_obs) == 1
        assert docs_obs[0].nivel == NivelObservacion.MAYOR

    def test_sin_anexo3(self):
        comps = [_comprobante(total=100.0)]
        exp = ExpedienteJSON(
            sinad="TEST2026-INT-0000001",
            naturaleza="VIÁTICOS",
            comprobantes=comps,
            anexo3=DatosAnexo3(),  # Vacío
        )
        resultado = self.reglas.validar(exp)
        docs_obs = [o for o in resultado.observaciones if "VIAT_DOC_ANEXO3" in o.regla_aplicada]
        assert len(docs_obs) == 1


# ==============================================================================
# TESTS: Tope de viáticos
# ==============================================================================


class TestTopeViaticos:
    def setup_method(self):
        self.reglas = ReglasViaticos()

    def test_dentro_tope(self):
        # 2 días × S/320 = S/640, rendido S/600
        comps = [
            _comprobante(total=300.0, serie="F001", numero="001", fecha_emision="07/02/2026"),
            _comprobante(total=300.0, serie="F001", numero="002", fecha_emision="08/02/2026"),
        ]
        exp = _expediente_viaticos(
            comprobantes=comps,
            comisionado="JUAN PEREZ",
            fecha_salida="07/02/2026",
            fecha_retorno="08/02/2026",
        )
        resultado = self.reglas.validar(exp)
        tope_obs = [o for o in resultado.observaciones if "VIAT_TOPE_DIARIO" == o.regla_aplicada]
        assert len(tope_obs) == 0

    def test_excede_tope(self):
        # 1 día × S/320 = S/320, rendido S/500
        comps = [_comprobante(total=500.0, fecha_emision="07/02/2026")]
        exp = _expediente_viaticos(
            comprobantes=comps,
            comisionado="JUAN PEREZ",
            fecha_salida="07/02/2026",
            fecha_retorno="07/02/2026",
        )
        resultado = self.reglas.validar(exp)
        tope_obs = [o for o in resultado.observaciones if "VIAT_TOPE_DIARIO" == o.regla_aplicada]
        assert len(tope_obs) == 1
        assert tope_obs[0].nivel == NivelObservacion.MAYOR
        assert "excede" in tope_obs[0].descripcion.lower()

    def test_sin_fechas_informativa(self):
        comps = [_comprobante(total=500.0)]
        exp = _expediente_viaticos(comprobantes=comps, comisionado="JUAN PEREZ")
        resultado = self.reglas.validar(exp)
        tope_obs = [
            o for o in resultado.observaciones if "VIAT_TOPE_DIARIO_INFO" == o.regla_aplicada
        ]
        assert len(tope_obs) == 1
        assert tope_obs[0].nivel == NivelObservacion.INFORMATIVA


# ==============================================================================
# TESTS: Fechas de comprobantes
# ==============================================================================


class TestFechasComprobantes:
    def setup_method(self):
        self.reglas = ReglasViaticos()

    def test_dentro_periodo(self):
        comps = [
            _comprobante(total=100.0, serie="F001", numero="001", fecha_emision="07/02/2026"),
            _comprobante(total=100.0, serie="F001", numero="002", fecha_emision="08/02/2026"),
        ]
        exp = _expediente_viaticos(
            comprobantes=comps,
            comisionado="JUAN PEREZ",
            fecha_salida="07/02/2026",
            fecha_retorno="10/02/2026",
        )
        resultado = self.reglas.validar(exp)
        fecha_obs = [
            o for o in resultado.observaciones if "VIAT_FECHA_FUERA_PERIODO" == o.regla_aplicada
        ]
        assert len(fecha_obs) == 0

    def test_fuera_periodo(self):
        comps = [
            _comprobante(total=100.0, fecha_emision="01/01/2026"),  # Mucho antes
        ]
        exp = _expediente_viaticos(
            comprobantes=comps,
            comisionado="JUAN PEREZ",
            fecha_salida="07/02/2026",
            fecha_retorno="10/02/2026",
        )
        resultado = self.reglas.validar(exp)
        fecha_obs = [
            o for o in resultado.observaciones if "VIAT_FECHA_FUERA_PERIODO" == o.regla_aplicada
        ]
        assert len(fecha_obs) == 1
        assert fecha_obs[0].nivel == NivelObservacion.MAYOR

    def test_tolerancia_1_dia(self):
        # Día antes de salida (dentro de tolerancia)
        comps = [_comprobante(total=100.0, fecha_emision="06/02/2026")]
        exp = _expediente_viaticos(
            comprobantes=comps,
            comisionado="JUAN PEREZ",
            fecha_salida="07/02/2026",
            fecha_retorno="10/02/2026",
        )
        resultado = self.reglas.validar(exp)
        fecha_obs = [
            o for o in resultado.observaciones if "VIAT_FECHA_FUERA_PERIODO" == o.regla_aplicada
        ]
        assert len(fecha_obs) == 0  # Dentro de tolerancia ±1 día

    def test_sin_periodo_informativa(self):
        comps = [_comprobante(total=100.0, fecha_emision="07/02/2026")]
        exp = _expediente_viaticos(comprobantes=comps, comisionado="JUAN PEREZ")
        resultado = self.reglas.validar(exp)
        fecha_info = [o for o in resultado.observaciones if "VIAT_FECHAS_INFO" == o.regla_aplicada]
        assert len(fecha_info) == 1


# ==============================================================================
# TESTS: Monto rendido vs viático otorgado
# ==============================================================================


class TestMontoVsAsignado:
    def setup_method(self):
        self.reglas = ReglasViaticos()

    def test_dentro_asignado(self):
        comps = [_comprobante(total=500.0)]
        exp = _expediente_viaticos(
            comprobantes=comps,
            comisionado="JUAN PEREZ",
            viatico_otorgado=640.0,
            total_gastado=500.0,
        )
        resultado = self.reglas.validar(exp)
        monto_obs = [
            o for o in resultado.observaciones if "VIAT_MONTO_EXCEDE_ASIGNADO" == o.regla_aplicada
        ]
        assert len(monto_obs) == 0

    def test_excede_asignado(self):
        comps = [_comprobante(total=800.0)]
        exp = _expediente_viaticos(
            comprobantes=comps,
            comisionado="JUAN PEREZ",
            viatico_otorgado=640.0,
            total_gastado=800.0,
        )
        resultado = self.reglas.validar(exp)
        monto_obs = [
            o for o in resultado.observaciones if "VIAT_MONTO_EXCEDE_ASIGNADO" == o.regla_aplicada
        ]
        assert len(monto_obs) == 1
        assert monto_obs[0].nivel == NivelObservacion.MAYOR

    def test_devolucion_correcta(self):
        comps = [_comprobante(total=400.0)]
        exp = _expediente_viaticos(
            comprobantes=comps,
            comisionado="JUAN PEREZ",
            viatico_otorgado=640.0,
            total_gastado=400.0,
            devolucion=240.0,
        )
        resultado = self.reglas.validar(exp)
        dev_obs = [
            o
            for o in resultado.observaciones
            if "VIAT_DEVOLUCION_INCONSISTENTE" == o.regla_aplicada
        ]
        assert len(dev_obs) == 0

    def test_devolucion_incorrecta(self):
        comps = [_comprobante(total=400.0)]
        exp = _expediente_viaticos(
            comprobantes=comps,
            comisionado="JUAN PEREZ",
            viatico_otorgado=640.0,
            total_gastado=400.0,
            devolucion=100.0,  # Debería ser 240
        )
        resultado = self.reglas.validar(exp)
        dev_obs = [
            o
            for o in resultado.observaciones
            if "VIAT_DEVOLUCION_INCONSISTENTE" == o.regla_aplicada
        ]
        assert len(dev_obs) == 1
        assert dev_obs[0].nivel == NivelObservacion.MENOR

    def test_sin_datos_informativa(self):
        comps = [_comprobante(total=400.0)]
        exp = _expediente_viaticos(
            comprobantes=comps,
            comisionado="JUAN PEREZ",
            viatico_otorgado=640.0,
            # total_gastado ausente
        )
        resultado = self.reglas.validar(exp)
        info_obs = [
            o for o in resultado.observaciones if "VIAT_MONTO_VS_ASIGNADO_INFO" == o.regla_aplicada
        ]
        assert len(info_obs) == 1


# ==============================================================================
# TESTS: Cobertura de días
# ==============================================================================


class TestCoberturaDias:
    def setup_method(self):
        self.reglas = ReglasViaticos()

    def test_todos_dias_cubiertos(self):
        comps = [
            _comprobante(total=100.0, serie="F001", numero="001", fecha_emision="07/02/2026"),
            _comprobante(total=100.0, serie="F001", numero="002", fecha_emision="08/02/2026"),
        ]
        exp = _expediente_viaticos(
            comprobantes=comps,
            comisionado="JUAN PEREZ",
            fecha_salida="07/02/2026",
            fecha_retorno="08/02/2026",
        )
        resultado = self.reglas.validar(exp)
        cob_obs = [o for o in resultado.observaciones if "VIAT_COBERTURA_DIAS" == o.regla_aplicada]
        assert len(cob_obs) == 0

    def test_dias_sin_comprobante(self):
        # 3 días, comprobantes solo de 1 día
        comps = [
            _comprobante(total=100.0, serie="F001", numero="001", fecha_emision="07/02/2026"),
        ]
        exp = _expediente_viaticos(
            comprobantes=comps,
            comisionado="JUAN PEREZ",
            fecha_salida="07/02/2026",
            fecha_retorno="09/02/2026",
        )
        resultado = self.reglas.validar(exp)
        cob_obs = [o for o in resultado.observaciones if "VIAT_COBERTURA_DIAS" == o.regla_aplicada]
        assert len(cob_obs) == 1
        assert cob_obs[0].nivel == NivelObservacion.MENOR

    def test_sin_periodo_informativa(self):
        comps = [_comprobante(total=100.0)]
        exp = _expediente_viaticos(comprobantes=comps, comisionado="JUAN PEREZ")
        resultado = self.reglas.validar(exp)
        cob_obs = [
            o for o in resultado.observaciones if "VIAT_COBERTURA_DIAS_INFO" == o.regla_aplicada
        ]
        assert len(cob_obs) == 1


# ==============================================================================
# TESTS: Boleta de venta — comprador
# ==============================================================================


class TestBoletaComprador:
    def setup_method(self):
        self.reglas = ReglasViaticos()

    def test_boleta_con_ruc_institucion(self):
        comp = _comprobante(total=50.0, tipo="BOLETA DE VENTA")
        comp.grupo_c = DatosAdquirente(
            ruc_adquirente=_campo("20380795907"),
        )
        exp = _expediente_viaticos(
            comprobantes=[comp],
            comisionado="JUAN PEREZ",
            dni="12345678",
        )
        resultado = self.reglas.validar(exp)
        bol_obs = [
            o
            for o in resultado.observaciones
            if "VIAT_BOLETA_COMPRADOR_PERSONAL" == o.regla_aplicada
        ]
        assert len(bol_obs) == 0

    def test_boleta_con_dni_comisionado(self):
        comp = _comprobante(total=50.0, tipo="BOLETA DE VENTA")
        comp.grupo_c = DatosAdquirente(
            ruc_adquirente=_campo("12345678"),  # DNI del comisionado
        )
        exp = _expediente_viaticos(
            comprobantes=[comp],
            comisionado="JUAN PEREZ",
            dni="12345678",
        )
        resultado = self.reglas.validar(exp)
        bol_obs = [
            o
            for o in resultado.observaciones
            if "VIAT_BOLETA_COMPRADOR_PERSONAL" == o.regla_aplicada
        ]
        assert len(bol_obs) == 1
        assert bol_obs[0].nivel == NivelObservacion.MAYOR

    def test_factura_no_afecta(self):
        comp = _comprobante(total=50.0, tipo="FACTURA")
        comp.grupo_c = DatosAdquirente(
            ruc_adquirente=_campo("12345678"),
        )
        exp = _expediente_viaticos(
            comprobantes=[comp],
            comisionado="JUAN PEREZ",
            dni="12345678",
        )
        resultado = self.reglas.validar(exp)
        bol_obs = [
            o
            for o in resultado.observaciones
            if "VIAT_BOLETA_COMPRADOR_PERSONAL" == o.regla_aplicada
        ]
        assert len(bol_obs) == 0  # Solo aplica a boletas


# ==============================================================================
# TESTS: Validación completa
# ==============================================================================


class TestValidacionCompleta:
    def setup_method(self):
        self.reglas = ReglasViaticos()

    def test_expediente_ok(self):
        comps = [
            _comprobante(total=200.0, serie="F001", numero="001", fecha_emision="07/02/2026"),
            _comprobante(total=200.0, serie="F001", numero="002", fecha_emision="08/02/2026"),
        ]
        exp = _expediente_viaticos(
            comprobantes=comps,
            comisionado="JUAN PEREZ",
            fecha_salida="07/02/2026",
            fecha_retorno="08/02/2026",
            viatico_otorgado=640.0,
            total_gastado=400.0,
            devolucion=240.0,
        )
        resultado = self.reglas.validar(exp)
        assert resultado.reglas_evaluadas == 6
        assert resultado.reglas_fallidas == 0
        assert resultado.total_hallazgos == 0

    def test_resultado_to_dict(self):
        comps = [_comprobante(total=200.0)]
        exp = _expediente_viaticos(comprobantes=comps, comisionado="JUAN PEREZ")
        resultado = self.reglas.validar(exp)
        d = resultado.to_dict()
        assert "reglas_evaluadas" in d
        assert "total_hallazgos" in d

    def test_funcion_conveniencia(self):
        comps = [_comprobante(total=200.0)]
        exp = _expediente_viaticos(comprobantes=comps, comisionado="JUAN PEREZ")
        resultado = validar_reglas_viaticos(exp)
        assert isinstance(resultado, ResultadoReglasViaticos)

    def test_version(self):
        assert self.reglas.version == "1.0.0"


# ==============================================================================
# TESTS: Estándar probatorio
# ==============================================================================


class TestEstandarProbatorio:
    def setup_method(self):
        self.reglas = ReglasViaticos()

    def test_mayores_tienen_evidencia(self):
        comps = [_comprobante(total=500.0, fecha_emision="01/01/2026")]
        exp = _expediente_viaticos(
            comprobantes=comps,
            comisionado="JUAN PEREZ",
            fecha_salida="07/02/2026",
            fecha_retorno="10/02/2026",
        )
        resultado = self.reglas.validar(exp)
        mayores = [o for o in resultado.observaciones if o.nivel == NivelObservacion.MAYOR]
        for o in mayores:
            assert o.tiene_evidencia_completa(), f"Sin evidencia: {o.descripcion}"

    def test_directiva_referenciada(self):
        comps = [_comprobante(total=500.0, fecha_emision="01/01/2026")]
        exp = _expediente_viaticos(
            comprobantes=comps,
            comisionado="JUAN PEREZ",
            fecha_salida="07/02/2026",
            fecha_retorno="07/02/2026",
        )
        resultado = self.reglas.validar(exp)
        mayores = [o for o in resultado.observaciones if o.nivel == NivelObservacion.MAYOR]
        # Al menos alguna observación referencia la directiva
        refs_directiva = [o for o in mayores if DIRECTIVA_VIGENTE in o.descripcion]
        assert len(refs_directiva) > 0
