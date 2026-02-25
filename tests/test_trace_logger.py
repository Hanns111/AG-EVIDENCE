# -*- coding: utf-8 -*-
"""
Tests para Logger Estructurado JSONL con trace_id (Tarea #11)
==============================================================
Verifica:
  - Creación de TraceContext y LogEntry
  - Ciclo de vida: start_trace → log → end_trace
  - Escritura JSONL correcta y parseable
  - Recuperación por trace_id y SINAD
  - Rotación de archivos por fecha
  - Manejo de errores y edge cases
  - Múltiples traces concurrentes (secuenciales)
"""

import json
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.ingestion.trace_logger import (
    LogEntry,
    TraceContext,
    TraceLogger,
)


# ==============================================================================
# FIXTURES
# ==============================================================================
@pytest.fixture
def temp_log_dir():
    """Crea un directorio temporal para logs."""
    base = tempfile.mkdtemp(prefix="ag_trace_test_")
    yield base
    shutil.rmtree(base, ignore_errors=True)


@pytest.fixture
def logger(temp_log_dir):
    """Crea una instancia de TraceLogger con dir temporal."""
    return TraceLogger(log_dir=temp_log_dir, logger_name="test_logger")


@pytest.fixture
def active_logger(logger):
    """Logger con trace ya activo."""
    logger.start_trace(sinad="EXP-2026-0001", source="test")
    yield logger
    # Limpieza: cerrar trace si sigue activo
    if logger.has_active_trace:
        logger.end_trace(status="cleanup")


# ==============================================================================
# TESTS: TraceContext
# ==============================================================================
class TestTraceContext:
    """Tests para la dataclass TraceContext."""

    def test_create_with_required_fields(self):
        """Crear TraceContext con campos mínimos."""
        ctx = TraceContext(trace_id="abc-123", sinad="EXP-001")
        assert ctx.trace_id == "abc-123"
        assert ctx.sinad == "EXP-001"
        assert ctx.source == "manual"  # default

    def test_create_with_all_fields(self):
        """Crear TraceContext con todos los campos."""
        ctx = TraceContext(
            trace_id="abc-123",
            sinad="EXP-001",
            source="batch",
            started_at="2026-02-11T00:00:00+00:00",
            agent_id="AG01",
            operation="classify",
            metadata={"key": "value"},
        )
        assert ctx.source == "batch"
        assert ctx.agent_id == "AG01"
        assert ctx.operation == "classify"
        assert ctx.metadata == {"key": "value"}

    def test_to_dict(self):
        """to_dict serializa correctamente."""
        ctx = TraceContext(trace_id="abc", sinad="EXP-001")
        d = ctx.to_dict()
        assert isinstance(d, dict)
        assert d["trace_id"] == "abc"
        assert d["sinad"] == "EXP-001"
        assert "metadata" in d

    def test_from_dict_roundtrip(self):
        """from_dict reconstruye desde to_dict."""
        original = TraceContext(
            trace_id="abc-123",
            sinad="EXP-001",
            source="api",
            agent_id="AG03",
        )
        d = original.to_dict()
        restored = TraceContext.from_dict(d)
        assert restored.trace_id == original.trace_id
        assert restored.sinad == original.sinad
        assert restored.source == original.source
        assert restored.agent_id == original.agent_id

    def test_from_dict_ignores_extra_keys(self):
        """from_dict ignora claves desconocidas."""
        d = {"trace_id": "abc", "sinad": "EXP", "unknown_key": "ignored"}
        ctx = TraceContext.from_dict(d)
        assert ctx.trace_id == "abc"
        assert not hasattr(ctx, "unknown_key")


# ==============================================================================
# TESTS: LogEntry
# ==============================================================================
class TestLogEntry:
    """Tests para la dataclass LogEntry."""

    def test_create_minimal(self):
        """Crear LogEntry con campos mínimos."""
        entry = LogEntry(
            timestamp="2026-02-11T00:00:00Z",
            trace_id="abc-123",
            level="INFO",
            logger="test",
            message="Test message",
        )
        assert entry.level == "INFO"
        assert entry.message == "Test message"
        assert entry.context == {}  # default
        assert entry.error is None  # default

    def test_to_dict_excludes_none(self):
        """to_dict excluye campos con valor None."""
        entry = LogEntry(
            timestamp="2026-02-11T00:00:00Z",
            trace_id="abc",
            level="INFO",
            logger="test",
            message="msg",
        )
        d = entry.to_dict()
        assert "duration_ms" not in d
        assert "error" not in d

    def test_to_dict_includes_values(self):
        """to_dict incluye campos con valor no-None."""
        entry = LogEntry(
            timestamp="2026-02-11T00:00:00Z",
            trace_id="abc",
            level="ERROR",
            logger="test",
            message="falló",
            duration_ms=500.5,
            error="timeout",
        )
        d = entry.to_dict()
        assert d["duration_ms"] == 500.5
        assert d["error"] == "timeout"

    def test_to_jsonl_line_valid_json(self):
        """to_jsonl_line produce JSON válido en una línea."""
        entry = LogEntry(
            timestamp="2026-02-11T00:00:00Z",
            trace_id="abc",
            level="INFO",
            logger="test",
            message="msg",
            context={"key": "value"},
        )
        line = entry.to_jsonl_line()
        assert "\n" not in line
        data = json.loads(line)
        assert data["trace_id"] == "abc"
        assert data["context"]["key"] == "value"

    def test_from_dict_roundtrip(self):
        """from_dict reconstruye desde to_dict."""
        original = LogEntry(
            timestamp="2026-02-11T00:00:00Z",
            trace_id="abc",
            level="WARNING",
            logger="test",
            message="advertencia",
            agent_id="AG05",
            duration_ms=100.0,
        )
        d = original.to_dict()
        # to_dict excluye None, así que agregar los None para from_dict
        d.setdefault("error", None)
        restored = LogEntry.from_dict(d)
        assert restored.trace_id == original.trace_id
        assert restored.level == original.level
        assert restored.agent_id == original.agent_id


# ==============================================================================
# TESTS: TraceLogger — Ciclo de vida
# ==============================================================================
class TestTraceLifecycle:
    """Tests para start_trace / end_trace."""

    def test_start_trace_returns_context(self, logger):
        """start_trace retorna un TraceContext válido."""
        ctx = logger.start_trace(sinad="EXP-001", source="test")
        assert isinstance(ctx, TraceContext)
        assert len(ctx.trace_id) == 36  # UUID format
        assert ctx.sinad == "EXP-001"
        assert ctx.source == "test"
        assert ctx.started_at  # timestamp presente
        logger.end_trace()

    def test_start_trace_sets_active(self, logger):
        """start_trace establece el trace como activo."""
        assert not logger.has_active_trace
        ctx = logger.start_trace(sinad="EXP-001")
        assert logger.has_active_trace
        assert logger.active_trace.trace_id == ctx.trace_id
        logger.end_trace()

    def test_start_trace_with_all_params(self, logger):
        """start_trace acepta todos los parámetros."""
        ctx = logger.start_trace(
            sinad="EXP-001",
            source="batch",
            agent_id="AG01",
            operation="classify",
            metadata={"batch_id": "B-100"},
        )
        assert ctx.agent_id == "AG01"
        assert ctx.operation == "classify"
        assert ctx.metadata["batch_id"] == "B-100"
        logger.end_trace()

    def test_start_trace_rejects_double_start(self, active_logger):
        """No se puede iniciar un trace si ya hay uno activo."""
        with pytest.raises(RuntimeError, match="Ya hay un trace activo"):
            active_logger.start_trace(sinad="EXP-002")

    def test_end_trace_returns_summary(self, active_logger):
        """end_trace retorna resumen con duración."""
        summary = active_logger.end_trace(status="success")
        assert isinstance(summary, dict)
        assert summary["status"] == "success"
        assert summary["sinad"] == "EXP-2026-0001"
        assert summary["trace_id"]  # UUID presente
        assert summary["duration_ms"] is not None
        assert summary["duration_ms"] >= 0
        assert summary["started_at"]
        assert summary["ended_at"]

    def test_end_trace_clears_active(self, active_logger):
        """end_trace limpia el contexto activo."""
        assert active_logger.has_active_trace
        active_logger.end_trace()
        assert not active_logger.has_active_trace
        assert active_logger.active_trace is None

    def test_end_trace_without_active_returns_none(self, logger):
        """end_trace sin trace activo retorna None."""
        result = logger.end_trace()
        assert result is None

    def test_end_trace_with_error_status(self, active_logger):
        """end_trace con error registra WARNING."""
        summary = active_logger.end_trace(
            status="error",
            message="OCR falló en página 3",
        )
        assert summary["status"] == "error"

    def test_full_lifecycle(self, logger):
        """Ciclo completo: start → log → end."""
        ctx = logger.start_trace(sinad="EXP-001", source="test")
        logger.info("Paso 1 completado", agent_id="AG01")
        logger.info("Paso 2 completado", agent_id="AG02")
        summary = logger.end_trace(status="success")

        # Verificar que se escribieron 4 eventos (start + 2 logs + end)
        entries = logger.get_trace(ctx.trace_id)
        assert len(entries) == 4
        assert entries[0].message.startswith("Trace iniciado")
        assert entries[1].message == "Paso 1 completado"
        assert entries[2].message == "Paso 2 completado"
        assert entries[3].message.startswith("Trace finalizado")

    def test_sequential_traces(self, logger):
        """Se pueden ejecutar traces secuenciales."""
        ctx1 = logger.start_trace(sinad="EXP-001")
        logger.info("Trace 1")
        logger.end_trace()

        ctx2 = logger.start_trace(sinad="EXP-002")
        logger.info("Trace 2")
        logger.end_trace()

        assert ctx1.trace_id != ctx2.trace_id

        entries1 = logger.get_trace(ctx1.trace_id)
        entries2 = logger.get_trace(ctx2.trace_id)
        assert len(entries1) == 3  # start + log + end
        assert len(entries2) == 3


# ==============================================================================
# TESTS: TraceLogger — Logging
# ==============================================================================
class TestLogging:
    """Tests para métodos de log."""

    def test_log_all_levels(self, active_logger):
        """Todos los niveles de log funcionan."""
        active_logger.debug("msg debug")
        active_logger.info("msg info")
        active_logger.warning("msg warning")
        active_logger.error("msg error")
        active_logger.critical("msg critical")

        entries = active_logger.get_trace(active_logger.active_trace.trace_id)
        # 1 start + 5 logs = 6
        assert len(entries) == 6
        levels = [e.level for e in entries[1:]]  # skip start event
        assert levels == ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def test_log_invalid_level(self, active_logger):
        """Nivel inválido lanza ValueError."""
        with pytest.raises(ValueError, match="Nivel de log inválido"):
            active_logger.log("INVALID", "mensaje")

    def test_log_with_context(self, active_logger):
        """Log con datos de contexto adicionales."""
        entry = active_logger.info(
            "Clasificación completada",
            agent_id="AG01",
            context={"naturaleza": "VIÁTICOS", "confianza": 0.95},
        )
        assert entry.context["naturaleza"] == "VIÁTICOS"
        assert entry.context["confianza"] == 0.95

    def test_log_with_duration(self, active_logger):
        """Log con duración en milisegundos."""
        entry = active_logger.info(
            "OCR completado",
            duration_ms=3456.78,
        )
        assert entry.duration_ms == 3456.78

    def test_log_with_error(self, active_logger):
        """Log con mensaje de error."""
        entry = active_logger.error(
            "Fallo en extracción",
            error="FileNotFoundError: documento.pdf",
        )
        assert entry.error == "FileNotFoundError: documento.pdf"

    def test_log_inherits_trace_context(self, active_logger):
        """Log hereda trace_id y sinad del contexto activo."""
        trace_id = active_logger.active_trace.trace_id
        entry = active_logger.info("Test")
        assert entry.trace_id == trace_id
        assert entry.sinad == "EXP-2026-0001"

    def test_log_overrides_agent_from_context(self, logger):
        """agent_id explícito sobreescribe el del contexto."""
        logger.start_trace(sinad="EXP-001", agent_id="AG01")
        entry = logger.info("Test", agent_id="AG02")
        assert entry.agent_id == "AG02"
        logger.end_trace()

    def test_log_without_active_trace(self, logger):
        """Log sin trace activo funciona pero sin trace_id."""
        entry = logger.info("Evento suelto")
        assert entry.trace_id == ""
        assert entry.sinad == ""
        assert entry.message == "Evento suelto"

    def test_log_returns_entry(self, active_logger):
        """Cada método de log retorna el LogEntry creado."""
        entry = active_logger.info("Test")
        assert isinstance(entry, LogEntry)
        assert entry.level == "INFO"


# ==============================================================================
# TESTS: TraceLogger — Archivo JSONL
# ==============================================================================
class TestJSONLFile:
    """Tests para escritura y lectura de archivos JSONL."""

    def test_creates_log_file(self, logger):
        """El primer log crea el archivo JSONL."""
        logger.start_trace(sinad="EXP-001")
        assert logger.current_log_file.exists()
        logger.end_trace()

    def test_jsonl_lines_parseable(self, logger):
        """Cada línea del archivo es JSON válido."""
        ctx = logger.start_trace(sinad="EXP-001")
        logger.info("Test 1")
        logger.info("Test 2")
        logger.end_trace()

        with open(logger.current_log_file, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]

        assert len(lines) == 4  # start + 2 logs + end
        for line in lines:
            data = json.loads(line)  # Should not raise
            assert "timestamp" in data
            assert "trace_id" in data
            assert "level" in data

    def test_jsonl_append_only(self, logger):
        """Múltiples logs se agregan al mismo archivo."""
        ctx = logger.start_trace(sinad="EXP-001")
        logger.info("Log 1")
        logger.end_trace()

        with open(logger.current_log_file, "r") as f:
            count_after_first = len(f.readlines())

        ctx2 = logger.start_trace(sinad="EXP-002")
        logger.info("Log 2")
        logger.end_trace()

        with open(logger.current_log_file, "r") as f:
            count_after_second = len(f.readlines())

        assert count_after_second > count_after_first

    def test_log_file_naming_convention(self, logger):
        """Archivo se nombra con fecha UTC del día."""
        logger.start_trace(sinad="EXP-001")
        log_file = logger.current_log_file
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert f"trace_{date_str}.jsonl" in str(log_file)
        logger.end_trace()

    def test_custom_prefix(self, temp_log_dir):
        """Prefijo personalizado se refleja en nombre de archivo."""
        logger = TraceLogger(log_dir=temp_log_dir, log_prefix="custom")
        logger.start_trace(sinad="EXP-001")
        assert "custom_" in logger.current_log_file.name
        logger.end_trace()

    def test_unicode_in_message(self, logger):
        """Caracteres Unicode se escriben correctamente."""
        ctx = logger.start_trace(sinad="EXP-001")
        logger.info("Expediente de viáticos — señor González ñoño")
        logger.end_trace()

        entries = logger.get_trace(ctx.trace_id)
        assert "viáticos" in entries[1].message
        assert "González" in entries[1].message
        assert "ñoño" in entries[1].message


# ==============================================================================
# TESTS: TraceLogger — Consultas
# ==============================================================================
class TestQueries:
    """Tests para métodos de consulta."""

    def test_get_trace_by_id(self, logger):
        """Recuperar eventos por trace_id."""
        ctx = logger.start_trace(sinad="EXP-001")
        logger.info("Evento 1")
        logger.end_trace()

        entries = logger.get_trace(ctx.trace_id)
        assert len(entries) == 3
        assert all(e.trace_id == ctx.trace_id for e in entries)

    def test_get_trace_not_found(self, logger):
        """trace_id inexistente retorna lista vacía."""
        entries = logger.get_trace("id-inexistente")
        assert entries == []

    def test_get_traces_by_sinad(self, logger):
        """Recuperar eventos por SINAD."""
        ctx = logger.start_trace(sinad="EXP-001")
        logger.info("Evento")
        logger.end_trace()

        entries = logger.get_traces_by_sinad("EXP-001")
        assert len(entries) == 3
        assert all(e.sinad == "EXP-001" for e in entries)

    def test_get_traces_by_sinad_not_found(self, logger):
        """SINAD inexistente retorna lista vacía."""
        entries = logger.get_traces_by_sinad("NO-EXISTE")
        assert entries == []

    def test_get_recent_entries(self, logger):
        """Recuperar entradas recientes."""
        ctx1 = logger.start_trace(sinad="EXP-001")
        logger.info("A")
        logger.end_trace()

        ctx2 = logger.start_trace(sinad="EXP-002")
        logger.info("B")
        logger.end_trace()

        recent = logger.get_recent_entries(limit=3)
        assert len(recent) == 3  # últimas 3 de 6 totales

    def test_get_recent_entries_with_level_filter(self, logger):
        """Filtrar recientes por nivel mínimo."""
        ctx = logger.start_trace(sinad="EXP-001")
        logger.debug("debug msg")
        logger.info("info msg")
        logger.warning("warning msg")
        logger.error("error msg")
        logger.end_trace()

        # Solo WARNING y superiores
        entries = logger.get_recent_entries(level="WARNING")
        levels = {e.level for e in entries}
        assert "DEBUG" not in levels
        assert "INFO" not in levels
        # WARNING y ERROR deberían estar
        assert "WARNING" in levels or "ERROR" in levels

    def test_get_stats(self, logger):
        """get_stats retorna estadísticas correctas."""
        ctx = logger.start_trace(sinad="EXP-001")
        logger.info("Test")
        logger.error("Error", error="algo falló")
        logger.end_trace()

        stats = logger.get_stats()
        assert stats["total_entries"] == 4  # start + info + error + end
        assert stats["unique_traces"] == 1
        assert stats["error_entries"] == 1
        assert stats["log_files_count"] == 1
        assert stats["has_active_trace"] is False

    def test_get_stats_empty(self, logger):
        """get_stats en logger vacío."""
        stats = logger.get_stats()
        assert stats["total_entries"] == 0
        assert stats["unique_traces"] == 0


# ==============================================================================
# TESTS: TraceLogger — set_agent
# ==============================================================================
class TestSetAgent:
    """Tests para cambio de agente en contexto."""

    def test_set_agent_updates_context(self, active_logger):
        """set_agent actualiza el agente activo."""
        active_logger.set_agent("AG03", "validate")
        assert active_logger.active_trace.agent_id == "AG03"
        assert active_logger.active_trace.operation == "validate"

    def test_set_agent_affects_subsequent_logs(self, active_logger):
        """Logs posteriores heredan el nuevo agente."""
        active_logger.set_agent("AG05", "verify_signatures")
        entry = active_logger.info("Verificando firmas")
        assert entry.agent_id == "AG05"
        assert entry.operation == "verify_signatures"

    def test_set_agent_without_trace(self, logger):
        """set_agent sin trace activo no falla."""
        logger.set_agent("AG01")  # No debería lanzar excepción


# ==============================================================================
# TESTS: Edge Cases
# ==============================================================================
class TestEdgeCases:
    """Tests para casos límite y errores."""

    def test_empty_message(self, active_logger):
        """Mensaje vacío es aceptado."""
        entry = active_logger.info("")
        assert entry.message == ""

    def test_very_long_message(self, active_logger):
        """Mensaje muy largo es aceptado."""
        long_msg = "A" * 10000
        entry = active_logger.info(long_msg)
        assert len(entry.message) == 10000

    def test_special_characters_in_context(self, active_logger):
        """Caracteres especiales en contexto se manejan."""
        entry = active_logger.info(
            "Test",
            context={
                "path": "C:\\Users\\test\\file.pdf",
                "quotes": 'valor con "comillas"',
                "newlines": "línea1\nlínea2",
            },
        )
        # Verificar que se escribió correctamente
        line = entry.to_jsonl_line()
        data = json.loads(line)
        assert data["context"]["path"] == "C:\\Users\\test\\file.pdf"

    def test_nested_context(self, active_logger):
        """Contexto anidado se serializa correctamente."""
        entry = active_logger.info(
            "Test",
            context={
                "resultado": {
                    "tipo": "VIÁTICOS",
                    "observaciones": [
                        {"nivel": "CRÍTICA", "desc": "Falta firma"},
                    ],
                }
            },
        )
        line = entry.to_jsonl_line()
        data = json.loads(line)
        assert data["context"]["resultado"]["tipo"] == "VIÁTICOS"

    def test_corrupted_jsonl_line_skipped(self, logger):
        """Líneas corruptas en JSONL se saltan sin error."""
        # Escribir una línea corrupta manualmente
        ctx = logger.start_trace(sinad="EXP-001")
        trace_id = ctx.trace_id
        logger.end_trace()

        # Inyectar línea corrupta
        with open(logger.current_log_file, "a") as f:
            f.write("ESTO NO ES JSON\n")

        # Debe seguir funcionando
        entries = logger.get_trace(trace_id)
        assert len(entries) >= 2  # start + end, sin crash

    def test_repr(self, logger):
        """__repr__ retorna string legible."""
        r = repr(logger)
        assert "TraceLogger" in r
        assert "entries=" in r

    def test_logger_name_in_entries(self, temp_log_dir):
        """logger_name aparece en cada entrada."""
        logger = TraceLogger(
            log_dir=temp_log_dir,
            logger_name="agente_01_clasificador",
        )
        ctx = logger.start_trace(sinad="EXP-001")
        logger.info("Test")
        logger.end_trace()

        entries = logger.get_trace(ctx.trace_id)
        assert all(e.logger == "agente_01_clasificador" for e in entries)

    def test_duration_calculated_on_end(self, logger):
        """end_trace calcula duración real."""
        logger.start_trace(sinad="EXP-001")
        time.sleep(0.05)  # 50ms mínimo
        summary = logger.end_trace()
        assert summary["duration_ms"] >= 40  # tolerancia

    def test_multiple_loggers_same_dir(self, temp_log_dir):
        """Múltiples loggers pueden escribir al mismo directorio."""
        logger1 = TraceLogger(
            log_dir=temp_log_dir,
            log_prefix="agent01",
            logger_name="AG01",
        )
        logger2 = TraceLogger(
            log_dir=temp_log_dir,
            log_prefix="agent02",
            logger_name="AG02",
        )

        ctx1 = logger1.start_trace(sinad="EXP-001")
        logger1.info("Desde AG01")
        logger1.end_trace()

        ctx2 = logger2.start_trace(sinad="EXP-001")
        logger2.info("Desde AG02")
        logger2.end_trace()

        # Cada logger tiene su archivo
        files = list(Path(temp_log_dir).glob("*.jsonl"))
        assert len(files) == 2

        entries1 = logger1.get_trace(ctx1.trace_id)
        entries2 = logger2.get_trace(ctx2.trace_id)
        assert all(e.logger == "AG01" for e in entries1)
        assert all(e.logger == "AG02" for e in entries2)
