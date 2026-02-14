# -*- coding: utf-8 -*-
"""
Tests para src/tools/vision.py
==============================
Preprocesador de imágenes para proveedores de visión.

Cobertura:
- preparar_imagen: imágenes dentro/fuera del límite, formatos, errores
- preparar_pagina_pdf: renderizado + redimensionamiento, errores
- _calcular_nuevas_dimensiones: aspect ratio, edge cases
- ResultadoVision: propiedades calculadas
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image

from src.tools.vision import (
    ResultadoVision,
    _calcular_nuevas_dimensiones,
    preparar_imagen,
    preparar_pagina_pdf,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def tmp_dir():
    """Directorio temporal para tests."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def imagen_pequena(tmp_dir):
    """Imagen 800x600 (dentro del límite de 2000px)."""
    ruta = os.path.join(tmp_dir, "pequena.png")
    img = Image.new("RGB", (800, 600), color="blue")
    img.save(ruta, "PNG")
    img.close()
    return ruta


@pytest.fixture
def imagen_grande_ancho(tmp_dir):
    """Imagen 4000x2000 (ancho excede 2000px)."""
    ruta = os.path.join(tmp_dir, "grande_ancho.png")
    img = Image.new("RGB", (4000, 2000), color="red")
    img.save(ruta, "PNG")
    img.close()
    return ruta


@pytest.fixture
def imagen_grande_alto(tmp_dir):
    """Imagen 1500x3000 (alto excede 2000px)."""
    ruta = os.path.join(tmp_dir, "grande_alto.png")
    img = Image.new("RGB", (1500, 3000), color="green")
    img.save(ruta, "PNG")
    img.close()
    return ruta


@pytest.fixture
def imagen_grande_ambos(tmp_dir):
    """Imagen 5000x4000 (ambos exceden 2000px)."""
    ruta = os.path.join(tmp_dir, "grande_ambos.png")
    img = Image.new("RGB", (5000, 4000), color="yellow")
    img.save(ruta, "PNG")
    img.close()
    return ruta


@pytest.fixture
def imagen_exacta(tmp_dir):
    """Imagen 2000x2000 (exactamente en el límite)."""
    ruta = os.path.join(tmp_dir, "exacta.png")
    img = Image.new("RGB", (2000, 2000), color="white")
    img.save(ruta, "PNG")
    img.close()
    return ruta


@pytest.fixture
def imagen_jpeg(tmp_dir):
    """Imagen JPEG con canal RGB."""
    ruta = os.path.join(tmp_dir, "foto.jpg")
    img = Image.new("RGB", (3000, 2000), color="purple")
    img.save(ruta, "JPEG", quality=90)
    img.close()
    return ruta


@pytest.fixture
def imagen_rgba(tmp_dir):
    """Imagen PNG con canal alpha (RGBA)."""
    ruta = os.path.join(tmp_dir, "transparente.png")
    img = Image.new("RGBA", (3000, 1000), color=(255, 0, 0, 128))
    img.save(ruta, "PNG")
    img.close()
    return ruta


@pytest.fixture
def archivo_no_imagen(tmp_dir):
    """Archivo que no es imagen."""
    ruta = os.path.join(tmp_dir, "no_imagen.txt")
    Path(ruta).write_text("esto no es una imagen")
    return ruta


@pytest.fixture
def pdf_simple(tmp_dir):
    """PDF de 2 páginas creado con PyMuPDF."""
    fitz = pytest.importorskip("fitz")
    ruta = os.path.join(tmp_dir, "test.pdf")
    doc = fitz.open()
    for i in range(2):
        page = doc.new_page(width=612, height=792)  # Carta
        page.insert_text((72, 72), f"Página {i + 1} de prueba", fontsize=24)
    doc.save(ruta)
    doc.close()
    return ruta


# ============================================================
# Tests: _calcular_nuevas_dimensiones
# ============================================================

class TestCalcularNuevasDimensiones:
    """Tests para el cálculo de dimensiones con aspect ratio."""

    def test_dentro_del_limite(self):
        assert _calcular_nuevas_dimensiones(800, 600, 2000) == (800, 600)

    def test_exactamente_en_el_limite(self):
        assert _calcular_nuevas_dimensiones(2000, 2000, 2000) == (2000, 2000)

    def test_ancho_excede(self):
        ancho, alto = _calcular_nuevas_dimensiones(4000, 2000, 2000)
        assert ancho == 2000
        assert alto == 1000  # 2000 * (2000/4000) = 1000

    def test_alto_excede(self):
        ancho, alto = _calcular_nuevas_dimensiones(1000, 4000, 2000)
        assert ancho == 500  # 1000 * (2000/4000) = 500
        assert alto == 2000

    def test_ambos_exceden_ancho_mayor(self):
        ancho, alto = _calcular_nuevas_dimensiones(5000, 4000, 2000)
        assert ancho == 2000
        assert alto == 1600  # 4000 * (2000/5000) = 1600

    def test_ambos_exceden_alto_mayor(self):
        ancho, alto = _calcular_nuevas_dimensiones(3000, 6000, 2000)
        assert ancho == 1000  # 3000 * (2000/6000) = 1000
        assert alto == 2000

    def test_imagen_cuadrada_grande(self):
        ancho, alto = _calcular_nuevas_dimensiones(3000, 3000, 2000)
        assert ancho == 2000
        assert alto == 2000

    def test_limite_personalizado(self):
        ancho, alto = _calcular_nuevas_dimensiones(1500, 1000, 500)
        assert ancho == 500
        assert alto == 333  # 1000 * (500/1500) = 333.33 -> 333

    def test_imagen_1px(self):
        assert _calcular_nuevas_dimensiones(1, 1, 2000) == (1, 1)

    def test_minimo_1px_resultado(self):
        """Si la proporción es extrema, no baja de 1px."""
        ancho, alto = _calcular_nuevas_dimensiones(10000, 1, 100)
        assert ancho == 100
        assert alto >= 1


# ============================================================
# Tests: preparar_imagen
# ============================================================

class TestPrepararImagen:
    """Tests para preparar_imagen con imágenes directas."""

    def test_imagen_pequena_sin_resize(self, imagen_pequena, tmp_dir):
        resultado = preparar_imagen(imagen_pequena, directorio_salida=tmp_dir)
        assert resultado.ancho_original == 800
        assert resultado.alto_original == 600
        assert resultado.ancho_final == 800
        assert resultado.alto_final == 600
        assert resultado.fue_redimensionada is False
        assert resultado.pagina_pdf is None
        assert resultado.dpi_render is None
        assert Path(resultado.ruta_procesada).exists()

    def test_imagen_grande_ancho_resize(self, imagen_grande_ancho, tmp_dir):
        resultado = preparar_imagen(imagen_grande_ancho, directorio_salida=tmp_dir)
        assert resultado.ancho_original == 4000
        assert resultado.alto_original == 2000
        assert resultado.ancho_final == 2000
        assert resultado.alto_final == 1000
        assert resultado.fue_redimensionada is True

    def test_imagen_grande_alto_resize(self, imagen_grande_alto, tmp_dir):
        resultado = preparar_imagen(imagen_grande_alto, directorio_salida=tmp_dir)
        assert resultado.ancho_original == 1500
        assert resultado.alto_original == 3000
        assert resultado.ancho_final == 1000
        assert resultado.alto_final == 2000
        assert resultado.fue_redimensionada is True

    def test_imagen_grande_ambos_resize(self, imagen_grande_ambos, tmp_dir):
        resultado = preparar_imagen(imagen_grande_ambos, directorio_salida=tmp_dir)
        assert resultado.ancho_final == 2000
        assert resultado.alto_final == 1600
        assert resultado.fue_redimensionada is True

    def test_imagen_exacta_sin_resize(self, imagen_exacta, tmp_dir):
        resultado = preparar_imagen(imagen_exacta, directorio_salida=tmp_dir)
        assert resultado.fue_redimensionada is False
        assert resultado.ancho_final == 2000
        assert resultado.alto_final == 2000

    def test_max_dimension_custom(self, imagen_pequena, tmp_dir):
        """Límite personalizado de 500px obliga a resize."""
        resultado = preparar_imagen(imagen_pequena, max_dimension=500, directorio_salida=tmp_dir)
        assert resultado.fue_redimensionada is True
        assert resultado.ancho_final == 500
        assert resultado.alto_final == 375  # 600 * (500/800) = 375

    def test_original_no_modificado(self, imagen_grande_ancho, tmp_dir):
        """El archivo original no se modifica."""
        tamanio_antes = Path(imagen_grande_ancho).stat().st_size
        resultado = preparar_imagen(imagen_grande_ancho, directorio_salida=tmp_dir)
        tamanio_despues = Path(imagen_grande_ancho).stat().st_size
        assert tamanio_antes == tamanio_despues
        assert resultado.ruta_original != resultado.ruta_procesada

    def test_archivo_no_existe(self, tmp_dir):
        with pytest.raises(FileNotFoundError, match="no encontrada"):
            preparar_imagen(os.path.join(tmp_dir, "fantasma.png"))

    def test_archivo_no_es_imagen(self, archivo_no_imagen, tmp_dir):
        with pytest.raises(ValueError, match="No es una imagen"):
            preparar_imagen(archivo_no_imagen, directorio_salida=tmp_dir)

    def test_formato_salida_png(self, imagen_grande_ancho, tmp_dir):
        resultado = preparar_imagen(imagen_grande_ancho, directorio_salida=tmp_dir)
        assert resultado.formato_salida == "PNG"
        assert resultado.ruta_procesada.endswith(".png")

    def test_imagen_rgba_a_png(self, imagen_rgba, tmp_dir):
        """Imagen RGBA se procesa correctamente."""
        resultado = preparar_imagen(imagen_rgba, directorio_salida=tmp_dir)
        assert resultado.fue_redimensionada is True
        assert resultado.ancho_final == 2000

    def test_directorio_salida_se_crea(self, imagen_pequena, tmp_dir):
        subdir = os.path.join(tmp_dir, "nuevo", "subdir")
        resultado = preparar_imagen(imagen_pequena, directorio_salida=subdir)
        assert Path(subdir).exists()
        assert Path(resultado.ruta_procesada).exists()

    def test_sin_directorio_salida_usa_temporal(self, imagen_pequena):
        resultado = preparar_imagen(imagen_pequena)
        assert Path(resultado.ruta_procesada).exists()
        # Limpiar temporal
        Path(resultado.ruta_procesada).unlink(missing_ok=True)

    def test_tamanio_bytes_positivo(self, imagen_grande_ancho, tmp_dir):
        resultado = preparar_imagen(imagen_grande_ancho, directorio_salida=tmp_dir)
        assert resultado.tamanio_bytes > 0

    def test_imagen_jpeg_input(self, imagen_jpeg, tmp_dir):
        resultado = preparar_imagen(imagen_jpeg, directorio_salida=tmp_dir)
        assert resultado.fue_redimensionada is True
        assert resultado.ancho_final == 2000


# ============================================================
# Tests: preparar_pagina_pdf
# ============================================================

class TestPrepararPaginaPdf:
    """Tests para renderizar páginas de PDF y preparar para visión."""

    def test_pagina_valida(self, pdf_simple, tmp_dir):
        resultado = preparar_pagina_pdf(pdf_simple, pagina=1, directorio_salida=tmp_dir)
        assert resultado.pagina_pdf == 1
        assert resultado.dpi_render is not None
        assert resultado.ancho_original > 0
        assert resultado.alto_original > 0
        assert Path(resultado.ruta_procesada).exists()

    def test_pagina_2(self, pdf_simple, tmp_dir):
        resultado = preparar_pagina_pdf(pdf_simple, pagina=2, directorio_salida=tmp_dir)
        assert resultado.pagina_pdf == 2

    def test_pagina_fuera_de_rango(self, pdf_simple, tmp_dir):
        with pytest.raises(ValueError, match="fuera de rango"):
            preparar_pagina_pdf(pdf_simple, pagina=5, directorio_salida=tmp_dir)

    def test_pagina_0_invalida(self, pdf_simple, tmp_dir):
        with pytest.raises(ValueError, match="fuera de rango"):
            preparar_pagina_pdf(pdf_simple, pagina=0, directorio_salida=tmp_dir)

    def test_pdf_no_existe(self, tmp_dir):
        with pytest.raises(FileNotFoundError, match="no encontrado"):
            preparar_pagina_pdf(
                os.path.join(tmp_dir, "fantasma.pdf"),
                pagina=1,
                directorio_salida=tmp_dir,
            )

    def test_archivo_no_es_pdf(self, archivo_no_imagen, tmp_dir):
        with pytest.raises(ValueError, match="No es un archivo PDF"):
            preparar_pagina_pdf(archivo_no_imagen, pagina=1, directorio_salida=tmp_dir)

    def test_dpi_custom(self, pdf_simple, tmp_dir):
        resultado = preparar_pagina_pdf(
            pdf_simple, pagina=1, dpi=72, directorio_salida=tmp_dir
        )
        assert resultado.dpi_render == 72
        # A 72 DPI una página carta es ~612x792px → dentro del límite
        assert resultado.ancho_final <= 2000
        assert resultado.alto_final <= 2000

    def test_dpi_alto_fuerza_resize(self, pdf_simple, tmp_dir):
        """A 300 DPI una página carta supera 2000px de alto."""
        resultado = preparar_pagina_pdf(
            pdf_simple, pagina=1, dpi=300, directorio_salida=tmp_dir
        )
        assert resultado.dpi_render == 300
        # 792 * (300/72) = 3300px alto → necesita resize
        assert resultado.fue_redimensionada is True
        assert resultado.alto_final <= 2000

    def test_max_dimension_custom_pdf(self, pdf_simple, tmp_dir):
        resultado = preparar_pagina_pdf(
            pdf_simple, pagina=1, max_dimension=500, directorio_salida=tmp_dir
        )
        assert resultado.ancho_final <= 500
        assert resultado.alto_final <= 500

    def test_original_pdf_no_modificado(self, pdf_simple, tmp_dir):
        tamanio_antes = Path(pdf_simple).stat().st_size
        preparar_pagina_pdf(pdf_simple, pagina=1, directorio_salida=tmp_dir)
        tamanio_despues = Path(pdf_simple).stat().st_size
        assert tamanio_antes == tamanio_despues


# ============================================================
# Tests: ResultadoVision propiedades
# ============================================================

class TestResultadoVision:
    """Tests para propiedades calculadas de ResultadoVision."""

    def test_excedia_limite_true(self):
        r = ResultadoVision(
            ruta_original="a.png", ruta_procesada="b.png",
            ancho_original=4000, alto_original=3000,
            ancho_final=2000, alto_final=1500,
            fue_redimensionada=True, formato_salida="PNG",
            tamanio_bytes=1000, pagina_pdf=None, dpi_render=None,
        )
        assert r.excedia_limite is True

    def test_excedia_limite_false(self):
        r = ResultadoVision(
            ruta_original="a.png", ruta_procesada="b.png",
            ancho_original=800, alto_original=600,
            ancho_final=800, alto_final=600,
            fue_redimensionada=False, formato_salida="PNG",
            tamanio_bytes=1000, pagina_pdf=None, dpi_render=None,
        )
        assert r.excedia_limite is False

    def test_ratio_reduccion_con_resize(self):
        r = ResultadoVision(
            ruta_original="a.png", ruta_procesada="b.png",
            ancho_original=4000, alto_original=2000,
            ancho_final=2000, alto_final=1000,
            fue_redimensionada=True, formato_salida="PNG",
            tamanio_bytes=1000, pagina_pdf=None, dpi_render=None,
        )
        assert r.ratio_reduccion == 0.5

    def test_ratio_reduccion_sin_resize(self):
        r = ResultadoVision(
            ruta_original="a.png", ruta_procesada="b.png",
            ancho_original=800, alto_original=600,
            ancho_final=800, alto_final=600,
            fue_redimensionada=False, formato_salida="PNG",
            tamanio_bytes=1000, pagina_pdf=None, dpi_render=None,
        )
        assert r.ratio_reduccion == 1.0

    def test_contexto_pdf(self):
        r = ResultadoVision(
            ruta_original="doc.pdf", ruta_procesada="doc_p1.png",
            ancho_original=1700, alto_original=2200,
            ancho_final=1545, alto_final=2000,
            fue_redimensionada=True, formato_salida="PNG",
            tamanio_bytes=5000, pagina_pdf=1, dpi_render=200,
        )
        assert r.pagina_pdf == 1
        assert r.dpi_render == 200


# ============================================================
# Tests: integración config
# ============================================================

class TestConfigIntegration:
    """Tests que verifican que la configuración se usa correctamente."""

    def test_vision_config_existe(self):
        from config.settings import VISION_CONFIG
        assert "max_dimension_px" in VISION_CONFIG
        assert VISION_CONFIG["max_dimension_px"] == 2000

    def test_config_formato_salida(self):
        from config.settings import VISION_CONFIG
        assert VISION_CONFIG["formato_salida"] in ("PNG", "JPEG")

    def test_config_dpi_render(self):
        from config.settings import VISION_CONFIG
        assert VISION_CONFIG["dpi_render_pdf"] >= 72
