# -*- coding: utf-8 -*-
"""
Tests para src/extraction/calibracion.py — Tarea #19
=====================================================

Cobertura:
  - TestEstadisticaCampo: dataclass, propiedades computadas, serialización
  - TestAnalisisBenchmark: dataclass, serialización roundtrip
  - TestPerfilCalibracion: enum valores
  - TestResultadoCalibracion: dataclass, serialización
  - TestCalibradorCarga: carga de benchmarks (archivo y dict)
  - TestCalibradorAnalisis: análisis de benchmark cc003
  - TestCalibradorPerfiles: generación y valores de perfiles
  - TestMonotonia: warning < critical en cada perfil
  - TestMonotoniaEntrePefiles: CONSERVADOR < BALANCEADO < PERMISIVO
  - TestJsonRoundtrip: exportar → importar → verificar igualdad
  - TestCalibradorUtilidades: propiedades y resumen
  - TestValidacionCruzada: perfiles vs benchmark cc003
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from src.extraction.calibracion import (
    VERSION_CALIBRACION,
    CAMPOS_BENCHMARK,
    RESULTADO_MATCH,
    RESULTADO_ERROR,
    RESULTADO_NO_EXTRAIDO,
    RESULTADO_SKIP,
    PerfilCalibracion,
    EstadisticaCampo,
    AnalisisBenchmark,
    ResultadoCalibracion,
    CalibradorUmbrales,
)


# ==============================================================================
# FIXTURES
# ==============================================================================

# Benchmark mínimo para tests sin archivo real
BENCHMARK_MINIMO = {
    "prueba": "test_minimo",
    "expediente": "TEST-001",
    "pipeline_version": "test_v1",
    "total_comprobantes": 2,
    "metricas": {
        "total_campos_evaluados": 6,
        "match_exacto": 3,
        "error": 2,
        "no_extraido": 1,
        "precision_pct": 50.0,
    },
    "resultados_por_comprobante": [
        {
            "gasto": 1,
            "pagina": 1,
            "motor": "paddleocr",
            "confianza": 0.95,
            "chars": 500,
            "campos": {
                "ruc": {"extraido": "20000000001", "esperado": "20000000001", "resultado": "MATCH"},
                "serie_numero": {"extraido": "F001-100", "esperado": "F001-100", "resultado": "MATCH"},
                "total": {"extraido": 100.0, "esperado": 100.0, "resultado": "MATCH"},
                "igv": {"extraido": None, "esperado": None, "resultado": "SKIP_GT_NULL"},
                "fecha": {"extraido": "01/01/2026", "esperado": "02/01/2026", "resultado": "ERROR"},
            },
        },
        {
            "gasto": 2,
            "pagina": 5,
            "motor": "paddleocr",
            "confianza": 0.88,
            "chars": 400,
            "campos": {
                "ruc": {"extraido": "20000000002", "esperado": "20000000003", "resultado": "ERROR"},
                "serie_numero": {"extraido": None, "esperado": "E001-200", "resultado": "NO_EXTRAIDO"},
                "total": {"extraido": None, "esperado": None, "resultado": "SKIP_GT_NULL"},
                "igv": {"extraido": None, "esperado": None, "resultado": "SKIP_GT_NULL"},
                "fecha": {"extraido": None, "esperado": None, "resultado": "SKIP_GT_NULL"},
            },
        },
    ],
}


@pytest.fixture
def benchmark_minimo():
    """Benchmark mínimo para tests."""
    return BENCHMARK_MINIMO.copy()


@pytest.fixture
def benchmark_cc003_path():
    """Ruta al benchmark real cc003."""
    path = Path(__file__).resolve().parent.parent / "data" / "evaluacion" / "prueba_empirica_cc003.json"
    if not path.exists():
        pytest.skip(f"Benchmark cc003 no disponible: {path}")
    return str(path)


@pytest.fixture
def calibrador_con_cc003(benchmark_cc003_path):
    """Calibrador con cc003 cargado y analizado."""
    cal = CalibradorUmbrales()
    cal.cargar_benchmark(benchmark_cc003_path)
    cal.analizar()
    return cal


@pytest.fixture
def calibrador_con_perfiles(calibrador_con_cc003):
    """Calibrador con cc003 cargado, analizado y con perfiles generados."""
    calibrador_con_cc003.generar_perfiles()
    return calibrador_con_cc003


@pytest.fixture
def tmp_json_path(tmp_path):
    """Ruta temporal para exportar JSON."""
    return str(tmp_path / "test_umbrales.json")


# ==============================================================================
# TEST ESTADÍSTICA CAMPO
# ==============================================================================

class TestEstadisticaCampo:
    """Tests para la dataclass EstadisticaCampo."""

    def test_defaults(self):
        stat = EstadisticaCampo(campo="ruc")
        assert stat.campo == "ruc"
        assert stat.evaluados == 0
        assert stat.match == 0
        assert stat.error == 0
        assert stat.no_extraido == 0
        assert stat.skip == 0

    def test_tasa_acierto_sin_evaluados(self):
        stat = EstadisticaCampo(campo="ruc")
        assert stat.tasa_acierto == 0.0

    def test_tasa_acierto_con_datos(self):
        stat = EstadisticaCampo(campo="igv", evaluados=10, match=7, error=1, no_extraido=2)
        assert stat.tasa_acierto == pytest.approx(0.7, abs=0.001)

    def test_tasa_error_con_datos(self):
        stat = EstadisticaCampo(campo="ruc", evaluados=11, match=0, error=11)
        assert stat.tasa_error == pytest.approx(1.0, abs=0.001)

    def test_tasa_no_extraido(self):
        stat = EstadisticaCampo(campo="total", evaluados=16, match=7, error=3, no_extraido=6)
        assert stat.tasa_no_extraido == pytest.approx(0.375, abs=0.001)

    def test_tasa_fallo(self):
        stat = EstadisticaCampo(campo="total", evaluados=16, match=7, error=3, no_extraido=6)
        assert stat.tasa_fallo == pytest.approx(0.5625, abs=0.001)

    def test_to_dict(self):
        stat = EstadisticaCampo(campo="ruc", evaluados=11, match=0, error=11)
        d = stat.to_dict()
        assert d["campo"] == "ruc"
        assert d["evaluados"] == 11
        assert d["match"] == 0
        assert d["tasa_acierto"] == 0.0
        assert d["tasa_error"] == pytest.approx(1.0, abs=0.001)

    def test_from_dict_roundtrip(self):
        original = EstadisticaCampo(campo="fecha", evaluados=16, match=5, error=8, no_extraido=3, skip=0)
        d = original.to_dict()
        restored = EstadisticaCampo.from_dict(d)
        assert restored.campo == original.campo
        assert restored.evaluados == original.evaluados
        assert restored.match == original.match
        assert restored.error == original.error


# ==============================================================================
# TEST ANÁLISIS BENCHMARK
# ==============================================================================

class TestAnalisisBenchmark:
    """Tests para la dataclass AnalisisBenchmark."""

    def test_defaults(self):
        a = AnalisisBenchmark()
        assert a.prueba_id == ""
        assert a.total_comprobantes == 0
        assert a.precision_pct == 0.0
        assert a.stats_por_campo == {}

    def test_con_datos(self):
        a = AnalisisBenchmark(
            prueba_id="test",
            total_comprobantes=16,
            total_campos_evaluados=69,
            total_match=29,
            precision_pct=42.0,
        )
        assert a.total_comprobantes == 16
        assert a.precision_pct == 42.0

    def test_to_dict(self):
        stat = EstadisticaCampo(campo="ruc", evaluados=11, match=0, error=11)
        a = AnalisisBenchmark(
            prueba_id="test",
            stats_por_campo={"ruc": stat},
        )
        d = a.to_dict()
        assert d["prueba_id"] == "test"
        assert "ruc" in d["stats_por_campo"]
        assert d["stats_por_campo"]["ruc"]["evaluados"] == 11

    def test_from_dict_roundtrip(self):
        stat = EstadisticaCampo(campo="ruc", evaluados=11, match=0, error=11)
        original = AnalisisBenchmark(
            prueba_id="test",
            expediente="EXP-001",
            total_comprobantes=16,
            stats_por_campo={"ruc": stat},
        )
        d = original.to_dict()
        restored = AnalisisBenchmark.from_dict(d)
        assert restored.prueba_id == "test"
        assert restored.expediente == "EXP-001"
        assert "ruc" in restored.stats_por_campo
        assert restored.stats_por_campo["ruc"].evaluados == 11


# ==============================================================================
# TEST PERFIL CALIBRACIÓN
# ==============================================================================

class TestPerfilCalibracion:
    """Tests para el Enum PerfilCalibracion."""

    def test_valores(self):
        assert PerfilCalibracion.CONSERVADOR.value == "conservador"
        assert PerfilCalibracion.BALANCEADO.value == "balanceado"
        assert PerfilCalibracion.PERMISIVO.value == "permisivo"

    def test_len(self):
        assert len(PerfilCalibracion) == 3

    def test_from_value(self):
        assert PerfilCalibracion("conservador") == PerfilCalibracion.CONSERVADOR


# ==============================================================================
# TEST RESULTADO CALIBRACIÓN
# ==============================================================================

class TestResultadoCalibracion:
    """Tests para la dataclass ResultadoCalibracion."""

    def test_defaults(self):
        r = ResultadoCalibracion()
        assert r.perfil == ""
        assert r.umbrales_router == {}
        assert r.umbrales_abstencion == {}
        assert r.justificaciones == {}

    def test_to_dict_roundtrip(self):
        original = ResultadoCalibracion(
            perfil="conservador",
            umbrales_router={"max_campos_abstencion_warning_pct": 0.20},
            umbrales_abstencion={"ruc": 0.90},
            justificaciones={"test": "justificación"},
        )
        d = original.to_dict()
        restored = ResultadoCalibracion.from_dict(d)
        assert restored.perfil == "conservador"
        assert restored.umbrales_router["max_campos_abstencion_warning_pct"] == 0.20
        assert restored.umbrales_abstencion["ruc"] == 0.90


# ==============================================================================
# TEST CALIBRADOR — CARGA
# ==============================================================================

class TestCalibradorCarga:
    """Tests para carga de benchmarks."""

    def test_vacio_inicial(self):
        cal = CalibradorUmbrales()
        assert not cal.tiene_benchmarks
        assert not cal.tiene_analisis
        assert not cal.tiene_perfiles
        assert cal.num_benchmarks == 0

    def test_cargar_dict(self, benchmark_minimo):
        cal = CalibradorUmbrales()
        cal.cargar_benchmark_dict(benchmark_minimo)
        assert cal.tiene_benchmarks
        assert cal.num_benchmarks == 1

    def test_cargar_dict_invalido_sin_comprobantes(self):
        cal = CalibradorUmbrales()
        with pytest.raises(ValueError, match="resultados_por_comprobante"):
            cal.cargar_benchmark_dict({"metricas": {}})

    def test_cargar_dict_invalido_sin_metricas(self):
        cal = CalibradorUmbrales()
        with pytest.raises(ValueError, match="metricas"):
            cal.cargar_benchmark_dict({"resultados_por_comprobante": []})

    def test_cargar_archivo_inexistente(self):
        cal = CalibradorUmbrales()
        with pytest.raises(FileNotFoundError):
            cal.cargar_benchmark("/ruta/inexistente.json")

    def test_cargar_archivo_real(self, benchmark_cc003_path):
        cal = CalibradorUmbrales()
        cal.cargar_benchmark(benchmark_cc003_path)
        assert cal.num_benchmarks == 1

    def test_cargar_multiples(self, benchmark_minimo):
        cal = CalibradorUmbrales()
        cal.cargar_benchmark_dict(benchmark_minimo)
        cal.cargar_benchmark_dict(benchmark_minimo)
        assert cal.num_benchmarks == 2

    def test_cargar_invalida_analisis_previo(self, benchmark_minimo):
        cal = CalibradorUmbrales()
        cal.cargar_benchmark_dict(benchmark_minimo)
        cal.analizar()
        assert cal.tiene_analisis
        # Cargar otro invalida el análisis
        cal.cargar_benchmark_dict(benchmark_minimo)
        assert not cal.tiene_analisis


# ==============================================================================
# TEST CALIBRADOR — ANÁLISIS
# ==============================================================================

class TestCalibradorAnalisis:
    """Tests para el análisis de benchmarks."""

    def test_analizar_sin_datos(self):
        cal = CalibradorUmbrales()
        with pytest.raises(ValueError, match="No hay benchmarks"):
            cal.analizar()

    def test_analizar_benchmark_minimo(self, benchmark_minimo):
        cal = CalibradorUmbrales()
        cal.cargar_benchmark_dict(benchmark_minimo)
        analisis = cal.analizar()

        assert analisis.prueba_id == "test_minimo"
        assert analisis.expediente == "TEST-001"
        assert analisis.total_comprobantes == 2

        # 3 match, 2 error, 1 no_extraido = 6 evaluados
        assert analisis.total_match == 3
        assert analisis.total_error == 2
        assert analisis.total_no_extraido == 1
        assert analisis.total_campos_evaluados == 6
        assert analisis.total_skip == 4  # 4 SKIP_GT_NULL

        assert analisis.precision_pct == pytest.approx(50.0, abs=0.1)

    def test_analizar_confianza_ocr(self, benchmark_minimo):
        cal = CalibradorUmbrales()
        cal.cargar_benchmark_dict(benchmark_minimo)
        analisis = cal.analizar()

        assert analisis.confianza_ocr_min == pytest.approx(0.88, abs=0.001)
        assert analisis.confianza_ocr_max == pytest.approx(0.95, abs=0.001)
        assert analisis.confianza_ocr_media == pytest.approx(0.915, abs=0.001)

    def test_analizar_stats_por_campo(self, benchmark_minimo):
        cal = CalibradorUmbrales()
        cal.cargar_benchmark_dict(benchmark_minimo)
        analisis = cal.analizar()

        # ruc: 1 MATCH + 1 ERROR = 2 evaluados
        assert analisis.stats_por_campo["ruc"].evaluados == 2
        assert analisis.stats_por_campo["ruc"].match == 1
        assert analisis.stats_por_campo["ruc"].error == 1

        # serie_numero: 1 MATCH + 1 NO_EXTRAIDO = 2 evaluados
        assert analisis.stats_por_campo["serie_numero"].evaluados == 2
        assert analisis.stats_por_campo["serie_numero"].match == 1
        assert analisis.stats_por_campo["serie_numero"].no_extraido == 1

    def test_analizar_cc003(self, benchmark_cc003_path):
        """Verifica análisis del benchmark real cc003."""
        cal = CalibradorUmbrales()
        cal.cargar_benchmark(benchmark_cc003_path)
        analisis = cal.analizar()

        assert analisis.prueba_id == "empirica_cc003"
        assert analisis.total_comprobantes == 16
        assert analisis.total_campos_evaluados == 69
        assert analisis.total_match == 29
        assert analisis.precision_pct == pytest.approx(42.03, abs=0.1)

        # RUC: 0/11 match
        ruc = analisis.stats_por_campo["ruc"]
        assert ruc.match == 0
        assert ruc.error == 11
        assert ruc.tasa_acierto == 0.0

        # Serie/Numero: 10/16 match
        sn = analisis.stats_por_campo["serie_numero"]
        assert sn.match == 10
        assert sn.evaluados == 16

        # IGV: 7/10 match
        igv = analisis.stats_por_campo["igv"]
        assert igv.match == 7
        assert igv.evaluados == 10

    def test_analizar_tasa_fallo_cc003(self, benchmark_cc003_path):
        """Verifica tasa de fallo global del benchmark cc003."""
        cal = CalibradorUmbrales()
        cal.cargar_benchmark(benchmark_cc003_path)
        analisis = cal.analizar()

        # (25 error + 15 no_extraido) / 69 evaluados ≈ 0.5797
        assert analisis.tasa_fallo_global == pytest.approx(0.5797, abs=0.01)

    def test_analizar_multiples_benchmarks(self, benchmark_minimo):
        """Verifica que múltiples benchmarks se agregan correctamente."""
        cal = CalibradorUmbrales()
        cal.cargar_benchmark_dict(benchmark_minimo)
        cal.cargar_benchmark_dict(benchmark_minimo)
        analisis = cal.analizar()

        assert analisis.prueba_id.startswith("combinado_")
        assert analisis.total_comprobantes == 4  # 2 + 2
        assert analisis.total_match == 6  # 3 + 3
        assert analisis.total_campos_evaluados == 12  # 6 + 6

    def test_obtener_analisis_sin_analizar(self):
        cal = CalibradorUmbrales()
        assert cal.obtener_analisis() is None


# ==============================================================================
# TEST CALIBRADOR — PERFILES
# ==============================================================================

class TestCalibradorPerfiles:
    """Tests para la generación de perfiles."""

    def test_generar_perfiles_sin_datos(self):
        cal = CalibradorUmbrales()
        with pytest.raises(ValueError):
            cal.generar_perfiles()

    def test_generar_tres_perfiles(self, calibrador_con_cc003):
        perfiles = calibrador_con_cc003.generar_perfiles()
        assert len(perfiles) == 3
        assert PerfilCalibracion.CONSERVADOR in perfiles
        assert PerfilCalibracion.BALANCEADO in perfiles
        assert PerfilCalibracion.PERMISIVO in perfiles

    def test_perfil_conservador_valores(self, calibrador_con_perfiles):
        perfil = calibrador_con_perfiles.obtener_perfil(PerfilCalibracion.CONSERVADOR)
        assert perfil is not None
        ur = perfil.umbrales_router
        assert ur["max_campos_abstencion_warning_pct"] == 0.20
        assert ur["max_campos_abstencion_critical_pct"] == 0.40
        assert ur["min_comprobantes_con_datos"] == 2
        assert ur["min_campos_por_comprobante"] == 4

    def test_perfil_balanceado_valores(self, calibrador_con_perfiles):
        perfil = calibrador_con_perfiles.obtener_perfil(PerfilCalibracion.BALANCEADO)
        assert perfil is not None
        ur = perfil.umbrales_router
        assert ur["max_campos_abstencion_warning_pct"] == 0.35
        assert ur["max_campos_abstencion_critical_pct"] == 0.55
        assert ur["min_comprobantes_con_datos"] == 1
        assert ur["min_campos_por_comprobante"] == 3

    def test_perfil_permisivo_valores(self, calibrador_con_perfiles):
        perfil = calibrador_con_perfiles.obtener_perfil(PerfilCalibracion.PERMISIVO)
        assert perfil is not None
        ur = perfil.umbrales_router
        assert ur["max_campos_abstencion_warning_pct"] == 0.50
        assert ur["max_campos_abstencion_critical_pct"] == 0.70
        assert ur["min_comprobantes_con_datos"] == 1
        assert ur["min_campos_por_comprobante"] == 2

    def test_cada_perfil_tiene_9_umbrales_router(self, calibrador_con_perfiles):
        """Cada perfil debe tener exactamente 9 umbrales del router."""
        for perfil_enum in PerfilCalibracion:
            perfil = calibrador_con_perfiles.obtener_perfil(perfil_enum)
            assert len(perfil.umbrales_router) == 9, (
                f"Perfil {perfil_enum.value} tiene {len(perfil.umbrales_router)} umbrales, esperados 9"
            )

    def test_cada_perfil_tiene_umbrales_abstencion(self, calibrador_con_perfiles):
        """Cada perfil debe tener umbrales de abstención."""
        for perfil_enum in PerfilCalibracion:
            perfil = calibrador_con_perfiles.obtener_perfil(perfil_enum)
            assert len(perfil.umbrales_abstencion) >= 9, (
                f"Perfil {perfil_enum.value} tiene {len(perfil.umbrales_abstencion)} umbrales abstención"
            )

    def test_cada_perfil_tiene_justificaciones(self, calibrador_con_perfiles):
        """Cada perfil debe tener justificaciones."""
        for perfil_enum in PerfilCalibracion:
            perfil = calibrador_con_perfiles.obtener_perfil(perfil_enum)
            assert len(perfil.justificaciones) > 0

    def test_generar_autoanaliza(self, benchmark_minimo):
        """generar_perfiles() llama analizar() automáticamente si no se hizo."""
        cal = CalibradorUmbrales()
        cal.cargar_benchmark_dict(benchmark_minimo)
        assert not cal.tiene_analisis
        cal.generar_perfiles()
        assert cal.tiene_analisis
        assert cal.tiene_perfiles

    def test_obtener_perfil_inexistente(self, calibrador_con_cc003):
        """obtener_perfil sin generar devuelve None."""
        assert calibrador_con_cc003.obtener_perfil(PerfilCalibracion.CONSERVADOR) is None


# ==============================================================================
# TEST MONOTONÍA — WARNING < CRITICAL (dentro de cada perfil)
# ==============================================================================

class TestMonotonia:
    """Verifica que warning < critical en todos los umbrales de cada perfil."""

    @pytest.mark.parametrize("perfil_enum", list(PerfilCalibracion))
    def test_abstencion_warning_menor_que_critical(self, calibrador_con_perfiles, perfil_enum):
        perfil = calibrador_con_perfiles.obtener_perfil(perfil_enum)
        ur = perfil.umbrales_router
        assert ur["max_campos_abstencion_warning_pct"] < ur["max_campos_abstencion_critical_pct"], (
            f"Perfil {perfil_enum.value}: warning ({ur['max_campos_abstencion_warning_pct']}) "
            f"≥ critical ({ur['max_campos_abstencion_critical_pct']})"
        )

    @pytest.mark.parametrize("perfil_enum", list(PerfilCalibracion))
    def test_obs_degradadas_warning_menor_que_critical(self, calibrador_con_perfiles, perfil_enum):
        perfil = calibrador_con_perfiles.obtener_perfil(perfil_enum)
        ur = perfil.umbrales_router
        assert ur["max_observaciones_degradadas_warning"] < ur["max_observaciones_degradadas_critical"], (
            f"Perfil {perfil_enum.value}: obs warning ({ur['max_observaciones_degradadas_warning']}) "
            f"≥ critical ({ur['max_observaciones_degradadas_critical']})"
        )

    @pytest.mark.parametrize("perfil_enum", list(PerfilCalibracion))
    def test_errores_arit_warning_menor_que_critical(self, calibrador_con_perfiles, perfil_enum):
        perfil = calibrador_con_perfiles.obtener_perfil(perfil_enum)
        ur = perfil.umbrales_router
        assert ur["max_errores_aritmeticos_warning"] < ur["max_errores_aritmeticos_critical"], (
            f"Perfil {perfil_enum.value}: err warning ({ur['max_errores_aritmeticos_warning']}) "
            f"≥ critical ({ur['max_errores_aritmeticos_critical']})"
        )

    @pytest.mark.parametrize("perfil_enum", list(PerfilCalibracion))
    def test_umbrales_positivos(self, calibrador_con_perfiles, perfil_enum):
        """Todos los umbrales deben ser positivos."""
        perfil = calibrador_con_perfiles.obtener_perfil(perfil_enum)
        for nombre, valor in perfil.umbrales_router.items():
            assert valor > 0, f"Perfil {perfil_enum.value}: {nombre} = {valor} ≤ 0"

    @pytest.mark.parametrize("perfil_enum", list(PerfilCalibracion))
    def test_umbrales_abstencion_rango_valido(self, calibrador_con_perfiles, perfil_enum):
        """Umbrales de abstención deben estar en rango (0, 1]."""
        perfil = calibrador_con_perfiles.obtener_perfil(perfil_enum)
        for tipo, valor in perfil.umbrales_abstencion.items():
            assert 0.0 < valor <= 1.0, (
                f"Perfil {perfil_enum.value}: umbral abstención {tipo} = {valor} fuera de (0, 1]"
            )


# ==============================================================================
# TEST MONOTONÍA ENTRE PERFILES
# ==============================================================================

class TestMonotoniaEntrePerfiles:
    """
    Verifica que CONSERVADOR ≤ BALANCEADO ≤ PERMISIVO para umbrales
    donde mayor valor = más tolerante.
    """

    def _get_perfiles(self, calibrador_con_perfiles):
        c = calibrador_con_perfiles.obtener_perfil(PerfilCalibracion.CONSERVADOR)
        b = calibrador_con_perfiles.obtener_perfil(PerfilCalibracion.BALANCEADO)
        p = calibrador_con_perfiles.obtener_perfil(PerfilCalibracion.PERMISIVO)
        return c.umbrales_router, b.umbrales_router, p.umbrales_router

    def test_abstencion_warning_monotona(self, calibrador_con_perfiles):
        c, b, p = self._get_perfiles(calibrador_con_perfiles)
        assert c["max_campos_abstencion_warning_pct"] <= b["max_campos_abstencion_warning_pct"]
        assert b["max_campos_abstencion_warning_pct"] <= p["max_campos_abstencion_warning_pct"]

    def test_abstencion_critical_monotona(self, calibrador_con_perfiles):
        c, b, p = self._get_perfiles(calibrador_con_perfiles)
        assert c["max_campos_abstencion_critical_pct"] <= b["max_campos_abstencion_critical_pct"]
        assert b["max_campos_abstencion_critical_pct"] <= p["max_campos_abstencion_critical_pct"]

    def test_obs_degradadas_warning_monotona(self, calibrador_con_perfiles):
        c, b, p = self._get_perfiles(calibrador_con_perfiles)
        assert c["max_observaciones_degradadas_warning"] <= b["max_observaciones_degradadas_warning"]
        assert b["max_observaciones_degradadas_warning"] <= p["max_observaciones_degradadas_warning"]

    def test_obs_degradadas_critical_monotona(self, calibrador_con_perfiles):
        c, b, p = self._get_perfiles(calibrador_con_perfiles)
        assert c["max_observaciones_degradadas_critical"] <= b["max_observaciones_degradadas_critical"]
        assert b["max_observaciones_degradadas_critical"] <= p["max_observaciones_degradadas_critical"]

    def test_errores_arit_warning_monotona(self, calibrador_con_perfiles):
        c, b, p = self._get_perfiles(calibrador_con_perfiles)
        assert c["max_errores_aritmeticos_warning"] <= b["max_errores_aritmeticos_warning"]
        assert b["max_errores_aritmeticos_warning"] <= p["max_errores_aritmeticos_warning"]

    def test_errores_arit_critical_monotona(self, calibrador_con_perfiles):
        c, b, p = self._get_perfiles(calibrador_con_perfiles)
        assert c["max_errores_aritmeticos_critical"] <= b["max_errores_aritmeticos_critical"]
        assert b["max_errores_aritmeticos_critical"] <= p["max_errores_aritmeticos_critical"]

    def test_completitud_critical_monotona(self, calibrador_con_perfiles):
        c, b, p = self._get_perfiles(calibrador_con_perfiles)
        assert c["completitud_problemas_critical"] <= b["completitud_problemas_critical"]
        assert b["completitud_problemas_critical"] <= p["completitud_problemas_critical"]

    def test_min_campos_monotona_inversa(self, calibrador_con_perfiles):
        """min_campos_por_comprobante: CONSERVADOR ≥ BALANCEADO ≥ PERMISIVO."""
        c, b, p = self._get_perfiles(calibrador_con_perfiles)
        assert c["min_campos_por_comprobante"] >= b["min_campos_por_comprobante"]
        assert b["min_campos_por_comprobante"] >= p["min_campos_por_comprobante"]

    def test_min_comprobantes_monotona_inversa(self, calibrador_con_perfiles):
        """min_comprobantes: CONSERVADOR ≥ BALANCEADO ≥ PERMISIVO."""
        c, b, p = self._get_perfiles(calibrador_con_perfiles)
        assert c["min_comprobantes_con_datos"] >= b["min_comprobantes_con_datos"]
        assert b["min_comprobantes_con_datos"] >= p["min_comprobantes_con_datos"]


# ==============================================================================
# TEST JSON ROUNDTRIP
# ==============================================================================

class TestJsonRoundtrip:
    """Tests para exportar → importar JSON."""

    def test_exportar_sin_perfiles(self):
        cal = CalibradorUmbrales()
        with pytest.raises(ValueError, match="No hay perfiles"):
            cal.exportar_json("/tmp/test.json")

    def test_exportar_crear_directorio(self, calibrador_con_perfiles, tmp_path):
        output = str(tmp_path / "subdir" / "test.json")
        calibrador_con_perfiles.exportar_json(output)
        assert Path(output).exists()

    def test_exportar_contenido_valido(self, calibrador_con_perfiles, tmp_json_path):
        calibrador_con_perfiles.exportar_json(tmp_json_path)

        with open(tmp_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["version"] == VERSION_CALIBRACION
        assert "timestamp" in data
        assert "analisis_benchmark" in data
        assert "perfiles" in data
        assert len(data["perfiles"]) == 3
        assert data["perfil_recomendado"] == "balanceado"

    def test_importar_roundtrip(self, calibrador_con_perfiles, tmp_json_path):
        calibrador_con_perfiles.exportar_json(tmp_json_path)

        restored = CalibradorUmbrales.importar_json(tmp_json_path)
        assert restored.tiene_analisis
        assert restored.tiene_perfiles

        # Verificar que los perfiles restaurados tienen los mismos valores
        for perfil_enum in PerfilCalibracion:
            original = calibrador_con_perfiles.obtener_perfil(perfil_enum)
            restaurado = restored.obtener_perfil(perfil_enum)
            assert original.umbrales_router == restaurado.umbrales_router
            assert original.umbrales_abstencion == restaurado.umbrales_abstencion

    def test_importar_archivo_inexistente(self):
        with pytest.raises(FileNotFoundError):
            CalibradorUmbrales.importar_json("/ruta/inexistente.json")

    def test_importar_json_invalido(self, tmp_path):
        invalid = str(tmp_path / "invalid.json")
        with open(invalid, "w") as f:
            json.dump({"version": "1.0.0"}, f)  # Falta 'perfiles'
        with pytest.raises(ValueError, match="perfiles"):
            CalibradorUmbrales.importar_json(invalid)


# ==============================================================================
# TEST UTILIDADES
# ==============================================================================

class TestCalibradorUtilidades:
    """Tests para propiedades y utilidades."""

    def test_propiedades_iniciales(self):
        cal = CalibradorUmbrales()
        assert not cal.tiene_benchmarks
        assert not cal.tiene_analisis
        assert not cal.tiene_perfiles
        assert cal.num_benchmarks == 0

    def test_propiedades_post_carga(self, benchmark_minimo):
        cal = CalibradorUmbrales()
        cal.cargar_benchmark_dict(benchmark_minimo)
        assert cal.tiene_benchmarks
        assert not cal.tiene_analisis
        assert cal.num_benchmarks == 1

    def test_propiedades_post_analisis(self, benchmark_minimo):
        cal = CalibradorUmbrales()
        cal.cargar_benchmark_dict(benchmark_minimo)
        cal.analizar()
        assert cal.tiene_analisis
        assert not cal.tiene_perfiles

    def test_propiedades_post_perfiles(self, benchmark_minimo):
        cal = CalibradorUmbrales()
        cal.cargar_benchmark_dict(benchmark_minimo)
        cal.generar_perfiles()
        assert cal.tiene_perfiles

    def test_resumen_vacio(self):
        cal = CalibradorUmbrales()
        resumen = cal.resumen()
        assert "CalibradorUmbrales" in resumen
        assert "Benchmarks cargados: 0" in resumen

    def test_resumen_con_datos(self, calibrador_con_perfiles):
        resumen = calibrador_con_perfiles.resumen()
        assert "empirica_cc003" in resumen
        assert "CONSERVADOR" in resumen
        assert "BALANCEADO" in resumen
        assert "PERMISIVO" in resumen


# ==============================================================================
# TEST VALIDACIÓN CRUZADA CON BENCHMARK
# ==============================================================================

class TestValidacionCruzada:
    """Verifica que los perfiles evalúan cc003 según lo esperado."""

    def test_cc003_conservador_critical(self, calibrador_con_perfiles):
        """cc003 con CONSERVADOR → CRITICAL (58% fallo > 40% umbral)."""
        analisis = calibrador_con_perfiles.obtener_analisis()
        perfil = calibrador_con_perfiles.obtener_perfil(PerfilCalibracion.CONSERVADOR)
        tasa_fallo = analisis.tasa_fallo_global
        critical = perfil.umbrales_router["max_campos_abstencion_critical_pct"]
        assert tasa_fallo >= critical, (
            f"cc003 tasa fallo {tasa_fallo:.3f} debería ser ≥ critical {critical}"
        )

    def test_cc003_balanceado_critical(self, calibrador_con_perfiles):
        """cc003 con BALANCEADO → CRITICAL (58% fallo > 55% umbral)."""
        analisis = calibrador_con_perfiles.obtener_analisis()
        perfil = calibrador_con_perfiles.obtener_perfil(PerfilCalibracion.BALANCEADO)
        tasa_fallo = analisis.tasa_fallo_global
        critical = perfil.umbrales_router["max_campos_abstencion_critical_pct"]
        assert tasa_fallo >= critical, (
            f"cc003 tasa fallo {tasa_fallo:.3f} debería ser ≥ critical {critical}"
        )

    def test_cc003_permisivo_warning_no_critical(self, calibrador_con_perfiles):
        """cc003 con PERMISIVO → WARNING (58% fallo > 50% warning, < 70% critical)."""
        analisis = calibrador_con_perfiles.obtener_analisis()
        perfil = calibrador_con_perfiles.obtener_perfil(PerfilCalibracion.PERMISIVO)
        tasa_fallo = analisis.tasa_fallo_global
        warning = perfil.umbrales_router["max_campos_abstencion_warning_pct"]
        critical = perfil.umbrales_router["max_campos_abstencion_critical_pct"]
        assert tasa_fallo >= warning, (
            f"cc003 tasa fallo {tasa_fallo:.3f} debería ser ≥ warning {warning}"
        )
        assert tasa_fallo < critical, (
            f"cc003 tasa fallo {tasa_fallo:.3f} debería ser < critical {critical}"
        )

    def test_umbrales_abstencion_sin_cambios(self, calibrador_con_perfiles):
        """Los umbrales de abstención per-campo NO cambian entre perfiles."""
        perfiles = [
            calibrador_con_perfiles.obtener_perfil(p) for p in PerfilCalibracion
        ]
        base = perfiles[0].umbrales_abstencion
        for perfil in perfiles[1:]:
            assert perfil.umbrales_abstencion == base, (
                f"Perfil {perfil.perfil} tiene umbrales de abstención diferentes al CONSERVADOR"
            )

    def test_umbrales_abstencion_valores_conocidos(self, calibrador_con_perfiles):
        """Verifica valores específicos de umbrales de abstención."""
        perfil = calibrador_con_perfiles.obtener_perfil(PerfilCalibracion.BALANCEADO)
        ua = perfil.umbrales_abstencion
        assert ua["ruc"] == 0.90
        assert ua["monto"] == 0.90
        assert ua["fecha"] == 0.85
        assert ua["numero_documento"] == 0.85
        assert ua["default"] == 0.75
