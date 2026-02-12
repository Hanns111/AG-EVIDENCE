# -*- coding: utf-8 -*-
"""
Tests para src/ocr/core.py — Motor OCR PaddleOCR + Tesseract
=============================================================
Tarea #13: Validacion completa del core OCR reescrito.

Estrategia:
- unittest.mock.patch para mockear imports de PaddleOCR y pytesseract
- PIL.Image.new para imagenes sinteticas
- pytest.mark.skipif para tests que requieren motores reales
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Importar modulo bajo test
from src.ocr import core


# =============================================================================
# Helpers
# =============================================================================

try:
    from PIL import Image as _PILImage
    _PIL_DISPONIBLE = True
except ImportError:
    _PILImage = None
    _PIL_DISPONIBLE = False


def _create_white_image(width=200, height=200):
    """Crea una imagen blanca sintetica para testing."""
    if _PIL_DISPONIBLE:
        return _PILImage.new("RGB", (width, height), "white")
    return None


def _create_mock_image():
    """Crea un mock de imagen para tests que no necesitan PIL real."""
    mock_img = MagicMock()
    mock_img.width = 200
    mock_img.height = 200
    mock_img.mode = "RGB"
    mock_img.convert.return_value = mock_img
    return mock_img


def _get_image_or_mock():
    """Retorna imagen real si PIL disponible, sino un mock."""
    img = _create_white_image()
    if img is not None:
        return img
    return _create_mock_image()


# =============================================================================
# 1. TestDependencyFlags
# =============================================================================

class TestDependencyFlags:
    """Verifica que los flags de dependencias sean booleanos."""

    def test_paddleocr_flag_is_bool(self):
        assert isinstance(core.PADDLEOCR_DISPONIBLE, bool)

    def test_tesseract_flag_is_bool(self):
        assert isinstance(core.TESSERACT_DISPONIBLE, bool)

    def test_cv2_flag_is_bool(self):
        assert isinstance(core.CV2_DISPONIBLE, bool)

    def test_active_engine_is_string(self):
        assert core._ACTIVE_ENGINE in ("paddleocr", "tesseract", "none")

    def test_version_is_3_0_0(self):
        assert core.__version__ == "3.0.0"


# =============================================================================
# 2. TestLanguageMapping
# =============================================================================

class TestLanguageMapping:
    """Verifica el mapeo de idiomas Tesseract -> PaddleOCR."""

    def test_spa_maps_to_es(self):
        assert core._map_lang_to_paddle("spa") == "es"

    def test_eng_maps_to_en(self):
        assert core._map_lang_to_paddle("eng") == "en"

    def test_por_maps_to_pt(self):
        assert core._map_lang_to_paddle("por") == "pt"

    def test_fra_maps_to_fr(self):
        assert core._map_lang_to_paddle("fra") == "fr"

    def test_unknown_lang_passes_through(self):
        """Idiomas desconocidos pasan tal cual."""
        assert core._map_lang_to_paddle("xyz") == "xyz"

    def test_paddle_supported_langs_is_set(self):
        assert isinstance(core._PADDLE_SUPPORTED_LANGS, set)
        assert "es" in core._PADDLE_SUPPORTED_LANGS
        assert "en" in core._PADDLE_SUPPORTED_LANGS


# =============================================================================
# 3. TestVerificacion
# =============================================================================

class TestVerificacion:
    """Verifica funciones de verificacion de motores."""

    def test_verificar_tesseract_returns_tuple(self):
        result = core.verificar_tesseract()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_verificar_paddleocr_returns_tuple(self):
        result = core.verificar_paddleocr()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_verificar_ocr_returns_triple(self):
        result = core.verificar_ocr()
        assert isinstance(result, tuple)
        assert len(result) == 3
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)
        assert result[2] in ("paddleocr", "tesseract", "none")

    def test_verificar_ocr_motor_coherente(self):
        """El motor reportado debe ser coherente con los flags."""
        disponible, msg, motor = core.verificar_ocr()
        if motor == "paddleocr":
            assert core.PADDLEOCR_DISPONIBLE
        elif motor == "tesseract":
            assert core.TESSERACT_DISPONIBLE
        elif motor == "none":
            # Si es "none", puede ser que no haya motores o que fallen
            pass


# =============================================================================
# 4. TestRenderizarPagina
# =============================================================================

class TestRenderizarPagina:
    """Tests para renderizar_pagina (solo usa PyMuPDF)."""

    def test_ruta_invalida_retorna_none(self):
        result = core.renderizar_pagina(Path("/ruta/inexistente.pdf"), 1)
        assert result is None

    def test_pagina_cero_retorna_none(self):
        """Pagina 0 es invalida (1-indexed)."""
        result = core.renderizar_pagina(Path("/fake.pdf"), 0)
        assert result is None

    def test_pagina_negativa_retorna_none(self):
        result = core.renderizar_pagina(Path("/fake.pdf"), -1)
        assert result is None


# =============================================================================
# 5. TestPreprocesarRotacion
# =============================================================================

class TestPreprocesarRotacion:
    """Tests para preprocesar_rotacion."""

    def test_retorna_tupla_imagen_dict(self):
        img = _create_white_image()
        if img is None:
            pytest.skip("PIL no disponible")
        resultado_img, info = core.preprocesar_rotacion(img, "eng")
        assert resultado_img is not None
        assert isinstance(info, dict)

    def test_info_tiene_claves_requeridas(self):
        img = _create_white_image()
        if img is None:
            pytest.skip("PIL no disponible")
        _, info = core.preprocesar_rotacion(img, "eng")
        assert "rotacion_grados" in info
        assert "rotacion_metodo" in info
        assert "deskew_grados" in info
        assert "rotacion_aplicada" in info

    def test_paddleocr_retorna_builtin(self):
        """Si PaddleOCR activo, metodo debe ser paddleocr_builtin."""
        img = _create_white_image()
        if img is None:
            pytest.skip("PIL no disponible")
        if core._ACTIVE_ENGINE == "paddleocr":
            _, info = core.preprocesar_rotacion(img, "spa")
            assert info["rotacion_metodo"] == "paddleocr_builtin"

    def test_rotacion_grados_es_numerico(self):
        img = _create_white_image()
        if img is None:
            pytest.skip("PIL no disponible")
        _, info = core.preprocesar_rotacion(img, "eng")
        assert isinstance(info["rotacion_grados"], (int, float))

    def test_rotacion_aplicada_es_bool(self):
        img = _create_white_image()
        if img is None:
            pytest.skip("PIL no disponible")
        _, info = core.preprocesar_rotacion(img, "eng")
        assert isinstance(info["rotacion_aplicada"], bool)


# =============================================================================
# 6. TestCalcularMetricas
# =============================================================================

class TestCalcularMetricas:
    """Tests para calcular_metricas_imagen."""

    def test_retorna_dict(self):
        img = _create_white_image()
        if img is None:
            pytest.skip("PIL no disponible")
        result = core.calcular_metricas_imagen(img)
        assert isinstance(result, dict)

    def test_dict_tiene_claves_requeridas(self):
        img = _create_white_image()
        if img is None:
            pytest.skip("PIL no disponible")
        result = core.calcular_metricas_imagen(img)
        assert "dpi_estimado" in result
        assert "width_px" in result
        assert "height_px" in result
        assert "contraste" in result
        assert "blur_score" in result

    def test_dimensiones_correctas(self):
        img = _create_white_image(300, 400)
        if img is None:
            pytest.skip("PIL no disponible")
        result = core.calcular_metricas_imagen(img)
        assert result["width_px"] == 300
        assert result["height_px"] == 400

    def test_dpi_default(self):
        img = _create_white_image()
        if img is None:
            pytest.skip("PIL no disponible")
        result = core.calcular_metricas_imagen(img, dpi_render=150)
        assert result["dpi_estimado"] == 150


# =============================================================================
# 7. TestEjecutarOCR
# =============================================================================

class TestEjecutarOCR:
    """Tests para ejecutar_ocr (dispatch + fallback)."""

    def test_retorna_dict(self):
        img = _create_white_image()
        if img is None:
            pytest.skip("PIL no disponible")
        result = core.ejecutar_ocr(img, "eng")
        assert isinstance(result, dict)

    def test_dict_tiene_claves_completas(self):
        img = _create_white_image()
        if img is None:
            pytest.skip("PIL no disponible")
        result = core.ejecutar_ocr(img, "eng")
        claves_requeridas = [
            "lang", "texto_completo", "snippet_200",
            "confianza_promedio", "num_palabras",
            "tiempo_ms", "error", "motor_ocr"
        ]
        for clave in claves_requeridas:
            assert clave in result, f"Falta clave '{clave}' en resultado OCR"

    def test_motor_ocr_presente(self):
        """El campo motor_ocr debe estar presente."""
        img = _create_white_image()
        if img is None:
            pytest.skip("PIL no disponible")
        result = core.ejecutar_ocr(img, "eng")
        assert "motor_ocr" in result
        assert result["motor_ocr"] in (
            "paddleocr", "tesseract", "tesseract_fallback", "none"
        )

    def test_confianza_en_rango_0_1(self):
        img = _create_white_image()
        if img is None:
            pytest.skip("PIL no disponible")
        result = core.ejecutar_ocr(img, "eng")
        assert 0.0 <= result["confianza_promedio"] <= 1.0

    def test_num_palabras_no_negativo(self):
        img = _create_white_image()
        if img is None:
            pytest.skip("PIL no disponible")
        result = core.ejecutar_ocr(img, "eng")
        assert result["num_palabras"] >= 0

    def test_tiempo_ms_no_negativo(self):
        img = _create_white_image()
        if img is None:
            pytest.skip("PIL no disponible")
        result = core.ejecutar_ocr(img, "eng")
        assert result["tiempo_ms"] >= 0

    def test_sin_motores_retorna_error(self):
        """Si no hay motores, debe retornar error."""
        img = _create_mock_image()

        with patch.object(core, 'PADDLEOCR_DISPONIBLE', False), \
             patch.object(core, 'TESSERACT_DISPONIBLE', False):
            result = core.ejecutar_ocr(img, "eng")
            assert result["error"] is not None
            assert result["motor_ocr"] == "none"

    def test_paddleocr_falla_fallback_tesseract(self):
        """Cuando PaddleOCR falla en runtime, debe usar Tesseract."""
        img = _create_mock_image()

        mock_tesseract_result = {
            "lang": "eng",
            "texto_completo": "mock text",
            "snippet_200": "mock text",
            "confianza_promedio": 0.85,
            "num_palabras": 2,
            "tiempo_ms": 50,
            "error": None,
            "motor_ocr": "tesseract",
        }

        with patch.object(core, 'PADDLEOCR_DISPONIBLE', True), \
             patch.object(core, 'TESSERACT_DISPONIBLE', True), \
             patch.object(core, '_ejecutar_ocr_paddleocr', side_effect=RuntimeError("GPU OOM")), \
             patch.object(core, '_ejecutar_ocr_tesseract', return_value=mock_tesseract_result):
            result = core.ejecutar_ocr(img, "eng")
            assert result["motor_ocr"] == "tesseract_fallback"
            assert result["texto_completo"] == "mock text"

    def test_paddleocr_falla_sin_tesseract(self):
        """Cuando PaddleOCR falla y Tesseract no existe."""
        img = _create_mock_image()

        with patch.object(core, 'PADDLEOCR_DISPONIBLE', True), \
             patch.object(core, 'TESSERACT_DISPONIBLE', False), \
             patch.object(core, '_ejecutar_ocr_paddleocr', side_effect=RuntimeError("GPU fail")):
            result = core.ejecutar_ocr(img, "eng")
            assert result["motor_ocr"] == "none"
            assert result["error"] is not None

    def test_solo_tesseract_disponible(self):
        """Cuando solo Tesseract esta disponible."""
        img = _create_mock_image()

        mock_result = {
            "lang": "eng",
            "texto_completo": "tesseract only",
            "snippet_200": "tesseract only",
            "confianza_promedio": 0.90,
            "num_palabras": 2,
            "tiempo_ms": 30,
            "error": None,
            "motor_ocr": "tesseract",
        }

        with patch.object(core, 'PADDLEOCR_DISPONIBLE', False), \
             patch.object(core, 'TESSERACT_DISPONIBLE', True), \
             patch.object(core, '_ejecutar_ocr_tesseract', return_value=mock_result):
            result = core.ejecutar_ocr(img, "eng")
            assert result["motor_ocr"] == "tesseract"
            assert result["texto_completo"] == "tesseract only"


# =============================================================================
# 8. TestEnsureLangAvailable
# =============================================================================

class TestEnsureLangAvailable:
    """Tests para ensure_lang_available."""

    def test_retorna_tupla_3(self):
        result = core.ensure_lang_available("eng")
        assert isinstance(result, tuple)
        assert len(result) == 3
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)
        assert isinstance(result[2], list)

    def test_paddleocr_spa_disponible(self):
        """Si PaddleOCR activo, spa debe estar disponible."""
        if not core.PADDLEOCR_DISPONIBLE:
            pytest.skip("PaddleOCR no disponible")
        ok, msg, langs = core.ensure_lang_available("spa")
        assert ok
        assert "PaddleOCR" in msg

    def test_sin_motores_retorna_false(self):
        """Sin motores, ensure_lang debe retornar False."""
        with patch.object(core, 'PADDLEOCR_DISPONIBLE', False), \
             patch.object(core, 'TESSERACT_DISPONIBLE', False):
            ok, msg, langs = core.ensure_lang_available("spa")
            assert not ok
            assert langs == []


# =============================================================================
# 9. TestListTesseractLangs
# =============================================================================

class TestListTesseractLangs:
    """Tests para list_tesseract_langs."""

    def test_retorna_dict(self):
        result = core.list_tesseract_langs()
        assert isinstance(result, dict)
        assert "ok" in result
        assert "langs" in result
        assert isinstance(result["langs"], list)


# =============================================================================
# 10. TestSingletonPaddleOCR
# =============================================================================

class TestSingletonPaddleOCR:
    """Tests para el patron singleton de PaddleOCR."""

    def test_instances_dict_exists(self):
        assert isinstance(core._paddleocr_instances, dict)

    def test_get_instance_sin_paddleocr_raises(self):
        """Sin PaddleOCR instalado, debe fallar."""
        if core.PADDLEOCR_DISPONIBLE:
            pytest.skip("PaddleOCR esta disponible")
        with pytest.raises((ImportError, RuntimeError)):
            core._get_paddleocr_instance("en")


# =============================================================================
# 11. TestOCRTesseractInterno
# =============================================================================

class TestOCRTesseractInterno:
    """Tests para _ejecutar_ocr_tesseract."""

    def test_sin_tesseract_retorna_error(self):
        img = _create_mock_image()
        with patch.object(core, 'TESSERACT_DISPONIBLE', False):
            result = core._ejecutar_ocr_tesseract(img, "eng")
            assert result["error"] is not None
            assert result["motor_ocr"] == "tesseract"

    def test_resultado_tiene_motor_ocr(self):
        img = _create_mock_image()
        with patch.object(core, 'TESSERACT_DISPONIBLE', False):
            result = core._ejecutar_ocr_tesseract(img, "eng")
            assert result["motor_ocr"] == "tesseract"


# =============================================================================
# 12. TestImportsPublicos
# =============================================================================

class TestImportsPublicos:
    """Verifica que los imports publicos del modulo funcionen."""

    def test_import_from_ocr_init(self):
        from src.ocr import (
            renderizar_pagina,
            ejecutar_ocr,
            preprocesar_rotacion,
            calcular_metricas_imagen,
            verificar_tesseract,
            verificar_paddleocr,
            verificar_ocr,
            ensure_lang_available,
            CV2_DISPONIBLE,
            TESSERACT_DISPONIBLE,
            PADDLEOCR_DISPONIBLE,
        )
        # Verificar que son callable
        assert callable(renderizar_pagina)
        assert callable(ejecutar_ocr)
        assert callable(preprocesar_rotacion)
        assert callable(calcular_metricas_imagen)
        assert callable(verificar_tesseract)
        assert callable(verificar_paddleocr)
        assert callable(verificar_ocr)
        assert callable(ensure_lang_available)
        # Flags son bools
        assert isinstance(CV2_DISPONIBLE, bool)
        assert isinstance(TESSERACT_DISPONIBLE, bool)
        assert isinstance(PADDLEOCR_DISPONIBLE, bool)

    def test_all_exports_match(self):
        """Verifica que __all__ en __init__.py contenga los exports correctos."""
        from src.ocr import __all__ as exports
        expected = {
            "renderizar_pagina", "ejecutar_ocr", "preprocesar_rotacion",
            "calcular_metricas_imagen", "verificar_tesseract",
            "verificar_paddleocr", "verificar_ocr", "ensure_lang_available",
            "CV2_DISPONIBLE", "TESSERACT_DISPONIBLE", "PADDLEOCR_DISPONIBLE",
        }
        assert set(exports) == expected
