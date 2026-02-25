# -*- coding: utf-8 -*-
"""
Tests para Capa C — Analista Local (IA confinada)
===================================================
Tests CRITICOS de seguridad:
  - Bloqueo de campos probatorios (RUC, montos, serie/numero, fecha)
  - Feature flag deshabilitado retorna vacio
  - AnalysisNotes solo contiene datos no-probatorios
  - _bloquear_valores_probatorios() elimina campos prohibidos
  - _process_ia_output() filtra correctamente
  - Integracion con TraceLogger (duck typing)
"""

import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.settings import MetodoExtraccion
from src.extraction.abstencion import CampoExtraido, EvidenceStatus
from src.extraction.local_analyst import (
    CAMPOS_PROBATORIOS,
    AnalysisNotes,
    _bloquear_valores_probatorios,
    _process_ia_output,
    analyze_evidence,
)


# ==============================================================================
# FIXTURES
# ==============================================================================
@pytest.fixture
def campo_legible():
    """CampoExtraido con alta confianza."""
    return CampoExtraido(
        nombre_campo="ruc_proveedor",
        valor="20100039207",
        archivo="test.pdf",
        pagina=1,
        confianza=0.95,
        metodo=MetodoExtraccion.OCR,
        tipo_campo="ruc",
        status=EvidenceStatus.LEGIBLE,
    )


@pytest.fixture
def campo_ilegible():
    """CampoExtraido en abstencion."""
    return CampoExtraido(
        nombre_campo="ruc_proveedor",
        valor=None,
        archivo="test.pdf",
        pagina=0,
        confianza=0.0,
        metodo=MetodoExtraccion.OCR,
        tipo_campo="ruc",
        status=EvidenceStatus.ILEGIBLE,
    )


# ==============================================================================
# BLOQUEO DE CAMPOS PROBATORIOS — TESTS DE SEGURIDAD
# ==============================================================================
class TestBloqueoCamposProbatorios:
    """Tests CRITICOS: la IA NUNCA puede escribir valores probatorios."""

    def test_bloquea_ruc(self):
        """Si la IA intenta escribir un RUC, se bloquea."""
        output = {"ruc": "20100039207", "notas": ["Algo"]}
        clean, bloqueados = _bloquear_valores_probatorios(output)
        assert clean["ruc"] == "NO_AUTORIZADO"
        assert clean["notas"] == ["Algo"]
        assert len(bloqueados) == 1
        assert bloqueados[0]["campo"] == "ruc"

    def test_bloquea_monto(self):
        output = {"monto": "250.00"}
        clean, bloqueados = _bloquear_valores_probatorios(output)
        assert clean["monto"] == "NO_AUTORIZADO"
        assert len(bloqueados) == 1

    def test_bloquea_serie_numero(self):
        output = {"serie_numero": "F001-468"}
        clean, bloqueados = _bloquear_valores_probatorios(output)
        assert clean["serie_numero"] == "NO_AUTORIZADO"

    def test_bloquea_fecha(self):
        output = {"fecha": "2026-02-06"}
        clean, bloqueados = _bloquear_valores_probatorios(output)
        assert clean["fecha"] == "NO_AUTORIZADO"

    def test_bloquea_razon_social(self):
        output = {"razon_social": "EMPRESA SAC"}
        clean, bloqueados = _bloquear_valores_probatorios(output)
        assert clean["razon_social"] == "NO_AUTORIZADO"

    def test_bloquea_igv(self):
        output = {"igv": "45.00"}
        clean, bloqueados = _bloquear_valores_probatorios(output)
        assert clean["igv"] == "NO_AUTORIZADO"

    def test_bloquea_valor_venta(self):
        output = {"valor_venta": "205.00"}
        clean, bloqueados = _bloquear_valores_probatorios(output)
        assert clean["valor_venta"] == "NO_AUTORIZADO"

    def test_bloquea_total(self):
        output = {"total": "250.00"}
        clean, bloqueados = _bloquear_valores_probatorios(output)
        assert clean["total"] == "NO_AUTORIZADO"

    def test_bloquea_ruc_proveedor(self):
        output = {"ruc_proveedor": "20100039207"}
        clean, bloqueados = _bloquear_valores_probatorios(output)
        assert clean["ruc_proveedor"] == "NO_AUTORIZADO"

    def test_bloquea_fecha_emision(self):
        output = {"fecha_emision": "2026-02-06"}
        clean, bloqueados = _bloquear_valores_probatorios(output)
        assert clean["fecha_emision"] == "NO_AUTORIZADO"

    def test_permite_notas(self):
        """Notas textuales NO son probatorias — deben pasar."""
        output = {"notas": ["Posible error en gasto #3"]}
        clean, bloqueados = _bloquear_valores_probatorios(output)
        assert clean["notas"] == ["Posible error en gasto #3"]
        assert len(bloqueados) == 0

    def test_permite_tags_riesgo(self):
        output = {"tags_riesgo": ["MONTO_INUSUAL", "RUC_SOSPECHOSO"]}
        clean, bloqueados = _bloquear_valores_probatorios(output)
        assert clean["tags_riesgo"] == ["MONTO_INUSUAL", "RUC_SOSPECHOSO"]
        assert len(bloqueados) == 0

    def test_permite_sugerencias_revision(self):
        output = {"sugerencias_revision": ["ruc_proveedor"]}
        clean, bloqueados = _bloquear_valores_probatorios(output)
        # "sugerencias_revision" como clave NO es un campo probatorio
        assert clean["sugerencias_revision"] == ["ruc_proveedor"]
        assert len(bloqueados) == 0

    def test_permite_confianza_analisis(self):
        output = {"confianza_analisis": 0.85}
        clean, bloqueados = _bloquear_valores_probatorios(output)
        assert clean["confianza_analisis"] == 0.85
        assert len(bloqueados) == 0

    def test_bloqueo_multiple(self):
        """Multiples campos probatorios se bloquean todos."""
        output = {
            "ruc": "20100039207",
            "monto": "250.00",
            "fecha": "2026-02-06",
            "notas": ["Revisar"],
        }
        clean, bloqueados = _bloquear_valores_probatorios(output)
        assert clean["ruc"] == "NO_AUTORIZADO"
        assert clean["monto"] == "NO_AUTORIZADO"
        assert clean["fecha"] == "NO_AUTORIZADO"
        assert clean["notas"] == ["Revisar"]
        assert len(bloqueados) == 3

    def test_valor_bloqueado_truncado(self):
        """Valor bloqueado se trunca a 100 chars en el registro."""
        output = {"ruc": "X" * 200}
        clean, bloqueados = _bloquear_valores_probatorios(output)
        assert len(bloqueados[0]["valor_bloqueado"]) <= 100


# ==============================================================================
# FEATURE FLAG
# ==============================================================================
class TestFeatureFlag:
    """Verify feature flag behavior."""

    def test_disabled_returns_empty(self):
        """Con LOCAL_ANALYST_ENABLED=False, retorna AnalysisNotes vacio."""
        notes = analyze_evidence(records=[], flags=[])
        assert notes.is_empty() is True
        assert notes.notas == []
        assert notes.tags_riesgo == []
        assert notes.sugerencias_revision == []

    def test_disabled_with_records(self, campo_legible):
        """Incluso con records, si flag off retorna vacio."""
        notes = analyze_evidence(
            records=[campo_legible],
            flags=["RUC_CHECKSUM_FAIL"],
        )
        assert notes.is_empty() is True

    def test_disabled_with_raw_text(self, campo_legible):
        """Raw text no cambia el resultado si flag off."""
        notes = analyze_evidence(
            records=[campo_legible],
            flags=[],
            raw_ocr_text="RUC: 20100039207",
        )
        assert notes.is_empty() is True


# ==============================================================================
# PROCESS IA OUTPUT
# ==============================================================================
class TestProcessIaOutput:
    """Tests de _process_ia_output() — filtro de salida de IA."""

    def test_output_limpio(self):
        raw = {
            "notas": ["Todo parece correcto"],
            "tags_riesgo": ["NINGUNO"],
            "sugerencias_revision": [],
            "confianza_analisis": 0.90,
        }
        notes = _process_ia_output(raw)
        assert notes.notas == ["Todo parece correcto"]
        assert notes.tags_riesgo == ["NINGUNO"]
        assert notes.confianza_analisis == 0.90
        assert notes.bloqueados == []

    def test_output_con_campo_probatorio(self):
        raw = {
            "notas": ["Revisado"],
            "ruc": "20100039207",
            "monto_total": "500.00",
        }
        notes = _process_ia_output(raw)
        assert notes.notas == ["Revisado"]
        assert len(notes.bloqueados) == 2

    def test_output_todo_probatorio(self):
        raw = {
            "ruc": "20100039207",
            "monto": "250.00",
            "serie_numero": "F001-468",
        }
        notes = _process_ia_output(raw)
        assert notes.notas == []
        assert notes.tags_riesgo == []
        assert len(notes.bloqueados) == 3

    def test_output_notas_no_lista(self):
        """Si notas no es lista, retorna lista vacia."""
        raw = {"notas": "un string suelto"}
        notes = _process_ia_output(raw)
        assert notes.notas == []

    def test_output_vacio(self):
        notes = _process_ia_output({})
        assert notes.is_empty() is True


# ==============================================================================
# ANALYSIS NOTES
# ==============================================================================
class TestAnalysisNotes:
    def test_empty(self):
        notes = AnalysisNotes()
        assert notes.is_empty() is True

    def test_not_empty_with_notas(self):
        notes = AnalysisNotes(notas=["Algo"])
        assert notes.is_empty() is False

    def test_not_empty_with_bloqueados(self):
        notes = AnalysisNotes(bloqueados=[{"campo": "ruc"}])
        assert notes.is_empty() is False

    def test_to_dict(self):
        notes = AnalysisNotes(
            notas=["Revisar gasto #5"],
            tags_riesgo=["MONTO_INUSUAL"],
            sugerencias_revision=["monto"],
            confianza_analisis=0.75,
        )
        d = notes.to_dict()
        assert d["notas"] == ["Revisar gasto #5"]
        assert d["tags_riesgo"] == ["MONTO_INUSUAL"]
        assert d["confianza_analisis"] == 0.75


# ==============================================================================
# CAMPOS PROBATORIOS SET
# ==============================================================================
class TestCamposProbatorios:
    """Verifica que la lista de campos probatorios es completa."""

    def test_contiene_ruc(self):
        assert "ruc" in CAMPOS_PROBATORIOS

    def test_contiene_monto(self):
        assert "monto" in CAMPOS_PROBATORIOS

    def test_contiene_serie_numero(self):
        assert "serie_numero" in CAMPOS_PROBATORIOS

    def test_contiene_fecha(self):
        assert "fecha" in CAMPOS_PROBATORIOS

    def test_contiene_razon_social(self):
        assert "razon_social" in CAMPOS_PROBATORIOS

    def test_contiene_igv(self):
        assert "igv" in CAMPOS_PROBATORIOS

    def test_contiene_total(self):
        assert "total" in CAMPOS_PROBATORIOS

    def test_no_contiene_notas(self):
        """'notas' NO es campo probatorio."""
        assert "notas" not in CAMPOS_PROBATORIOS

    def test_no_contiene_tags(self):
        assert "tags_riesgo" not in CAMPOS_PROBATORIOS

    def test_es_set(self):
        assert isinstance(CAMPOS_PROBATORIOS, set)
