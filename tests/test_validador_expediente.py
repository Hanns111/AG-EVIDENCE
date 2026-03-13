# -*- coding: utf-8 -*-
"""
Tests para ValidadorExpediente — Tarea #27 (Fase 4: Validaciones)

Cubre:
  - Validación aritmética IGV (18%, 10% MYPE, 0% exonerado)
  - Validación total = subtotal + IGV
  - Validación suma de items
  - Validación noches de hospedaje
  - Validaciones cruzadas: duplicidad, suma vs Anexo 3
  - Campos obligatorios por tipo de comprobante
  - Casos edge: campos nulos, valores no numéricos, tolerancia
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import NivelObservacion
from src.extraction.abstencion import CampoExtraido, MetodoExtraccion
from src.extraction.expediente_contract import (
    ComprobanteExtraido,
    DatosAnexo3,
    DatosComprobante,
    DatosEmisor,
    DatosHospedaje,
    ExpedienteJSON,
    ItemDetalle,
    TotalesTributos,
    ValidacionesAritmeticas,
)
from src.validation.validador_expediente import (
    TOLERANCIA_ARITMETICA,
    ResultadoValidacion,
    ValidadorExpediente,
    _cerca,
    _extraer_float,
    validar_expediente,
)

# ==============================================================================
# HELPERS
# ==============================================================================


def _campo(valor, archivo="test.pdf", pagina=1, nombre="test"):
    """Crea un CampoExtraido rápido para tests."""
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


def _comprobante_factura(
    subtotal=None,
    igv=None,
    total=None,
    serie="F001",
    numero="00123",
    ruc="20123456789",
    tipo="FACTURA",
    archivo="test.pdf",
    pagina=1,
):
    """Crea un ComprobanteExtraido tipo factura para tests."""
    return ComprobanteExtraido(
        grupo_a=DatosEmisor(
            ruc_emisor=_campo(ruc, archivo, pagina, "ruc_emisor") if ruc else None,
            razon_social=_campo("EMPRESA TEST S.A.C.", archivo, pagina, "razon_social"),
        ),
        grupo_b=DatosComprobante(
            tipo_comprobante=_campo(tipo, archivo, pagina, "tipo_comprobante"),
            serie=_campo(serie, archivo, pagina, "serie"),
            numero=_campo(numero, archivo, pagina, "numero"),
            fecha_emision=_campo("2026-02-15", archivo, pagina, "fecha_emision"),
        ),
        grupo_f=TotalesTributos(
            subtotal=_campo(str(subtotal), archivo, pagina, "subtotal")
            if subtotal is not None
            else None,
            igv_monto=_campo(str(igv), archivo, pagina, "igv_monto") if igv is not None else None,
            importe_total=_campo(str(total), archivo, pagina, "importe_total")
            if total is not None
            else None,
        ),
        grupo_j=ValidacionesAritmeticas(),
    )


def _expediente_con_comprobantes(comprobantes, total_anexo3=None):
    """Crea ExpedienteJSON con comprobantes para tests."""
    anexo3 = DatosAnexo3()
    if total_anexo3 is not None:
        anexo3.total_gastado = _campo(str(total_anexo3), "anexo3.pdf", 1, "total_gastado")
    return ExpedienteJSON(
        sinad="TEST2026-INT-0000001",
        naturaleza="VIÁTICOS",
        comprobantes=comprobantes,
        anexo3=anexo3,
    )


# ==============================================================================
# TESTS: Funciones auxiliares
# ==============================================================================


class TestExtraerFloat:
    def test_float_directo(self):
        assert _extraer_float(_campo("1000.50")) == 1000.50

    def test_float_con_soles(self):
        assert _extraer_float(_campo("S/ 1,234.56")) == 1234.56

    def test_float_con_soles_punto(self):
        assert _extraer_float(_campo("S/.500.00")) == 500.00

    def test_float_entero(self):
        assert _extraer_float(_campo("100")) == 100.0

    def test_none_campo(self):
        assert _extraer_float(None) is None

    def test_none_valor(self):
        campo = _campo(None)
        campo.valor = None
        assert _extraer_float(campo) is None

    def test_texto_invalido(self):
        assert _extraer_float(_campo("ILEGIBLE")) is None

    def test_cero(self):
        assert _extraer_float(_campo("0.00")) == 0.0


class TestCerca:
    def test_iguales(self):
        assert _cerca(100.0, 100.0)

    def test_dentro_tolerancia(self):
        assert _cerca(100.0, 100.01)

    def test_exacto_en_limite(self):
        assert _cerca(100.0, 100.02)

    def test_fuera_tolerancia(self):
        assert not _cerca(100.0, 100.03)

    def test_tolerancia_custom(self):
        assert _cerca(100.0, 100.05, tol=0.1)


# ==============================================================================
# TESTS: Validación IGV
# ==============================================================================


class TestValidarIGV:
    def setup_method(self):
        self.validador = ValidadorExpediente()

    def test_igv_18_correcto(self):
        comp = _comprobante_factura(subtotal=1000.0, igv=180.0, total=1180.0)
        obs = self.validador.validar_aritmetica_comprobante(comp)
        assert comp.grupo_j.igv_ok is True
        igv_obs = [o for o in obs if "IGV" in o.descripcion]
        assert len(igv_obs) == 0

    def test_igv_10_mype_correcto(self):
        comp = _comprobante_factura(subtotal=500.0, igv=50.0, total=550.0)
        obs = self.validador.validar_aritmetica_comprobante(comp)
        assert comp.grupo_j.igv_ok is True

    def test_igv_0_exonerado(self):
        comp = _comprobante_factura(subtotal=100.0, igv=0.0, total=100.0)
        obs = self.validador.validar_aritmetica_comprobante(comp)
        assert comp.grupo_j.igv_ok is True

    def test_igv_incorrecto(self):
        comp = _comprobante_factura(subtotal=1000.0, igv=150.0, total=1150.0)
        obs = self.validador.validar_aritmetica_comprobante(comp)
        assert comp.grupo_j.igv_ok is False
        igv_obs = [o for o in obs if "IGV" in o.descripcion]
        assert len(igv_obs) == 1
        assert igv_obs[0].nivel == NivelObservacion.MAYOR

    def test_igv_dentro_tolerancia(self):
        # 1000 * 0.18 = 180.00, pero extrajo 180.01
        comp = _comprobante_factura(subtotal=1000.0, igv=180.01, total=1180.01)
        obs = self.validador.validar_aritmetica_comprobante(comp)
        assert comp.grupo_j.igv_ok is True

    def test_igv_sin_subtotal_ni_igv(self):
        comp = _comprobante_factura(total=1180.0)
        obs = self.validador.validar_aritmetica_comprobante(comp)
        assert comp.grupo_j.igv_ok is None

    def test_igv_con_total_e_igv_sin_subtotal(self):
        # subtotal se calcula como total - igv = 1180 - 180 = 1000
        comp = _comprobante_factura(igv=180.0, total=1180.0)
        obs = self.validador.validar_aritmetica_comprobante(comp)
        assert comp.grupo_j.igv_ok is True

    def test_igv_evidencia_completa(self):
        comp = _comprobante_factura(subtotal=1000.0, igv=150.0, total=1150.0)
        obs = self.validador.validar_aritmetica_comprobante(comp)
        igv_obs = [o for o in obs if "IGV" in o.descripcion]
        assert len(igv_obs) == 1
        assert igv_obs[0].tiene_evidencia_completa()
        assert igv_obs[0].regla_aplicada == "VAL_IGV_ARITMETICA"


# ==============================================================================
# TESTS: Validación Total
# ==============================================================================


class TestValidarTotal:
    def setup_method(self):
        self.validador = ValidadorExpediente()

    def test_total_correcto(self):
        comp = _comprobante_factura(subtotal=1000.0, igv=180.0, total=1180.0)
        obs = self.validador.validar_aritmetica_comprobante(comp)
        assert comp.grupo_j.total_ok is True

    def test_total_incorrecto(self):
        comp = _comprobante_factura(subtotal=1000.0, igv=180.0, total=1200.0)
        obs = self.validador.validar_aritmetica_comprobante(comp)
        assert comp.grupo_j.total_ok is False
        total_obs = [o for o in obs if "Total" in o.descripcion]
        assert len(total_obs) == 1
        assert total_obs[0].nivel == NivelObservacion.MAYOR

    def test_total_sin_igv(self):
        comp = _comprobante_factura(subtotal=100.0, total=100.0)
        obs = self.validador.validar_aritmetica_comprobante(comp)
        assert comp.grupo_j.total_ok is True

    def test_total_sin_subtotal(self):
        comp = _comprobante_factura(igv=180.0, total=1180.0)
        obs = self.validador.validar_aritmetica_comprobante(comp)
        assert comp.grupo_j.total_ok is None

    def test_total_dentro_tolerancia(self):
        comp = _comprobante_factura(subtotal=1000.0, igv=180.0, total=1180.01)
        obs = self.validador.validar_aritmetica_comprobante(comp)
        assert comp.grupo_j.total_ok is True


# ==============================================================================
# TESTS: Validación Suma de Items
# ==============================================================================


class TestValidarSumaItems:
    def setup_method(self):
        self.validador = ValidadorExpediente()

    def test_sin_items(self):
        comp = _comprobante_factura(subtotal=1000.0, igv=180.0, total=1180.0)
        self.validador.validar_aritmetica_comprobante(comp)
        assert comp.grupo_j.suma_items_ok is None

    def test_items_correctos(self):
        comp = _comprobante_factura(subtotal=300.0, igv=54.0, total=354.0)
        comp.grupo_e = [
            ItemDetalle(importe=_campo("100.00")),
            ItemDetalle(importe=_campo("200.00")),
        ]
        self.validador.validar_aritmetica_comprobante(comp)
        assert comp.grupo_j.suma_items_ok is True

    def test_items_incorrectos(self):
        comp = _comprobante_factura(subtotal=300.0, igv=54.0, total=354.0)
        comp.grupo_e = [
            ItemDetalle(importe=_campo("100.00")),
            ItemDetalle(importe=_campo("100.00")),
        ]
        obs = self.validador.validar_aritmetica_comprobante(comp)
        assert comp.grupo_j.suma_items_ok is False
        items_obs = [o for o in obs if "Suma items" in o.descripcion]
        assert len(items_obs) == 1


# ==============================================================================
# TESTS: Validación Noches Hospedaje
# ==============================================================================


class TestValidarNoches:
    def setup_method(self):
        self.validador = ValidadorExpediente()

    def test_sin_hospedaje(self):
        comp = _comprobante_factura(subtotal=100.0, igv=18.0, total=118.0)
        self.validador.validar_aritmetica_comprobante(comp)
        assert comp.grupo_j.noches_ok is None

    def test_hospedaje_ok(self):
        comp = _comprobante_factura(subtotal=400.0, igv=72.0, total=472.0)
        comp.grupo_h = DatosHospedaje(
            numero_noches=_campo("2"),
        )
        self.validador.validar_aritmetica_comprobante(comp)
        assert comp.grupo_j.noches_ok is True

    def test_hospedaje_sin_noches(self):
        comp = _comprobante_factura(subtotal=400.0, igv=72.0, total=472.0)
        comp.grupo_h = DatosHospedaje()
        self.validador.validar_aritmetica_comprobante(comp)
        assert comp.grupo_j.noches_ok is None


# ==============================================================================
# TESTS: Validaciones Cruzadas
# ==============================================================================


class TestValidarCruzado:
    def setup_method(self):
        self.validador = ValidadorExpediente()

    def test_sin_duplicados(self):
        comps = [
            _comprobante_factura(total=100.0, serie="F001", numero="001"),
            _comprobante_factura(total=200.0, serie="F001", numero="002"),
        ]
        exp = _expediente_con_comprobantes(comps)
        obs = self.validador.validar_cruzado(exp)
        dup = [o for o in obs if "duplicado" in o.descripcion.lower()]
        assert len(dup) == 0

    def test_con_duplicados(self):
        comps = [
            _comprobante_factura(total=100.0, serie="F001", numero="001"),
            _comprobante_factura(total=100.0, serie="F001", numero="001"),
        ]
        exp = _expediente_con_comprobantes(comps)
        obs = self.validador.validar_cruzado(exp)
        dup = [o for o in obs if "duplicado" in o.descripcion.lower()]
        assert len(dup) == 1
        assert dup[0].nivel == NivelObservacion.CRITICA

    def test_suma_vs_anexo3_ok(self):
        comps = [
            _comprobante_factura(total=500.0, serie="F001", numero="001"),
            _comprobante_factura(total=500.0, serie="F001", numero="002"),
        ]
        exp = _expediente_con_comprobantes(comps, total_anexo3=1000.0)
        obs = self.validador.validar_cruzado(exp)
        suma_obs = [o for o in obs if "Anexo 3" in o.descripcion]
        assert len(suma_obs) == 0

    def test_suma_vs_anexo3_mismatch(self):
        comps = [
            _comprobante_factura(total=500.0, serie="F001", numero="001"),
            _comprobante_factura(total=300.0, serie="F001", numero="002"),
        ]
        exp = _expediente_con_comprobantes(comps, total_anexo3=1000.0)
        obs = self.validador.validar_cruzado(exp)
        suma_obs = [o for o in obs if "Anexo 3" in o.descripcion]
        assert len(suma_obs) == 1
        assert suma_obs[0].nivel == NivelObservacion.MAYOR

    def test_sin_anexo3_informativa(self):
        comps = [_comprobante_factura(total=500.0, serie="F001", numero="001")]
        exp = _expediente_con_comprobantes(comps)
        obs = self.validador.validar_cruzado(exp)
        info = [
            o for o in obs if o.nivel == NivelObservacion.INFORMATIVA and "Anexo 3" in o.descripcion
        ]
        assert len(info) == 1


# ==============================================================================
# TESTS: Validación Campos Obligatorios
# ==============================================================================


class TestValidarCamposObligatorios:
    def setup_method(self):
        self.validador = ValidadorExpediente()

    def test_factura_completa(self):
        comp = _comprobante_factura(subtotal=1000.0, igv=180.0, total=1180.0, ruc="20123456789")
        comp.grupo_e = [ItemDetalle(descripcion=_campo("Servicio de consultoría"))]
        exp = _expediente_con_comprobantes([comp])
        obs = self.validador.validar_campos_obligatorios(exp)
        assert len(obs) == 0

    def test_factura_sin_ruc(self):
        comp = _comprobante_factura(subtotal=1000.0, igv=180.0, total=1180.0, ruc=None)
        exp = _expediente_con_comprobantes([comp])
        obs = self.validador.validar_campos_obligatorios(exp)
        faltantes = [o for o in obs if "ruc_emisor" in o.descripcion]
        assert len(faltantes) >= 1


# ==============================================================================
# TESTS: Validación Completa de Expediente
# ==============================================================================


class TestValidarExpediente:
    def setup_method(self):
        self.validador = ValidadorExpediente()

    def test_expediente_vacio(self):
        exp = _expediente_con_comprobantes([])
        resultado = self.validador.validar_expediente(exp)
        assert resultado.comprobantes_validados == 0
        assert len(resultado.observaciones) == 1
        assert resultado.observaciones[0].nivel == NivelObservacion.MAYOR

    def test_expediente_correcto(self):
        comps = [
            _comprobante_factura(
                subtotal=1000.0, igv=180.0, total=1180.0, serie="F001", numero="001"
            ),
            _comprobante_factura(subtotal=500.0, igv=50.0, total=550.0, serie="F001", numero="002"),
        ]
        exp = _expediente_con_comprobantes(comps, total_anexo3=1730.0)
        resultado = self.validador.validar_expediente(exp)
        assert resultado.comprobantes_validados == 2
        assert resultado.errores_aritmeticos == 0

    def test_expediente_con_errores(self):
        comps = [
            _comprobante_factura(
                subtotal=1000.0, igv=150.0, total=1200.0, serie="F001", numero="001"
            ),
        ]
        exp = _expediente_con_comprobantes(comps)
        resultado = self.validador.validar_expediente(exp)
        assert resultado.errores_aritmeticos > 0

    def test_resultado_to_dict(self):
        comps = [
            _comprobante_factura(subtotal=1000.0, igv=180.0, total=1180.0),
        ]
        exp = _expediente_con_comprobantes(comps)
        resultado = self.validador.validar_expediente(exp)
        d = resultado.to_dict()
        assert "comprobantes_validados" in d
        assert "total_hallazgos" in d

    def test_funcion_conveniencia(self):
        comps = [
            _comprobante_factura(subtotal=1000.0, igv=180.0, total=1180.0),
        ]
        exp = _expediente_con_comprobantes(comps)
        resultado = validar_expediente(exp)
        assert isinstance(resultado, ResultadoValidacion)


# ==============================================================================
# TESTS: Observaciones con estándar probatorio
# ==============================================================================


class TestEstandarProbatorio:
    def setup_method(self):
        self.validador = ValidadorExpediente()

    def test_observacion_mayor_tiene_evidencia(self):
        comp = _comprobante_factura(subtotal=1000.0, igv=150.0, total=1150.0)
        obs = self.validador.validar_aritmetica_comprobante(comp)
        mayores = [o for o in obs if o.nivel == NivelObservacion.MAYOR]
        for o in mayores:
            assert o.tiene_evidencia_completa(), f"Observación sin evidencia: {o.descripcion}"

    def test_observacion_critica_tiene_evidencia(self):
        comps = [
            _comprobante_factura(total=100.0, serie="F001", numero="001"),
            _comprobante_factura(total=100.0, serie="F001", numero="001"),
        ]
        exp = _expediente_con_comprobantes(comps)
        obs = self.validador.validar_cruzado(exp)
        criticas = [o for o in obs if o.nivel == NivelObservacion.CRITICA]
        for o in criticas:
            assert o.tiene_evidencia_completa(), f"Observación sin evidencia: {o.descripcion}"

    def test_no_degrada_con_evidencia(self):
        comp = _comprobante_factura(subtotal=1000.0, igv=150.0, total=1150.0)
        obs = self.validador.validar_aritmetica_comprobante(comp)
        for o in obs:
            original_nivel = o.nivel
            o.validar_y_degradar()
            if original_nivel in (NivelObservacion.CRITICA, NivelObservacion.MAYOR):
                assert o.nivel == original_nivel  # No degrada porque tiene evidencia


# ==============================================================================
# TESTS: Versión
# ==============================================================================


class TestVersion:
    def test_version(self):
        v = ValidadorExpediente()
        assert v.version == "1.0.0"
