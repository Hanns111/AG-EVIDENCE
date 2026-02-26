# -*- coding: utf-8 -*-
"""
Escribano Fiel — Orquestador del Pipeline de Extracción
=========================================================
Tarea #21 del Plan de Desarrollo (Fase 2: Contrato + Router)

Pipeline completo: custodia → OCR → parseo → router → Excel con diagnóstico.

Opera como punto de entrada único para procesar un expediente completo.
Cada paso del pipeline se ejecuta secuencialmente con trazabilidad JSONL
y verificación de integridad en cada transición.

Flujo:
  1. Custodia: registrar PDF en bóveda inmutable (CustodyChain)
  2. Extracción OCR: renderizar páginas + ejecutar OCR (core.py)
  3. Parseo: construir ExpedienteJSON desde resultados OCR
  4. Evaluación: ConfidenceRouter + IntegrityCheckpoint
  5. Diagnóstico Excel: hoja DIAGNOSTICO con semáforo

Principios:
  - Cada paso produce un resultado verificable antes de avanzar
  - Si IntegrityCheckpoint marca CRITICAL → pipeline se detiene (señal)
  - El orquestador NO toma decisiones probatorias; delega a módulos
  - Trazabilidad completa via TraceLogger (trace_id por expediente)
  - Anti-alucinación: nunca inventa datos, solo transporta lo extraído

Gobernanza:
  - Art. 2: Flujo secuencial custodia→OCR→router (no altera AG01→AG09)
  - Art. 3: Anti-alucinación (delega a AbstencionPolicy)
  - Art. 4-5: Estándar probatorio (delega a EvidenceEnforcer)
  - Art. 17: Trazabilidad (TraceLogger integrado)
  - ADR-005: Orquestador liviano, módulos independientes

Uso:
    from src.extraction.escribano_fiel import EscribanoFiel

    escribano = EscribanoFiel()
    resultado = escribano.procesar_expediente(
        pdf_path="data/expedientes/ODI2026-INT-0139051.pdf",
        sinad="ODI2026-INT-0139051",
    )

    if resultado.exito:
        print(f"Excel: {resultado.ruta_excel}")
    else:
        print(f"Detenido: {resultado.razon_detencion}")

Versión: 1.0.0
Fecha: 2026-02-25
"""

import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Asegurar que el directorio raíz del proyecto esté en el path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.settings import (
    OUTPUT_DIR,
    NaturalezaExpediente,
    Observacion,
)
from src.extraction.abstencion import (
    AbstencionPolicy,
    UmbralesAbstencion,
)
from src.extraction.confidence_router import (
    DecisionCheckpoint,
    IntegrityCheckpoint,
    ResultadoRouter,
    UmbralesRouter,
)
from src.extraction.expediente_contract import (
    ArchivoFuente,
    DatosAnexo3,
    ExpedienteJSON,
    IntegridadExpediente,
    ResumenExtraccion,
)
from src.ingestion.custody_chain import CustodyChain, CustodyRecord
from src.ingestion.trace_logger import TraceLogger

# ==============================================================================
# CONSTANTES
# ==============================================================================

VERSION_ESCRIBANO = "1.0.0"
"""Versión del módulo escribano_fiel."""

AGENTE_ID = "ESCRIBANO"
"""ID de agente para logging."""


# ==============================================================================
# DATACLASSES — Resultado del Pipeline
# ==============================================================================


@dataclass
class ResultadoPaso:
    """Resultado de un paso individual del pipeline."""

    paso: str
    exito: bool
    duracion_ms: float = 0.0
    mensaje: str = ""
    datos: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "paso": self.paso,
            "exito": self.exito,
            "duracion_ms": round(self.duracion_ms, 1),
            "mensaje": self.mensaje,
            "error": self.error,
        }


@dataclass
class ResultadoPipeline:
    """Resultado completo del pipeline de extracción."""

    sinad: str
    exito: bool = False
    pasos: List[ResultadoPaso] = field(default_factory=list)
    duracion_total_ms: float = 0.0

    # Productos del pipeline
    custody_record: Optional[CustodyRecord] = None
    expediente: Optional[ExpedienteJSON] = None
    resultado_router: Optional[ResultadoRouter] = None
    decision: Optional[DecisionCheckpoint] = None
    ruta_excel: Optional[str] = None

    # Si el pipeline se detuvo
    detenido: bool = False
    razon_detencion: str = ""

    # Observaciones acumuladas
    observaciones: List[Observacion] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sinad": self.sinad,
            "exito": self.exito,
            "detenido": self.detenido,
            "razon_detencion": self.razon_detencion,
            "duracion_total_ms": round(self.duracion_total_ms, 1),
            "ruta_excel": self.ruta_excel,
            "pasos": [p.to_dict() for p in self.pasos],
            "decision": self.decision.to_dict() if self.decision else None,
        }


# ==============================================================================
# CONFIGURACIÓN DEL PIPELINE
# ==============================================================================


@dataclass
class ConfigPipeline:
    """Configuración del pipeline de extracción."""

    # Directorios
    vault_dir: Optional[str] = None
    registry_dir: Optional[str] = None
    output_dir: Optional[str] = None
    log_dir: Optional[str] = None

    # Comportamiento
    generar_excel: bool = True
    detener_en_critical: bool = True
    nombre_hoja_diagnostico: str = "DIAGNOSTICO"

    # Umbrales (None = usar defaults)
    umbrales_router: Optional[UmbralesRouter] = None
    umbrales_abstencion: Optional[UmbralesAbstencion] = None

    # OCR
    idioma_ocr: str = "spa"
    dpi_render: int = 200

    # Operador
    operador: str = "pipeline"
    source: str = "escribano_fiel"


# ==============================================================================
# CLASE PRINCIPAL — EscribanoFiel
# ==============================================================================


class EscribanoFiel:
    """
    Orquestador del pipeline de extracción de expedientes.

    Encadena: custodia → OCR → parseo → router → Excel
    con trazabilidad completa y verificación de integridad.
    """

    def __init__(
        self,
        config: Optional[ConfigPipeline] = None,
        custody_chain: Optional[CustodyChain] = None,
        trace_logger: Optional[TraceLogger] = None,
        checkpoint: Optional[IntegrityCheckpoint] = None,
        abstencion_policy: Optional[AbstencionPolicy] = None,
    ):
        """
        Inicializa el orquestador con dependencias inyectables.

        Parameters
        ----------
        config : ConfigPipeline, optional
            Configuración del pipeline. Si None, usa defaults.
        custody_chain : CustodyChain, optional
            Cadena de custodia. Si None, se crea con config.
        trace_logger : TraceLogger, optional
            Logger de trazabilidad. Si None, se crea con config.
        checkpoint : IntegrityCheckpoint, optional
            Checkpoint de integridad (wrapper de ConfidenceRouter).
            Si None, se crea con config.
        abstencion_policy : AbstencionPolicy, optional
            Política de abstención. Si None, se crea con config.
        """
        self._config = config or ConfigPipeline()

        # Inyección de dependencias: usar lo proporcionado o crear nuevo
        self._custody = custody_chain or CustodyChain(
            vault_dir=self._config.vault_dir,
            registry_dir=self._config.registry_dir,
        )

        self._logger = trace_logger or TraceLogger(
            log_dir=self._config.log_dir,
        )

        self._checkpoint = checkpoint or IntegrityCheckpoint(
            umbrales=self._config.umbrales_router,
            umbrales_abstencion=self._config.umbrales_abstencion,
            trace_logger=self._logger,
        )

        self._abstencion = abstencion_policy or AbstencionPolicy(
            umbrales=self._config.umbrales_abstencion,
            agente_id=AGENTE_ID,
            trace_logger=self._logger,
        )

    @property
    def version(self) -> str:
        """Versión del escribano."""
        return VERSION_ESCRIBANO

    @property
    def config(self) -> ConfigPipeline:
        """Configuración actual del pipeline."""
        return self._config

    # ==========================================================================
    # PIPELINE PRINCIPAL
    # ==========================================================================

    def procesar_expediente(
        self,
        pdf_path: str,
        sinad: str,
        naturaleza: NaturalezaExpediente = NaturalezaExpediente.NO_DETERMINADO,
        observaciones_previas: Optional[List[Observacion]] = None,
        expediente_preconstruido: Optional[ExpedienteJSON] = None,
        ruta_excel: Optional[str] = None,
    ) -> ResultadoPipeline:
        """
        Ejecuta el pipeline completo de extracción para un expediente.

        Parameters
        ----------
        pdf_path : str
            Ruta al PDF del expediente.
        sinad : str
            Identificador SINAD del expediente.
        naturaleza : NaturalezaExpediente
            Tipo de expediente (viáticos, caja chica, etc.).
        observaciones_previas : list, optional
            Observaciones pre-existentes para incluir en evaluación.
        expediente_preconstruido : ExpedienteJSON, optional
            Si se proporciona, salta los pasos de custodia+OCR+parseo
            y va directo a evaluación con router. Útil para re-evaluar
            expedientes ya extraídos.
        ruta_excel : str, optional
            Ruta de salida para el Excel. Si None, se genera automáticamente
            en el directorio de output.

        Returns
        -------
        ResultadoPipeline
            Resultado completo con productos de cada paso.
        """
        inicio = time.perf_counter()
        resultado = ResultadoPipeline(sinad=sinad)
        observaciones = list(observaciones_previas or [])

        # Abrir traza
        ctx = self._logger.start_trace(
            sinad=sinad,
            source=self._config.source,
            agent_id=AGENTE_ID,
            operation="procesar_expediente",
            metadata={
                "version": VERSION_ESCRIBANO,
                "naturaleza": naturaleza.value,
                "tiene_expediente_preconstruido": expediente_preconstruido is not None,
            },
        )

        try:
            if expediente_preconstruido is not None:
                # Modo re-evaluación: saltar custodia+OCR+parseo
                self._logger.info(
                    "Modo re-evaluación: usando expediente preconstruido",
                    agent_id=AGENTE_ID,
                    operation="procesar_expediente",
                )
                expediente = expediente_preconstruido
                resultado.pasos.append(
                    ResultadoPaso(
                        paso="custodia",
                        exito=True,
                        mensaje="Omitido: expediente preconstruido",
                    )
                )
                resultado.pasos.append(
                    ResultadoPaso(
                        paso="extraccion_ocr",
                        exito=True,
                        mensaje="Omitido: expediente preconstruido",
                    )
                )
                resultado.pasos.append(
                    ResultadoPaso(
                        paso="parseo",
                        exito=True,
                        mensaje="Omitido: expediente preconstruido",
                    )
                )
            else:
                # --- PASO 1: Custodia ---
                paso_custodia = self._paso_custodia(pdf_path, sinad)
                resultado.pasos.append(paso_custodia)
                if not paso_custodia.exito:
                    resultado.razon_detencion = f"Custodia falló: {paso_custodia.error}"
                    resultado.detenido = True
                    self._finalizar(resultado, inicio, "error_custodia")
                    return resultado
                resultado.custody_record = paso_custodia.datos.get("custody_record")

                # --- PASO 2: Extracción OCR ---
                paso_ocr = self._paso_extraccion_ocr(pdf_path, sinad)
                resultado.pasos.append(paso_ocr)
                if not paso_ocr.exito:
                    resultado.razon_detencion = f"OCR falló: {paso_ocr.error}"
                    resultado.detenido = True
                    self._finalizar(resultado, inicio, "error_ocr")
                    return resultado

                # --- PASO 3: Parseo a ExpedienteJSON ---
                paso_parseo = self._paso_parseo(
                    sinad=sinad,
                    paginas_ocr=paso_ocr.datos.get("paginas", []),
                    pdf_path=pdf_path,
                    naturaleza=naturaleza,
                )
                resultado.pasos.append(paso_parseo)
                if not paso_parseo.exito:
                    resultado.razon_detencion = f"Parseo falló: {paso_parseo.error}"
                    resultado.detenido = True
                    self._finalizar(resultado, inicio, "error_parseo")
                    return resultado
                expediente = paso_parseo.datos.get("expediente")

            # --- PASO 4: Evaluación con IntegrityCheckpoint ---
            paso_router = self._paso_evaluacion(expediente, observaciones)
            resultado.pasos.append(paso_router)
            resultado.expediente = expediente
            resultado.resultado_router = paso_router.datos.get("resultado_router")
            resultado.decision = paso_router.datos.get("decision")
            resultado.observaciones = observaciones

            # Verificar señal CRITICAL (viene de ResultadoRouter)
            debe_detener = resultado.resultado_router and resultado.resultado_router.debe_detener
            if self._config.detener_en_critical and debe_detener:
                resultado.detenido = True
                resultado.razon_detencion = (
                    resultado.resultado_router.razon_detencion
                    if resultado.resultado_router
                    else "IntegrityCheckpoint: señal CRITICAL"
                )
                self._logger.warning(
                    f"Pipeline detenido por señal CRITICAL: {resultado.razon_detencion}",
                    agent_id=AGENTE_ID,
                    operation="evaluacion",
                )
                # Aún así generar Excel si está configurado
                # (el Excel documenta POR QUÉ se detuvo)

            # --- PASO 5: Generar Excel ---
            if self._config.generar_excel and resultado.decision:
                paso_excel = self._paso_excel(
                    sinad=sinad,
                    decision=resultado.decision,
                    ruta_excel=ruta_excel,
                )
                resultado.pasos.append(paso_excel)
                if paso_excel.exito:
                    resultado.ruta_excel = paso_excel.datos.get("ruta_excel")

            # Pipeline exitoso (aunque detenido = el Excel se generó)
            resultado.exito = not resultado.detenido or (resultado.ruta_excel is not None)
            self._finalizar(resultado, inicio, "success")

        except Exception as e:
            resultado.exito = False
            resultado.razon_detencion = f"Error inesperado: {e}"
            self._logger.error(
                f"Error inesperado en pipeline: {e}",
                agent_id=AGENTE_ID,
                operation="procesar_expediente",
                error=str(e),
            )
            self._finalizar(resultado, inicio, "error")

        return resultado

    # ==========================================================================
    # PASOS INDIVIDUALES DEL PIPELINE
    # ==========================================================================

    def _paso_custodia(self, pdf_path: str, sinad: str) -> ResultadoPaso:
        """Paso 1: Registrar PDF en bóveda de custodia."""
        inicio = time.perf_counter()
        self._logger.info(
            f"Paso 1/5: Custodia — registrando {Path(pdf_path).name}",
            agent_id=AGENTE_ID,
            operation="custodia",
        )

        try:
            path = Path(pdf_path)
            if not path.exists():
                return ResultadoPaso(
                    paso="custodia",
                    exito=False,
                    duracion_ms=_elapsed_ms(inicio),
                    error=f"Archivo no encontrado: {pdf_path}",
                )

            if not path.suffix.lower() == ".pdf":
                return ResultadoPaso(
                    paso="custodia",
                    exito=False,
                    duracion_ms=_elapsed_ms(inicio),
                    error=f"No es un PDF: {path.suffix}",
                )

            record = self._custody.ingest(
                path_pdf=str(path),
                sinad=sinad,
                source=self._config.source,
                operator=self._config.operador,
            )

            self._logger.info(
                f"Custodia OK: {record.custody_id} (SHA256: {record.hash_sha256[:16]}...)",
                agent_id=AGENTE_ID,
                operation="custodia",
                context={"custody_id": record.custody_id},
            )

            return ResultadoPaso(
                paso="custodia",
                exito=True,
                duracion_ms=_elapsed_ms(inicio),
                mensaje=f"Registrado: {record.custody_id}",
                datos={"custody_record": record},
            )

        except Exception as e:
            self._logger.error(
                f"Error en custodia: {e}",
                agent_id=AGENTE_ID,
                operation="custodia",
                error=str(e),
            )
            return ResultadoPaso(
                paso="custodia",
                exito=False,
                duracion_ms=_elapsed_ms(inicio),
                error=str(e),
            )

    def _paso_extraccion_ocr(self, pdf_path: str, sinad: str) -> ResultadoPaso:
        """
        Paso 2: Extraer texto de cada página vía OCR.

        Intenta importar el motor OCR. Si no está disponible (entorno
        sin PaddleOCR/Tesseract), retorna resultado vacío con advertencia.
        La extracción real requiere WSL2 + GPU — este paso documenta
        la interfaz del pipeline sin acoplar al motor OCR.
        """
        inicio = time.perf_counter()
        self._logger.info(
            f"Paso 2/5: Extracción OCR — {Path(pdf_path).name}",
            agent_id=AGENTE_ID,
            operation="extraccion_ocr",
        )

        try:
            from src.ocr.core import ejecutar_ocr, renderizar_pagina

            path = Path(pdf_path)
            paginas_resultado: List[Dict[str, Any]] = []

            # Determinar número de páginas
            try:
                import fitz  # PyMuPDF

                doc = fitz.open(str(path))
                num_paginas = len(doc)
                doc.close()
            except ImportError:
                # Sin PyMuPDF, no podemos renderizar
                return ResultadoPaso(
                    paso="extraccion_ocr",
                    exito=True,
                    duracion_ms=_elapsed_ms(inicio),
                    mensaje="PyMuPDF no disponible; OCR requiere WSL2",
                    datos={"paginas": [], "motor": "no_disponible"},
                )

            self._logger.info(
                f"PDF tiene {num_paginas} páginas",
                agent_id=AGENTE_ID,
                operation="extraccion_ocr",
                context={"num_paginas": num_paginas},
            )

            for i in range(num_paginas):
                page_num = i + 1
                img = renderizar_pagina(path, page_num, dpi=self._config.dpi_render)
                if img is None:
                    paginas_resultado.append(
                        {
                            "pagina": page_num,
                            "texto": "",
                            "confianza": 0.0,
                            "error": "No se pudo renderizar",
                        }
                    )
                    continue

                resultado_ocr = ejecutar_ocr(
                    img,
                    lang=self._config.idioma_ocr,
                    trace_logger=self._logger,
                )
                paginas_resultado.append(
                    {
                        "pagina": page_num,
                        "texto": resultado_ocr.get("texto_completo", ""),
                        "confianza": resultado_ocr.get("confianza_promedio", 0.0),
                        "motor": resultado_ocr.get("motor_ocr", "none"),
                        "lineas": resultado_ocr.get("lineas", []),
                        "num_palabras": resultado_ocr.get("num_palabras", 0),
                    }
                )

            total_palabras = sum(p.get("num_palabras", 0) for p in paginas_resultado)
            self._logger.info(
                f"OCR completado: {num_paginas} páginas, {total_palabras} palabras",
                agent_id=AGENTE_ID,
                operation="extraccion_ocr",
            )

            return ResultadoPaso(
                paso="extraccion_ocr",
                exito=True,
                duracion_ms=_elapsed_ms(inicio),
                mensaje=f"{num_paginas} páginas, {total_palabras} palabras",
                datos={
                    "paginas": paginas_resultado,
                    "num_paginas": num_paginas,
                    "total_palabras": total_palabras,
                },
            )

        except ImportError:
            # Motor OCR no disponible en este entorno
            self._logger.warning(
                "Motor OCR no disponible (requiere WSL2+GPU)",
                agent_id=AGENTE_ID,
                operation="extraccion_ocr",
            )
            return ResultadoPaso(
                paso="extraccion_ocr",
                exito=True,
                duracion_ms=_elapsed_ms(inicio),
                mensaje="Motor OCR no disponible; pipeline continúa sin OCR",
                datos={"paginas": [], "motor": "no_disponible"},
            )

        except Exception as e:
            self._logger.error(
                f"Error en OCR: {e}",
                agent_id=AGENTE_ID,
                operation="extraccion_ocr",
                error=str(e),
            )
            return ResultadoPaso(
                paso="extraccion_ocr",
                exito=False,
                duracion_ms=_elapsed_ms(inicio),
                error=str(e),
            )

    def _paso_parseo(
        self,
        sinad: str,
        paginas_ocr: List[Dict[str, Any]],
        pdf_path: str,
        naturaleza: NaturalezaExpediente,
    ) -> ResultadoPaso:
        """
        Paso 3: Construir ExpedienteJSON desde resultados OCR.

        Crea la estructura mínima del contrato tipado. El parseo profundo
        (regex por tipo de comprobante, grupos A-K) se implementa en
        fases posteriores. Aquí se construye el esqueleto con los datos
        disponibles.
        """
        inicio = time.perf_counter()
        self._logger.info(
            "Paso 3/5: Parseo a ExpedienteJSON",
            agent_id=AGENTE_ID,
            operation="parseo",
        )

        try:
            # Construir archivos fuente
            archivo_fuente = ArchivoFuente(
                nombre=Path(pdf_path).name,
                ruta_relativa=pdf_path,
                hash_sha256="",  # Se llena si hay custody_record
                total_paginas=len(paginas_ocr),
            )

            # Construir resumen de extracción
            total_palabras = sum(p.get("num_palabras", 0) for p in paginas_ocr)
            paginas_con_texto = sum(1 for p in paginas_ocr if p.get("texto", ""))

            resumen = ResumenExtraccion(
                total_campos=0,  # Se llena post-parseo profundo
                comprobantes_procesados=0,
            )

            # Construir integridad
            integridad = IntegridadExpediente()

            # Construir ExpedienteJSON mínimo
            expediente = ExpedienteJSON(
                sinad=sinad,
                naturaleza=naturaleza.value,
                archivos_fuente=[archivo_fuente],
                anexo3=DatosAnexo3(),
                comprobantes=[],
                declaracion_jurada=[],
                boletos=[],
                resumen_extraccion=resumen,
                integridad=integridad,
            )

            self._logger.info(
                f"Parseo OK: ExpedienteJSON({sinad}), "
                f"{len(paginas_ocr)} páginas, "
                f"{paginas_con_texto} con texto, "
                f"{total_palabras} palabras",
                agent_id=AGENTE_ID,
                operation="parseo",
            )

            return ResultadoPaso(
                paso="parseo",
                exito=True,
                duracion_ms=_elapsed_ms(inicio),
                mensaje=f"ExpedienteJSON creado: {sinad}",
                datos={"expediente": expediente},
            )

        except Exception as e:
            self._logger.error(
                f"Error en parseo: {e}",
                agent_id=AGENTE_ID,
                operation="parseo",
                error=str(e),
            )
            return ResultadoPaso(
                paso="parseo",
                exito=False,
                duracion_ms=_elapsed_ms(inicio),
                error=str(e),
            )

    def _paso_evaluacion(
        self,
        expediente: ExpedienteJSON,
        observaciones: List[Observacion],
    ) -> ResultadoPaso:
        """
        Paso 4: Evaluar expediente con IntegrityCheckpoint.

        Ejecuta IntegrityCheckpoint.evaluar() que internamente:
        - Ejecuta ConfidenceRouter.evaluar_expediente()
        - Genera ReporteEnforcement detallado
        - Genera DiagnosticoExpediente para Excel
        - Determina acción: CONTINUAR / CONTINUAR_CON_ALERTAS / DETENER
        """
        inicio = time.perf_counter()
        self._logger.info(
            "Paso 4/5: Evaluación con IntegrityCheckpoint",
            agent_id=AGENTE_ID,
            operation="evaluacion",
        )

        try:
            # IntegrityCheckpoint.evaluar() devuelve DecisionCheckpoint
            decision = self._checkpoint.evaluar(
                expediente=expediente,
                observaciones=observaciones if observaciones else None,
            )

            resultado_router = decision.resultado

            status_val = resultado_router.status.value if resultado_router else "N/A"
            campos_eval = resultado_router.campos_evaluados if resultado_router else 0
            tasa_abs = resultado_router.tasa_abstencion if resultado_router else 0.0

            self._logger.info(
                f"Evaluación OK: status={status_val}, "
                f"acción={decision.accion}, "
                f"debe_detener="
                f"{resultado_router.debe_detener if resultado_router else False}",
                agent_id=AGENTE_ID,
                operation="evaluacion",
                context={
                    "status": status_val,
                    "accion": decision.accion,
                    "campos_evaluados": campos_eval,
                    "tasa_abstencion": round(tasa_abs, 3),
                },
            )

            return ResultadoPaso(
                paso="evaluacion",
                exito=True,
                duracion_ms=_elapsed_ms(inicio),
                mensaje=(f"Status: {status_val}, Acción: {decision.accion}"),
                datos={
                    "resultado_router": resultado_router,
                    "decision": decision,
                },
            )

        except Exception as e:
            self._logger.error(
                f"Error en evaluación: {e}",
                agent_id=AGENTE_ID,
                operation="evaluacion",
                error=str(e),
            )
            return ResultadoPaso(
                paso="evaluacion",
                exito=False,
                duracion_ms=_elapsed_ms(inicio),
                error=str(e),
            )

    def _paso_excel(
        self,
        sinad: str,
        decision: DecisionCheckpoint,
        ruta_excel: Optional[str] = None,
    ) -> ResultadoPaso:
        """
        Paso 5: Generar Excel con hoja DIAGNOSTICO.

        Crea un workbook nuevo con la hoja DIAGNOSTICO usando
        EscritorDiagnostico. La ruta de salida se genera automáticamente
        si no se proporciona.
        """
        inicio = time.perf_counter()
        self._logger.info(
            "Paso 5/5: Generar Excel con DIAGNOSTICO",
            agent_id=AGENTE_ID,
            operation="excel",
        )

        try:
            from src.extraction.excel_writer import (
                OPENPYXL_DISPONIBLE,
                escribir_diagnostico,
            )

            if not OPENPYXL_DISPONIBLE:
                return ResultadoPaso(
                    paso="excel",
                    exito=False,
                    duracion_ms=_elapsed_ms(inicio),
                    error="openpyxl no disponible",
                )

            from openpyxl import Workbook

            # Determinar ruta de salida
            if ruta_excel is None:
                output_dir = self._config.output_dir or OUTPUT_DIR
                os.makedirs(output_dir, exist_ok=True)
                ruta_excel = os.path.join(output_dir, f"RENDICION_{sinad}.xlsx")

            # Crear workbook y escribir diagnóstico
            wb = Workbook()
            escribir_diagnostico(
                wb=wb,
                decision=decision,
                nombre_hoja=self._config.nombre_hoja_diagnostico,
            )
            wb.save(ruta_excel)

            self._logger.info(
                f"Excel generado: {ruta_excel}",
                agent_id=AGENTE_ID,
                operation="excel",
                context={"ruta": ruta_excel},
            )

            return ResultadoPaso(
                paso="excel",
                exito=True,
                duracion_ms=_elapsed_ms(inicio),
                mensaje=f"Excel: {ruta_excel}",
                datos={"ruta_excel": ruta_excel},
            )

        except Exception as e:
            self._logger.error(
                f"Error generando Excel: {e}",
                agent_id=AGENTE_ID,
                operation="excel",
                error=str(e),
            )
            return ResultadoPaso(
                paso="excel",
                exito=False,
                duracion_ms=_elapsed_ms(inicio),
                error=str(e),
            )

    # ==========================================================================
    # MÉTODOS DE CONVENIENCIA
    # ==========================================================================

    def evaluar_expediente(
        self,
        expediente: ExpedienteJSON,
        observaciones: Optional[List[Observacion]] = None,
    ) -> ResultadoPipeline:
        """
        Atajo: evalúa un ExpedienteJSON ya construido (sin custodia/OCR).

        Equivale a procesar_expediente() con expediente_preconstruido.
        """
        return self.procesar_expediente(
            pdf_path="",
            sinad=expediente.sinad,
            expediente_preconstruido=expediente,
            observaciones_previas=observaciones,
        )

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del orquestador."""
        return {
            "version": VERSION_ESCRIBANO,
            "config": {
                "generar_excel": self._config.generar_excel,
                "detener_en_critical": self._config.detener_en_critical,
                "dpi_render": self._config.dpi_render,
            },
        }

    # ==========================================================================
    # INTERNOS
    # ==========================================================================

    def _finalizar(
        self,
        resultado: ResultadoPipeline,
        inicio: float,
        status: str,
    ) -> None:
        """Finaliza el pipeline: calcula duración y cierra traza."""
        resultado.duracion_total_ms = _elapsed_ms(inicio)
        self._logger.end_trace(
            status=status,
            message=f"Pipeline {'exitoso' if resultado.exito else 'fallido'}: {resultado.sinad}",
            context={
                "duracion_ms": resultado.duracion_total_ms,
                "pasos_completados": len(resultado.pasos),
                "detenido": resultado.detenido,
            },
        )


# ==============================================================================
# FUNCIONES DE CONVENIENCIA
# ==============================================================================


def procesar_expediente(
    pdf_path: str,
    sinad: str,
    naturaleza: NaturalezaExpediente = NaturalezaExpediente.NO_DETERMINADO,
    config: Optional[ConfigPipeline] = None,
    **kwargs: Any,
) -> ResultadoPipeline:
    """
    Función de conveniencia: procesa un expediente completo.

    Crea un EscribanoFiel con la configuración dada y ejecuta el pipeline.

    Parameters
    ----------
    pdf_path : str
        Ruta al PDF del expediente.
    sinad : str
        Identificador SINAD.
    naturaleza : NaturalezaExpediente
        Tipo de expediente.
    config : ConfigPipeline, optional
        Configuración del pipeline.

    Returns
    -------
    ResultadoPipeline
    """
    escribano = EscribanoFiel(config=config)
    return escribano.procesar_expediente(
        pdf_path=pdf_path,
        sinad=sinad,
        naturaleza=naturaleza,
        **kwargs,
    )


# ==============================================================================
# UTILIDADES
# ==============================================================================


def _elapsed_ms(start: float) -> float:
    """Calcula milisegundos transcurridos desde start."""
    return (time.perf_counter() - start) * 1000.0
