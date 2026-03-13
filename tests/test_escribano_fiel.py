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
        assert VERSION_ESCRIBANO == "3.0.0"

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
        assert escribano.version == "3.0.0"
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
        assert stats["version"] == "3.0.0"
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
        # La observación previa + posibles observaciones de validación (Fase 4)
        assert any(o.agente == "TEST" for o in resultado.observaciones)
        assert resultado.observaciones[0].descripcion == "Observación de prueba"


# ==============================================================================
# TESTS — Parseo Profundo VLM (Fase 3 Integration)
# ==============================================================================


class TestIdentificarPaginasComprobante:
    """Tests para _identificar_paginas_comprobante()."""

    def test_pagina_con_factura_y_ruc(self, config_test):
        """Página con 'FACTURA' y RUC detectada como comprobante."""
        escribano = EscribanoFiel(config=config_test)
        paginas_ocr = [
            {"pagina": 1, "texto": "FACTURA ELECTRONICA RUC: 20123456789 Total 100.00"},
        ]
        result = escribano._identificar_paginas_comprobante(paginas_ocr, min_keywords=2)
        assert 1 in result

    def test_pagina_sin_keywords(self, config_test):
        """Página sin keywords de comprobante no se incluye."""
        escribano = EscribanoFiel(config=config_test)
        paginas_ocr = [
            {"pagina": 1, "texto": "DECLARACION JURADA DE VIATICOS"},
        ]
        result = escribano._identificar_paginas_comprobante(paginas_ocr, min_keywords=2)
        assert result == []

    def test_pagina_con_un_solo_keyword_no_alcanza(self, config_test):
        """Una sola keyword no alcanza con min_keywords=2."""
        escribano = EscribanoFiel(config=config_test)
        paginas_ocr = [
            {"pagina": 3, "texto": "FACTURA de servicio general"},
        ]
        result = escribano._identificar_paginas_comprobante(paginas_ocr, min_keywords=2)
        assert result == []

    def test_min_keywords_1(self, config_test):
        """Con min_keywords=1, una keyword basta."""
        escribano = EscribanoFiel(config=config_test)
        paginas_ocr = [
            {"pagina": 5, "texto": "IGV incluido en el total"},
        ]
        result = escribano._identificar_paginas_comprobante(paginas_ocr, min_keywords=1)
        assert 5 in result

    def test_multiples_paginas(self, config_test):
        """Varias páginas, solo las comprobantes se detectan."""
        escribano = EscribanoFiel(config=config_test)
        paginas_ocr = [
            {"pagina": 1, "texto": "OFICIO DE COMISION"},
            {"pagina": 2, "texto": "FACTURA ELECTRONICA RUC: 20123456789 IGV SUBTOTAL"},
            {"pagina": 3, "texto": "DECLARACION JURADA"},
            {"pagina": 4, "texto": "BOLETA DE VENTA SERIE: F001 IMPORTE TOTAL"},
        ]
        result = escribano._identificar_paginas_comprobante(paginas_ocr, min_keywords=2)
        assert 2 in result
        assert 4 in result
        assert 1 not in result
        assert 3 not in result

    def test_texto_vacio(self, config_test):
        """Página con texto vacío o None no se incluye."""
        escribano = EscribanoFiel(config=config_test)
        paginas_ocr = [
            {"pagina": 1, "texto": ""},
            {"pagina": 2, "texto": None},
            {"pagina": 3},
        ]
        result = escribano._identificar_paginas_comprobante(paginas_ocr, min_keywords=1)
        assert result == []

    def test_case_insensitive(self, config_test):
        """Keywords se detectan sin importar mayúsculas/minúsculas."""
        escribano = EscribanoFiel(config=config_test)
        paginas_ocr = [
            {"pagina": 1, "texto": "factura electronica ruc: 20123456789"},
        ]
        result = escribano._identificar_paginas_comprobante(paginas_ocr, min_keywords=2)
        assert 1 in result


class TestClasificarTipoComprobante:
    """Tests para _clasificar_tipo_comprobante() — ADR-011 gating mejorado."""

    def test_factura_electronica(self, config_test):
        escribano = EscribanoFiel(config=config_test)
        assert escribano._clasificar_tipo_comprobante("FACTURA ELECTRONICA F001-123") == "FACTURA"

    def test_factura_por_serie(self, config_test):
        escribano = EscribanoFiel(config=config_test)
        assert escribano._clasificar_tipo_comprobante("SERIE: F001 algo más") == "FACTURA"

    def test_boleta_de_venta(self, config_test):
        escribano = EscribanoFiel(config=config_test)
        assert escribano._clasificar_tipo_comprobante("BOLETA DE VENTA B001-999") == "BOLETA"

    def test_boleta_por_serie(self, config_test):
        escribano = EscribanoFiel(config=config_test)
        assert escribano._clasificar_tipo_comprobante("SERIE: B001 IGV TOTAL") == "BOLETA"

    def test_boarding_pass(self, config_test):
        escribano = EscribanoFiel(config=config_test)
        assert (
            escribano._clasificar_tipo_comprobante("BOARDING PASS GATE 5 SEAT 12A")
            == "BOARDING_PASS"
        )

    def test_boarding_tarjeta_embarque(self, config_test):
        escribano = EscribanoFiel(config=config_test)
        assert (
            escribano._clasificar_tipo_comprobante("TARJETA DE EMBARQUE PASAJERO")
            == "BOARDING_PASS"
        )

    def test_declaracion_jurada(self, config_test):
        escribano = EscribanoFiel(config=config_test)
        assert (
            escribano._clasificar_tipo_comprobante("DECLARACION JURADA DE GASTOS")
            == "DECLARACION_JURADA"
        )

    def test_recibo_honorarios(self, config_test):
        escribano = EscribanoFiel(config=config_test)
        assert (
            escribano._clasificar_tipo_comprobante("RECIBO POR HONORARIOS E001-500")
            == "RECIBO_HONORARIOS"
        )

    def test_administrativo_default(self, config_test):
        escribano = EscribanoFiel(config=config_test)
        assert (
            escribano._clasificar_tipo_comprobante("OFICIO DE COMISION DE SERVICIO")
            == "ADMINISTRATIVO"
        )

    def test_texto_vacio(self, config_test):
        escribano = EscribanoFiel(config=config_test)
        assert escribano._clasificar_tipo_comprobante("") == "ADMINISTRATIVO"

    def test_case_insensitive(self, config_test):
        escribano = EscribanoFiel(config=config_test)
        assert escribano._clasificar_tipo_comprobante("factura electronica") == "FACTURA"

    def test_prioridad_factura_sobre_admin(self, config_test):
        """Si texto tiene keywords de factura, clasifica como FACTURA aunque tenga otros textos."""
        escribano = EscribanoFiel(config=config_test)
        assert (
            escribano._clasificar_tipo_comprobante("OFICIO FACTURA ELECTRONICA RUC: 20123456789")
            == "FACTURA"
        )


class TestConstantesADR011:
    """Tests para constantes de ADR-011."""

    def test_max_vlm_image_px(self):
        from src.extraction.escribano_fiel import MAX_VLM_IMAGE_PX

        assert MAX_VLM_IMAGE_PX == 1200

    def test_patrones_tipo_comprobante_completos(self):
        from src.extraction.escribano_fiel import PATRONES_TIPO_COMPROBANTE

        assert "FACTURA" in PATRONES_TIPO_COMPROBANTE
        assert "BOLETA" in PATRONES_TIPO_COMPROBANTE
        assert "BOARDING_PASS" in PATRONES_TIPO_COMPROBANTE
        assert "DECLARACION_JURADA" in PATRONES_TIPO_COMPROBANTE
        assert "RECIBO_HONORARIOS" in PATRONES_TIPO_COMPROBANTE


class TestPasoParseProfundoVLMDisabled:
    """Tests para _paso_parseo_profundo con VLM deshabilitado."""

    def test_vlm_disabled_returns_success(self, tmp_dir, expediente_minimo):
        """Con vlm_enabled=False, retorna éxito sin procesar."""
        config = ConfigPipeline(
            vault_dir=os.path.join(tmp_dir, "vault"),
            registry_dir=os.path.join(tmp_dir, "registry"),
            output_dir=os.path.join(tmp_dir, "output"),
            log_dir=os.path.join(tmp_dir, "logs"),
            vlm_enabled=False,
        )
        escribano = EscribanoFiel(config=config)
        result = escribano._paso_parseo_profundo(
            expediente=expediente_minimo,
            paginas_ocr=[],
            pdf_path="dummy.pdf",
        )
        assert result.exito is True
        assert "deshabilitado" in result.mensaje.lower()

    def test_zero_comprobante_pages(self, config_test, expediente_minimo):
        """Sin páginas comprobante, retorna éxito con 0 extraídos."""
        escribano = EscribanoFiel(config=config_test)
        paginas_ocr = [
            {"pagina": 1, "texto": "DECLARACION JURADA DE VIATICOS"},
        ]
        result = escribano._paso_parseo_profundo(
            expediente=expediente_minimo,
            paginas_ocr=paginas_ocr,
            pdf_path="dummy.pdf",
        )
        assert result.exito is True
        assert "0 páginas" in result.mensaje

    def test_import_error_handled(self, config_test, expediente_minimo):
        """Si módulos VLM no están disponibles, no crashea."""
        escribano = EscribanoFiel(config=config_test)
        paginas_ocr = [
            {"pagina": 1, "texto": "FACTURA ELECTRONICA RUC: 20123456789 IGV SUBTOTAL"},
        ]
        with patch(
            "src.extraction.escribano_fiel.EscribanoFiel._identificar_paginas_comprobante",
            return_value=[1],
        ):
            with patch.dict("sys.modules", {"src.extraction.qwen_fallback": None}):
                result = escribano._paso_parseo_profundo(
                    expediente=expediente_minimo,
                    paginas_ocr=paginas_ocr,
                    pdf_path="dummy.pdf",
                )
        assert result.exito is True
        assert "no disponibles" in result.mensaje.lower() or result.mensaje


class TestConfigPipelineVLM:
    """Tests para las nuevas opciones VLM en ConfigPipeline."""

    def test_defaults(self):
        config = ConfigPipeline()
        assert config.vlm_enabled is True
        assert config.vlm_config is None
        assert config.dpi_vlm == 200
        assert config.min_keywords_comprobante == 2

    def test_custom_values(self):
        config = ConfigPipeline(
            vlm_enabled=False,
            vlm_config={"model": "qwen3-vl:8b"},
            dpi_vlm=300,
            min_keywords_comprobante=3,
        )
        assert config.vlm_enabled is False
        assert config.vlm_config == {"model": "qwen3-vl:8b"}
        assert config.dpi_vlm == 300
        assert config.min_keywords_comprobante == 3


# ==============================================================================
# TESTS — ADR-011 Nivel 2: OCR-first + Score Suficiencia
# ==============================================================================

from src.extraction.escribano_fiel import (
    CAMPOS_ESPERADOS_POR_TIPO,
    REGEX_FECHA_EMISION,
    REGEX_FECHA_GENERAL,
    REGEX_IGV,
    REGEX_RUC,
    REGEX_SERIE_NUMERO,
    REGEX_SUBTOTAL,
    REGEX_TOTAL,
    RUCS_PAGADOR,
    SCORE_UMBRAL_CON_OBS,
    SCORE_UMBRAL_SIN_VLM,
)


class TestRegexOCRFirst:
    """Tests para los regex de extracción OCR-first."""

    def test_regex_ruc_basico(self):
        texto = "R.U.C.: 20610827171 RESTAURANTE EL CHALAN"
        m = REGEX_RUC.findall(texto)
        assert "20610827171" in m

    def test_regex_ruc_sin_puntos(self):
        texto = "RUC: 20604955498"
        m = REGEX_RUC.findall(texto)
        assert "20604955498" in m

    def test_regex_ruc_multiple(self):
        texto = "RUC: 20131370998 MINEDU\nRUC: 20610827171 PROVEEDOR"
        m = REGEX_RUC.findall(texto)
        assert len(m) == 2
        assert "20131370998" in m
        assert "20610827171" in m

    def test_regex_ruc_filtra_estado(self):
        rucs = ["20131370998", "20610827171"]
        filtrados = [r for r in rucs if r not in RUCS_PAGADOR]
        assert filtrados == ["20610827171"]

    def test_regex_fecha_emision(self):
        texto = "FECHA DE EMISIÓN: 06/02/2026"
        m = REGEX_FECHA_EMISION.search(texto)
        assert m is not None
        assert m.group(1) == "06/02/2026"

    def test_regex_fecha_emision_variante(self):
        texto = "F. EMISION: 03-02-2026"
        m = REGEX_FECHA_EMISION.search(texto)
        assert m is not None
        assert m.group(1) == "03-02-2026"

    def test_regex_fecha_emision_simple(self):
        texto = "FECHA: 07.02.2026"
        m = REGEX_FECHA_EMISION.search(texto)
        assert m is not None
        assert m.group(1) == "07.02.2026"

    def test_regex_fecha_general_fallback(self):
        texto = "Emitido el 15/03/2026 en Lima"
        m = REGEX_FECHA_GENERAL.search(texto)
        assert m is not None
        assert m.group(1) == "15/03/2026"

    def test_regex_serie_numero_factura(self):
        texto = "F011-8846"
        m = REGEX_SERIE_NUMERO.search(texto)
        assert m is not None
        assert m.group(1).upper() == "F011"
        assert m.group(2) == "8846"

    def test_regex_serie_numero_boleta(self):
        texto = "B001-005367"
        m = REGEX_SERIE_NUMERO.search(texto)
        assert m is not None
        assert m.group(1).upper() == "B001"
        assert m.group(2) == "005367"

    def test_regex_serie_numero_electronico(self):
        texto = "E001-1771"
        m = REGEX_SERIE_NUMERO.search(texto)
        assert m is not None
        assert m.group(1).upper() == "E001"
        assert m.group(2) == "1771"

    def test_regex_serie_numero_largo(self):
        texto = "FP01-233"
        m = REGEX_SERIE_NUMERO.search(texto)
        assert m is not None

    def test_regex_total(self):
        texto = "IMPORTE TOTAL S/. 125.50"
        m = REGEX_TOTAL.search(texto)
        assert m is not None
        assert m.group(1) == "125.50"

    def test_regex_total_con_coma(self):
        texto = "TOTAL A PAGAR S/ 1,250.00"
        m = REGEX_TOTAL.search(texto)
        assert m is not None
        assert m.group(1) == "1,250.00"

    def test_regex_total_venta(self):
        texto = "TOTAL VENTA : S/. 89.00"
        m = REGEX_TOTAL.search(texto)
        assert m is not None
        assert m.group(1) == "89.00"

    def test_regex_igv(self):
        texto = "I.G.V. (18%) S/. 22.50"
        m = REGEX_IGV.search(texto)
        assert m is not None
        assert m.group(1) == "22.50"

    def test_regex_igv_simple(self):
        texto = "IGV: S/ 18.00"
        m = REGEX_IGV.search(texto)
        assert m is not None
        assert m.group(1) == "18.00"

    def test_regex_subtotal(self):
        texto = "SUB TOTAL S/. 100.00"
        m = REGEX_SUBTOTAL.search(texto)
        assert m is not None
        assert m.group(1) == "100.00"

    def test_regex_op_gravada(self):
        texto = "OP. GRAVADA S/. 200.00"
        m = REGEX_SUBTOTAL.search(texto)
        assert m is not None
        assert m.group(1) == "200.00"

    def test_regex_valor_venta(self):
        texto = "VALOR DE VENTA S/. 150.00"
        m = REGEX_SUBTOTAL.search(texto)
        assert m is not None
        assert m.group(1) == "150.00"


class TestConstantesOCRFirst:
    """Tests para constantes OCR-first."""

    def test_umbrales_definidos(self):
        assert SCORE_UMBRAL_SIN_VLM == 0.75
        assert SCORE_UMBRAL_CON_OBS == 0.50

    def test_campos_esperados_factura(self):
        campos = CAMPOS_ESPERADOS_POR_TIPO["FACTURA"]
        assert "ruc_emisor" in campos
        assert "fecha_emision" in campos
        assert "serie_numero" in campos
        assert "importe_total" in campos
        assert "igv_monto" in campos

    def test_campos_esperados_boleta(self):
        campos = CAMPOS_ESPERADOS_POR_TIPO["BOLETA"]
        assert "igv_monto" not in campos  # Boleta no requiere IGV

    def test_campos_esperados_boarding_pass(self):
        campos = CAMPOS_ESPERADOS_POR_TIPO["BOARDING_PASS"]
        assert len(campos) == 1  # Solo fecha

    def test_rucs_pagador_minedu(self):
        assert "20131370998" in RUCS_PAGADOR


class TestExtraerCamposOCRPorTipo:
    """Tests para _extraer_campos_ocr_por_tipo()."""

    @pytest.fixture
    def escribano(self, tmp_dir):
        config = ConfigPipeline(
            vault_dir=os.path.join(tmp_dir, "vault"),
            registry_dir=os.path.join(tmp_dir, "registry"),
            output_dir=os.path.join(tmp_dir, "output"),
            log_dir=os.path.join(tmp_dir, "logs"),
        )
        return EscribanoFiel(config=config)

    def test_factura_completa(self, escribano):
        texto = """
        FACTURA ELECTRONICA
        R.U.C.: 20610827171
        RESTAURANTE EL CHALAN S.A.C.
        FECHA DE EMISIÓN: 06/02/2026
        F011-8846
        OP. GRAVADA S/. 106.36
        I.G.V. (18%) S/. 19.14
        IMPORTE TOTAL S/. 125.50
        """
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "FACTURA", "test.pdf", 5)

        assert comp.grupo_a.ruc_emisor is not None
        assert comp.grupo_a.ruc_emisor.valor == "20610827171"
        assert comp.grupo_b.fecha_emision is not None
        assert comp.grupo_b.fecha_emision.valor == "06/02/2026"
        assert comp.grupo_b.serie is not None
        assert comp.grupo_b.serie.valor == "F011"
        assert comp.grupo_b.numero is not None
        assert comp.grupo_b.numero.valor == "8846"
        assert comp.grupo_f.importe_total is not None
        assert comp.grupo_f.importe_total.valor == "125.50"
        assert comp.grupo_f.igv_monto is not None
        assert comp.grupo_f.igv_monto.valor == "19.14"
        assert comp.grupo_f.subtotal is not None
        assert comp.grupo_f.subtotal.valor == "106.36"

    def test_factura_filtra_ruc_minedu(self, escribano):
        texto = """
        RUC: 20131370998 MINISTERIO DE EDUCACION
        RUC: 20610827171 PROVEEDOR SAC
        FECHA DE EMISIÓN: 06/02/2026
        F011-8846
        IMPORTE TOTAL S/. 125.50
        """
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "FACTURA", "test.pdf", 1)
        assert comp.grupo_a.ruc_emisor.valor == "20610827171"

    def test_boleta_sin_igv(self, escribano):
        texto = """
        BOLETA DE VENTA
        RUC: 10701855406
        FECHA: 07/02/2026
        B001-005367
        TOTAL VENTA : S/. 25.00
        """
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "BOLETA", "test.pdf", 10)
        assert comp.grupo_a.ruc_emisor is not None
        assert comp.grupo_a.ruc_emisor.valor == "10701855406"
        assert comp.grupo_b.fecha_emision is not None
        assert comp.grupo_f.importe_total is not None
        assert comp.grupo_f.igv_monto is None

    def test_recibo_honorarios(self, escribano):
        texto = """
        RECIBO POR HONORARIOS ELECTRONICO
        RUC: 10073775006
        FECHA DE EMISIÓN: 15/02/2026
        E001-1771
        IMPORTE TOTAL S/. 500.00
        """
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "RECIBO_HONORARIOS", "test.pdf", 3)
        assert comp.grupo_a.ruc_emisor.valor == "10073775006"
        assert comp.grupo_b.serie.valor == "E001"
        assert comp.grupo_b.numero.valor == "1771"

    def test_metadatos_ocr_first(self, escribano):
        texto = "RUC: 20610827171\nFECHA: 06/02/2026\nIMPORTE TOTAL S/. 100.00"
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "FACTURA", "exp.pdf", 7)
        assert comp.grupo_k.pagina_origen == 7
        assert comp.grupo_k.metodo_extraccion == "OCR_FIRST_REGEX"
        assert comp.grupo_k.timestamp_extraccion != ""

    def test_metodo_extraccion_regex(self, escribano):
        texto = "RUC: 20610827171"
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "FACTURA", "test.pdf", 1)
        from config.settings import MetodoExtraccion

        assert comp.grupo_a.ruc_emisor.metodo == MetodoExtraccion.REGEX

    def test_texto_vacio(self, escribano):
        comp = escribano._extraer_campos_ocr_por_tipo("", "FACTURA", "test.pdf", 1)
        assert comp.grupo_a.ruc_emisor is None
        assert comp.grupo_b.fecha_emision is None
        assert comp.grupo_f.importe_total is None

    def test_solo_ruc_estado(self, escribano):
        texto = "RUC: 20131370998 MINISTERIO DE EDUCACION"
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "FACTURA", "test.pdf", 1)
        # Should be None because only state RUC found
        assert comp.grupo_a.ruc_emisor is None

    def test_tipo_comprobante_siempre_presente(self, escribano):
        texto = "algo de texto"
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "BOLETA", "test.pdf", 1)
        assert comp.grupo_b.tipo_comprobante is not None
        assert comp.grupo_b.tipo_comprobante.valor == "BOLETA"

    def test_confianza_fecha_emision_alta(self, escribano):
        texto = "FECHA DE EMISIÓN: 06/02/2026"
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "FACTURA", "test.pdf", 1)
        assert comp.grupo_b.fecha_emision.confianza == 0.85

    def test_confianza_fecha_general_baja(self, escribano):
        texto = "Documento del 06/02/2026"
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "FACTURA", "test.pdf", 1)
        assert comp.grupo_b.fecha_emision.confianza == 0.6

    def test_total_con_coma_limpia_valor(self, escribano):
        texto = "TOTAL A PAGAR S/ 1,250.00"
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "FACTURA", "test.pdf", 1)
        assert comp.grupo_f.importe_total.valor == "1250.00"


class TestCalcularScoreSuficiencia:
    """Tests para _calcular_score_suficiencia()."""

    @pytest.fixture
    def escribano(self, tmp_dir):
        config = ConfigPipeline(
            vault_dir=os.path.join(tmp_dir, "vault"),
            registry_dir=os.path.join(tmp_dir, "registry"),
            output_dir=os.path.join(tmp_dir, "output"),
            log_dir=os.path.join(tmp_dir, "logs"),
        )
        return EscribanoFiel(config=config)

    def test_factura_completa_score_1(self, escribano):
        texto = """
        RUC: 20610827171
        FECHA DE EMISIÓN: 06/02/2026
        F011-8846
        IMPORTE TOTAL S/. 125.50
        IGV: S/ 19.14
        """
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "FACTURA", "t.pdf", 1)
        score, encontrados, esperados, faltantes = escribano._calcular_score_suficiencia(
            comp, "FACTURA"
        )
        assert score == 1.0
        assert len(faltantes) == 0
        assert len(encontrados) == 5

    def test_factura_sin_igv_score_080(self, escribano):
        texto = """
        RUC: 20610827171
        FECHA DE EMISIÓN: 06/02/2026
        F011-8846
        IMPORTE TOTAL S/. 125.50
        """
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "FACTURA", "t.pdf", 1)
        score, encontrados, esperados, faltantes = escribano._calcular_score_suficiencia(
            comp, "FACTURA"
        )
        assert score == 0.8
        assert "igv_monto" in faltantes

    def test_factura_solo_ruc_fecha_score_040(self, escribano):
        texto = """
        RUC: 20610827171
        FECHA DE EMISIÓN: 06/02/2026
        """
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "FACTURA", "t.pdf", 1)
        score, encontrados, esperados, faltantes = escribano._calcular_score_suficiencia(
            comp, "FACTURA"
        )
        assert score == 0.4
        assert "serie_numero" in faltantes
        assert "importe_total" in faltantes
        assert "igv_monto" in faltantes

    def test_boleta_completa_score_1(self, escribano):
        texto = """
        RUC: 10701855406
        FECHA: 07/02/2026
        B001-005367
        TOTAL VENTA : S/. 25.00
        """
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "BOLETA", "t.pdf", 1)
        score, encontrados, esperados, faltantes = escribano._calcular_score_suficiencia(
            comp, "BOLETA"
        )
        assert score == 1.0

    def test_boarding_pass_solo_fecha(self, escribano):
        texto = "15/03/2026"
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "BOARDING_PASS", "t.pdf", 1)
        score, encontrados, esperados, faltantes = escribano._calcular_score_suficiencia(
            comp, "BOARDING_PASS"
        )
        assert score == 1.0

    def test_vacio_score_0(self, escribano):
        from src.extraction.expediente_contract import ComprobanteExtraido

        comp = ComprobanteExtraido()
        score, encontrados, esperados, faltantes = escribano._calcular_score_suficiencia(
            comp, "FACTURA"
        )
        assert score == 0.0
        assert len(faltantes) == 5

    def test_score_umbral_sin_vlm(self, escribano):
        """Score >= 0.75 should resolve without VLM."""
        texto = """
        RUC: 20610827171
        FECHA DE EMISIÓN: 06/02/2026
        F011-8846
        IMPORTE TOTAL S/. 125.50
        """
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "FACTURA", "t.pdf", 1)
        score, _, _, _ = escribano._calcular_score_suficiencia(comp, "FACTURA")
        assert score >= SCORE_UMBRAL_SIN_VLM

    def test_score_umbral_con_obs(self, escribano):
        """Score 0.50-0.74 should resolve with observation."""
        texto = """
        RUC: 20610827171
        FECHA DE EMISIÓN: 06/02/2026
        IMPORTE TOTAL S/. 125.50
        """
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "FACTURA", "t.pdf", 1)
        score, _, _, _ = escribano._calcular_score_suficiencia(comp, "FACTURA")
        assert SCORE_UMBRAL_CON_OBS <= score < SCORE_UMBRAL_SIN_VLM

    def test_score_bajo_escalar_vlm(self, escribano):
        """Score < 0.50 should escalate to VLM."""
        texto = """
        RUC: 20610827171
        """
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "FACTURA", "t.pdf", 1)
        score, _, _, _ = escribano._calcular_score_suficiencia(comp, "FACTURA")
        assert score < SCORE_UMBRAL_CON_OBS

    def test_tipo_desconocido_usa_default(self, escribano):
        from src.extraction.expediente_contract import ComprobanteExtraido

        comp = ComprobanteExtraido()
        score, _, esperados, _ = escribano._calcular_score_suficiencia(comp, "TIPO_RARO")
        assert esperados == ["fecha_emision"]


class TestOCRFirstIntegracion:
    """Tests de integración para OCR-first en pipeline."""

    @pytest.fixture
    def escribano(self, tmp_dir):
        config = ConfigPipeline(
            vault_dir=os.path.join(tmp_dir, "vault"),
            registry_dir=os.path.join(tmp_dir, "registry"),
            output_dir=os.path.join(tmp_dir, "output"),
            log_dir=os.path.join(tmp_dir, "logs"),
        )
        return EscribanoFiel(config=config)

    def test_factura_ocr_first_sin_vlm(self, escribano):
        """Factura con score alto → comprobante resuelto sin VLM."""
        texto = """
        FACTURA ELECTRONICA
        R.U.C.: 20610827171
        RESTAURANTE EL CHALAN S.A.C.
        FECHA DE EMISIÓN: 06/02/2026
        F011-8846
        OP. GRAVADA S/. 106.36
        I.G.V. (18%) S/. 19.14
        IMPORTE TOTAL S/. 125.50
        """
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "FACTURA", "test.pdf", 5)
        score, _, _, _ = escribano._calcular_score_suficiencia(comp, "FACTURA")

        assert score == 1.0
        assert comp.grupo_a.ruc_emisor.valor == "20610827171"
        assert comp.grupo_b.fecha_emision.valor == "06/02/2026"
        assert comp.grupo_b.serie.valor == "F011"
        assert comp.grupo_f.importe_total.valor == "125.50"
        assert comp.grupo_f.igv_monto.valor == "19.14"

    def test_snippet_ruc_contexto(self, escribano):
        """Snippet del RUC incluye contexto circundante."""
        texto = "EMISOR R.U.C.: 20610827171 SAC LIMA"
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "FACTURA", "test.pdf", 1)
        assert comp.grupo_a.ruc_emisor.snippet != ""
        assert "20610827171" in comp.grupo_a.ruc_emisor.snippet

    def test_multiples_ruc_toma_primero_no_estado(self, escribano):
        """Con múltiples RUCs, toma el primer no-pagador."""
        texto = """
        RUC: 20505855627
        RUC: 20380795907
        RUC: 20610827171
        RUC: 20440493781
        """
        comp = escribano._extraer_campos_ocr_por_tipo(texto, "FACTURA", "test.pdf", 1)
        assert comp.grupo_a.ruc_emisor.valor == "20610827171"
