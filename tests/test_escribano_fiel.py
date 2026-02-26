# -*- coding: utf-8 -*-
"""
Tests para EscribanoFiel — Orquestador del Pipeline de Extracción
==================================================================
Tarea #21 del Plan de Desarrollo (Fase 2: Contrato + Router)

Verifica:
  - Instanciación con inyección de dependencias
  - Pipeline completo con expediente preconstruido
  - Pipeline con PDF mock (custodia + OCR + parseo)
  - Detención por señal CRITICAL
  - Generación de Excel con hoja DIAGNOSTICO
  - Serialización de ResultadoPipeline
  - Función de conveniencia procesar_expediente()
  - Manejo de errores en cada paso
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from config.settings import (
    NaturalezaExpediente,
    NivelObservacion,
    Observacion,
)
from src.extraction.abstencion import AbstencionPolicy, UmbralesAbstencion
from src.extraction.confidence_router import (
    DecisionCheckpoint,
    DiagnosticoExpediente,
    IntegrityCheckpoint,
    ResultadoRouter,
    UmbralesRouter,
)
from src.extraction.escribano_fiel import (
    AGENTE_ID,
    VERSION_ESCRIBANO,
    ConfigPipeline,
    EscribanoFiel,
    ResultadoPaso,
    ResultadoPipeline,
    procesar_expediente,
)
from src.extraction.expediente_contract import (
    ConfianzaGlobal,
    DatosAnexo3,
    ExpedienteJSON,
    IntegridadExpediente,
    IntegridadStatus,
    ResumenExtraccion,
)
from src.ingestion.custody_chain import CustodyChain
from src.ingestion.trace_logger import TraceLogger

# ==============================================================================
# FIXTURES
# ==============================================================================


@pytest.fixture
def tmp_dir():
    """Directorio temporal para tests."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def expediente_minimo():
    """ExpedienteJSON mínimo para tests."""
    return ExpedienteJSON(
        sinad="TEST-2026-001",
        naturaleza=NaturalezaExpediente.VIATICOS.value,
        anexo3=DatosAnexo3(),
        comprobantes=[],
        declaracion_jurada=[],
        boletos=[],
        resumen_extraccion=ResumenExtraccion(),
        integridad=IntegridadExpediente(),
    )


@pytest.fixture
def config_test(tmp_dir):
    """Configuración de test con directorios temporales."""
    return ConfigPipeline(
        vault_dir=os.path.join(tmp_dir, "vault"),
        registry_dir=os.path.join(tmp_dir, "registry"),
        output_dir=os.path.join(tmp_dir, "output"),
        log_dir=os.path.join(tmp_dir, "logs"),
        generar_excel=True,
        detener_en_critical=True,
    )


@pytest.fixture
def pdf_dummy(tmp_dir):
    """Crea un archivo PDF dummy para tests de custodia."""
    pdf_path = os.path.join(tmp_dir, "test_expediente.pdf")
    # Crear un PDF mínimo válido
    pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
    with open(pdf_path, "wb") as f:
        f.write(pdf_content)
    return pdf_path


@pytest.fixture
def escribano_basico(config_test):
    """EscribanoFiel con configuración de test."""
    return EscribanoFiel(config=config_test)


# ==============================================================================
# TESTS — Constantes y versión
# ==============================================================================


class TestConstantes:
    """Tests para constantes y metadatos del módulo."""

    def test_version_definida(self):
        assert VERSION_ESCRIBANO == "1.0.0"

    def test_agente_id_definido(self):
        assert AGENTE_ID == "ESCRIBANO"


# ==============================================================================
# TESTS — ConfigPipeline
# ==============================================================================


class TestConfigPipeline:
    """Tests para la configuración del pipeline."""

    def test_defaults(self):
        config = ConfigPipeline()
        assert config.generar_excel is True
        assert config.detener_en_critical is True
        assert config.idioma_ocr == "spa"
        assert config.dpi_render == 200
        assert config.nombre_hoja_diagnostico == "DIAGNOSTICO"
        assert config.operador == "pipeline"
        assert config.source == "escribano_fiel"

    def test_custom_values(self):
        config = ConfigPipeline(
            generar_excel=False,
            detener_en_critical=False,
            dpi_render=300,
        )
        assert config.generar_excel is False
        assert config.detener_en_critical is False
        assert config.dpi_render == 300

    def test_directorios_none_por_defecto(self):
        config = ConfigPipeline()
        assert config.vault_dir is None
        assert config.output_dir is None
        assert config.log_dir is None


# ==============================================================================
# TESTS — ResultadoPaso
# ==============================================================================


class TestResultadoPaso:
    """Tests para ResultadoPaso."""

    def test_creacion_exitosa(self):
        paso = ResultadoPaso(
            paso="custodia",
            exito=True,
            duracion_ms=123.4,
            mensaje="OK",
        )
        assert paso.paso == "custodia"
        assert paso.exito is True
        assert paso.duracion_ms == 123.4

    def test_creacion_fallida(self):
        paso = ResultadoPaso(
            paso="ocr",
            exito=False,
            error="Motor no disponible",
        )
        assert paso.exito is False
        assert paso.error == "Motor no disponible"

    def test_to_dict(self):
        paso = ResultadoPaso(
            paso="evaluacion",
            exito=True,
            duracion_ms=50.555,
            mensaje="Status: OK",
        )
        d = paso.to_dict()
        assert d["paso"] == "evaluacion"
        assert d["exito"] is True
        assert d["duracion_ms"] == 50.6  # Redondeado a 1 decimal
        assert d["error"] is None


# ==============================================================================
# TESTS — ResultadoPipeline
# ==============================================================================


class TestResultadoPipeline:
    """Tests para ResultadoPipeline."""

    def test_creacion_minima(self):
        resultado = ResultadoPipeline(sinad="TEST-001", exito=True)
        assert resultado.sinad == "TEST-001"
        assert resultado.exito is True
        assert resultado.detenido is False
        assert resultado.ruta_excel is None
        assert len(resultado.pasos) == 0

    def test_to_dict(self):
        resultado = ResultadoPipeline(
            sinad="TEST-002",
            exito=False,
            detenido=True,
            razon_detencion="CRITICAL",
            duracion_total_ms=1000.5,
        )
        d = resultado.to_dict()
        assert d["sinad"] == "TEST-002"
        assert d["exito"] is False
        assert d["detenido"] is True
        assert d["razon_detencion"] == "CRITICAL"
        assert d["duracion_total_ms"] == 1000.5

    def test_to_dict_serializable_json(self):
        resultado = ResultadoPipeline(sinad="TEST-003", exito=True)
        resultado.pasos.append(ResultadoPaso(paso="test", exito=True, duracion_ms=10.0))
        d = resultado.to_dict()
        # Debe ser serializable a JSON
        json_str = json.dumps(d, ensure_ascii=False)
        assert "TEST-003" in json_str


# ==============================================================================
# TESTS — EscribanoFiel instanciación
# ==============================================================================


class TestEscribanoFielInit:
    """Tests para la instanciación de EscribanoFiel."""

    def test_instanciacion_default(self, config_test):
        escribano = EscribanoFiel(config=config_test)
        assert escribano.version == "1.0.0"
        assert escribano.config is config_test

    def test_instanciacion_sin_config(self):
        escribano = EscribanoFiel()
        assert escribano.config is not None
        assert escribano.config.generar_excel is True

    def test_inyeccion_custody_chain(self, config_test):
        custom_chain = CustodyChain(
            vault_dir=config_test.vault_dir,
            registry_dir=config_test.registry_dir,
        )
        escribano = EscribanoFiel(
            config=config_test,
            custody_chain=custom_chain,
        )
        assert escribano._custody is custom_chain

    def test_inyeccion_trace_logger(self, config_test):
        custom_logger = TraceLogger(log_dir=config_test.log_dir)
        escribano = EscribanoFiel(
            config=config_test,
            trace_logger=custom_logger,
        )
        assert escribano._logger is custom_logger

    def test_inyeccion_checkpoint(self, config_test):
        custom_checkpoint = IntegrityCheckpoint()
        escribano = EscribanoFiel(
            config=config_test,
            checkpoint=custom_checkpoint,
        )
        assert escribano._checkpoint is custom_checkpoint

    def test_inyeccion_abstencion(self, config_test):
        custom_policy = AbstencionPolicy()
        escribano = EscribanoFiel(
            config=config_test,
            abstencion_policy=custom_policy,
        )
        assert escribano._abstencion is custom_policy

    def test_get_stats(self, escribano_basico):
        stats = escribano_basico.get_stats()
        assert stats["version"] == "1.0.0"
        assert "config" in stats


# ==============================================================================
# TESTS — Pipeline con expediente preconstruido
# ==============================================================================


class TestPipelinePreconstruido:
    """Tests para el pipeline con expediente ya construido."""

    def test_evaluacion_expediente_vacio(self, escribano_basico, expediente_minimo):
        """Un expediente vacío debe evaluarse sin errores."""
        resultado = escribano_basico.evaluar_expediente(expediente_minimo)
        assert resultado.sinad == "TEST-2026-001"
        assert resultado.expediente is expediente_minimo
        assert resultado.decision is not None
        assert len(resultado.pasos) >= 4  # 3 omitidos + evaluación

    def test_pasos_omitidos_marcados(self, escribano_basico, expediente_minimo):
        """Los pasos custodia/OCR/parseo deben marcarse como omitidos."""
        resultado = escribano_basico.evaluar_expediente(expediente_minimo)
        assert resultado.pasos[0].paso == "custodia"
        assert "Omitido" in resultado.pasos[0].mensaje
        assert resultado.pasos[1].paso == "extraccion_ocr"
        assert "Omitido" in resultado.pasos[1].mensaje
        assert resultado.pasos[2].paso == "parseo"
        assert "Omitido" in resultado.pasos[2].mensaje

    def test_decision_checkpoint_presente(self, escribano_basico, expediente_minimo):
        """El DecisionCheckpoint debe estar en el resultado."""
        resultado = escribano_basico.evaluar_expediente(expediente_minimo)
        assert isinstance(resultado.decision, DecisionCheckpoint)
        assert resultado.decision.accion in [
            "CONTINUAR",
            "CONTINUAR_CON_ALERTAS",
            "DETENER",
        ]

    def test_resultado_router_presente(self, escribano_basico, expediente_minimo):
        """El ResultadoRouter debe estar en el resultado."""
        resultado = escribano_basico.evaluar_expediente(expediente_minimo)
        assert isinstance(resultado.resultado_router, ResultadoRouter)

    def test_procesar_con_expediente_preconstruido(self, escribano_basico, expediente_minimo):
        """procesar_expediente con expediente_preconstruido funciona."""
        resultado = escribano_basico.procesar_expediente(
            pdf_path="",
            sinad="TEST-PRE",
            expediente_preconstruido=expediente_minimo,
        )
        assert resultado.sinad == "TEST-PRE"
        assert resultado.decision is not None

    def test_excel_se_genera(self, config_test, expediente_minimo):
        """El Excel con DIAGNOSTICO debe generarse."""
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            pytest.skip("openpyxl no disponible")

        escribano = EscribanoFiel(config=config_test)
        resultado = escribano.evaluar_expediente(expediente_minimo)
        assert resultado.ruta_excel is not None
        assert os.path.exists(resultado.ruta_excel)
        assert resultado.ruta_excel.endswith(".xlsx")

    def test_excel_deshabilitado(self, config_test, expediente_minimo):
        """Si generar_excel=False, no se genera Excel."""
        config_test.generar_excel = False
        escribano = EscribanoFiel(config=config_test)
        resultado = escribano.evaluar_expediente(expediente_minimo)
        assert resultado.ruta_excel is None

    def test_ruta_excel_custom(self, config_test, expediente_minimo, tmp_dir):
        """Se puede especificar ruta de Excel custom."""
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            pytest.skip("openpyxl no disponible")

        ruta = os.path.join(tmp_dir, "custom_output.xlsx")
        escribano = EscribanoFiel(config=config_test)
        resultado = escribano.procesar_expediente(
            pdf_path="",
            sinad="TEST-CUSTOM",
            expediente_preconstruido=expediente_minimo,
            ruta_excel=ruta,
        )
        assert resultado.ruta_excel == ruta
        assert os.path.exists(ruta)


# ==============================================================================
# TESTS — Detención por CRITICAL
# ==============================================================================


class TestDetencionCritical:
    """Tests para detención del pipeline por señal CRITICAL."""

    def test_detener_en_critical(self, config_test, expediente_minimo):
        """Pipeline se detiene cuando IntegrityCheckpoint marca CRITICAL."""
        # Crear mock del checkpoint que retorna DETENER
        mock_checkpoint = MagicMock(spec=IntegrityCheckpoint)
        resultado_router = ResultadoRouter(
            status=IntegridadStatus.CRITICAL,
            debe_detener=True,
            razon_detencion="Tasa de abstención > 70%",
        )
        mock_checkpoint.evaluar.return_value = DecisionCheckpoint(
            accion="DETENER",
            resultado=resultado_router,
        )

        escribano = EscribanoFiel(
            config=config_test,
            checkpoint=mock_checkpoint,
        )
        resultado = escribano.evaluar_expediente(expediente_minimo)

        assert resultado.detenido is True
        assert "abstención" in resultado.razon_detencion

    def test_no_detener_si_deshabilitado(self, config_test, expediente_minimo):
        """Si detener_en_critical=False, no se detiene."""
        config_test.detener_en_critical = False

        mock_checkpoint = MagicMock(spec=IntegrityCheckpoint)
        resultado_router = ResultadoRouter(
            status=IntegridadStatus.CRITICAL,
            debe_detener=True,
            razon_detencion="Tasa de abstención > 70%",
        )
        mock_checkpoint.evaluar.return_value = DecisionCheckpoint(
            accion="DETENER",
            resultado=resultado_router,
        )

        escribano = EscribanoFiel(
            config=config_test,
            checkpoint=mock_checkpoint,
        )
        resultado = escribano.evaluar_expediente(expediente_minimo)

        assert resultado.detenido is False

    def test_continuar_con_alertas(self, config_test, expediente_minimo):
        """CONTINUAR_CON_ALERTAS no detiene el pipeline."""
        mock_checkpoint = MagicMock(spec=IntegrityCheckpoint)
        resultado_router = ResultadoRouter(
            status=IntegridadStatus.WARNING,
            debe_detener=False,
            alertas=["Baja confianza en campos de fecha"],
        )
        mock_checkpoint.evaluar.return_value = DecisionCheckpoint(
            accion="CONTINUAR_CON_ALERTAS",
            resultado=resultado_router,
        )

        escribano = EscribanoFiel(
            config=config_test,
            checkpoint=mock_checkpoint,
        )
        resultado = escribano.evaluar_expediente(expediente_minimo)

        assert resultado.detenido is False
        assert resultado.decision.accion == "CONTINUAR_CON_ALERTAS"


# ==============================================================================
# TESTS — Custodia
# ==============================================================================


class TestPasoCustodia:
    """Tests para el paso de custodia."""

    def test_custodia_archivo_no_existe(self, escribano_basico):
        """Custodia falla si el archivo no existe."""
        resultado = escribano_basico.procesar_expediente(
            pdf_path="/ruta/inexistente/archivo.pdf",
            sinad="TEST-NOFILE",
        )
        assert resultado.detenido is True
        assert (
            "no encontrado" in resultado.razon_detencion.lower()
            or "no existe" in resultado.razon_detencion.lower()
            or "Archivo no encontrado" in resultado.razon_detencion
        )

    def test_custodia_no_es_pdf(self, escribano_basico, tmp_dir):
        """Custodia falla si el archivo no es PDF."""
        txt_path = os.path.join(tmp_dir, "not_a.txt")
        with open(txt_path, "w") as f:
            f.write("no soy pdf")

        resultado = escribano_basico.procesar_expediente(
            pdf_path=txt_path,
            sinad="TEST-NOTPDF",
        )
        assert resultado.detenido is True
        assert "PDF" in resultado.razon_detencion or ".txt" in resultado.razon_detencion

    def test_custodia_exitosa(self, config_test, pdf_dummy):
        """Custodia exitosa con PDF válido."""
        escribano = EscribanoFiel(config=config_test)
        resultado = escribano._paso_custodia(pdf_dummy, "TEST-OK")
        assert resultado.exito is True
        assert resultado.datos.get("custody_record") is not None


# ==============================================================================
# TESTS — Parseo
# ==============================================================================


class TestPasoParseo:
    """Tests para el paso de parseo."""

    def test_parseo_sin_paginas(self, escribano_basico):
        """Parseo con 0 páginas crea expediente vacío."""
        paso = escribano_basico._paso_parseo(
            sinad="TEST-VACIO",
            paginas_ocr=[],
            pdf_path="test.pdf",
            naturaleza=NaturalezaExpediente.VIATICOS,
        )
        assert paso.exito is True
        expediente = paso.datos["expediente"]
        assert isinstance(expediente, ExpedienteJSON)
        assert expediente.sinad == "TEST-VACIO"

    def test_parseo_con_paginas(self, escribano_basico):
        """Parseo con páginas OCR crea expediente con archivos fuente."""
        paginas = [
            {
                "pagina": 1,
                "texto": "Factura F001-123",
                "confianza": 0.85,
                "motor": "paddleocr",
                "num_palabras": 3,
            },
            {
                "pagina": 2,
                "texto": "Boleta B001-456",
                "confianza": 0.90,
                "motor": "paddleocr",
                "num_palabras": 3,
            },
        ]
        paso = escribano_basico._paso_parseo(
            sinad="TEST-OCR",
            paginas_ocr=paginas,
            pdf_path="expediente.pdf",
            naturaleza=NaturalezaExpediente.CAJA_CHICA,
        )
        assert paso.exito is True
        expediente = paso.datos["expediente"]
        assert expediente.naturaleza == NaturalezaExpediente.CAJA_CHICA.value
        assert len(expediente.archivos_fuente) == 1
        assert expediente.archivos_fuente[0].total_paginas == 2


# ==============================================================================
# TESTS — Evaluación
# ==============================================================================


class TestPasoEvaluacion:
    """Tests para el paso de evaluación con IntegrityCheckpoint."""

    def test_evaluacion_expediente_vacio(self, escribano_basico, expediente_minimo):
        """Evaluación de expediente vacío no falla."""
        paso = escribano_basico._paso_evaluacion(expediente_minimo, [])
        assert paso.exito is True
        assert "decision" in paso.datos
        assert "resultado_router" in paso.datos

    def test_evaluacion_con_observaciones(self, escribano_basico, expediente_minimo):
        """Evaluación incluye observaciones previas."""
        obs = [
            Observacion(
                nivel=NivelObservacion.MENOR,
                agente="TEST",
                descripcion="Obs de test",
                accion_requerida="Ninguna",
            )
        ]
        paso = escribano_basico._paso_evaluacion(expediente_minimo, obs)
        assert paso.exito is True


# ==============================================================================
# TESTS — Excel
# ==============================================================================


class TestPasoExcel:
    """Tests para el paso de generación de Excel."""

    def test_excel_con_decision(self, escribano_basico, tmp_dir):
        """Excel se genera correctamente con DecisionCheckpoint."""
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            pytest.skip("openpyxl no disponible")

        decision = DecisionCheckpoint(
            accion="CONTINUAR",
            resultado=ResultadoRouter(),
            diagnostico=DiagnosticoExpediente(sinad="TEST-XLS"),
        )

        ruta = os.path.join(tmp_dir, "test_diag.xlsx")
        paso = escribano_basico._paso_excel(
            sinad="TEST-XLS",
            decision=decision,
            ruta_excel=ruta,
        )
        assert paso.exito is True
        assert os.path.exists(ruta)

    def test_excel_ruta_automatica(self, config_test):
        """Si no se da ruta, se genera automáticamente."""
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            pytest.skip("openpyxl no disponible")

        escribano = EscribanoFiel(config=config_test)
        decision = DecisionCheckpoint(
            accion="CONTINUAR",
            resultado=ResultadoRouter(),
            diagnostico=DiagnosticoExpediente(sinad="TEST-AUTO"),
        )

        paso = escribano._paso_excel(
            sinad="TEST-AUTO",
            decision=decision,
        )
        assert paso.exito is True
        assert "RENDICION_TEST-AUTO.xlsx" in paso.datos["ruta_excel"]


# ==============================================================================
# TESTS — Función de conveniencia
# ==============================================================================


class TestFuncionConveniencia:
    """Tests para la función procesar_expediente()."""

    def test_procesar_expediente_funcion(self, config_test, expediente_minimo):
        """La función de conveniencia funciona."""
        resultado = procesar_expediente(
            pdf_path="",
            sinad="TEST-CONV",
            config=config_test,
            expediente_preconstruido=expediente_minimo,
        )
        assert resultado.sinad == "TEST-CONV"
        assert resultado.decision is not None


# ==============================================================================
# TESTS — Manejo de errores
# ==============================================================================


class TestManejoErrores:
    """Tests para manejo robusto de errores."""

    def test_error_en_checkpoint_no_crash(self, config_test, expediente_minimo):
        """Si el checkpoint falla, el pipeline no crashea."""
        mock_checkpoint = MagicMock(spec=IntegrityCheckpoint)
        mock_checkpoint.evaluar.side_effect = RuntimeError("Error simulado")

        escribano = EscribanoFiel(
            config=config_test,
            checkpoint=mock_checkpoint,
        )
        resultado = escribano.evaluar_expediente(expediente_minimo)

        # El paso de evaluación falla pero no hay crash
        assert any(p.paso == "evaluacion" and not p.exito for p in resultado.pasos)

    def test_duracion_total_siempre_calculada(self, escribano_basico, expediente_minimo):
        """La duración total siempre se calcula."""
        resultado = escribano_basico.evaluar_expediente(expediente_minimo)
        assert resultado.duracion_total_ms > 0


# ==============================================================================
# TESTS — Integración pipeline completo
# ==============================================================================


class TestIntegracionPipeline:
    """Tests de integración del pipeline completo."""

    def test_pipeline_completo_preconstruido(self, config_test, expediente_minimo):
        """Pipeline completo con expediente preconstruido."""
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            pytest.skip("openpyxl no disponible")

        escribano = EscribanoFiel(config=config_test)
        resultado = escribano.evaluar_expediente(expediente_minimo)

        # Verificar productos
        assert resultado.expediente is not None
        assert resultado.decision is not None
        assert resultado.resultado_router is not None
        assert resultado.ruta_excel is not None

        # Verificar serialización
        d = resultado.to_dict()
        assert d["sinad"] == "TEST-2026-001"
        json_str = json.dumps(d, ensure_ascii=False)
        assert len(json_str) > 0

    def test_pipeline_con_custodia_real(self, config_test, pdf_dummy):
        """Pipeline con custodia real (PDF dummy)."""
        # El OCR no estará disponible en Windows, pero el pipeline
        # debe manejar eso gracefully
        escribano = EscribanoFiel(config=config_test)
        resultado = escribano.procesar_expediente(
            pdf_path=pdf_dummy,
            sinad="TEST-CUSTODIA-REAL",
        )
        # Custodia debe ser exitosa
        assert resultado.pasos[0].paso == "custodia"
        assert resultado.pasos[0].exito is True
        assert resultado.custody_record is not None

    def test_observaciones_previas_se_propagan(self, config_test, expediente_minimo):
        """Observaciones previas se incluyen en la evaluación."""
        obs = [
            Observacion(
                nivel=NivelObservacion.INFORMATIVA,
                agente="TEST",
                descripcion="Observación de prueba",
                accion_requerida="Ninguna",
            )
        ]
        escribano = EscribanoFiel(config=config_test)
        resultado = escribano.procesar_expediente(
            pdf_path="",
            sinad="TEST-OBS",
            expediente_preconstruido=expediente_minimo,
            observaciones_previas=obs,
        )
        assert len(resultado.observaciones) == 1
