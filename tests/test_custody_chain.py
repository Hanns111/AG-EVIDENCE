# -*- coding: utf-8 -*-
"""
Tests para Cadena de Custodia (Tarea #10)
==========================================
Verifica:
  - Ingesta de PDF con copia inmutable + hash SHA-256
  - Registro JSONL correcto
  - Verificación de integridad
  - Detección de duplicados
  - Manejo de errores
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from src.ingestion.custody_chain import (
    HASH_ALGORITHM,
    CustodyChain,
    CustodyRecord,
    VerificationResult,
    compute_sha256,
)


# ==============================================================================
# FIXTURES
# ==============================================================================
@pytest.fixture
def temp_dirs():
    """Crea directorios temporales para vault y registry."""
    base = tempfile.mkdtemp(prefix="ag_custody_test_")
    vault = os.path.join(base, "vault")
    registry = os.path.join(base, "registry")
    yield base, vault, registry
    shutil.rmtree(base, ignore_errors=True)


@pytest.fixture
def chain(temp_dirs):
    """Crea una instancia de CustodyChain con dirs temporales."""
    _, vault, registry = temp_dirs
    return CustodyChain(vault_dir=vault, registry_dir=registry)


@pytest.fixture
def sample_pdf(temp_dirs):
    """Crea un PDF de prueba mínimo válido."""
    base, _, _ = temp_dirs
    pdf_path = os.path.join(base, "expediente_test.pdf")
    # Estructura mínima de un PDF válido
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<< /Size 4 /Root 1 0 R >>
startxref
206
%%EOF"""
    with open(pdf_path, "wb") as f:
        f.write(pdf_content)
    return pdf_path


@pytest.fixture
def second_pdf(temp_dirs):
    """Crea un segundo PDF diferente para tests de duplicados."""
    base, _, _ = temp_dirs
    pdf_path = os.path.join(base, "expediente_otro.pdf")
    # PDF con contenido ligeramente diferente
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<< /Size 4 /Root 1 0 R >>
startxref
206
%%EOF"""
    with open(pdf_path, "wb") as f:
        f.write(pdf_content)
    return pdf_path


# ==============================================================================
# TESTS: HASH SHA-256
# ==============================================================================
class TestComputeSHA256:
    """Tests para la función de cálculo de hash."""

    def test_hash_deterministic(self, sample_pdf):
        """El hash del mismo archivo siempre es igual."""
        h1 = compute_sha256(sample_pdf)
        h2 = compute_sha256(sample_pdf)
        assert h1 == h2

    def test_hash_is_hex_string(self, sample_pdf):
        """El hash es un string hexadecimal de 64 caracteres."""
        h = compute_sha256(sample_pdf)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_different_files(self, sample_pdf, second_pdf):
        """Archivos diferentes producen hashes diferentes."""
        h1 = compute_sha256(sample_pdf)
        h2 = compute_sha256(second_pdf)
        assert h1 != h2

    def test_hash_file_not_found(self):
        """Archivo inexistente lanza FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            compute_sha256("/ruta/que/no/existe.pdf")


# ==============================================================================
# TESTS: INGESTA
# ==============================================================================
class TestIngest:
    """Tests para el proceso de ingesta."""

    def test_ingest_creates_vault_copy(self, chain, sample_pdf):
        """La ingesta crea una copia en la bóveda."""
        record = chain.ingest(sample_pdf, sinad="EXP-2026-0001")
        assert os.path.exists(record.vault_path)

    def test_ingest_vault_copy_matches_original(self, chain, sample_pdf):
        """La copia en bóveda tiene el mismo hash que el original."""
        record = chain.ingest(sample_pdf, sinad="EXP-2026-0001")
        vault_hash = compute_sha256(record.vault_path)
        assert vault_hash == record.hash_sha256

    def test_ingest_returns_custody_record(self, chain, sample_pdf):
        """La ingesta retorna un CustodyRecord completo."""
        record = chain.ingest(
            sample_pdf,
            sinad="EXP-2026-0001",
            source="test",
            operator="pytest",
            notes="Test de ingesta",
        )
        assert isinstance(record, CustodyRecord)
        assert record.custody_id  # UUID generado
        assert record.sinad == "EXP-2026-0001"
        assert record.original_filename == "expediente_test.pdf"
        assert record.original_size_bytes > 0
        assert record.hash_sha256  # Hash calculado
        assert record.hash_algorithm == HASH_ALGORITHM
        assert record.vault_path  # Ruta de bóveda
        assert record.ingested_at  # Timestamp
        assert record.source == "test"
        assert record.operator == "pytest"
        assert record.notes == "Test de ingesta"

    def test_ingest_writes_jsonl(self, chain, sample_pdf):
        """La ingesta escribe un registro JSONL."""
        chain.ingest(sample_pdf, sinad="EXP-2026-0001")

        assert chain.registry_file.exists()
        with open(chain.registry_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["sinad"] == "EXP-2026-0001"
        assert data["hash_algorithm"] == HASH_ALGORITHM
        assert len(data["hash_sha256"]) == 64

    def test_ingest_multiple_files(self, chain, sample_pdf, second_pdf):
        """Se pueden ingestar múltiples archivos."""
        r1 = chain.ingest(sample_pdf, sinad="EXP-001")
        r2 = chain.ingest(second_pdf, sinad="EXP-002")

        assert r1.custody_id != r2.custody_id
        assert r1.hash_sha256 != r2.hash_sha256

        records = chain.list_records()
        assert len(records) == 2

    def test_ingest_duplicate_rejected(self, chain, sample_pdf):
        """Ingestar el mismo archivo dos veces es rechazado."""
        chain.ingest(sample_pdf, sinad="EXP-001")

        with pytest.raises(ValueError, match="ya registrado"):
            chain.ingest(sample_pdf, sinad="EXP-002")

    def test_ingest_file_not_found(self, chain):
        """Archivo inexistente lanza FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            chain.ingest("/no/existe.pdf", sinad="EXP-001")

    def test_ingest_not_pdf(self, chain, temp_dirs):
        """Archivo no-PDF es rechazado."""
        base, _, _ = temp_dirs
        txt_path = os.path.join(base, "archivo.txt")
        with open(txt_path, "w") as f:
            f.write("no soy un PDF")

        with pytest.raises(ValueError, match="Solo se aceptan archivos PDF"):
            chain.ingest(txt_path, sinad="EXP-001")

    def test_ingest_empty_file(self, chain, temp_dirs):
        """Archivo vacío es rechazado."""
        base, _, _ = temp_dirs
        empty_pdf = os.path.join(base, "vacio.pdf")
        with open(empty_pdf, "wb") as f:
            pass  # 0 bytes

        with pytest.raises(ValueError, match="vacío"):
            chain.ingest(empty_pdf, sinad="EXP-001")

    def test_original_file_untouched(self, chain, sample_pdf):
        """El archivo original NO se modifica ni elimina."""
        hash_before = compute_sha256(sample_pdf)
        chain.ingest(sample_pdf, sinad="EXP-001")
        hash_after = compute_sha256(sample_pdf)
        assert hash_before == hash_after
        assert os.path.exists(sample_pdf)


# ==============================================================================
# TESTS: VERIFICACIÓN
# ==============================================================================
class TestVerify:
    """Tests para verificación de integridad."""

    def test_verify_intact_file(self, chain, sample_pdf):
        """Un archivo no modificado pasa la verificación."""
        record = chain.ingest(sample_pdf, sinad="EXP-001")
        result = chain.verify(record.custody_id)

        assert isinstance(result, VerificationResult)
        assert result.is_intact is True
        assert result.expected_hash == result.actual_hash
        assert result.verified_at  # Timestamp presente
        assert result.error == ""

    def test_verify_tampered_file(self, chain, sample_pdf):
        """Un archivo modificado falla la verificación."""
        record = chain.ingest(sample_pdf, sinad="EXP-001")

        # Alterar el archivo en bóveda (simulando tampering)
        vault_path = Path(record.vault_path)
        # Quitar read-only para poder modificar
        try:
            os.chmod(str(vault_path), 0o644)
        except OSError:
            pass
        with open(vault_path, "ab") as f:
            f.write(b"TAMPERED DATA")

        result = chain.verify(record.custody_id)
        assert result.is_intact is False
        assert result.expected_hash != result.actual_hash

    def test_verify_missing_vault_file(self, chain, sample_pdf):
        """Archivo eliminado de bóveda falla la verificación."""
        record = chain.ingest(sample_pdf, sinad="EXP-001")

        # Eliminar archivo de bóveda
        vault_path = Path(record.vault_path)
        try:
            os.chmod(str(vault_path), 0o644)
        except OSError:
            pass
        vault_path.unlink()

        result = chain.verify(record.custody_id)
        assert result.is_intact is False
        assert "no encontrado" in result.error

    def test_verify_nonexistent_id(self, chain):
        """ID inexistente retorna error."""
        result = chain.verify("id-que-no-existe")
        assert result.is_intact is False
        assert "no encontrado" in result.error

    def test_verify_all(self, chain, sample_pdf, second_pdf):
        """verify_all verifica todos los registros."""
        chain.ingest(sample_pdf, sinad="EXP-001")
        chain.ingest(second_pdf, sinad="EXP-002")

        results = chain.verify_all()
        assert len(results) == 2
        assert all(r.is_intact for r in results)


# ==============================================================================
# TESTS: CONSULTAS
# ==============================================================================
class TestQueries:
    """Tests para funciones de consulta."""

    def test_get_record_by_id(self, chain, sample_pdf):
        """Buscar por custody_id retorna el registro correcto."""
        record = chain.ingest(sample_pdf, sinad="EXP-001")
        found = chain.get_record(record.custody_id)
        assert found is not None
        assert found.sinad == "EXP-001"

    def test_get_record_by_sinad(self, chain, sample_pdf):
        """Buscar por SINAD retorna el registro correcto."""
        chain.ingest(sample_pdf, sinad="EXP-001")
        found = chain.get_record_by_sinad("EXP-001")
        assert found is not None
        assert found.original_filename == "expediente_test.pdf"

    def test_get_record_not_found(self, chain):
        """Buscar ID inexistente retorna None."""
        assert chain.get_record("no-existe") is None
        assert chain.get_record_by_sinad("NO-EXISTE") is None

    def test_list_records_empty(self, chain):
        """Sin registros, list_records retorna lista vacía."""
        assert chain.list_records() == []

    def test_get_stats(self, chain, sample_pdf):
        """get_stats retorna estadísticas correctas."""
        chain.ingest(sample_pdf, sinad="EXP-001")
        stats = chain.get_stats()

        assert stats["total_records"] == 1
        assert stats["total_size_bytes"] > 0
        assert stats["total_size_mb"] >= 0


# ==============================================================================
# TESTS: SERIALIZACIÓN
# ==============================================================================
class TestSerialization:
    """Tests para serialización CustodyRecord."""

    def test_to_dict(self, chain, sample_pdf):
        """to_dict retorna diccionario con todos los campos."""
        record = chain.ingest(sample_pdf, sinad="EXP-001")
        d = record.to_dict()

        assert isinstance(d, dict)
        assert d["sinad"] == "EXP-001"
        assert d["hash_algorithm"] == HASH_ALGORITHM
        assert "custody_id" in d

    def test_to_jsonl_line(self, chain, sample_pdf):
        """to_jsonl_line retorna JSON válido en una línea."""
        record = chain.ingest(sample_pdf, sinad="EXP-001")
        line = record.to_jsonl_line()

        assert "\n" not in line
        data = json.loads(line)
        assert data["sinad"] == "EXP-001"

    def test_from_dict_roundtrip(self, chain, sample_pdf):
        """from_dict reconstuye correctamente desde to_dict."""
        record = chain.ingest(sample_pdf, sinad="EXP-001")
        d = record.to_dict()
        restored = CustodyRecord.from_dict(d)

        assert restored.custody_id == record.custody_id
        assert restored.sinad == record.sinad
        assert restored.hash_sha256 == record.hash_sha256
