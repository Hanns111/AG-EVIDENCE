# -*- coding: utf-8 -*-
"""
Tests para src/utils/security.py — Utilidades de Seguridad
============================================================
Cubre:
  - SEC-INP-002: Validacion de paths contra traversal
  - SEC-TMP-001: Limpieza automatica de archivos temporales
  - SEC-INP-003: Validacion de tamano de JSON
  - Validacion de estructura de ExpedienteJSON
"""

import json
from pathlib import Path

import pytest

from src.utils.security import (
    EXTENSIONES_IMAGEN_PERMITIDAS,
    EXTENSIONES_PDF_PERMITIDAS,
    LONGITUD_MAX_RUTA,
    TAMANIO_MAX_JSON_BYTES,
    DirectorioTemporalSeguro,
    RutaInseguraError,
    limpiar_directorio_temporal,
    validar_expediente_json_estructura,
    validar_json_tamano,
    validar_ruta_imagen,
    validar_ruta_pdf,
    validar_ruta_segura,
)

# =============================================================================
# CONSTANTES
# =============================================================================


class TestConstantes:
    """Verifica que las constantes de seguridad esten definidas correctamente."""

    def test_tamanio_max_json_es_50mb(self):
        assert TAMANIO_MAX_JSON_BYTES == 50 * 1024 * 1024

    def test_extensiones_pdf(self):
        assert ".pdf" in EXTENSIONES_PDF_PERMITIDAS
        assert len(EXTENSIONES_PDF_PERMITIDAS) == 1

    def test_extensiones_imagen(self):
        assert ".png" in EXTENSIONES_IMAGEN_PERMITIDAS
        assert ".jpg" in EXTENSIONES_IMAGEN_PERMITIDAS
        assert ".jpeg" in EXTENSIONES_IMAGEN_PERMITIDAS
        assert ".tiff" in EXTENSIONES_IMAGEN_PERMITIDAS
        assert ".tif" in EXTENSIONES_IMAGEN_PERMITIDAS
        assert ".bmp" in EXTENSIONES_IMAGEN_PERMITIDAS
        # No debe incluir extensiones peligrosas
        assert ".exe" not in EXTENSIONES_IMAGEN_PERMITIDAS
        assert ".py" not in EXTENSIONES_IMAGEN_PERMITIDAS

    def test_longitud_max_ruta(self):
        assert LONGITUD_MAX_RUTA == 500

    def test_extensiones_son_frozenset(self):
        """frozenset previene modificacion accidental."""
        assert isinstance(EXTENSIONES_PDF_PERMITIDAS, frozenset)
        assert isinstance(EXTENSIONES_IMAGEN_PERMITIDAS, frozenset)


# =============================================================================
# VALIDACION DE PATHS (SEC-INP-002)
# =============================================================================


class TestValidarRutaSegura:
    """Tests para validacion de rutas contra path traversal."""

    def test_ruta_simple_valida(self):
        result = validar_ruta_segura("data/expedientes/doc.pdf")
        assert isinstance(result, Path)

    def test_ruta_vacia_rechazada(self):
        with pytest.raises(RutaInseguraError, match="vacia"):
            validar_ruta_segura("")

    def test_ruta_none_rechazada(self):
        with pytest.raises((RutaInseguraError, TypeError)):
            validar_ruta_segura(None)

    def test_traversal_punto_punto_rechazado(self):
        with pytest.raises(RutaInseguraError, match="traversal"):
            validar_ruta_segura("../../etc/passwd")

    def test_traversal_medio_de_ruta_rechazado(self):
        with pytest.raises(RutaInseguraError, match="traversal"):
            validar_ruta_segura("data/../../../etc/shadow")

    def test_null_byte_rechazado(self):
        with pytest.raises(RutaInseguraError, match="nulos"):
            validar_ruta_segura("data/expediente\x00.pdf")

    def test_ruta_excede_longitud_maxima(self):
        ruta_larga = "a/" * 300 + "file.pdf"
        with pytest.raises(RutaInseguraError, match="longitud maxima"):
            validar_ruta_segura(ruta_larga)

    def test_containment_check_dentro_de_base(self, tmp_path):
        # Crear archivo dentro del directorio base
        subdir = tmp_path / "data"
        subdir.mkdir()
        archivo = subdir / "test.pdf"
        archivo.touch()

        result = validar_ruta_segura(
            str(archivo),
            directorio_base=str(tmp_path),
        )
        assert result == archivo.resolve()

    def test_containment_check_fuera_de_base(self, tmp_path):
        with pytest.raises(RutaInseguraError, match="fuera del directorio base"):
            validar_ruta_segura(
                "/etc/passwd",
                directorio_base=str(tmp_path),
            )

    def test_extension_permitida(self):
        result = validar_ruta_segura(
            "doc.pdf",
            extensiones_permitidas=frozenset({".pdf"}),
        )
        assert result.suffix == ".pdf"

    def test_extension_no_permitida(self):
        with pytest.raises(RutaInseguraError, match="Extension no permitida"):
            validar_ruta_segura(
                "script.exe",
                extensiones_permitidas=frozenset({".pdf"}),
            )

    def test_extension_case_insensitive(self):
        result = validar_ruta_segura(
            "DOC.PDF",
            extensiones_permitidas=frozenset({".pdf"}),
        )
        assert isinstance(result, Path)

    def test_ruta_con_espacios_valida(self):
        result = validar_ruta_segura("data/mis documentos/archivo con espacios.pdf")
        assert isinstance(result, Path)

    def test_ruta_absoluta_valida(self, tmp_path):
        archivo = tmp_path / "test.pdf"
        archivo.touch()
        result = validar_ruta_segura(str(archivo))
        assert isinstance(result, Path)

    def test_ruta_path_object(self):
        result = validar_ruta_segura(Path("data/test.pdf"))
        assert isinstance(result, Path)


class TestValidarRutaPdf:
    """Tests para atajo de validacion de PDF."""

    def test_pdf_valido(self):
        result = validar_ruta_pdf("expediente.pdf")
        assert result.suffix == ".pdf"

    def test_no_pdf_rechazado(self):
        with pytest.raises(RutaInseguraError, match="Extension"):
            validar_ruta_pdf("documento.docx")

    def test_traversal_rechazado(self):
        with pytest.raises(RutaInseguraError, match="traversal"):
            validar_ruta_pdf("../../etc/passwd.pdf")


class TestValidarRutaImagen:
    """Tests para atajo de validacion de imagen."""

    def test_png_valido(self):
        result = validar_ruta_imagen("pagina.png")
        assert result.suffix == ".png"

    def test_jpg_valido(self):
        result = validar_ruta_imagen("foto.jpg")
        assert result.suffix == ".jpg"

    def test_tiff_valido(self):
        result = validar_ruta_imagen("scan.tiff")
        assert result.suffix == ".tiff"

    def test_no_imagen_rechazada(self):
        with pytest.raises(RutaInseguraError):
            validar_ruta_imagen("script.py")


# =============================================================================
# DIRECTORIO TEMPORAL SEGURO (SEC-TMP-001)
# =============================================================================


class TestDirectorioTemporalSeguro:
    """Tests para limpieza automatica de archivos temporales."""

    def test_crea_directorio_temporal(self):
        with DirectorioTemporalSeguro() as tmp_dir:
            assert tmp_dir.exists()
            assert tmp_dir.is_dir()

    def test_elimina_directorio_al_salir(self):
        ruta_guardada = None
        with DirectorioTemporalSeguro() as tmp_dir:
            ruta_guardada = tmp_dir
            # Crear archivos dentro
            (tmp_dir / "test1.png").write_text("fake image data")
            (tmp_dir / "test2.txt").write_text("metadata")
        # Verificar que se elimino
        assert not ruta_guardada.exists()

    def test_elimina_archivos_en_excepcion(self):
        ruta_guardada = None
        try:
            with DirectorioTemporalSeguro() as tmp_dir:
                ruta_guardada = tmp_dir
                (tmp_dir / "sensitive.png").write_text("datos sensibles")
                raise ValueError("Error simulado")
        except ValueError:
            pass
        # Debe haberse eliminado a pesar de la excepcion
        assert not ruta_guardada.exists()

    def test_mantener_en_error(self):
        ruta_guardada = None
        try:
            with DirectorioTemporalSeguro(mantener_en_error=True) as tmp_dir:
                ruta_guardada = tmp_dir
                (tmp_dir / "debug.log").write_text("debug info")
                raise ValueError("Error para debug")
        except ValueError:
            pass
        # Debe haberse MANTENIDO porque mantener_en_error=True
        assert ruta_guardada.exists()
        # Limpiar manualmente
        import shutil

        shutil.rmtree(str(ruta_guardada))

    def test_prefijo_personalizado(self):
        with DirectorioTemporalSeguro(prefijo="ocr_test_") as tmp_dir:
            assert "ocr_test_" in tmp_dir.name

    def test_directorio_padre_personalizado(self, tmp_path):
        with DirectorioTemporalSeguro(directorio_padre=tmp_path) as tmp_dir:
            assert str(tmp_path) in str(tmp_dir)
            assert tmp_dir.exists()

    def test_property_ruta(self):
        ctx = DirectorioTemporalSeguro()
        assert ctx.ruta is None  # Antes de entrar
        with ctx as tmp_dir:
            assert ctx.ruta == tmp_dir
            assert ctx.ruta.exists()

    def test_property_archivos_creados(self):
        with DirectorioTemporalSeguro() as tmp_dir:
            (tmp_dir / "a.txt").write_text("a")
            (tmp_dir / "b.txt").write_text("b")
            (tmp_dir / "c.txt").write_text("c")
            ctx = DirectorioTemporalSeguro.__new__(DirectorioTemporalSeguro)
            ctx._ruta = tmp_dir
            ctx._archivos_creados = 0
            assert ctx.archivos_creados == 3

    def test_multiples_archivos_y_subdirectorios(self):
        ruta_guardada = None
        with DirectorioTemporalSeguro() as tmp_dir:
            ruta_guardada = tmp_dir
            sub = tmp_dir / "subdir"
            sub.mkdir()
            (tmp_dir / "file1.png").write_text("data1")
            (sub / "file2.png").write_text("data2")
            (sub / "file3.txt").write_text("data3")
        assert not ruta_guardada.exists()


class TestLimpiarDirectorioTemporal:
    """Tests para limpieza manual de directorios temporales."""

    def test_limpia_archivos(self, tmp_path):
        # Crear archivos
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.png").write_text("b")

        eliminados = limpiar_directorio_temporal(tmp_path)
        assert eliminados == 2

    def test_directorio_inexistente_retorna_cero(self, tmp_path):
        eliminados = limpiar_directorio_temporal(tmp_path / "no_existe")
        assert eliminados == 0

    def test_traversal_rechazado(self):
        with pytest.raises(RutaInseguraError, match="traversal"):
            limpiar_directorio_temporal("../../tmp")

    def test_no_directorio_rechazado(self, tmp_path):
        archivo = tmp_path / "file.txt"
        archivo.write_text("test")
        with pytest.raises(RutaInseguraError, match="no es un directorio"):
            limpiar_directorio_temporal(archivo)


# =============================================================================
# VALIDACION DE JSON (SEC-INP-003)
# =============================================================================


class TestValidarJsonTamano:
    """Tests para limites de tamano de JSON."""

    def test_json_pequeno_ok(self):
        json_str = json.dumps({"expediente": "test", "datos": [1, 2, 3]})
        validar_json_tamano(json_str)  # No debe lanzar excepcion

    def test_json_excede_limite(self):
        # Crear string grande (60 MB)
        json_str = "x" * (60 * 1024 * 1024)
        with pytest.raises(ValueError, match="excede tamano maximo"):
            validar_json_tamano(json_str)

    def test_limite_personalizado(self):
        json_str = "x" * 1000
        with pytest.raises(ValueError, match="excede tamano maximo"):
            validar_json_tamano(json_str, max_bytes=500)

    def test_json_exactamente_en_limite(self):
        json_str = "x" * 100
        validar_json_tamano(json_str, max_bytes=100)  # No debe lanzar

    def test_json_unicode_tamano_en_bytes(self):
        # Caracteres unicode pueden ser mas de 1 byte
        json_str = "\u00e9" * 50  # e con acento (2 bytes en UTF-8)
        # 50 caracteres * 2 bytes = 100 bytes
        validar_json_tamano(json_str, max_bytes=100)  # Exactamente en limite


# =============================================================================
# VALIDACION DE ESTRUCTURA EXPEDIENTE JSON
# =============================================================================


class TestValidarExpedienteJsonEstructura:
    """Tests para validacion de estructura basica de ExpedienteJSON."""

    def _crear_estructura_valida(self):
        return {
            "version_contrato": "1.0.0",
            "expediente_id": "TEST-001",
            "naturaleza_expediente": "VIATICOS",
            "archivos_fuente": [{"nombre": "doc.pdf"}],
            "comprobantes": [],
            "declaracion_jurada": [],
            "boletos": [],
            "resumen_extraccion": {"total_campos": 0},
            "integridad": {
                "hash_expediente": "abc123",
                "timestamp_verificacion": "2026-02-19T00:00:00Z",
            },
        }

    def test_estructura_valida_sin_errores(self):
        data = self._crear_estructura_valida()
        errores = validar_expediente_json_estructura(data)
        assert errores == []

    def test_campo_obligatorio_ausente(self):
        data = self._crear_estructura_valida()
        del data["version_contrato"]
        errores = validar_expediente_json_estructura(data)
        assert any("version_contrato" in e for e in errores)

    def test_tipo_incorrecto(self):
        data = self._crear_estructura_valida()
        data["comprobantes"] = "no es lista"
        errores = validar_expediente_json_estructura(data)
        assert any("Tipo incorrecto" in e for e in errores)

    def test_integridad_sin_hash(self):
        data = self._crear_estructura_valida()
        del data["integridad"]["hash_expediente"]
        errores = validar_expediente_json_estructura(data)
        assert any("hash_expediente" in e for e in errores)

    def test_integridad_sin_timestamp(self):
        data = self._crear_estructura_valida()
        del data["integridad"]["timestamp_verificacion"]
        errores = validar_expediente_json_estructura(data)
        assert any("timestamp_verificacion" in e for e in errores)

    def test_archivos_fuente_vacio(self):
        data = self._crear_estructura_valida()
        data["archivos_fuente"] = []
        errores = validar_expediente_json_estructura(data)
        assert any("archivos_fuente esta vacio" in e for e in errores)

    def test_multiples_errores(self):
        data = {}  # Todos los campos faltantes
        errores = validar_expediente_json_estructura(data)
        assert len(errores) >= 5  # Al menos los campos obligatorios

    def test_campos_extra_no_causan_error(self):
        data = self._crear_estructura_valida()
        data["campo_extra_futuro"] = "valor"
        errores = validar_expediente_json_estructura(data)
        assert errores == []


# =============================================================================
# EXCEPCIONES
# =============================================================================


class TestRutaInseguraError:
    """Tests para la excepcion personalizada."""

    def test_es_subclase_de_value_error(self):
        assert issubclass(RutaInseguraError, ValueError)

    def test_mensaje_descriptivo(self):
        error = RutaInseguraError("Path traversal detectado: ../../etc/passwd")
        assert "traversal" in str(error)

    def test_captura_con_value_error(self):
        """Debe ser capturable como ValueError para compatibilidad."""
        with pytest.raises(ValueError):
            raise RutaInseguraError("test")
