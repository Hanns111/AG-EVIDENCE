# -*- coding: utf-8 -*-
"""
Logger Estructurado JSONL con trace_id
========================================
Tarea #11 del Plan de Desarrollo (Fase 1: Trazabilidad + OCR)

Proporciona trazabilidad completa del proceso de análisis de expedientes.
Cada operación genera un registro JSONL con trace_id único que permite
reconstruir el camino completo de un expediente desde ingesta hasta
resultado final.

Mientras la Cadena de Custodia (Tarea #10) protege la integridad del
documento, el TraceLogger registra qué pasó durante el procesamiento:
qué agente actuó, cuánto tardó, qué decidió, y si hubo errores.

Principios:
  - Un trace_id UUID agrupa todos los eventos de un expediente
  - Cada línea JSONL es autocontenida y parseable independientemente
  - Append-only: nunca se modifican registros existentes
  - Timestamps en ISO-8601 UTC para consistencia global
  - Compatible con herramientas estándar (jq, grep, ELK, Grafana)

Uso:
    from src.ingestion.trace_logger import TraceLogger

    logger = TraceLogger(log_dir="data/traces")
    ctx = logger.start_trace(sinad="EXP-2026-0001", source="batch")
    logger.info("Clasificación iniciada", agent_id="AG01")
    logger.info("Clasificación completada", agent_id="AG01",
                naturaleza="VIÁTICOS", confianza=0.95)
    logger.end_trace(status="success")
"""

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
_DEFAULT_LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "traces"
)

# Niveles de log válidos (orden de severidad)
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

# Mapeo de nivel a peso numérico para filtrado
_LEVEL_WEIGHTS = {level: idx for idx, level in enumerate(LOG_LEVELS)}


# ==============================================================================
# DATACLASSES
# ==============================================================================
@dataclass
class TraceContext:
    """
    Contexto de un trace activo.

    Agrupa la información de sesión que se adjunta automáticamente
    a cada evento registrado mientras el trace está abierto.

    Attributes:
        trace_id: UUID único que identifica este trace.
        sinad: Identificador SINAD del expediente.
        source: Origen del procesamiento (manual, api, batch).
        started_at: Timestamp ISO-8601 UTC de inicio.
        agent_id: Agente activo actual (AG01-AG09).
        operation: Operación en curso (classify, extract, verify, etc.).
        metadata: Datos adicionales libres del contexto.
    """

    trace_id: str
    sinad: str
    source: str = "manual"
    started_at: str = ""
    agent_id: str = ""
    operation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraceContext":
        """Reconstruye desde diccionario."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class LogEntry:
    """
    Una entrada individual del log estructurado.

    Cada instancia representa una línea en el archivo JSONL.
    Es autocontenida: incluye toda la información necesaria para
    entender qué pasó sin necesidad de contexto externo.

    Attributes:
        timestamp: Momento exacto del evento (ISO-8601 UTC).
        trace_id: UUID del trace al que pertenece.
        level: Severidad (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        logger: Nombre del logger que generó el evento.
        message: Descripción legible del evento.
        agent_id: Agente que generó el evento (AG01-AG09).
        operation: Operación en curso.
        sinad: SINAD del expediente.
        context: Datos adicionales estructurados del evento.
        duration_ms: Duración en milisegundos (si aplica).
        error: Mensaje de error (si aplica).
    """

    timestamp: str
    trace_id: str
    level: str
    logger: str
    message: str
    agent_id: str = ""
    operation: str = ""
    sinad: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario para JSON."""
        d = asdict(self)
        # Eliminar campos None para líneas más limpias
        return {k: v for k, v in d.items() if v is not None}

    def to_jsonl_line(self) -> str:
        """Serializa a línea JSONL (una línea, sin salto al final)."""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogEntry":
        """Reconstruye desde diccionario."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ==============================================================================
# CLASE PRINCIPAL: TraceLogger
# ==============================================================================
class TraceLogger:
    """
    Logger estructurado JSONL con soporte de trace_id.

    Gestiona el ciclo de vida de trazas de procesamiento:
      1. start_trace() → abre un nuevo trace con UUID único
      2. log/info/warning/error() → registra eventos dentro del trace
      3. end_trace() → cierra el trace con resultado final

    Cada evento se escribe inmediatamente al archivo JSONL (append-only).
    Los archivos se rotan por día automáticamente.

    Ejemplo:
        logger = TraceLogger(log_dir="data/traces")
        ctx = logger.start_trace(sinad="EXP-2026-0001")
        logger.info("Procesamiento iniciado", agent_id="AG01")
        logger.end_trace(status="success")

    Attributes:
        log_dir: Directorio de archivos de log.
        log_prefix: Prefijo para nombres de archivo.
        logger_name: Nombre del logger para identificación.
    """

    def __init__(
        self,
        log_dir: Optional[str] = None,
        log_prefix: str = "trace",
        logger_name: str = "ag_evidence",
    ):
        """
        Inicializa el TraceLogger.

        Args:
            log_dir: Directorio donde se almacenan los logs JSONL.
                     Por defecto: data/traces/
            log_prefix: Prefijo para nombres de archivo JSONL.
                        Resultado: {prefix}_2026-02-11.jsonl
            logger_name: Nombre identificador del logger.
        """
        self.log_dir = Path(log_dir or _DEFAULT_LOG_DIR)
        self.log_prefix = log_prefix
        self.logger_name = logger_name

        # Contexto de trace activo
        self._active_context: Optional[TraceContext] = None
        self._trace_start_time: Optional[float] = None

        # Crear directorio si no existe
        self.log_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # PROPIEDADES
    # ------------------------------------------------------------------
    @property
    def active_trace(self) -> Optional[TraceContext]:
        """Retorna el contexto del trace activo, o None."""
        return self._active_context

    @property
    def has_active_trace(self) -> bool:
        """Indica si hay un trace activo."""
        return self._active_context is not None

    @property
    def current_log_file(self) -> Path:
        """Retorna la ruta del archivo de log del día actual."""
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.log_dir / f"{self.log_prefix}_{date_str}.jsonl"

    # ------------------------------------------------------------------
    # CICLO DE VIDA DEL TRACE
    # ------------------------------------------------------------------
    def start_trace(
        self,
        sinad: str,
        source: str = "manual",
        agent_id: str = "",
        operation: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceContext:
        """
        Inicia un nuevo trace para un expediente.

        Genera un UUID único como trace_id y establece el contexto
        que se adjuntará automáticamente a todos los eventos posteriores.

        Args:
            sinad: Identificador SINAD del expediente.
            source: Origen del procesamiento (manual, api, batch).
            agent_id: Agente inicial (ej: "AG01").
            operation: Operación inicial (ej: "classify").
            metadata: Datos adicionales del contexto.

        Returns:
            TraceContext con el trace_id generado.

        Raises:
            RuntimeError: Si ya hay un trace activo sin cerrar.
        """
        if self._active_context is not None:
            raise RuntimeError(
                f"Ya hay un trace activo: {self._active_context.trace_id} "
                f"(sinad: {self._active_context.sinad}). "
                f"Ciérralo con end_trace() antes de iniciar otro."
            )

        trace_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        context = TraceContext(
            trace_id=trace_id,
            sinad=sinad,
            source=source,
            started_at=timestamp,
            agent_id=agent_id,
            operation=operation,
            metadata=metadata or {},
        )

        self._active_context = context
        self._trace_start_time = time.monotonic()

        # Registrar evento de inicio
        self._write_entry(
            level="INFO",
            message=f"Trace iniciado para expediente {sinad}",
            agent_id=agent_id,
            operation=operation or "start_trace",
            context={"source": source, **(metadata or {})},
        )

        return context

    def end_trace(
        self,
        status: str = "success",
        message: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Cierra el trace activo con un resultado final.

        Args:
            status: Estado final (success, error, partial, timeout).
            message: Mensaje de cierre opcional.
            context: Datos adicionales del resultado.

        Returns:
            Dict con resumen del trace (trace_id, sinad, duration_ms, status).
            None si no hay trace activo.
        """
        if self._active_context is None:
            return None

        # Calcular duración total
        duration_ms = None
        if self._trace_start_time is not None:
            duration_ms = round((time.monotonic() - self._trace_start_time) * 1000, 2)

        trace_id = self._active_context.trace_id
        sinad = self._active_context.sinad

        close_message = message or f"Trace finalizado con status: {status}"

        # Registrar evento de cierre
        self._write_entry(
            level="INFO" if status == "success" else "WARNING",
            message=close_message,
            operation="end_trace",
            context={"status": status, **(context or {})},
            duration_ms=duration_ms,
        )

        summary = {
            "trace_id": trace_id,
            "sinad": sinad,
            "status": status,
            "duration_ms": duration_ms,
            "started_at": self._active_context.started_at,
            "ended_at": datetime.now(timezone.utc).isoformat(),
        }

        # Limpiar contexto
        self._active_context = None
        self._trace_start_time = None

        return summary

    # ------------------------------------------------------------------
    # MÉTODOS DE LOG POR NIVEL
    # ------------------------------------------------------------------
    def log(
        self,
        level: str,
        message: str,
        agent_id: str = "",
        operation: str = "",
        context: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> LogEntry:
        """
        Registra un evento con nivel explícito.

        Args:
            level: Nivel de severidad (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            message: Descripción del evento.
            agent_id: Agente que genera el evento (sobreescribe contexto).
            operation: Operación en curso (sobreescribe contexto).
            context: Datos adicionales del evento.
            duration_ms: Duración de la operación en milisegundos.
            error: Mensaje de error si aplica.

        Returns:
            LogEntry creado y escrito al archivo.

        Raises:
            ValueError: Si el nivel no es válido.
        """
        level = level.upper()
        if level not in LOG_LEVELS:
            raise ValueError(f"Nivel de log inválido: '{level}'. Valores válidos: {LOG_LEVELS}")

        return self._write_entry(
            level=level,
            message=message,
            agent_id=agent_id,
            operation=operation,
            context=context,
            duration_ms=duration_ms,
            error=error,
        )

    def debug(self, message: str, **kwargs) -> LogEntry:
        """Registra evento nivel DEBUG."""
        return self.log("DEBUG", message, **kwargs)

    def info(self, message: str, **kwargs) -> LogEntry:
        """Registra evento nivel INFO."""
        return self.log("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs) -> LogEntry:
        """Registra evento nivel WARNING."""
        return self.log("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs) -> LogEntry:
        """Registra evento nivel ERROR."""
        return self.log("ERROR", message, **kwargs)

    def critical(self, message: str, **kwargs) -> LogEntry:
        """Registra evento nivel CRITICAL."""
        return self.log("CRITICAL", message, **kwargs)

    # ------------------------------------------------------------------
    # CONTEXTO DE AGENTE
    # ------------------------------------------------------------------
    def set_agent(self, agent_id: str, operation: str = "") -> None:
        """
        Actualiza el agente activo en el contexto del trace.

        Útil cuando el procesamiento pasa de un agente a otro
        dentro del mismo trace.

        Args:
            agent_id: Nuevo agente activo (ej: "AG02").
            operation: Nueva operación (ej: "ocr_extract").
        """
        if self._active_context is not None:
            self._active_context.agent_id = agent_id
            if operation:
                self._active_context.operation = operation

    # ------------------------------------------------------------------
    # CONSULTAS
    # ------------------------------------------------------------------
    def get_trace(self, trace_id: str) -> List[LogEntry]:
        """
        Recupera todos los eventos de un trace específico.

        Lee todos los archivos JSONL del directorio y filtra
        por trace_id.

        Args:
            trace_id: UUID del trace a buscar.

        Returns:
            Lista de LogEntry ordenados cronológicamente.
        """
        entries = []
        for log_file in sorted(self.log_dir.glob(f"{self.log_prefix}_*.jsonl")):
            entries.extend(self._read_entries_from_file(log_file, trace_id=trace_id))
        return entries

    def get_traces_by_sinad(self, sinad: str) -> List[LogEntry]:
        """
        Recupera todos los eventos asociados a un SINAD.

        Args:
            sinad: Identificador SINAD del expediente.

        Returns:
            Lista de LogEntry ordenados cronológicamente.
        """
        entries = []
        for log_file in sorted(self.log_dir.glob(f"{self.log_prefix}_*.jsonl")):
            entries.extend(self._read_entries_from_file(log_file, sinad=sinad))
        return entries

    def get_recent_entries(
        self,
        limit: int = 100,
        level: Optional[str] = None,
    ) -> List[LogEntry]:
        """
        Recupera las entradas más recientes del log.

        Args:
            limit: Número máximo de entradas a retornar.
            level: Filtrar por nivel mínimo (ej: "WARNING" incluye WARNING+ERROR+CRITICAL).

        Returns:
            Lista de LogEntry más recientes.
        """
        min_weight = _LEVEL_WEIGHTS.get(level.upper(), 0) if level else 0
        entries = []

        # Leer archivos en orden inverso (más recientes primero)
        log_files = sorted(
            self.log_dir.glob(f"{self.log_prefix}_*.jsonl"),
            reverse=True,
        )

        for log_file in log_files:
            file_entries = self._read_entries_from_file(log_file)

            if min_weight > 0:
                file_entries = [
                    e for e in file_entries if _LEVEL_WEIGHTS.get(e.level, 0) >= min_weight
                ]

            entries.extend(file_entries)
            if len(entries) >= limit:
                break

        # Retornar las más recientes, ordenadas cronológicamente
        entries = entries[-limit:] if len(entries) > limit else entries
        return sorted(entries, key=lambda e: e.timestamp)

    def get_stats(self) -> Dict[str, Any]:
        """
        Retorna estadísticas generales del logger.

        Returns:
            Dict con total de archivos, entradas, traces únicos, etc.
        """
        log_files = list(self.log_dir.glob(f"{self.log_prefix}_*.jsonl"))
        total_entries = 0
        trace_ids = set()
        level_counts: Dict[str, int] = {}
        error_count = 0

        for log_file in log_files:
            entries = self._read_entries_from_file(log_file)
            total_entries += len(entries)
            for entry in entries:
                trace_ids.add(entry.trace_id)
                level_counts[entry.level] = level_counts.get(entry.level, 0) + 1
                if entry.error:
                    error_count += 1

        return {
            "log_dir": str(self.log_dir),
            "log_files_count": len(log_files),
            "total_entries": total_entries,
            "unique_traces": len(trace_ids),
            "level_counts": level_counts,
            "error_entries": error_count,
            "has_active_trace": self.has_active_trace,
            "active_trace_id": (self._active_context.trace_id if self._active_context else None),
        }

    # ------------------------------------------------------------------
    # INTERNOS
    # ------------------------------------------------------------------
    def _write_entry(
        self,
        level: str,
        message: str,
        agent_id: str = "",
        operation: str = "",
        context: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> LogEntry:
        """
        Crea y escribe una entrada al archivo JSONL.

        Combina los datos explícitos con el contexto activo del trace.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # Resolver valores desde contexto activo si no se proporcionan
        ctx = self._active_context
        resolved_trace_id = ctx.trace_id if ctx else ""
        resolved_agent_id = agent_id or (ctx.agent_id if ctx else "")
        resolved_operation = operation or (ctx.operation if ctx else "")
        resolved_sinad = ctx.sinad if ctx else ""

        entry = LogEntry(
            timestamp=timestamp,
            trace_id=resolved_trace_id,
            level=level,
            logger=self.logger_name,
            message=message,
            agent_id=resolved_agent_id,
            operation=resolved_operation,
            sinad=resolved_sinad,
            context=context or {},
            duration_ms=duration_ms,
            error=error,
        )

        # Escribir al archivo del día (append-only)
        log_file = self.current_log_file
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry.to_jsonl_line() + "\n")

        return entry

    def _read_entries_from_file(
        self,
        file_path: Path,
        trace_id: Optional[str] = None,
        sinad: Optional[str] = None,
    ) -> List[LogEntry]:
        """
        Lee entradas de un archivo JSONL con filtro opcional.

        Args:
            file_path: Ruta al archivo JSONL.
            trace_id: Filtrar por trace_id específico.
            sinad: Filtrar por SINAD específico.

        Returns:
            Lista de LogEntry que cumplen los filtros.
        """
        entries = []
        if not file_path.exists():
            return entries

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    # Aplicar filtros
                    if trace_id and data.get("trace_id") != trace_id:
                        continue
                    if sinad and data.get("sinad") != sinad:
                        continue
                    entries.append(LogEntry.from_dict(data))
                except (json.JSONDecodeError, TypeError):
                    # Log corrupto — saltar sin detener lectura
                    continue

        return entries

    # ------------------------------------------------------------------
    # REPRESENTACIÓN
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"TraceLogger("
            f"entries={stats['total_entries']}, "
            f"traces={stats['unique_traces']}, "
            f"dir='{self.log_dir}')"
        )
