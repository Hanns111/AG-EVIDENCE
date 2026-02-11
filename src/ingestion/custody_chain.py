# -*- coding: utf-8 -*-
"""
Cadena de Custodia — Copia inmutable PDF + registro JSONL
==========================================================
Tarea #10 del Plan de Desarrollo (Fase 1: Trazabilidad + OCR)

Garantiza la integridad de cada expediente desde su ingreso:
  1. Copia inmutable del PDF original a bóveda segura
  2. Cálculo de hash SHA-256 como huella digital
  3. Registro en archivo JSONL con metadata completa
  4. Verificación posterior de integridad

Principio: ningún análisis altera el documento original.
El hash calculado al ingreso permite demostrar que el archivo
nunca fue modificado durante todo el proceso de revisión.

Uso:
    from src.ingestion.custody_chain import CustodyChain

    chain = CustodyChain(vault_dir="data/vault")
    registro = chain.ingest(path_pdf="expediente.pdf", sinad="EXP-2026-0001")
    # -> copia inmutable en vault + registro JSONL

    # Verificar integridad después
    es_integro = chain.verify(registro.custody_id)
"""

import hashlib
import json
import os
import shutil
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict


# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
_DEFAULT_VAULT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "vault"
)

_DEFAULT_REGISTRY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "custody_registry"
)

HASH_ALGORITHM = "sha256"
BUFFER_SIZE = 65536  # 64 KB para lectura eficiente de archivos grandes


# ==============================================================================
# DATACLASSES
# ==============================================================================
@dataclass
class CustodyRecord:
    """
    Registro de custodia para un expediente.
    Cada campo es inmutable una vez creado.
    """
    # Identificación
    custody_id: str              # UUID único del registro
    sinad: str                   # Identificador del expediente (SINAD)

    # Archivo original
    original_filename: str       # Nombre del archivo tal como llegó
    original_path: str           # Ruta completa del archivo original
    original_size_bytes: int     # Tamaño en bytes
    original_page_count: int     # Número de páginas (si es PDF)

    # Integridad
    hash_sha256: str             # Hash SHA-256 del archivo original
    hash_algorithm: str = HASH_ALGORITHM

    # Bóveda
    vault_path: str = ""         # Ruta de la copia inmutable en bóveda
    vault_filename: str = ""     # Nombre del archivo en bóveda

    # Timestamps
    ingested_at: str = ""        # ISO-8601 UTC del momento de ingesta

    # Metadata adicional
    source: str = "manual"       # Origen: manual, api, batch
    operator: str = ""           # Quién ejecutó la ingesta
    notes: str = ""              # Notas opcionales

    # Verificación
    verified_at: str = ""        # Última verificación de integridad
    is_verified: bool = False    # Resultado de última verificación

    def to_dict(self) -> Dict:
        """Serializa a diccionario para JSON."""
        return asdict(self)

    def to_jsonl_line(self) -> str:
        """Serializa a línea JSONL (una línea, sin salto al final)."""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    @classmethod
    def from_dict(cls, data: Dict) -> "CustodyRecord":
        """Reconstruye desde diccionario."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class VerificationResult:
    """Resultado de una verificación de integridad."""
    custody_id: str
    is_intact: bool                # True si el hash coincide
    expected_hash: str             # Hash registrado al ingreso
    actual_hash: str               # Hash calculado ahora
    vault_path: str                # Ruta del archivo verificado
    verified_at: str = ""          # Timestamp de verificación
    error: str = ""                # Mensaje de error si falló

    def to_dict(self) -> Dict:
        return asdict(self)


# ==============================================================================
# FUNCIONES DE HASH
# ==============================================================================
def compute_sha256(file_path: str) -> str:
    """
    Calcula el hash SHA-256 de un archivo.

    Lee en bloques de 64KB para soportar archivos grandes
    sin consumir memoria excesiva.

    Args:
        file_path: Ruta absoluta al archivo.

    Returns:
        String hexadecimal del hash SHA-256.

    Raises:
        FileNotFoundError: Si el archivo no existe.
        PermissionError: Si no hay permisos de lectura.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            data = f.read(BUFFER_SIZE)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest()


def _get_pdf_page_count(file_path: str) -> int:
    """
    Obtiene el número de páginas de un PDF.
    Usa PyMuPDF (fitz) si está disponible, sino retorna 0.
    """
    try:
        import fitz  # PyMuPDF
        with fitz.open(file_path) as doc:
            return len(doc)
    except ImportError:
        return 0
    except Exception:
        return 0


# ==============================================================================
# CLASE PRINCIPAL: CustodyChain
# ==============================================================================
class CustodyChain:
    """
    Gestiona la cadena de custodia de expedientes PDF.

    Responsabilidades:
      - Copiar el PDF original a una bóveda inmutable
      - Calcular y almacenar el hash SHA-256
      - Registrar cada ingesta en archivo JSONL
      - Verificar integridad bajo demanda

    Ejemplo:
        chain = CustodyChain()
        record = chain.ingest("expediente.pdf", sinad="EXP-2026-0001")
        result = chain.verify(record.custody_id)
        assert result.is_intact
    """

    def __init__(
        self,
        vault_dir: Optional[str] = None,
        registry_dir: Optional[str] = None,
        registry_filename: str = "custody_log.jsonl",
    ):
        """
        Inicializa la cadena de custodia.

        Args:
            vault_dir: Directorio donde se almacenan las copias inmutables.
            registry_dir: Directorio donde se guarda el registro JSONL.
            registry_filename: Nombre del archivo JSONL de registro.
        """
        self.vault_dir = Path(vault_dir or _DEFAULT_VAULT_DIR)
        self.registry_dir = Path(registry_dir or _DEFAULT_REGISTRY_DIR)
        self.registry_file = self.registry_dir / registry_filename

        # Crear directorios si no existen
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self.registry_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # INGESTA
    # ------------------------------------------------------------------
    def ingest(
        self,
        path_pdf: str,
        sinad: str,
        source: str = "manual",
        operator: str = "",
        notes: str = "",
    ) -> CustodyRecord:
        """
        Ingresa un expediente PDF a la cadena de custodia.

        Pasos:
          1. Valida que el archivo existe y es PDF
          2. Calcula hash SHA-256 del original
          3. Genera ID de custodia único
          4. Copia el archivo a la bóveda con nombre basado en custody_id
          5. Verifica que la copia es idéntica (hash)
          6. Registra en JSONL

        Args:
            path_pdf: Ruta al archivo PDF a ingestar.
            sinad: Identificador SINAD del expediente.
            source: Origen de la ingesta (manual, api, batch).
            operator: Identificador del operador.
            notes: Notas opcionales.

        Returns:
            CustodyRecord con todos los datos del registro.

        Raises:
            FileNotFoundError: Si el PDF no existe.
            ValueError: Si el archivo no es PDF o está vacío.
            RuntimeError: Si la copia en bóveda falla la verificación.
        """
        path = Path(path_pdf).resolve()

        # --- Validaciones ---
        if not path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {path}")

        if not path.is_file():
            raise ValueError(f"No es un archivo válido: {path}")

        if path.suffix.lower() != ".pdf":
            raise ValueError(
                f"Solo se aceptan archivos PDF. Recibido: {path.suffix}"
            )

        file_size = path.stat().st_size
        if file_size == 0:
            raise ValueError(f"Archivo vacío: {path}")

        # --- Generar identificadores ---
        custody_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        # --- Hash del original ---
        original_hash = compute_sha256(str(path))

        # --- Verificar duplicados ---
        existing = self._find_by_hash(original_hash)
        if existing:
            raise ValueError(
                f"Archivo ya registrado. custody_id existente: {existing.custody_id}, "
                f"sinad: {existing.sinad}, ingresado: {existing.ingested_at}"
            )

        # --- Página count ---
        page_count = _get_pdf_page_count(str(path))

        # --- Copiar a bóveda ---
        vault_filename = f"{custody_id}.pdf"
        vault_path = self.vault_dir / vault_filename
        shutil.copy2(str(path), str(vault_path))

        # --- Verificar copia ---
        vault_hash = compute_sha256(str(vault_path))
        if vault_hash != original_hash:
            # Eliminar copia corrupta
            vault_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"La copia en bóveda NO coincide con el original. "
                f"Original: {original_hash}, Copia: {vault_hash}"
            )

        # --- Hacer la copia read-only ---
        try:
            os.chmod(str(vault_path), 0o444)
        except OSError:
            pass  # En algunos sistemas (Windows) puede fallar

        # --- Crear registro ---
        record = CustodyRecord(
            custody_id=custody_id,
            sinad=sinad,
            original_filename=path.name,
            original_path=str(path),
            original_size_bytes=file_size,
            original_page_count=page_count,
            hash_sha256=original_hash,
            hash_algorithm=HASH_ALGORITHM,
            vault_path=str(vault_path),
            vault_filename=vault_filename,
            ingested_at=timestamp,
            source=source,
            operator=operator,
            notes=notes,
        )

        # --- Escribir en JSONL ---
        self._append_record(record)

        return record

    # ------------------------------------------------------------------
    # VERIFICACIÓN
    # ------------------------------------------------------------------
    def verify(self, custody_id: str) -> VerificationResult:
        """
        Verifica la integridad de un archivo en la bóveda.

        Compara el hash SHA-256 actual del archivo en bóveda
        con el hash registrado al momento de la ingesta.

        Args:
            custody_id: ID de custodia del registro a verificar.

        Returns:
            VerificationResult con el resultado de la verificación.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # Buscar registro
        record = self.get_record(custody_id)
        if record is None:
            return VerificationResult(
                custody_id=custody_id,
                is_intact=False,
                expected_hash="",
                actual_hash="",
                vault_path="",
                verified_at=timestamp,
                error=f"Registro no encontrado: {custody_id}",
            )

        vault_path = Path(record.vault_path)
        if not vault_path.exists():
            return VerificationResult(
                custody_id=custody_id,
                is_intact=False,
                expected_hash=record.hash_sha256,
                actual_hash="",
                vault_path=str(vault_path),
                verified_at=timestamp,
                error=f"Archivo en bóveda no encontrado: {vault_path}",
            )

        # Calcular hash actual
        try:
            actual_hash = compute_sha256(str(vault_path))
        except Exception as e:
            return VerificationResult(
                custody_id=custody_id,
                is_intact=False,
                expected_hash=record.hash_sha256,
                actual_hash="",
                vault_path=str(vault_path),
                verified_at=timestamp,
                error=f"Error al calcular hash: {e}",
            )

        is_intact = actual_hash == record.hash_sha256

        result = VerificationResult(
            custody_id=custody_id,
            is_intact=is_intact,
            expected_hash=record.hash_sha256,
            actual_hash=actual_hash,
            vault_path=str(vault_path),
            verified_at=timestamp,
        )

        # Actualizar registro con resultado de verificación
        self._update_verification(custody_id, timestamp, is_intact)

        return result

    def verify_all(self) -> List[VerificationResult]:
        """
        Verifica la integridad de TODOS los archivos en la bóveda.

        Returns:
            Lista de VerificationResult, uno por cada registro.
        """
        records = self.list_records()
        results = []
        for record in records:
            result = self.verify(record.custody_id)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # CONSULTAS
    # ------------------------------------------------------------------
    def get_record(self, custody_id: str) -> Optional[CustodyRecord]:
        """Busca un registro por custody_id."""
        for record in self._read_all_records():
            if record.custody_id == custody_id:
                return record
        return None

    def get_record_by_sinad(self, sinad: str) -> Optional[CustodyRecord]:
        """Busca un registro por SINAD."""
        for record in self._read_all_records():
            if record.sinad == sinad:
                return record
        return None

    def list_records(self) -> List[CustodyRecord]:
        """Lista todos los registros de custodia."""
        return self._read_all_records()

    def get_stats(self) -> Dict:
        """
        Retorna estadísticas del registro de custodia.

        Returns:
            Dict con total, verified, pending, size_total, etc.
        """
        records = self._read_all_records()
        total_size = sum(r.original_size_bytes for r in records)
        verified = sum(1 for r in records if r.is_verified)

        return {
            "total_records": len(records),
            "verified_count": verified,
            "pending_verification": len(records) - verified,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "vault_dir": str(self.vault_dir),
            "registry_file": str(self.registry_file),
        }

    # ------------------------------------------------------------------
    # INTERNOS
    # ------------------------------------------------------------------
    def _append_record(self, record: CustodyRecord) -> None:
        """Agrega un registro al archivo JSONL."""
        with open(self.registry_file, "a", encoding="utf-8") as f:
            f.write(record.to_jsonl_line() + "\n")

    def _read_all_records(self) -> List[CustodyRecord]:
        """Lee todos los registros del archivo JSONL."""
        records = []
        if not self.registry_file.exists():
            return records

        with open(self.registry_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    records.append(CustodyRecord.from_dict(data))
                except (json.JSONDecodeError, TypeError) as e:
                    # Log pero no detener la lectura
                    pass

        return records

    def _find_by_hash(self, hash_sha256: str) -> Optional[CustodyRecord]:
        """Busca si un hash ya fue registrado (detección de duplicados)."""
        for record in self._read_all_records():
            if record.hash_sha256 == hash_sha256:
                return record
        return None

    def _update_verification(
        self, custody_id: str, timestamp: str, is_verified: bool
    ) -> None:
        """
        Actualiza el registro de verificación.
        Reescribe el JSONL completo (operación atómica con archivo temporal).
        """
        records = self._read_all_records()
        updated = False

        for record in records:
            if record.custody_id == custody_id:
                record.verified_at = timestamp
                record.is_verified = is_verified
                updated = True
                break

        if updated:
            # Escritura atómica: escribir a temporal y renombrar
            tmp_file = self.registry_file.with_suffix(".jsonl.tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                for record in records:
                    f.write(record.to_jsonl_line() + "\n")

            # Renombrar (atómico en la mayoría de sistemas)
            tmp_file.replace(self.registry_file)

    # ------------------------------------------------------------------
    # REPRESENTACIÓN
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"CustodyChain("
            f"records={stats['total_records']}, "
            f"vault='{self.vault_dir}', "
            f"size={stats['total_size_mb']}MB)"
        )
