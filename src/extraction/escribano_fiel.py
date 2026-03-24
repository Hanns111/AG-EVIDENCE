# -*- coding: utf-8 -*-
"""
Escribano Fiel — Orquestador del Pipeline de Extracción
=========================================================
Tarea #21 del Plan de Desarrollo (Fase 2: Contrato + Router)

Pipeline completo: custodia → OCR → parseo → OCR-first + parseo profundo VLM → router → Excel.

Opera como punto de entrada único para procesar un expediente completo.
Cada paso del pipeline se ejecuta secuencialmente con trazabilidad JSONL
y verificación de integridad en cada transición.

Flujo:
  1. Custodia: registrar PDF en bóveda inmutable (CustodyChain)
  2. Extracción OCR: renderizar páginas + ejecutar OCR (core.py)
  3. Parseo: construir ExpedienteJSON esqueleto desde resultados OCR
  4. Parseo profundo: VLM extrae comprobantes (Grupos A-K) de páginas imagen
  5. Evaluación: ConfidenceRouter + IntegrityCheckpoint
  6. Validación: aritméticas + reglas viáticos (Fase 4)
  7. Excel: hojas DIAGNOSTICO + HALLAZGOS

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

import base64
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Asegurar que el directorio raíz del proyecto esté en el path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.settings import (
    OUTPUT_DIR,
    MetodoExtraccion,
    NaturalezaExpediente,
    Observacion,
)
from src.extraction.abstencion import (
    AbstencionPolicy,
    CampoExtraido,
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
    ComprobanteExtraido,
    DatosAnexo3,
    DatosComprobante,
    DatosEmisor,
    ExpedienteJSON,
    IntegridadExpediente,
    MetadatosExtraccion,
    ResumenExtraccion,
    TotalesTributos,
)
from src.ingestion.custody_chain import CustodyChain, CustodyRecord
from src.ingestion.trace_logger import TraceLogger

# ==============================================================================
# CONSTANTES
# ==============================================================================

VERSION_ESCRIBANO = "4.1.0"
"""Versión del módulo escribano_fiel (4.1: overlap + keep_alive + JSON estricto)."""

AGENTE_ID = "ESCRIBANO"
"""ID de agente para logging."""

# Patrones para identificar páginas que contienen comprobantes de pago
KEYWORDS_COMPROBANTE = [
    r"factura\s*(electr[oó]nica)?",
    r"boleta\s+de\s+venta",
    r"recibo\s+por\s+honorarios",
    r"nota\s+de\s+cr[eé]dito",
    r"nota\s+de\s+d[eé]bito",
    r"comprobante\s+de\s+pago",
    r"liquidaci[oó]n\s+de\s+compra",
    r"R\.?U\.?C\.?\s*[:.]?\s*\d{11}",
    r"\bIGV\b",
    r"\bSUBTOTAL\b",
    r"IMPORTE\s+TOTAL",
    r"OP\.?\s*GRAVADA",
    r"SERIE\s*[-:]?\s*[A-Z]\d{3}",
    r"TOTAL\s+VENTA",
]

# Patrones para clasificar tipo de comprobante (ADR-011: gating mejorado)
PATRONES_TIPO_COMPROBANTE = {
    "FACTURA": [
        r"factura\s*(electr[oó]nica)?",
        r"SERIE\s*[-:]?\s*F\d{3}",
        r"FW?\d{2,3}\s*-\s*\d+",
    ],
    "BOLETA": [
        r"boleta\s+de\s+venta",
        r"SERIE\s*[-:]?\s*B\d{3}",
        r"B\d{3}\s*-\s*\d+",
    ],
    "BOARDING_PASS": [
        r"boarding\s*pass",
        r"tarjeta\s+de\s+embarque",
        r"pasajero",
        r"vuelo\s*n",
        r"flight",
        r"gate\s*\d",
        r"seat\s*\d",
    ],
    "DECLARACION_JURADA": [
        r"declaraci[oó]n\s+jurada",
        r"bajo\s+juramento",
        r"DJ\s*[-:.]",
    ],
    "RECIBO_HONORARIOS": [
        r"recibo\s+por\s+honorarios",
        r"SERIE\s*[-:]?\s*E\d{3}",
    ],
}

# Resolución máxima para VLM (ADR-011: downscale adaptativo)
MAX_VLM_IMAGE_PX = 1200
"""Lado mayor máximo de imagen antes de enviar al VLM (px)."""

# ==============================================================================
# ADR-011 NIVEL 3 — ROI crop: Recorte inteligente antes del VLM
# ==============================================================================

MIN_BBOXES_FOR_CROP = 3
"""Mínimo de líneas OCR con bbox para intentar crop."""

MIN_BBOX_CONFIDENCE = 0.3
"""Confianza mínima de una línea OCR para incluirla en el cálculo de ROI."""

CROP_MARGIN_PERCENT = 0.05
"""Margen de seguridad alrededor del ROI (5% de cada lado)."""

# ==============================================================================
# ADR-011 NIVEL 2 — OCR-first: Regex por tipo de comprobante
# ==============================================================================

# Campos núcleo para score de suficiencia (RUC + fecha + total)
# score = campos_encontrados / campos_esperados
# >=0.75 → sin VLM | 0.50-0.74 → con observación | <0.50 → escalar a VLM
SCORE_UMBRAL_SIN_VLM = 0.60
SCORE_UMBRAL_CON_OBS = 0.40

# Regex robustos para extracción OCR-first por campo
# Cada regex captura el valor en group(1) o group(0)
# Ampliados para cubrir variantes OCR impreciso (espacios, puntos, mayúsculas)
REGEX_RUC = re.compile(
    r"R[\s.]?U[\s.]?C[\s.]?\s*[:.]?\s*(\d{11})"
    r"|N[°o]\s*(?:de\s+)?RUC\s*[:.]?\s*(\d{11})",
    re.IGNORECASE,
)
REGEX_FECHA_EMISION = re.compile(
    r"(?:FECHA\s*(?:DE\s*)?EMISI[OÓ]N|F\.?\s*EMISI[OÓ]N|FECHA\s*DE\s*EMISION"
    r"|FEC\.?\s*EMIS\.?|FECHA)\s*[:.]?\s*"
    r"(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
    re.IGNORECASE,
)
REGEX_FECHA_GENERAL = re.compile(r"(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})")
REGEX_SERIE_NUMERO = re.compile(
    r"([FBEP]\w{0,2}\d{2,4})\s*[-–—]\s*(\d{3,10})"
    r"|(?:SERIE|NRO\.?|N[°o]\.?)\s*[:.]?\s*([FBEP]\w{0,2}\d{2,4})\s*[-–—]\s*(\d{3,10})",
    re.IGNORECASE,
)
REGEX_TOTAL = re.compile(
    r"(?:IMPORTE\s+TOTAL|TOTAL\s+(?:A\s+)?PAGAR|TOTAL\s+VENTA|TOTAL\s*S/?\.?"
    r"|MONTO\s+TOTAL|PRECIO\s+TOTAL|TOTAL\s*:)"
    r"\s*[:.]?\s*S/?\.?\s*([\d,]+\.\d{2})",
    re.IGNORECASE,
)
REGEX_IGV = re.compile(
    r"(?:I\.?G\.?V\.?|IMPUESTO\s*(?:GENERAL)?)\s*(?:\(\s*\d+\s*%?\s*\))?\s*"
    r"[:.]?\s*S/?\.?\s*([\d,]+\.\d{2})",
    re.IGNORECASE,
)
REGEX_SUBTOTAL = re.compile(
    r"(?:SUB\s*TOTAL|OP\.?\s*GRAVADA|VALOR\s+(?:DE\s+)?VENTA|BASE\s+IMPONIBLE"
    r"|GRAVADA|VALOR\s+VENTA)\s*"
    r"[:.]?\s*S/?\.?\s*([\d,]+\.\d{2})",
    re.IGNORECASE,
)

# RUCs conocidos del Estado peruano (filtrar como "pagador", no "emisor")
RUCS_PAGADOR = {
    "20131370998",  # MINEDU
    "20304634781",  # MEF
    "20380795907",  # PROGRAMA EDUCACION BASICA PARA TODOS
    "20505855627",  # SUNAT
}

# Campos esperados por tipo de comprobante (para score)
CAMPOS_ESPERADOS_POR_TIPO = {
    "FACTURA": ["ruc_emisor", "fecha_emision", "serie_numero", "importe_total", "igv_monto"],
    "BOLETA": ["ruc_emisor", "fecha_emision", "serie_numero", "importe_total"],
    "RECIBO_HONORARIOS": ["ruc_emisor", "fecha_emision", "serie_numero", "importe_total"],
    "BOARDING_PASS": ["fecha_emision"],  # Boarding pass tiene campos distintos
    "DECLARACION_JURADA": ["fecha_emision"],
    "ADMINISTRATIVO": ["fecha_emision"],
}


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

    # VLM (parseo profundo)
    vlm_enabled: bool = True
    vlm_config: Optional[Dict[str, Any]] = None
    dpi_vlm: int = 200
    min_keywords_comprobante: int = 2

    # Validación (Fase 4)
    validacion_enabled: bool = True

    # Operador
    operador: str = "pipeline"
    source: str = "escribano_fiel"


# ==============================================================================
# CLASE PRINCIPAL — EscribanoFiel
# ==============================================================================


class EscribanoFiel:
    """
    Orquestador del pipeline de extracción de expedientes.

    Encadena: custodia → OCR → parseo → parseo profundo VLM → router → Excel
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
                resultado.pasos.append(
                    ResultadoPaso(
                        paso="parseo_profundo",
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

                # --- PASO 4: Parseo profundo con VLM ---
                paso_profundo = self._paso_parseo_profundo(
                    expediente=expediente,
                    paginas_ocr=paso_ocr.datos.get("paginas", []),
                    pdf_path=pdf_path,
                )
                resultado.pasos.append(paso_profundo)
                # Parseo profundo es no-bloqueante: si falla, pipeline continúa
                # con comprobantes=[] (router lo marcará CRITICAL)

            # --- PASO 5: Evaluación con IntegrityCheckpoint ---
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

            # --- PASO 6: Validación (Fase 4) ---
            obs_validacion = []
            if self._config.validacion_enabled and expediente:
                paso_val = self._paso_validacion(
                    expediente=expediente,
                    naturaleza=naturaleza,
                )
                resultado.pasos.append(paso_val)
                obs_validacion = paso_val.datos.get("observaciones", [])
                observaciones.extend(obs_validacion)
                resultado.observaciones = observaciones

            # --- PASO 7: Generar Excel ---
            if self._config.generar_excel and resultado.decision:
                paso_excel = self._paso_excel(
                    sinad=sinad,
                    decision=resultado.decision,
                    expediente=resultado.expediente,
                    ruta_excel=ruta_excel,
                    observaciones_validacion=obs_validacion,
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
            f"Paso 1/6: Custodia — registrando {Path(pdf_path).name}",
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
            f"Paso 2/6: Extracción OCR — {Path(pdf_path).name}",
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
            "Paso 3/6: Parseo a ExpedienteJSON",
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

    def _paso_parseo_profundo(
        self,
        expediente: ExpedienteJSON,
        paginas_ocr: List[Dict[str, Any]],
        pdf_path: str,
    ) -> ResultadoPaso:
        """
        Paso 4: Extracción profunda de comprobantes (estrategia mixta ADR-009).

        Clasifica cada página comprobante como digital o imagen:
          - Digital (PyMuPDF extrae texto): envía texto al LLM (rápido, ~5-15s)
          - Imagen (escaneado): renderiza y envía imagen al VLM (~60-100s)
        """
        inicio = time.perf_counter()

        if not self._config.vlm_enabled:
            return ResultadoPaso(
                paso="parseo_profundo",
                exito=True,
                duracion_ms=_elapsed_ms(inicio),
                mensaje="Parseo profundo deshabilitado en configuración",
            )

        self._logger.info(
            "Paso 4/6: Parseo profundo (estrategia mixta ADR-009)",
            agent_id=AGENTE_ID,
            operation="parseo_profundo",
        )

        try:
            from src.extraction.qwen_fallback import QwenFallbackClient
            from src.extraction.vlm_abstencion import VLMAbstencionHandler

            # Identificar páginas con comprobantes
            paginas_comprobante = self._identificar_paginas_comprobante(
                paginas_ocr,
                min_keywords=self._config.min_keywords_comprobante,
            )

            if not paginas_comprobante:
                return ResultadoPaso(
                    paso="parseo_profundo",
                    exito=True,
                    duracion_ms=_elapsed_ms(inicio),
                    mensaje="0 páginas comprobante detectadas",
                    datos={"paginas_analizadas": 0, "comprobantes_extraidos": 0},
                )

            # Clasificar páginas: digital vs imagen
            digitales, imagenes_pg = self._clasificar_paginas_digital_imagen(
                pdf_path, paginas_comprobante
            )

            self._logger.info(
                f"{len(paginas_comprobante)} páginas comprobante: "
                f"{len(digitales)} digital, {len(imagenes_pg)} imagen",
                agent_id=AGENTE_ID,
                operation="parseo_profundo",
            )

            # Inicializar cliente LLM/VLM
            vlm_client = QwenFallbackClient(
                config=self._config.vlm_config,
                trace_logger=self._logger,
            )
            vlm_handler = VLMAbstencionHandler(trace_logger=self._logger)

            # Healthcheck + pre-carga del modelo (keep_alive)
            if not vlm_client.healthcheck():
                self._logger.warning(
                    "Ollama no disponible; parseo profundo omitido",
                    agent_id=AGENTE_ID,
                    operation="parseo_profundo",
                )
                return ResultadoPaso(
                    paso="parseo_profundo",
                    exito=True,
                    duracion_ms=_elapsed_ms(inicio),
                    mensaje="Ollama no disponible; parseo profundo omitido",
                    datos={"paginas_analizadas": 0, "comprobantes_extraidos": 0},
                )

            # Pre-cargar modelo para evitar cold start en primera página
            vlm_client.precargar_modelo()

            comprobantes = []
            n_digital = 0
            n_imagen = 0
            tiempo_vlm_total = 0.0
            tipos_detectados: Dict[str, int] = {}

            # ADR-011 Nivel 2: OCR-first metrics
            n_resueltas_ocr = 0
            n_escaladas_vlm = 0
            scores_ocr: List[float] = []

            # ADR-011: clasificar tipo de cada página comprobante
            paginas_ocr_dict = {p.get("pagina", 0): p for p in paginas_ocr}
            for pg_num in paginas_comprobante:
                pag_data = paginas_ocr_dict.get(pg_num, {})
                texto_ocr = pag_data.get("texto", "") or ""
                tipo = self._clasificar_tipo_comprobante(texto_ocr)
                tipos_detectados[tipo] = tipos_detectados.get(tipo, 0) + 1

            self._logger.info(
                f"Tipos detectados: {tipos_detectados}",
                agent_id=AGENTE_ID,
                operation="parseo_profundo",
            )

            # --- Ruta 1: Páginas digitales → OCR-first → LLM texto si necesario ---
            digitales_pendientes_vlm = []
            for page_num, texto in digitales:
                tipo = self._clasificar_tipo_comprobante(texto)

                # ADR-011 Nivel 2: intentar OCR-first con regex
                comp_ocr = self._extraer_campos_ocr_por_tipo(
                    texto_ocr=texto,
                    tipo=tipo,
                    archivo=Path(pdf_path).name,
                    pagina=page_num,
                )
                score, encontrados, esperados, faltantes = self._calcular_score_suficiencia(
                    comp_ocr, tipo
                )
                scores_ocr.append(score)

                if score >= SCORE_UMBRAL_SIN_VLM:
                    # OCR-first suficiente — skip VLM
                    comp_ocr.grupo_k.confianza_global = "alta"
                    comprobantes.append(comp_ocr)
                    n_resueltas_ocr += 1
                    n_digital += 1
                    self._logger.info(
                        f"OCR-first pág {page_num} [{tipo}] score={score:.2f} "
                        f"({len(encontrados)}/{len(esperados)}) → SIN VLM",
                        agent_id=AGENTE_ID,
                        operation="parseo_profundo",
                    )
                elif score >= SCORE_UMBRAL_CON_OBS:
                    # OCR-first parcial — resolver con observación
                    comp_ocr.grupo_k.confianza_global = "media"
                    comp_ocr.grupo_k.campos_no_encontrados = faltantes
                    comprobantes.append(comp_ocr)
                    n_resueltas_ocr += 1
                    n_digital += 1
                    self._logger.info(
                        f"OCR-first pág {page_num} [{tipo}] score={score:.2f} "
                        f"({len(encontrados)}/{len(esperados)}) → CON OBSERVACIÓN "
                        f"(faltantes: {faltantes})",
                        agent_id=AGENTE_ID,
                        operation="parseo_profundo",
                    )
                else:
                    # OCR-first insuficiente — acumular para LLM texto paralelo
                    n_escaladas_vlm += 1
                    digitales_pendientes_vlm.append((page_num, texto, tipo, faltantes))

            # Procesar páginas digitales escaladas a LLM en paralelo
            if digitales_pendientes_vlm:
                from concurrent.futures import ThreadPoolExecutor, as_completed

                def _procesar_texto_vlm(item):
                    pg_num, txt, tp, flt = item
                    t_start = time.perf_counter()
                    c = vlm_client.extraer_comprobante_texto(
                        texto_pagina=txt,
                        archivo=Path(pdf_path).name,
                        pagina=pg_num,
                    )
                    t_elapsed = time.perf_counter() - t_start
                    return pg_num, c, t_elapsed, tp, flt

                max_w = min(vlm_client.vlm_workers, len(digitales_pendientes_vlm))
                self._logger.info(
                    f"LLM texto paralelo: {len(digitales_pendientes_vlm)} págs con {max_w} workers",
                    agent_id=AGENTE_ID,
                    operation="parseo_profundo",
                )

                with ThreadPoolExecutor(max_workers=max_w) as executor:
                    futures = {
                        executor.submit(_procesar_texto_vlm, item): item[0]
                        for item in digitales_pendientes_vlm
                    }
                    for future in as_completed(futures):
                        pg_num, comp, t_elapsed, tipo, faltantes = future.result()
                        tiempo_vlm_total += t_elapsed
                        if comp is not None:
                            comprobantes.append(comp)
                            n_digital += 1
                        else:
                            comp_abstencion = vlm_handler.generar_abstencion_vlm(
                                archivo=Path(pdf_path).name,
                                pagina=pg_num,
                                razon="LLM texto falló tras retries",
                            )
                            comprobantes.append(comp_abstencion)
                        self._logger.info(
                            f"LLM texto pág {pg_num} [{tipo}] {t_elapsed:.1f}s "
                            f"(faltantes: {faltantes})",
                            agent_id=AGENTE_ID,
                            operation="parseo_profundo",
                        )

            # --- Ruta 2: Páginas imagen → OCR-first → VLM imagen si necesario ---
            if imagenes_pg:
                # Intentar OCR-first en páginas imagen también (tienen texto OCR)
                imagenes_pendientes_vlm = []
                for page_num in imagenes_pg:
                    pag_data = paginas_ocr_dict.get(page_num, {})
                    texto = pag_data.get("texto", "") or ""
                    tipo = self._clasificar_tipo_comprobante(texto)

                    if texto.strip():
                        comp_ocr = self._extraer_campos_ocr_por_tipo(
                            texto_ocr=texto,
                            tipo=tipo,
                            archivo=Path(pdf_path).name,
                            pagina=page_num,
                        )
                        score, encontrados, esperados, faltantes = self._calcular_score_suficiencia(
                            comp_ocr, tipo
                        )
                        scores_ocr.append(score)

                        if score >= SCORE_UMBRAL_SIN_VLM:
                            comp_ocr.grupo_k.confianza_global = "alta"
                            comprobantes.append(comp_ocr)
                            n_resueltas_ocr += 1
                            n_imagen += 1
                            self._logger.info(
                                f"OCR-first imagen pág {page_num} [{tipo}] score={score:.2f} "
                                f"→ SIN VLM",
                                agent_id=AGENTE_ID,
                                operation="parseo_profundo",
                            )
                            continue
                        elif score >= SCORE_UMBRAL_CON_OBS:
                            comp_ocr.grupo_k.confianza_global = "media"
                            comp_ocr.grupo_k.campos_no_encontrados = faltantes
                            comprobantes.append(comp_ocr)
                            n_resueltas_ocr += 1
                            n_imagen += 1
                            self._logger.info(
                                f"OCR-first imagen pág {page_num} [{tipo}] score={score:.2f} "
                                f"→ CON OBSERVACIÓN",
                                agent_id=AGENTE_ID,
                                operation="parseo_profundo",
                            )
                            continue

                    # Score insuficiente o sin texto → escalar a VLM
                    imagenes_pendientes_vlm.append(page_num)
                    n_escaladas_vlm += 1

                # Solo renderizar y enviar al VLM las páginas que realmente lo necesitan
                if imagenes_pendientes_vlm:
                    imagenes_b64 = self._renderizar_paginas_base64(
                        pdf_path=pdf_path,
                        paginas=imagenes_pendientes_vlm,
                        dpi=self._config.dpi_vlm,
                        paginas_ocr_dict=paginas_ocr_dict,
                    )

                    # Paralelismo controlado: procesar páginas VLM concurrentemente
                    from concurrent.futures import ThreadPoolExecutor, as_completed

                    def _procesar_imagen_vlm(page_img_tuple):
                        pg_num, ib64 = page_img_tuple
                        t_start = time.perf_counter()
                        c = vlm_handler.extraer_o_abstener(
                            client=vlm_client,
                            image_b64=ib64,
                            archivo=Path(pdf_path).name,
                            pagina=pg_num,
                        )
                        t_elapsed = time.perf_counter() - t_start
                        return pg_num, c, t_elapsed

                    max_workers = min(vlm_client.vlm_workers, len(imagenes_b64))
                    self._logger.info(
                        f"VLM paralelo: {len(imagenes_b64)} páginas con {max_workers} workers",
                        agent_id=AGENTE_ID,
                        operation="parseo_profundo",
                    )

                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        futures = {
                            executor.submit(_procesar_imagen_vlm, item): item[0]
                            for item in imagenes_b64
                        }
                        for future in as_completed(futures):
                            pg_num, comp, t_elapsed = future.result()
                            tiempo_vlm_total += t_elapsed
                            comprobantes.append(comp)
                            n_imagen += 1
                            pag_data = paginas_ocr_dict.get(pg_num, {})
                            tipo = self._clasificar_tipo_comprobante(
                                pag_data.get("texto", "") or ""
                            )
                            self._logger.info(
                                f"VLM imagen pág {pg_num} [{tipo}] {t_elapsed:.1f}s",
                                agent_id=AGENTE_ID,
                                operation="parseo_profundo",
                            )

            # Deduplicar por serie_numero
            antes = len(comprobantes)
            comprobantes = vlm_client._deduplicar(comprobantes)
            dedup = antes - len(comprobantes)

            # Actualizar expediente
            expediente.comprobantes = comprobantes
            expediente.resumen_extraccion.comprobantes_procesados = len(comprobantes)

            stats = vlm_handler.get_estadisticas()
            msg = (
                f"{len(comprobantes)} comprobantes de {len(paginas_comprobante)} páginas "
                f"({n_digital} digital, {n_imagen} imagen)"
            )
            if dedup > 0:
                msg += f" ({dedup} dedup)"
            if stats.total_abstenciones > 0:
                msg += f" ({stats.total_abstenciones} abstenciones)"

            self._logger.info(msg, agent_id=AGENTE_ID, operation="parseo_profundo")

            # ADR-011: métricas del dispatcher
            total_paginas = len(paginas_ocr)
            paginas_enviadas_vlm = (n_digital + n_imagen) - n_resueltas_ocr
            tiempo_vlm_promedio = (
                tiempo_vlm_total / paginas_enviadas_vlm if paginas_enviadas_vlm > 0 else 0.0
            )
            score_promedio = sum(scores_ocr) / len(scores_ocr) if scores_ocr else 0.0

            # Agregar métricas OCR-first al mensaje
            if n_resueltas_ocr > 0:
                msg += f" | OCR-first: {n_resueltas_ocr} resueltas sin VLM"

            return ResultadoPaso(
                paso="parseo_profundo",
                exito=True,
                duracion_ms=_elapsed_ms(inicio),
                mensaje=msg,
                datos={
                    "paginas_analizadas": len(paginas_comprobante),
                    "comprobantes_extraidos": len(comprobantes),
                    "paginas_digital": n_digital,
                    "paginas_imagen": n_imagen,
                    "deduplicados": dedup,
                    "vlm_stats": stats.to_dict(),
                    # ADR-011: métricas dispatcher
                    "dispatcher": {
                        "total_paginas_pdf": total_paginas,
                        "paginas_comprobante": len(paginas_comprobante),
                        "paginas_digitales": len(digitales),
                        "paginas_imagen": len(imagenes_pg),
                        "paginas_enviadas_vlm": paginas_enviadas_vlm,
                        "tipos_detectados": tipos_detectados,
                        "tiempo_vlm_total_s": round(tiempo_vlm_total, 1),
                        "tiempo_vlm_promedio_s": round(tiempo_vlm_promedio, 1),
                        "max_image_px": MAX_VLM_IMAGE_PX,
                    },
                    # ADR-011 Nivel 2: métricas OCR-first
                    "ocr_first": {
                        "paginas_resueltas_sin_vlm": n_resueltas_ocr,
                        "paginas_escaladas_vlm": n_escaladas_vlm,
                        "score_promedio_ocr": round(score_promedio, 3),
                        "scores_por_pagina": [round(s, 3) for s in scores_ocr],
                    },
                    # ADR-011 Nivel 3: métricas ROI crop
                    "roi_crop": getattr(self, "_ultimo_crop_stats", {}),
                    # Telemetría VLM detallada
                    "telemetry": vlm_client.get_telemetry(),
                },
            )

        except ImportError as e:
            self._logger.warning(
                f"Módulos VLM no disponibles: {e}",
                agent_id=AGENTE_ID,
                operation="parseo_profundo",
            )
            return ResultadoPaso(
                paso="parseo_profundo",
                exito=True,
                duracion_ms=_elapsed_ms(inicio),
                mensaje=f"Módulos VLM no disponibles: {e}",
            )

        except Exception as e:
            self._logger.error(
                f"Error en parseo profundo: {e}",
                agent_id=AGENTE_ID,
                operation="parseo_profundo",
                error=str(e),
            )
            return ResultadoPaso(
                paso="parseo_profundo",
                exito=False,
                duracion_ms=_elapsed_ms(inicio),
                error=str(e),
            )

    # ==========================================================================
    # ADR-011 NIVEL 2 — OCR-first: Extracción regex antes de VLM
    # ==========================================================================

    def _extraer_campos_ocr_por_tipo(
        self,
        texto_ocr: str,
        tipo: str,
        archivo: str,
        pagina: int,
    ) -> ComprobanteExtraido:
        """
        Extrae campos de un comprobante usando regex sobre texto OCR.

        ADR-011 Nivel 2: intenta resolver campos robustos (RUC, fecha, total,
        serie/numero, IGV) sin VLM. Para cada campo encontrado, crea un
        CampoExtraido con metodo=REGEX y confianza basada en OCR.

        Parameters
        ----------
        texto_ocr : str
            Texto OCR de la página.
        tipo : str
            Tipo de comprobante (FACTURA, BOLETA, etc.).
        archivo : str
            Nombre del archivo fuente.
        pagina : int
            Número de página (1-indexed).

        Returns
        -------
        ComprobanteExtraido
            Comprobante con los campos extraídos por regex.
        """
        comp = ComprobanteExtraido()

        # --- RUC emisor ---
        rucs_raw = REGEX_RUC.findall(texto_ocr)
        # findall returns tuples with alternation; flatten to non-empty matches
        rucs = []
        for match in rucs_raw:
            if isinstance(match, tuple):
                rucs.extend(m for m in match if m)
            elif match:
                rucs.append(match)
        # Filtrar RUCs del pagador/Estado
        rucs_emisor = [r for r in rucs if r not in RUCS_PAGADOR]
        if rucs_emisor:
            ruc_val = rucs_emisor[0]
            # Buscar snippet alrededor del RUC
            idx = texto_ocr.find(ruc_val)
            snippet = texto_ocr[max(0, idx - 30) : idx + 30] if idx >= 0 else ""
            comp.grupo_a.ruc_emisor = CampoExtraido(
                nombre_campo="ruc_emisor",
                valor=ruc_val,
                archivo=archivo,
                pagina=pagina,
                confianza=0.8,
                metodo=MetodoExtraccion.REGEX,
                snippet=snippet.strip(),
                regla_aplicada="OCR_FIRST_RUC",
                tipo_campo="ruc",
            )

        # --- Fecha de emisión ---
        m_fecha = REGEX_FECHA_EMISION.search(texto_ocr)
        if m_fecha:
            fecha_val = m_fecha.group(1)
            comp.grupo_b.fecha_emision = CampoExtraido(
                nombre_campo="fecha_emision",
                valor=fecha_val,
                archivo=archivo,
                pagina=pagina,
                confianza=0.85,
                metodo=MetodoExtraccion.REGEX,
                snippet=m_fecha.group(0)[:100],
                regla_aplicada="OCR_FIRST_FECHA_EMISION",
                tipo_campo="fecha",
            )
        else:
            # Fallback: primera fecha con formato dd/mm/yyyy
            m_fecha_gen = REGEX_FECHA_GENERAL.search(texto_ocr)
            if m_fecha_gen:
                comp.grupo_b.fecha_emision = CampoExtraido(
                    nombre_campo="fecha_emision",
                    valor=m_fecha_gen.group(1),
                    archivo=archivo,
                    pagina=pagina,
                    confianza=0.6,
                    metodo=MetodoExtraccion.REGEX,
                    snippet=texto_ocr[
                        max(0, m_fecha_gen.start() - 20) : m_fecha_gen.end() + 20
                    ].strip(),
                    regla_aplicada="OCR_FIRST_FECHA_GENERAL",
                    tipo_campo="fecha",
                )

        # --- Serie y número ---
        m_serie = REGEX_SERIE_NUMERO.search(texto_ocr)
        if m_serie:
            # Alternation: groups 1,2 or 3,4
            serie_val = (m_serie.group(1) or m_serie.group(3) or "").upper()
            numero_val = m_serie.group(2) or m_serie.group(4) or ""
            comp.grupo_b.serie = CampoExtraido(
                nombre_campo="serie",
                valor=serie_val,
                archivo=archivo,
                pagina=pagina,
                confianza=0.85,
                metodo=MetodoExtraccion.REGEX,
                snippet=m_serie.group(0),
                regla_aplicada="OCR_FIRST_SERIE",
                tipo_campo="serie",
            )
            comp.grupo_b.numero = CampoExtraido(
                nombre_campo="numero",
                valor=numero_val,
                archivo=archivo,
                pagina=pagina,
                confianza=0.85,
                metodo=MetodoExtraccion.REGEX,
                snippet=m_serie.group(0),
                regla_aplicada="OCR_FIRST_NUMERO",
                tipo_campo="numero",
            )

        # --- Tipo de comprobante ---
        comp.grupo_b.tipo_comprobante = CampoExtraido(
            nombre_campo="tipo_comprobante",
            valor=tipo,
            archivo=archivo,
            pagina=pagina,
            confianza=0.9,
            metodo=MetodoExtraccion.REGEX,
            snippet="",
            regla_aplicada="OCR_FIRST_TIPO",
            tipo_campo="tipo",
        )

        # --- Importe total ---
        m_total = REGEX_TOTAL.search(texto_ocr)
        if m_total:
            total_val = m_total.group(1).replace(",", "")
            comp.grupo_f.importe_total = CampoExtraido(
                nombre_campo="importe_total",
                valor=total_val,
                archivo=archivo,
                pagina=pagina,
                confianza=0.8,
                metodo=MetodoExtraccion.REGEX,
                snippet=m_total.group(0)[:100],
                regla_aplicada="OCR_FIRST_TOTAL",
                tipo_campo="monto",
            )

        # --- IGV ---
        m_igv = REGEX_IGV.search(texto_ocr)
        if m_igv:
            igv_val = m_igv.group(1).replace(",", "")
            comp.grupo_f.igv_monto = CampoExtraido(
                nombre_campo="igv_monto",
                valor=igv_val,
                archivo=archivo,
                pagina=pagina,
                confianza=0.8,
                metodo=MetodoExtraccion.REGEX,
                snippet=m_igv.group(0)[:100],
                regla_aplicada="OCR_FIRST_IGV",
                tipo_campo="monto",
            )

        # --- Subtotal ---
        m_sub = REGEX_SUBTOTAL.search(texto_ocr)
        if m_sub:
            sub_val = m_sub.group(1).replace(",", "")
            comp.grupo_f.subtotal = CampoExtraido(
                nombre_campo="subtotal",
                valor=sub_val,
                archivo=archivo,
                pagina=pagina,
                confianza=0.8,
                metodo=MetodoExtraccion.REGEX,
                snippet=m_sub.group(0)[:100],
                regla_aplicada="OCR_FIRST_SUBTOTAL",
                tipo_campo="monto",
            )

        # --- Metadatos ---
        import datetime

        comp.grupo_k = MetadatosExtraccion(
            pagina_origen=pagina,
            metodo_extraccion="OCR_FIRST_REGEX",
            confianza_global="media",
            timestamp_extraccion=datetime.datetime.now().isoformat(),
        )

        return comp

    def _calcular_score_suficiencia(
        self,
        comprobante: ComprobanteExtraido,
        tipo: str,
    ) -> tuple:
        """
        Calcula score de suficiencia: campos_encontrados / campos_esperados.

        ADR-011 Nivel 2: determina si el comprobante tiene suficientes campos
        extraídos por OCR-first para evitar llamar al VLM.

        Parameters
        ----------
        comprobante : ComprobanteExtraido
            Comprobante con campos extraídos por regex.
        tipo : str
            Tipo de comprobante.

        Returns
        -------
        (score, campos_encontrados, campos_esperados, campos_faltantes)
        """
        esperados = CAMPOS_ESPERADOS_POR_TIPO.get(tipo, ["fecha_emision"])
        encontrados = []
        faltantes = []

        for campo in esperados:
            if campo == "ruc_emisor":
                if comprobante.grupo_a.ruc_emisor and comprobante.grupo_a.ruc_emisor.valor:
                    encontrados.append(campo)
                else:
                    faltantes.append(campo)
            elif campo == "fecha_emision":
                if comprobante.grupo_b.fecha_emision and comprobante.grupo_b.fecha_emision.valor:
                    encontrados.append(campo)
                else:
                    faltantes.append(campo)
            elif campo == "serie_numero":
                if (
                    comprobante.grupo_b.serie
                    and comprobante.grupo_b.serie.valor
                    and comprobante.grupo_b.numero
                    and comprobante.grupo_b.numero.valor
                ):
                    encontrados.append(campo)
                else:
                    faltantes.append(campo)
            elif campo == "importe_total":
                if comprobante.grupo_f.importe_total and comprobante.grupo_f.importe_total.valor:
                    encontrados.append(campo)
                else:
                    faltantes.append(campo)
            elif campo == "igv_monto":
                if comprobante.grupo_f.igv_monto and comprobante.grupo_f.igv_monto.valor:
                    encontrados.append(campo)
                else:
                    faltantes.append(campo)
            else:
                faltantes.append(campo)

        n_esperados = len(esperados)
        score = len(encontrados) / n_esperados if n_esperados > 0 else 0.0

        return score, encontrados, esperados, faltantes

    # ==========================================================================
    # ADR-011 NIVEL 3 — ROI crop: Recorte inteligente antes del VLM
    # ==========================================================================

    def _calcular_roi_desde_bboxes(
        self,
        lineas: List[Dict[str, Any]],
        img_width: int,
        img_height: int,
    ) -> Optional[tuple]:
        """
        Calcula la región de interés (ROI) desde bboxes de OCR.

        ADR-011 Nivel 3: usa la unión de bboxes de PaddleOCR para
        determinar la región dominante del comprobante. Añade margen
        de seguridad y clampea a los límites de la imagen.

        Parameters
        ----------
        lineas : list
            Lista de dicts con bbox y confianza (de LineaOCR.to_dict()).
        img_width : int
            Ancho de la imagen en píxeles.
        img_height : int
            Alto de la imagen en píxeles.

        Returns
        -------
        (x_min, y_min, x_max, y_max) o None si no hay suficientes bboxes.
        """
        # Filtrar líneas con bbox válido y confianza mínima
        bboxes_validos = []
        for linea in lineas:
            bbox = linea.get("bbox")
            conf = linea.get("confianza")
            if bbox is None or len(bbox) < 4:
                continue
            if conf is not None and conf < MIN_BBOX_CONFIDENCE:
                continue
            bboxes_validos.append(bbox)

        if len(bboxes_validos) < MIN_BBOXES_FOR_CROP:
            return None

        # Unión de todos los bboxes
        x_min = min(b[0] for b in bboxes_validos)
        y_min = min(b[1] for b in bboxes_validos)
        x_max = max(b[2] for b in bboxes_validos)
        y_max = max(b[3] for b in bboxes_validos)

        # Añadir margen de seguridad (5% de cada lado)
        margin_x = img_width * CROP_MARGIN_PERCENT
        margin_y = img_height * CROP_MARGIN_PERCENT

        x_min = max(0, x_min - margin_x)
        y_min = max(0, y_min - margin_y)
        x_max = min(img_width, x_max + margin_x)
        y_max = min(img_height, y_max + margin_y)

        # Verificar que el crop tenga tamaño razonable (al menos 10% del área)
        crop_area = (x_max - x_min) * (y_max - y_min)
        full_area = img_width * img_height
        if full_area > 0 and crop_area / full_area < 0.05:
            return None  # Crop demasiado pequeño, probablemente ruido

        return (int(x_min), int(y_min), int(x_max), int(y_max))

    def _identificar_paginas_comprobante(
        self,
        paginas_ocr: List[Dict[str, Any]],
        min_keywords: int = 2,
    ) -> List[int]:
        """Identifica páginas que probablemente contienen comprobantes de pago."""
        paginas = []
        for pag in paginas_ocr:
            texto = (pag.get("texto", "") or "").upper()
            if not texto:
                continue
            matches = sum(1 for kw in KEYWORDS_COMPROBANTE if re.search(kw, texto, re.IGNORECASE))
            if matches >= min_keywords:
                paginas.append(pag.get("pagina", 0))
        return paginas

    def _clasificar_tipo_comprobante(
        self,
        texto: str,
    ) -> str:
        """
        Clasifica el tipo de comprobante de una página por su texto OCR.

        Devuelve uno de: FACTURA, BOLETA, BOARDING_PASS, DECLARACION_JURADA,
        RECIBO_HONORARIOS, ADMINISTRATIVO.

        ADR-011: gating mejorado para habilitar prompts especializados,
        validaciones por tipo y métricas por clase documental.
        """
        if not texto:
            return "ADMINISTRATIVO"
        for tipo, patrones in PATRONES_TIPO_COMPROBANTE.items():
            if any(re.search(p, texto, re.IGNORECASE) for p in patrones):
                return tipo
        return "ADMINISTRATIVO"

    def _clasificar_paginas_digital_imagen(
        self,
        pdf_path: str,
        paginas_comprobante: List[int],
        min_chars_digital: int = 100,
    ) -> tuple:
        """
        Clasifica páginas comprobante como digitales o imagen (ADR-009).

        Digital: PyMuPDF get_text() extrae >= min_chars_digital caracteres.
        Imagen: texto digital insuficiente → necesita VLM con imagen.

        Returns:
            (digitales, imagenes) donde:
            - digitales: List[(page_num, texto)] — páginas con texto digital
            - imagenes: List[int] — páginas que necesitan VLM imagen
        """
        digitales = []
        imagenes = []
        try:
            import fitz

            doc = fitz.open(pdf_path)
            for page_num in paginas_comprobante:
                if page_num < 1 or page_num > len(doc):
                    continue
                page = doc[page_num - 1]
                texto = page.get_text("text").strip()
                if len(texto) >= min_chars_digital:
                    digitales.append((page_num, texto))
                else:
                    imagenes.append(page_num)
            doc.close()
        except ImportError:
            # Sin PyMuPDF, asumir todo es imagen
            imagenes = list(paginas_comprobante)
        except Exception as e:
            self._logger.warning(
                f"Error clasificando páginas: {e}",
                agent_id=AGENTE_ID,
                operation="parseo_profundo",
            )
            imagenes = list(paginas_comprobante)

        return digitales, imagenes

    def _renderizar_paginas_base64(
        self,
        pdf_path: str,
        paginas: List[int],
        dpi: int = 200,
        paginas_ocr_dict: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> List[tuple]:
        """
        Renderiza páginas de un PDF como imágenes base64 PNG.

        ADR-011 Nivel 1: downscale adaptativo (MAX_VLM_IMAGE_PX).
        ADR-011 Nivel 3: ROI crop usando bboxes OCR antes del downscale.

        Si paginas_ocr_dict se proporciona, intenta hacer crop a la región
        del comprobante antes de aplicar downscale. Si no hay bboxes útiles,
        hace fallback a página completa con downscale.
        """
        resultado = []
        self._ultimo_crop_stats = {
            "pages_with_crop": 0,
            "pages_full_page": 0,
            "crop_area_ratios": [],
        }

        try:
            import io

            import fitz
            from PIL import Image

            doc = fitz.open(pdf_path)
            zoom = dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)

            for page_num in paginas:
                if page_num < 1 or page_num > len(doc):
                    continue
                page = doc[page_num - 1]
                pix = page.get_pixmap(matrix=matrix)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                original_w, original_h = pix.width, pix.height
                cropped = False

                # ADR-011 Nivel 3: intentar ROI crop si hay datos OCR
                if paginas_ocr_dict is not None:
                    pag_data = paginas_ocr_dict.get(page_num, {})
                    lineas = pag_data.get("lineas", [])
                    roi = self._calcular_roi_desde_bboxes(lineas, pix.width, pix.height)
                    if roi is not None:
                        x_min, y_min, x_max, y_max = roi
                        img = img.crop((x_min, y_min, x_max, y_max))
                        crop_area = (x_max - x_min) * (y_max - y_min)
                        full_area = original_w * original_h
                        ratio = round(crop_area / full_area, 3) if full_area > 0 else 1.0
                        self._ultimo_crop_stats["pages_with_crop"] += 1
                        self._ultimo_crop_stats["crop_area_ratios"].append(ratio)
                        cropped = True
                        self._logger.info(
                            f"ROI crop pág {page_num}: {original_w}x{original_h} → "
                            f"{img.width}x{img.height} (ratio={ratio})",
                            agent_id=AGENTE_ID,
                            operation="parseo_profundo",
                        )
                    else:
                        self._ultimo_crop_stats["pages_full_page"] += 1

                # ADR-011 Nivel 1: downscale si excede MAX_VLM_IMAGE_PX
                max_side = max(img.width, img.height)
                if max_side > MAX_VLM_IMAGE_PX:
                    scale = MAX_VLM_IMAGE_PX / max_side
                    new_w = int(img.width * scale)
                    new_h = int(img.height * scale)
                    img = img.resize((new_w, new_h), Image.LANCZOS)
                    action = "Crop+downscale" if cropped else "Downscale"
                    self._logger.info(
                        f"{action} pág {page_num}: → {new_w}x{new_h}",
                        agent_id=AGENTE_ID,
                        operation="parseo_profundo",
                    )

                # Codificar a base64
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                img_bytes = buf.getvalue()
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")

                # Log dimensiones finales para auditoría de timeouts
                b64_kb = len(img_b64) // 1024
                self._logger.info(
                    f"VLM input pág {page_num}: {img.width}x{img.height} "
                    f"({b64_kb} KB b64, crop={'sí' if cropped else 'no'})",
                    agent_id=AGENTE_ID,
                    operation="parseo_profundo",
                )

                resultado.append((page_num, img_b64))

            doc.close()
        except ImportError:
            self._logger.warning(
                "PyMuPDF/PIL no disponible para renderizar páginas",
                agent_id=AGENTE_ID,
                operation="parseo_profundo",
            )
        except Exception as e:
            self._logger.error(
                f"Error renderizando páginas: {e}",
                agent_id=AGENTE_ID,
                operation="parseo_profundo",
                error=str(e),
            )
        return resultado

    def _paso_evaluacion(
        self,
        expediente: ExpedienteJSON,
        observaciones: List[Observacion],
    ) -> ResultadoPaso:
        """
        Paso 5: Evaluar expediente con IntegrityCheckpoint.

        Ejecuta IntegrityCheckpoint.evaluar() que internamente:
        - Ejecuta ConfidenceRouter.evaluar_expediente()
        - Genera ReporteEnforcement detallado
        - Genera DiagnosticoExpediente para Excel
        - Determina acción: CONTINUAR / CONTINUAR_CON_ALERTAS / DETENER
        """
        inicio = time.perf_counter()
        self._logger.info(
            "Paso 5/6: Evaluación con IntegrityCheckpoint",
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

    def _paso_validacion(
        self,
        expediente: ExpedienteJSON,
        naturaleza: NaturalezaExpediente = NaturalezaExpediente.NO_DETERMINADO,
    ) -> ResultadoPaso:
        """
        Paso 6: Validaciones aritméticas y reglas de viáticos (Fase 4).

        Ejecuta ValidadorExpediente (Grupo J) y ReglasViaticos (directiva).
        No es bloqueante: si falla, pipeline continúa sin validaciones.
        """
        inicio = time.perf_counter()
        self._logger.info(
            "Paso 6/7: Validación aritmética + reglas viáticos",
            agent_id=AGENTE_ID,
            operation="validacion",
        )

        try:
            from src.validation.reglas_viaticos import ReglasViaticos
            from src.validation.validador_expediente import ValidadorExpediente

            todas_obs = []

            # Validaciones aritméticas (Tarea #27)
            validador = ValidadorExpediente()
            resultado_val = validador.validar_expediente(expediente)
            todas_obs.extend(resultado_val.observaciones)

            # Reglas de viáticos (Tarea #28) — solo si es viáticos
            resultado_reglas = None
            if naturaleza == NaturalezaExpediente.VIATICOS:
                reglas = ReglasViaticos()
                resultado_reglas = reglas.validar(expediente)
                todas_obs.extend(resultado_reglas.observaciones)

            n_arit = resultado_val.errores_aritmeticos
            n_reglas = resultado_reglas.reglas_fallidas if resultado_reglas else 0

            return ResultadoPaso(
                paso="validacion",
                exito=True,
                duracion_ms=_elapsed_ms(inicio),
                mensaje=(f"{len(todas_obs)} hallazgos ({n_arit} aritmético, {n_reglas} normativo)"),
                datos={
                    "observaciones": todas_obs,
                    "validacion_aritmetica": resultado_val.to_dict(),
                    "validacion_reglas": resultado_reglas.to_dict() if resultado_reglas else None,
                    "total_hallazgos": len(todas_obs),
                },
            )

        except ImportError as e:
            self._logger.warning(
                f"Módulos de validación no disponibles: {e}",
                agent_id=AGENTE_ID,
                operation="validacion",
            )
            return ResultadoPaso(
                paso="validacion",
                exito=True,
                duracion_ms=_elapsed_ms(inicio),
                mensaje="Validación omitida: módulos no disponibles",
                datos={"observaciones": []},
            )

        except Exception as e:
            self._logger.error(
                f"Error en validación: {e}",
                agent_id=AGENTE_ID,
                operation="validacion",
                error=str(e),
            )
            return ResultadoPaso(
                paso="validacion",
                exito=False,
                duracion_ms=_elapsed_ms(inicio),
                error=str(e),
                datos={"observaciones": []},
            )

    def _paso_excel(
        self,
        sinad: str,
        decision: DecisionCheckpoint,
        expediente: Optional[ExpedienteJSON] = None,
        ruta_excel: Optional[str] = None,
        observaciones_validacion: Optional[List[Observacion]] = None,
    ) -> ResultadoPaso:
        """
        Paso 7: Generar Excel con hojas DIAGNOSTICO + HALLAZGOS + ANEXO_3 + COMPROBANTES.

        Crea un workbook nuevo con todas las hojas.
        ANEXO_3 y COMPROBANTES muestran datos extraídos sin alucinaciones.
        """
        inicio = time.perf_counter()
        self._logger.info(
            "Paso 7/7: Generar Excel con DIAGNOSTICO + HALLAZGOS",
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

            # Escribir hoja HALLAZGOS si hay observaciones de validación
            if observaciones_validacion:
                try:
                    from src.validation.reporte_hallazgos import escribir_hallazgos

                    escribir_hallazgos(
                        wb=wb,
                        observaciones=observaciones_validacion,
                        sinad=sinad,
                    )
                except ImportError:
                    pass  # Módulo no disponible, omitir hoja

            # Escribir hojas ANEXO_3 y COMPROBANTES (datos extraídos, sin alucinaciones)
            if expediente:
                try:
                    from src.extraction.excel_writer import (
                        escribir_anexo3,
                        escribir_comprobantes,
                    )

                    escribir_anexo3(wb, expediente.anexo3, sinad=sinad)
                    escribir_comprobantes(wb, expediente.comprobantes)
                except ImportError:
                    pass

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
