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

    def test_version_is_current(self):
        assert core.__version__ in ("3.0.0", "3.1.0", "3.2.0", "4.0.0")


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
            "lineas": [],
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
            "lineas": [],
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
            "LineaOCR",
            "CV2_DISPONIBLE", "TESSERACT_DISPONIBLE", "PADDLEOCR_DISPONIBLE",
        }
        assert set(exports) == expected

    def test_linea_ocr_importable(self):
        """LineaOCR debe ser importable desde src.ocr."""
        from src.ocr import LineaOCR
        assert LineaOCR is not None

    def test_linea_ocr_in_all(self):
        """LineaOCR debe estar en __all__."""
        from src.ocr import __all__ as exports
        assert "LineaOCR" in exports


# =============================================================================
# 13. TestLineaOCR — Dataclass
# =============================================================================

class TestLineaOCR:
    """Tests para la dataclass LineaOCR."""

    def test_creation_completa(self):
        """Crear LineaOCR con todos los campos."""
        linea = core.LineaOCR(
            texto="Hola mundo",
            bbox=(10.0, 20.0, 100.0, 50.0),
            confianza=0.95,
            motor="paddleocr",
        )
        assert linea.texto == "Hola mundo"
        assert linea.bbox == (10.0, 20.0, 100.0, 50.0)
        assert linea.confianza == 0.95
        assert linea.motor == "paddleocr"

    def test_creation_bbox_none(self):
        """Crear LineaOCR con bbox=None (motor no provee ubicacion)."""
        linea = core.LineaOCR(texto="test", bbox=None, confianza=0.8)
        assert linea.bbox is None

    def test_creation_confianza_none(self):
        """Crear LineaOCR con confianza=None (score no disponible)."""
        linea = core.LineaOCR(texto="test", bbox=(0, 0, 10, 10), confianza=None)
        assert linea.confianza is None

    def test_to_dict_con_bbox(self):
        """to_dict serializa bbox como lista."""
        linea = core.LineaOCR(
            texto="ejemplo",
            bbox=(5.0, 10.0, 50.0, 30.0),
            confianza=0.9234,
            motor="tesseract",
        )
        d = linea.to_dict()
        assert d["texto"] == "ejemplo"
        assert d["bbox"] == [5.0, 10.0, 50.0, 30.0]
        assert d["confianza"] == 0.9234
        assert d["motor"] == "tesseract"

    def test_to_dict_bbox_none(self):
        """to_dict con bbox=None serializa como None."""
        linea = core.LineaOCR(texto="x", bbox=None, confianza=0.5)
        d = linea.to_dict()
        assert d["bbox"] is None

    def test_to_dict_confianza_none(self):
        """to_dict con confianza=None serializa como None."""
        linea = core.LineaOCR(texto="x", bbox=(0, 0, 1, 1), confianza=None)
        d = linea.to_dict()
        assert d["confianza"] is None

    def test_from_dict_con_bbox_lista(self):
        """from_dict convierte lista a tupla para bbox."""
        data = {
            "texto": "hola",
            "bbox": [1.0, 2.0, 3.0, 4.0],
            "confianza": 0.88,
            "motor": "paddleocr",
        }
        linea = core.LineaOCR.from_dict(data)
        assert isinstance(linea.bbox, tuple)
        assert linea.bbox == (1.0, 2.0, 3.0, 4.0)
        assert linea.confianza == 0.88

    def test_from_dict_bbox_none(self):
        """from_dict con bbox=None."""
        data = {"texto": "x", "bbox": None, "confianza": 0.5, "motor": ""}
        linea = core.LineaOCR.from_dict(data)
        assert linea.bbox is None

    def test_from_dict_ignora_campos_extra(self):
        """from_dict ignora campos que no son del dataclass."""
        data = {
            "texto": "hola",
            "bbox": [1, 2, 3, 4],
            "confianza": 0.9,
            "motor": "test",
            "campo_extra": "ignorar",
        }
        linea = core.LineaOCR.from_dict(data)
        assert linea.texto == "hola"
        assert not hasattr(linea, "campo_extra")

    def test_roundtrip_to_from_dict(self):
        """Roundtrip: LineaOCR → dict → LineaOCR."""
        original = core.LineaOCR(
            texto="roundtrip",
            bbox=(10.5, 20.3, 100.7, 50.1),
            confianza=0.8765,
            motor="paddleocr",
        )
        d = original.to_dict()
        restored = core.LineaOCR.from_dict(d)
        assert restored.texto == original.texto
        assert restored.bbox == original.bbox
        assert restored.confianza == round(original.confianza, 4)
        assert restored.motor == original.motor

    def test_to_dict_json_serializable(self):
        """to_dict debe ser serializable a JSON."""
        import json
        linea = core.LineaOCR(
            texto="json test",
            bbox=(1, 2, 3, 4),
            confianza=0.99,
            motor="paddleocr",
        )
        serialized = json.dumps(linea.to_dict())
        assert isinstance(serialized, str)
        parsed = json.loads(serialized)
        assert parsed["texto"] == "json test"


# =============================================================================
# 14. TestPolygonToBbox
# =============================================================================

class TestPolygonToBbox:
    """Tests para _polygon_to_bbox."""

    def test_rectangulo_simple(self):
        """Poligono rectangular → bbox correcto."""
        polygon = [[10, 20], [100, 20], [100, 50], [10, 50]]
        bbox = core._polygon_to_bbox(polygon)
        assert bbox == (10, 20, 100, 50)

    def test_poligono_rotado(self):
        """Poligono rotado → bbox envolvente."""
        polygon = [[50, 10], [90, 50], [50, 90], [10, 50]]
        bbox = core._polygon_to_bbox(polygon)
        assert bbox == (10, 10, 90, 90)

    def test_punto_degenerado(self):
        """Todos los puntos iguales → bbox de tamanio cero."""
        polygon = [[50, 50], [50, 50], [50, 50], [50, 50]]
        bbox = core._polygon_to_bbox(polygon)
        assert bbox == (50, 50, 50, 50)

    def test_coordenadas_float(self):
        """Coordenadas flotantes se preservan."""
        polygon = [[10.5, 20.3], [100.7, 20.3], [100.7, 50.1], [10.5, 50.1]]
        bbox = core._polygon_to_bbox(polygon)
        assert bbox == (10.5, 20.3, 100.7, 50.1)


# =============================================================================
# 15. TestAgruparPalabrasEnLineas
# =============================================================================

class TestAgruparPalabrasEnLineas:
    """Tests para _agrupar_palabras_en_lineas."""

    def _make_tesseract_data(self, words_info):
        """
        Helper para crear estructura de datos Tesseract.

        words_info: lista de (text, block, line, left, top, width, height, conf)
        """
        data = {
            "text": [],
            "block_num": [],
            "line_num": [],
            "left": [],
            "top": [],
            "width": [],
            "height": [],
            "conf": [],
        }
        for word in words_info:
            text, block, line, left, top, width, height, conf = word
            data["text"].append(text)
            data["block_num"].append(block)
            data["line_num"].append(line)
            data["left"].append(left)
            data["top"].append(top)
            data["width"].append(width)
            data["height"].append(height)
            data["conf"].append(conf)
        return data

    def test_dos_lineas(self):
        """Agrupa correctamente 2 lineas con 2 palabras cada una."""
        data = self._make_tesseract_data([
            ("Hello", 1, 1, 10, 10, 50, 20, 95),
            ("World", 1, 1, 70, 10, 50, 20, 90),
            ("Foo", 1, 2, 10, 40, 30, 20, 80),
            ("Bar", 1, 2, 50, 40, 30, 20, 85),
        ])
        lineas = core._agrupar_palabras_en_lineas(data)
        assert len(lineas) == 2
        assert lineas[0].texto == "Hello World"
        assert lineas[1].texto == "Foo Bar"
        assert lineas[0].motor == "tesseract"

    def test_filtra_vacios(self):
        """Palabras vacias son ignoradas."""
        data = self._make_tesseract_data([
            ("Hello", 1, 1, 10, 10, 50, 20, 90),
            ("", 1, 1, 70, 10, 50, 20, -1),
            ("  ", 1, 1, 130, 10, 50, 20, -1),
            ("World", 1, 2, 10, 40, 50, 20, 85),
        ])
        lineas = core._agrupar_palabras_en_lineas(data)
        assert len(lineas) == 2
        assert lineas[0].texto == "Hello"
        assert lineas[1].texto == "World"

    def test_union_bbox_correcta(self):
        """Union de bboxes calcula envolvente correcta."""
        data = self._make_tesseract_data([
            ("A", 1, 1, 10, 10, 30, 20, 90),
            ("B", 1, 1, 50, 15, 40, 25, 80),
        ])
        lineas = core._agrupar_palabras_en_lineas(data)
        assert len(lineas) == 1
        bbox = lineas[0].bbox
        assert bbox is not None
        # x_min = min(10, 50) = 10
        assert bbox[0] == 10.0
        # y_min = min(10, 15) = 10
        assert bbox[1] == 10.0
        # x_max = max(10+30, 50+40) = max(40, 90) = 90
        assert bbox[2] == 90.0
        # y_max = max(10+20, 15+25) = max(30, 40) = 40
        assert bbox[3] == 40.0

    def test_confianza_promedio(self):
        """Confianza por linea es el promedio normalizado 0-1."""
        data = self._make_tesseract_data([
            ("A", 1, 1, 0, 0, 10, 10, 90),
            ("B", 1, 1, 20, 0, 10, 10, 80),
        ])
        lineas = core._agrupar_palabras_en_lineas(data)
        assert len(lineas) == 1
        # promedio = (90/100 + 80/100) / 2 = 0.85
        assert lineas[0].confianza is not None
        assert abs(lineas[0].confianza - 0.85) < 0.001

    def test_confianza_none_cuando_todos_minus_1(self):
        """Confianza es None si todas las confs son -1."""
        data = self._make_tesseract_data([
            ("X", 1, 1, 0, 0, 10, 10, -1),
        ])
        lineas = core._agrupar_palabras_en_lineas(data)
        assert len(lineas) == 1
        assert lineas[0].confianza is None

    def test_datos_vacios(self):
        """Sin palabras validas, retorna lista vacia."""
        data = self._make_tesseract_data([
            ("", 1, 1, 0, 0, 10, 10, -1),
            ("  ", 1, 2, 0, 0, 10, 10, -1),
        ])
        lineas = core._agrupar_palabras_en_lineas(data)
        assert lineas == []


# =============================================================================
# 16. TestEjecutarOCR_Lineas — Integracion con lineas
# =============================================================================

class TestEjecutarOCR_Lineas:
    """Tests de integracion: ejecutar_ocr retorna lineas."""

    def test_sin_motores_lineas_vacia(self):
        """Sin motores disponibles, lineas debe ser lista vacia."""
        img = _create_mock_image()
        with patch.object(core, 'PADDLEOCR_DISPONIBLE', False), \
             patch.object(core, 'TESSERACT_DISPONIBLE', False):
            result = core.ejecutar_ocr(img, "eng")
            assert "lineas" in result
            assert result["lineas"] == []

    def test_paddleocr_retorna_lineas(self):
        """PaddleOCR retorna lineas con bbox y confianza."""
        img = _create_mock_image()

        mock_result = {
            "lang": "eng",
            "texto_completo": "Hello World",
            "snippet_200": "Hello World",
            "confianza_promedio": 0.95,
            "num_palabras": 2,
            "tiempo_ms": 100,
            "error": None,
            "motor_ocr": "paddleocr",
            "lineas": [
                {"texto": "Hello", "bbox": [10, 20, 100, 50], "confianza": 0.95, "motor": "paddleocr"},
                {"texto": "World", "bbox": [10, 60, 100, 90], "confianza": 0.92, "motor": "paddleocr"},
            ],
        }

        with patch.object(core, 'PADDLEOCR_DISPONIBLE', True), \
             patch.object(core, '_ejecutar_ocr_paddleocr', return_value=mock_result):
            result = core.ejecutar_ocr(img, "eng")
            assert "lineas" in result
            assert len(result["lineas"]) == 2
            assert result["lineas"][0]["texto"] == "Hello"
            assert result["lineas"][0]["bbox"] is not None

    def test_tesseract_retorna_lineas(self):
        """Tesseract retorna lineas con bbox y confianza."""
        img = _create_mock_image()

        mock_result = {
            "lang": "eng",
            "texto_completo": "Test text",
            "snippet_200": "Test text",
            "confianza_promedio": 0.88,
            "num_palabras": 2,
            "tiempo_ms": 50,
            "error": None,
            "motor_ocr": "tesseract",
            "lineas": [
                {"texto": "Test text", "bbox": [10, 10, 90, 30], "confianza": 0.88, "motor": "tesseract"},
            ],
        }

        with patch.object(core, 'PADDLEOCR_DISPONIBLE', False), \
             patch.object(core, 'TESSERACT_DISPONIBLE', True), \
             patch.object(core, '_ejecutar_ocr_tesseract', return_value=mock_result):
            result = core.ejecutar_ocr(img, "eng")
            assert "lineas" in result
            assert len(result["lineas"]) == 1

    def test_fallback_tiene_lineas(self):
        """Fallback PaddleOCR→Tesseract tambien retorna lineas."""
        img = _create_mock_image()

        mock_result = {
            "lang": "eng",
            "texto_completo": "fallback text",
            "snippet_200": "fallback text",
            "confianza_promedio": 0.80,
            "num_palabras": 2,
            "tiempo_ms": 40,
            "error": None,
            "motor_ocr": "tesseract",
            "lineas": [{"texto": "fallback text", "bbox": [0, 0, 50, 20], "confianza": 0.80, "motor": "tesseract"}],
        }

        with patch.object(core, 'PADDLEOCR_DISPONIBLE', True), \
             patch.object(core, 'TESSERACT_DISPONIBLE', True), \
             patch.object(core, '_ejecutar_ocr_paddleocr', side_effect=RuntimeError("GPU")), \
             patch.object(core, '_ejecutar_ocr_tesseract', return_value=mock_result):
            result = core.ejecutar_ocr(img, "eng")
            assert result["motor_ocr"] == "tesseract_fallback"
            assert "lineas" in result
            assert len(result["lineas"]) == 1

    def test_paddleocr_falla_sin_tesseract_lineas_vacia(self):
        """PaddleOCR falla + sin Tesseract: lineas debe ser []."""
        img = _create_mock_image()

        with patch.object(core, 'PADDLEOCR_DISPONIBLE', True), \
             patch.object(core, 'TESSERACT_DISPONIBLE', False), \
             patch.object(core, '_ejecutar_ocr_paddleocr', side_effect=RuntimeError("fail")):
            result = core.ejecutar_ocr(img, "eng")
            assert result["lineas"] == []
            assert result["motor_ocr"] == "none"

    def test_backward_compat_8_keys_present(self):
        """Las 8 claves originales siguen presentes."""
        img = _create_mock_image()

        with patch.object(core, 'PADDLEOCR_DISPONIBLE', False), \
             patch.object(core, 'TESSERACT_DISPONIBLE', False):
            result = core.ejecutar_ocr(img, "eng")
            claves_originales = [
                "lang", "texto_completo", "snippet_200",
                "confianza_promedio", "num_palabras",
                "tiempo_ms", "error", "motor_ocr"
            ]
            for clave in claves_originales:
                assert clave in result, f"Falta clave original '{clave}'"

    def test_lineas_son_json_serializable(self):
        """Las lineas retornadas deben ser serializables a JSON."""
        import json
        img = _create_mock_image()

        mock_result = {
            "lang": "eng",
            "texto_completo": "test",
            "snippet_200": "test",
            "confianza_promedio": 0.9,
            "num_palabras": 1,
            "tiempo_ms": 10,
            "error": None,
            "motor_ocr": "paddleocr",
            "lineas": [
                {"texto": "test", "bbox": [10, 20, 100, 50], "confianza": 0.9, "motor": "paddleocr"},
            ],
        }

        with patch.object(core, 'PADDLEOCR_DISPONIBLE', True), \
             patch.object(core, '_ejecutar_ocr_paddleocr', return_value=mock_result):
            result = core.ejecutar_ocr(img, "eng")
            serialized = json.dumps(result["lineas"])
            assert isinstance(serialized, str)

    def test_contrato_retorno_9_keys(self):
        """El resultado debe tener exactamente 9 keys (8 originales + lineas)."""
        img = _create_mock_image()

        with patch.object(core, 'PADDLEOCR_DISPONIBLE', False), \
             patch.object(core, 'TESSERACT_DISPONIBLE', False):
            result = core.ejecutar_ocr(img, "eng")
            expected_keys = {
                "lang", "texto_completo", "snippet_200",
                "confianza_promedio", "num_palabras",
                "tiempo_ms", "error", "motor_ocr", "lineas"
            }
            assert set(result.keys()) == expected_keys

    def test_linea_bbox_none_valido(self):
        """Una linea con bbox=None es valida en el resultado."""
        linea = core.LineaOCR(texto="test", bbox=None, confianza=0.5, motor="paddleocr")
        d = linea.to_dict()
        assert d["bbox"] is None
        # Verificar que se puede meter en resultado sin error
        resultado = {"lineas": [d]}
        assert resultado["lineas"][0]["bbox"] is None

    def test_linea_confianza_none_valido(self):
        """Una linea con confianza=None es valida."""
        linea = core.LineaOCR(texto="test", bbox=(0, 0, 10, 10), confianza=None, motor="tesseract")
        d = linea.to_dict()
        assert d["confianza"] is None


# =============================================================================
# 17. TestTraceLoggerIntegration — TraceLogger en OCR
# =============================================================================

class TestTraceLoggerIntegration:
    """Tests para integracion de TraceLogger en ejecutar_ocr."""

    def test_sin_trace_logger_no_falla(self):
        """ejecutar_ocr sin trace_logger funciona normal."""
        img = _create_mock_image()

        with patch.object(core, 'PADDLEOCR_DISPONIBLE', False), \
             patch.object(core, 'TESSERACT_DISPONIBLE', False):
            result = core.ejecutar_ocr(img, "eng")
            assert result is not None
            assert "error" in result

    def test_sin_trace_logger_backward_compat(self):
        """Llamada sin trace_logger (backward compat) funciona."""
        img = _create_mock_image()

        with patch.object(core, 'PADDLEOCR_DISPONIBLE', False), \
             patch.object(core, 'TESSERACT_DISPONIBLE', False):
            # Llamada sin tercer argumento (backward compat)
            result = core.ejecutar_ocr(img, "eng")
            assert isinstance(result, dict)

    def test_trace_logger_mock_registra(self):
        """TraceLogger mock recibe llamadas info/warning."""
        img = _create_mock_image()
        mock_logger = MagicMock()

        with patch.object(core, 'PADDLEOCR_DISPONIBLE', False), \
             patch.object(core, 'TESSERACT_DISPONIBLE', False):
            core.ejecutar_ocr(img, "eng", trace_logger=mock_logger)
            # Debe haber al menos 1 llamada (info inicio + error sin motores)
            assert mock_logger.info.called or mock_logger.error.called

    def test_trace_logger_roto_no_crashea(self):
        """Un trace_logger que lanza excepciones no debe crashear OCR."""
        img = _create_mock_image()
        mock_logger = MagicMock()
        mock_logger.info.side_effect = Exception("logger roto")
        mock_logger.error.side_effect = Exception("logger roto")

        with patch.object(core, 'PADDLEOCR_DISPONIBLE', False), \
             patch.object(core, 'TESSERACT_DISPONIBLE', False):
            # No debe lanzar excepcion
            result = core.ejecutar_ocr(img, "eng", trace_logger=mock_logger)
            assert result is not None
            assert result["motor_ocr"] == "none"

    def test_fallback_registra_warning(self):
        """Fallback PaddleOCR→Tesseract registra warning."""
        img = _create_mock_image()
        mock_logger = MagicMock()

        mock_result = {
            "lang": "eng",
            "texto_completo": "fb",
            "snippet_200": "fb",
            "confianza_promedio": 0.8,
            "num_palabras": 1,
            "tiempo_ms": 10,
            "error": None,
            "motor_ocr": "tesseract",
            "lineas": [],
        }

        with patch.object(core, 'PADDLEOCR_DISPONIBLE', True), \
             patch.object(core, 'TESSERACT_DISPONIBLE', True), \
             patch.object(core, '_ejecutar_ocr_paddleocr', side_effect=RuntimeError("GPU")), \
             patch.object(core, '_ejecutar_ocr_tesseract', return_value=mock_result):
            core.ejecutar_ocr(img, "eng", trace_logger=mock_logger)
            # Debe haber un warning por el fallback
            assert mock_logger.warning.called


# =============================================================================
# 18. TestLogOCR — Helper _log_ocr
# =============================================================================

class TestLogOCR:
    """Tests para el helper _log_ocr."""

    def test_none_logger_no_falla(self):
        """Con trace_logger=None no debe hacer nada ni fallar."""
        # No debe lanzar excepcion
        core._log_ocr(None, "info", "test message")

    def test_level_info(self):
        """level=info llama a logger.info."""
        mock = MagicMock()
        core._log_ocr(mock, "info", "mensaje")
        mock.info.assert_called_once()

    def test_level_warning(self):
        """level=warning llama a logger.warning."""
        mock = MagicMock()
        core._log_ocr(mock, "warning", "advertencia")
        mock.warning.assert_called_once()

    def test_level_error(self):
        """level=error llama a logger.error."""
        mock = MagicMock()
        core._log_ocr(mock, "error", "error msg")
        mock.error.assert_called_once()

    def test_logger_roto_silencioso(self):
        """Logger que lanza excepciones no crashea."""
        mock = MagicMock()
        mock.info.side_effect = RuntimeError("boom")
        # No debe lanzar excepcion
        core._log_ocr(mock, "info", "test")

    def test_context_pasado_correctamente(self):
        """El context se pasa al logger."""
        mock = MagicMock()
        ctx = {"key": "value"}
        core._log_ocr(mock, "info", "msg", context=ctx)
        call_args = mock.info.call_args
        assert call_args[1]["context"] == ctx


# =============================================================================
# 19. TestValidarDimensiones — Regla 2
# =============================================================================

class TestValidarDimensiones:
    """Tests para _validar_dimensiones (Regla 2: robustez frente a limites externos)."""

    def test_imagen_dentro_de_limite_no_cambia(self):
        """Imagen dentro del limite se retorna sin modificar."""
        img = _create_white_image(1500, 1000)
        if img is None:
            pytest.skip("PIL no disponible")
        result = core._validar_dimensiones(img, max_dim=2000)
        assert result.size == (1500, 1000)
        assert result is img  # Misma referencia, no se copio

    def test_imagen_exacta_limite_no_cambia(self):
        """Imagen exactamente en el limite no se redimensiona."""
        img = _create_white_image(2000, 2000)
        if img is None:
            pytest.skip("PIL no disponible")
        result = core._validar_dimensiones(img, max_dim=2000)
        assert result.size == (2000, 2000)
        assert result is img

    def test_imagen_ancha_excede_redimensiona(self):
        """Imagen mas ancha que el limite se reduce."""
        img = _create_white_image(4000, 2000)
        if img is None:
            pytest.skip("PIL no disponible")
        result = core._validar_dimensiones(img, max_dim=2000)
        assert result.size[0] == 2000
        assert result.size[1] == 1000  # Mantiene aspect ratio

    def test_imagen_alta_excede_redimensiona(self):
        """Imagen mas alta que el limite se reduce."""
        img = _create_white_image(1500, 3000)
        if img is None:
            pytest.skip("PIL no disponible")
        result = core._validar_dimensiones(img, max_dim=2000)
        assert result.size[1] == 2000
        assert result.size[0] == 1000  # Mantiene aspect ratio

    def test_ambas_dimensiones_exceden(self):
        """Ambas dimensiones exceden: la mayor se lleva al limite."""
        img = _create_white_image(4000, 3000)
        if img is None:
            pytest.skip("PIL no disponible")
        result = core._validar_dimensiones(img, max_dim=2000)
        assert result.size[0] == 2000
        assert result.size[1] == 1500

    def test_aspecto_ratio_preservado(self):
        """El aspect ratio se preserva tras redimensionamiento."""
        img = _create_white_image(3000, 2000)
        if img is None:
            pytest.skip("PIL no disponible")
        ratio_original = 3000 / 2000
        result = core._validar_dimensiones(img, max_dim=2000)
        ratio_resultado = result.size[0] / result.size[1]
        assert abs(ratio_original - ratio_resultado) < 0.01

    def test_max_dim_custom(self):
        """Funciona con max_dim personalizado."""
        img = _create_white_image(2000, 1000)
        if img is None:
            pytest.skip("PIL no disponible")
        result = core._validar_dimensiones(img, max_dim=1000)
        assert result.size[0] == 1000
        assert result.size[1] == 500

    def test_max_dim_none_usa_config(self):
        """Con max_dim=None, usa VISION_CONFIG."""
        img = _create_white_image(3000, 1500)
        if img is None:
            pytest.skip("PIL no disponible")
        # Patchear config para asegurar valor conocido
        with patch.dict('config.settings.VISION_CONFIG', {"max_dimension_px": 2000}):
            result = core._validar_dimensiones(img, max_dim=None)
            assert result.size[0] == 2000
            assert result.size[1] == 1000

    def test_minimo_1px_garantizado(self):
        """Una dimension muy pequena nunca baja de 1px."""
        img = _create_white_image(10000, 1)
        if img is None:
            pytest.skip("PIL no disponible")
        result = core._validar_dimensiones(img, max_dim=2000)
        assert result.size[0] == 2000
        assert result.size[1] >= 1

    def test_imagen_pequena_sin_cambio(self):
        """Imagen mucho menor al limite no se toca."""
        img = _create_white_image(100, 100)
        if img is None:
            pytest.skip("PIL no disponible")
        result = core._validar_dimensiones(img, max_dim=2000)
        assert result.size == (100, 100)
        assert result is img


# =============================================================================
# 20. TestRenderizarPaginaValidaDimensiones — Integracion Regla 2
# =============================================================================

class TestRenderizarPaginaValidaDimensiones:
    """Verifica que renderizar_pagina integra _validar_dimensiones."""

    def test_renderizar_llama_validar_dimensiones(self):
        """renderizar_pagina debe llamar a _validar_dimensiones."""
        mock_img = _create_mock_image()
        mock_img.size = (3000, 2000)

        with patch.object(core, 'fitz') as mock_fitz, \
             patch.object(core, 'Image') as mock_pil, \
             patch.object(core, '_validar_dimensiones', return_value=mock_img) as mock_val:
            # Setup mock fitz
            mock_doc = MagicMock()
            mock_doc.__len__ = MagicMock(return_value=5)
            mock_page = MagicMock()
            mock_pix = MagicMock()
            mock_pix.tobytes.return_value = b"fake_png_data"
            mock_page.get_pixmap.return_value = mock_pix
            mock_doc.__getitem__ = MagicMock(return_value=mock_page)
            mock_fitz.open.return_value = mock_doc
            mock_fitz.Matrix.return_value = MagicMock()

            # Setup mock PIL
            mock_pil.open.return_value = mock_img

            result = core.renderizar_pagina(Path("/fake.pdf"), 1, dpi=200)

            # _validar_dimensiones DEBE haber sido llamada
            mock_val.assert_called_once_with(mock_img)

    def test_renderizar_retorna_imagen_validada(self):
        """El resultado de renderizar_pagina es la imagen validada."""
        mock_img_original = MagicMock()
        mock_img_original.size = (4000, 3000)

        mock_img_validada = MagicMock()
        mock_img_validada.size = (2000, 1500)

        with patch.object(core, 'fitz') as mock_fitz, \
             patch.object(core, 'Image') as mock_pil, \
             patch.object(core, '_validar_dimensiones', return_value=mock_img_validada):
            mock_doc = MagicMock()
            mock_doc.__len__ = MagicMock(return_value=5)
            mock_page = MagicMock()
            mock_pix = MagicMock()
            mock_pix.tobytes.return_value = b"fake"
            mock_page.get_pixmap.return_value = mock_pix
            mock_doc.__getitem__ = MagicMock(return_value=mock_page)
            mock_fitz.open.return_value = mock_doc
            mock_fitz.Matrix.return_value = MagicMock()
            mock_pil.open.return_value = mock_img_original

            result = core.renderizar_pagina(Path("/fake.pdf"), 1)

            # El resultado debe ser la imagen validada, no la original
            assert result is mock_img_validada
