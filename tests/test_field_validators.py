# -*- coding: utf-8 -*-
"""
Tests para Capa B — Validadores Deterministas de Campos
=========================================================
Verifica:
  - validar_ruc: longitud, prefijo, digitos
  - validar_serie_numero: patrones SUNAT
  - validar_monto: formato numerico, negativos, decimales
  - validar_fecha: formatos, rangos
  - validar_consistencia_aritmetica: subtotal + IGV = total
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.rules.field_validators import (
    ValidationFlag,
    ValidationResult,
    validar_consistencia_aritmetica,
    validar_fecha,
    validar_monto,
    validar_ruc,
    validar_serie_numero,
)


# ==============================================================================
# VALIDAR RUC
# ==============================================================================
class TestValidarRuc:
    def test_ruc_valido_persona_juridica(self):
        result = validar_ruc("20100039207")
        assert result.valido is True
        assert result.flags == []

    def test_ruc_valido_persona_natural(self):
        result = validar_ruc("10701855406")
        assert result.valido is True

    def test_ruc_vacio(self):
        result = validar_ruc("")
        assert result.valido is False
        assert "RUC_VACIO" in result.flags

    def test_ruc_none(self):
        result = validar_ruc(None)
        assert result.valido is False
        assert "RUC_VACIO" in result.flags

    def test_ruc_longitud_corta(self):
        result = validar_ruc("2010003920")
        assert result.valido is False
        assert "RUC_LONGITUD_INVALIDA" in result.flags

    def test_ruc_longitud_larga(self):
        result = validar_ruc("201000392070")
        assert result.valido is False
        assert "RUC_LONGITUD_INVALIDA" in result.flags

    def test_ruc_no_numerico(self):
        result = validar_ruc("2010003920A")
        assert result.valido is False
        assert "RUC_NO_NUMERICO" in result.flags

    def test_ruc_prefijo_invalido(self):
        result = validar_ruc("30100039207")
        assert result.valido is False
        assert "RUC_PREFIJO_INVALIDO" in result.flags

    def test_ruc_prefijo_15_valido(self):
        result = validar_ruc("15100039207")
        assert result.valido is True

    def test_ruc_con_espacios(self):
        result = validar_ruc("  20100039207  ")
        assert result.valido is True

    def test_ruc_needs_human_review(self):
        result = validar_ruc("ABC")
        assert result.needs_human_review is True


# ==============================================================================
# VALIDAR SERIE-NUMERO
# ==============================================================================
class TestValidarSerieNumero:
    def test_factura_electronica_valida(self):
        result = validar_serie_numero("F001-468")
        assert result.valido is True
        assert "FACTURA_ELECTRONICA" in result.detalle

    def test_factura_numero_largo(self):
        result = validar_serie_numero("F001-32196")
        assert result.valido is True

    def test_boleta_electronica(self):
        result = validar_serie_numero("B001-12345")
        assert result.valido is True
        assert "BOLETA_ELECTRONICA" in result.detalle

    def test_comprobante_e(self):
        result = validar_serie_numero("E001-1094")
        assert result.valido is True

    def test_boleta_venta_eb(self):
        result = validar_serie_numero("EB01-6")
        assert result.valido is True

    def test_factura_fo(self):
        result = validar_serie_numero("FO002-8351")
        assert result.valido is True

    def test_factura_fd(self):
        result = validar_serie_numero("FD1-21821")
        assert result.valido is True

    def test_factura_fq(self):
        result = validar_serie_numero("FQ01-569")
        assert result.valido is True

    def test_declaracion_jurada(self):
        result = validar_serie_numero("0000-002")
        assert result.valido is True

    def test_recibo_servicio(self):
        result = validar_serie_numero("0000-260001715589")
        assert result.valido is True

    def test_vacio(self):
        result = validar_serie_numero("")
        assert result.valido is False
        assert "SERIE_NUMERO_VACIO" in result.flags

    def test_none(self):
        result = validar_serie_numero(None)
        assert result.valido is False

    def test_sin_separador(self):
        result = validar_serie_numero("F001468")
        assert result.valido is False
        assert "SERIE_NUMERO_SIN_SEPARADOR" in result.flags

    def test_formato_desconocido(self):
        result = validar_serie_numero("XYZ-123")
        assert result.valido is False
        assert "SERIE_NUMERO_FORMATO_DESCONOCIDO" in result.flags

    def test_case_insensitive(self):
        """Serie-numero se convierte a mayusculas."""
        result = validar_serie_numero("f001-468")
        assert result.valido is True

    def test_con_espacios(self):
        result = validar_serie_numero("  F001-468  ")
        assert result.valido is True


# ==============================================================================
# VALIDAR MONTO
# ==============================================================================
class TestValidarMonto:
    def test_monto_valido(self):
        result = validar_monto("250.00")
        assert result.valido is True

    def test_monto_con_soles(self):
        result = validar_monto("S/ 1,234.56")
        assert result.valido is True

    def test_monto_entero(self):
        result = validar_monto("100")
        assert result.valido is True

    def test_monto_cero(self):
        result = validar_monto("0.00")
        assert result.valido is True

    def test_monto_vacio(self):
        result = validar_monto("")
        assert result.valido is False
        assert "MONTO_VACIO" in result.flags

    def test_monto_none(self):
        result = validar_monto(None)
        assert result.valido is False

    def test_monto_no_numerico(self):
        result = validar_monto("ABC")
        assert result.valido is False
        assert "MONTO_NO_NUMERICO" in result.flags

    def test_monto_negativo(self):
        result = validar_monto("-50.00")
        assert result.valido is False
        assert "MONTO_NEGATIVO" in result.flags

    def test_monto_mas_de_2_decimales(self):
        result = validar_monto("250.123")
        assert result.valido is False
        assert "MONTO_MAS_DE_2_DECIMALES" in result.flags

    def test_monto_con_comas_miles(self):
        result = validar_monto("1,028.70")
        assert result.valido is True


# ==============================================================================
# VALIDAR FECHA
# ==============================================================================
class TestValidarFecha:
    def test_fecha_peruana_valida(self):
        result = validar_fecha("06/02/2026")
        assert result.valido is True

    def test_fecha_iso_valida(self):
        result = validar_fecha("2026-02-06")
        assert result.valido is True

    def test_fecha_guion_valida(self):
        result = validar_fecha("06-02-2026")
        assert result.valido is True

    def test_fecha_vacia(self):
        result = validar_fecha("")
        assert result.valido is False
        assert "FECHA_VACIA" in result.flags

    def test_fecha_none(self):
        result = validar_fecha(None)
        assert result.valido is False

    def test_fecha_formato_invalido(self):
        result = validar_fecha("febrero 6, 2026")
        assert result.valido is False
        assert "FECHA_FORMATO_INVALIDO" in result.flags

    def test_fecha_fuera_de_rango_anterior(self):
        result = validar_fecha("01/01/2015")
        assert result.valido is False
        assert "FECHA_FUERA_DE_RANGO" in result.flags

    def test_fecha_fuera_de_rango_futura(self):
        result = validar_fecha("01/01/2035")
        assert result.valido is False
        assert "FECHA_FUERA_DE_RANGO" in result.flags

    def test_fecha_rango_custom(self):
        result = validar_fecha("15/06/2025", rango_min="2025-01-01", rango_max="2025-12-31")
        assert result.valido is True

    def test_fecha_con_espacios(self):
        result = validar_fecha("  06/02/2026  ")
        assert result.valido is True


# ==============================================================================
# VALIDAR CONSISTENCIA ARITMETICA
# ==============================================================================
class TestValidarConsistenciaAritmetica:
    def test_consistencia_correcta(self):
        result = validar_consistencia_aritmetica(valor_venta=211.86, igv=38.14, total=250.00)
        assert result.valido is True

    def test_consistencia_con_centimos(self):
        result = validar_consistencia_aritmetica(valor_venta=80.51, igv=14.49, total=95.00)
        assert result.valido is True

    def test_discrepancia(self):
        result = validar_consistencia_aritmetica(valor_venta=100.00, igv=18.00, total=120.00)
        assert result.valido is False
        assert "ARITMETICA_DISCREPANCIA" in result.flags

    def test_campos_faltantes(self):
        result = validar_consistencia_aritmetica(valor_venta=100.00, igv=None, total=118.00)
        assert result.valido is False
        assert "ARITMETICA_CAMPOS_FALTANTES" in result.flags

    def test_todos_none(self):
        result = validar_consistencia_aritmetica(valor_venta=None, igv=None, total=None)
        assert result.valido is False

    def test_tolerancia_dentro(self):
        """Diferencia de S/0.01 dentro de tolerancia default (0.02)."""
        result = validar_consistencia_aritmetica(valor_venta=100.00, igv=18.00, total=118.01)
        assert result.valido is True

    def test_tolerancia_fuera(self):
        """Diferencia de S/0.05 fuera de tolerancia default (0.02)."""
        result = validar_consistencia_aritmetica(valor_venta=100.00, igv=18.00, total=118.05)
        assert result.valido is False

    def test_tolerancia_custom(self):
        result = validar_consistencia_aritmetica(
            valor_venta=100.00,
            igv=18.00,
            total=118.10,
            tolerancia=0.15,
        )
        assert result.valido is True

    def test_igv_cero(self):
        """Comprobante exonerado de IGV."""
        result = validar_consistencia_aritmetica(valor_venta=50.00, igv=0.00, total=50.00)
        assert result.valido is True


# ==============================================================================
# VALIDATION RESULT / FLAG SERIALIZATION
# ==============================================================================
class TestSerializacion:
    def test_validation_result_to_dict(self):
        r = ValidationResult(
            valido=False,
            flags=["RUC_LONGITUD_INVALIDA"],
            needs_human_review=True,
            detalle="RUC tiene 10 digitos",
        )
        d = r.to_dict()
        assert d["valido"] is False
        assert d["flags"] == ["RUC_LONGITUD_INVALIDA"]
        assert d["needs_human_review"] is True

    def test_validation_flag_to_dict(self):
        f = ValidationFlag(
            campo="ruc_proveedor",
            codigo="RUC_CHECKSUM_FAIL",
            detalle="Check digit incorrecto",
            needs_human_review=True,
        )
        d = f.to_dict()
        assert d["campo"] == "ruc_proveedor"
        assert d["codigo"] == "RUC_CHECKSUM_FAIL"
