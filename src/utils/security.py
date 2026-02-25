# -*- coding: utf-8 -*-
"""
Utilidades de Seguridad — AG-EVIDENCE
======================================
Funciones centralizadas de seguridad para todo el pipeline.

Controles implementados:
  - SEC-INP-002: Validacion de paths contra traversal
  - SEC-TMP-001: Limpieza automatica de archivos temporales
  - SEC-INP-003: Validacion de tamano de JSON
  - Constantes de seguridad centralizadas

Alineamiento: NIST CSF PR.DS, CISA Secure by Design, NIS2 Art.21

Version: 1.0.0
Fecha: 2026-02-19
"""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTES DE SEGURIDAD
# =============================================================================

# Tamano maximo de JSON que el sistema acepta deserializar (50 MB)
TAMANIO_MAX_JSON_BYTES: int = 50 * 1024 * 1024

# Extensiones permitidas para archivos de entrada
EXTENSIONES_PDF_PERMITIDAS: frozenset = frozenset({".pdf"})
EXTENSIONES_IMAGEN_PERMITIDAS: frozenset = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".tiff",
        ".tif",
        ".bmp",
    }
)

# Longitud maxima de ruta de archivo (previene paths excesivamente largos)
LONGITUD_MAX_RUTA: int = 500

# Prefijos peligrosos en paths
_PREFIJOS_PELIGROSOS = ("..", "~")

# Caracteres no permitidos en nombres de archivo (cross-platform)
_CARACTERES_PROHIBIDOS = set("\x00")


# =============================================================================
# EXCEPCIONES
# =============================================================================


class RutaInseguraError(ValueError):
    """
    Excepcion lanzada cuando una ruta de archivo no pasa
    las validaciones de seguridad.

    SEC-INP-002: Proteccion contra path traversal.
    """

    pass


# =============================================================================
# VALIDACION DE PATHS (SEC-INP-002)
# =============================================================================


def validar_ruta_segura(
    ruta: Union[str, Path],
    directorio_base: Optional[Union[str, Path]] = None,
    extensiones_permitidas: Optional[frozenset] = None,
) -> Path:
    """
    Valida que una ruta de archivo sea segura contra path traversal
    y otros ataques basados en rutas.

    Args:
        ruta: Ruta del archivo a validar.
        directorio_base: Si se proporciona, la ruta resuelta debe estar
            dentro de este directorio (containment check).
        extensiones_permitidas: Si se proporciona, la extension del archivo
            debe estar en este conjunto.

    Returns:
        Path: Ruta resuelta y validada.

    Raises:
        RutaInseguraError: Si la ruta no pasa alguna validacion.

    Ejemplo:
        >>> validar_ruta_segura("data/expedientes/doc.pdf", directorio_base="data/")
        PosixPath('/abs/path/data/expedientes/doc.pdf')

        >>> validar_ruta_segura("../../etc/passwd")
        RutaInseguraError: Ruta contiene componentes de traversal: ...
    """
    if not ruta:
        raise RutaInseguraError("Ruta vacia no permitida")

    ruta_str = str(ruta)

    # --- Verificar longitud ---
    if len(ruta_str) > LONGITUD_MAX_RUTA:
        raise RutaInseguraError(
            f"Ruta excede longitud maxima ({len(ruta_str)} > {LONGITUD_MAX_RUTA}): "
            f"{ruta_str[:80]}..."
        )

    # --- Verificar caracteres nulos (null byte injection) ---
    if "\x00" in ruta_str:
        raise RutaInseguraError(
            f"Ruta contiene caracteres nulos (null byte): {repr(ruta_str[:80])}"
        )

    # --- Verificar componentes de traversal ---
    ruta_path = Path(ruta_str)
    partes = ruta_path.parts

    for parte in partes:
        if parte == "..":
            raise RutaInseguraError(f"Ruta contiene componentes de traversal (..): {ruta_str}")
        # Verificar caracteres prohibidos en cada componente
        if any(c in parte for c in _CARACTERES_PROHIBIDOS):
            raise RutaInseguraError(f"Ruta contiene caracteres prohibidos: {repr(parte)}")

    # --- Containment check contra directorio base ---
    if directorio_base is not None:
        base_resuelta = Path(directorio_base).resolve()
        ruta_resuelta = ruta_path.resolve()

        # Verificar que la ruta resuelta esta dentro del directorio base
        try:
            ruta_resuelta.relative_to(base_resuelta)
        except ValueError:
            raise RutaInseguraError(
                f"Ruta resuelta esta fuera del directorio base: "
                f"ruta={ruta_resuelta}, base={base_resuelta}"
            )

    # --- Verificar extension ---
    if extensiones_permitidas is not None:
        extension = ruta_path.suffix.lower()
        if extension not in extensiones_permitidas:
            raise RutaInseguraError(
                f"Extension no permitida: {extension}. Permitidas: {sorted(extensiones_permitidas)}"
            )

    # Retornar ruta resuelta
    return ruta_path.resolve() if directorio_base else ruta_path


def validar_ruta_pdf(
    ruta: Union[str, Path],
    directorio_base: Optional[Union[str, Path]] = None,
) -> Path:
    """
    Atajo para validar una ruta que debe ser un archivo PDF.

    Args:
        ruta: Ruta al PDF.
        directorio_base: Directorio contenedor opcional.

    Returns:
        Path validada.
    """
    return validar_ruta_segura(
        ruta,
        directorio_base=directorio_base,
        extensiones_permitidas=EXTENSIONES_PDF_PERMITIDAS,
    )


def validar_ruta_imagen(
    ruta: Union[str, Path],
    directorio_base: Optional[Union[str, Path]] = None,
) -> Path:
    """
    Atajo para validar una ruta que debe ser un archivo de imagen.

    Args:
        ruta: Ruta a la imagen.
        directorio_base: Directorio contenedor opcional.

    Returns:
        Path validada.
    """
    return validar_ruta_segura(
        ruta,
        directorio_base=directorio_base,
        extensiones_permitidas=EXTENSIONES_IMAGEN_PERMITIDAS,
    )


# =============================================================================
# LIMPIEZA DE ARCHIVOS TEMPORALES (SEC-TMP-001)
# =============================================================================


class DirectorioTemporalSeguro:
    """
    Context manager para directorios temporales con limpieza garantizada.

    Crea un directorio temporal que se elimina automaticamente al salir
    del bloque `with`, incluso si ocurre una excepcion.

    SEC-TMP-001: Garantiza que archivos temporales con datos potencialmente
    sensibles (paginas OCR renderizadas, etc.) no persistan en disco.

    Uso:
        with DirectorioTemporalSeguro(prefijo="ocr_") as tmp_dir:
            img_path = tmp_dir / "pagina_1.png"
            img.save(str(img_path))
            # ... procesar imagen ...
        # tmp_dir y todo su contenido eliminado automaticamente

    Args:
        prefijo: Prefijo para el nombre del directorio temporal.
        directorio_padre: Directorio donde crear el temporal.
            Si es None, usa el directorio temporal del sistema.
        mantener_en_error: Si True, no eliminar en caso de excepcion
            (util para debugging). Default: False.
    """

    def __init__(
        self,
        prefijo: str = "ag_evidence_",
        directorio_padre: Optional[Union[str, Path]] = None,
        mantener_en_error: bool = False,
    ):
        self.prefijo = prefijo
        self.directorio_padre = str(directorio_padre) if directorio_padre else None
        self.mantener_en_error = mantener_en_error
        self._ruta: Optional[Path] = None
        self._archivos_creados: int = 0

    def __enter__(self) -> Path:
        self._ruta = Path(
            tempfile.mkdtemp(
                prefix=self.prefijo,
                dir=self.directorio_padre,
            )
        )
        logger.debug(f"Directorio temporal creado: {self._ruta}")
        return self._ruta

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._ruta is None:
            return False

        # Contar archivos antes de limpiar (para logging)
        if self._ruta.exists():
            self._archivos_creados = sum(1 for _ in self._ruta.rglob("*") if _.is_file())

        # Si hay excepcion y mantener_en_error, no limpiar
        if exc_type is not None and self.mantener_en_error:
            logger.warning(
                f"Directorio temporal NO eliminado (mantener_en_error=True): "
                f"{self._ruta} ({self._archivos_creados} archivos)"
            )
            return False

        # Limpiar
        try:
            if self._ruta.exists():
                shutil.rmtree(str(self._ruta))
                logger.debug(
                    f"Directorio temporal eliminado: {self._ruta} "
                    f"({self._archivos_creados} archivos limpiados)"
                )
        except OSError as e:
            logger.error(f"Error al eliminar directorio temporal {self._ruta}: {e}")

        return False  # No suprimir excepciones

    @property
    def ruta(self) -> Optional[Path]:
        """Ruta del directorio temporal, o None si no esta activo."""
        return self._ruta

    @property
    def archivos_creados(self) -> int:
        """Numero de archivos creados en el directorio temporal."""
        if self._ruta and self._ruta.exists():
            return sum(1 for _ in self._ruta.rglob("*") if _.is_file())
        return self._archivos_creados


def limpiar_directorio_temporal(directorio: Union[str, Path]) -> int:
    """
    Elimina todos los archivos de un directorio temporal especifico.

    Util para limpieza manual de directorios temporales que no
    fueron gestionados con DirectorioTemporalSeguro.

    Args:
        directorio: Ruta del directorio a limpiar.

    Returns:
        Numero de archivos eliminados.

    Raises:
        RutaInseguraError: Si la ruta contiene componentes de traversal.
    """
    dir_path = Path(directorio)

    # Validacion basica de seguridad
    if ".." in dir_path.parts:
        raise RutaInseguraError(f"No se permite limpiar directorio con traversal: {directorio}")

    if not dir_path.exists():
        return 0

    if not dir_path.is_dir():
        raise RutaInseguraError(f"La ruta no es un directorio: {directorio}")

    archivos_eliminados = 0
    for archivo in dir_path.rglob("*"):
        if archivo.is_file():
            try:
                archivo.unlink()
                archivos_eliminados += 1
            except OSError as e:
                logger.error(f"Error al eliminar {archivo}: {e}")

    logger.info(
        f"Limpieza de directorio temporal: {archivos_eliminados} archivos "
        f"eliminados de {directorio}"
    )

    return archivos_eliminados


# =============================================================================
# VALIDACION DE JSON (SEC-INP-003)
# =============================================================================


def validar_json_tamano(json_str: str, max_bytes: int = TAMANIO_MAX_JSON_BYTES) -> None:
    """
    Valida que un string JSON no exceda el tamano maximo permitido.

    SEC-INP-003: Previene ataques de denegacion de servicio por
    JSON excesivamente grandes.

    Args:
        json_str: String JSON a validar.
        max_bytes: Tamano maximo en bytes.

    Raises:
        ValueError: Si el JSON excede el tamano permitido.
    """
    tamano = len(json_str.encode("utf-8"))
    if tamano > max_bytes:
        raise ValueError(
            f"JSON excede tamano maximo: {tamano:,} bytes > "
            f"{max_bytes:,} bytes ({max_bytes // (1024 * 1024)} MB)"
        )


def validar_expediente_json_estructura(data: dict) -> list:
    """
    Valida la estructura basica de un diccionario de ExpedienteJSON.

    Verifica que los campos obligatorios existan y tengan el tipo correcto.
    NO valida el contenido de cada campo (eso lo hace el contrato tipado).

    Args:
        data: Diccionario deserializado de JSON.

    Returns:
        Lista de errores encontrados (vacia si todo OK).
    """
    errores = []

    # Campos obligatorios de nivel superior
    campos_obligatorios = {
        "version_contrato": str,
        "expediente_id": str,
        "archivos_fuente": list,
        "comprobantes": list,
        "resumen_extraccion": dict,
        "integridad": dict,
    }

    for campo, tipo_esperado in campos_obligatorios.items():
        if campo not in data:
            errores.append(f"Campo obligatorio ausente: '{campo}'")
        elif not isinstance(data[campo], tipo_esperado):
            errores.append(
                f"Tipo incorrecto para '{campo}': "
                f"esperado {tipo_esperado.__name__}, "
                f"encontrado {type(data[campo]).__name__}"
            )

    # Validar estructura de integridad
    if "integridad" in data and isinstance(data["integridad"], dict):
        integridad = data["integridad"]
        for sub_campo in ["hash_expediente", "timestamp_verificacion"]:
            if sub_campo not in integridad:
                errores.append(f"Campo obligatorio ausente en integridad: '{sub_campo}'")

    # Validar que archivos_fuente tenga al menos un elemento
    if isinstance(data.get("archivos_fuente"), list) and len(data["archivos_fuente"]) == 0:
        errores.append("archivos_fuente esta vacio (se requiere al menos un archivo)")

    return errores
