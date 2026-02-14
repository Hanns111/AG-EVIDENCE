# -*- coding: utf-8 -*-
"""
Preprocesador de imágenes para proveedores de visión
=====================================================
Valida dimensiones y redimensiona imágenes que excedan el límite
del proveedor (default: 2000px en ancho o alto).

El archivo original NUNCA se modifica. Se genera una copia temporal
redimensionada que es la que se envía al proveedor.

Soporta:
- Imágenes directas (PNG, JPEG, TIFF, BMP, WEBP)
- Páginas de PDF renderizadas a imagen (via PyMuPDF)

Versión: 1.0.0
Fecha: 2026-02-13
"""

import logging
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from config.settings import VISION_CONFIG

logger = logging.getLogger(__name__)

# Métodos de resample soportados por Pillow
_RESAMPLE_MAP = {
    "LANCZOS": Image.LANCZOS,
    "BICUBIC": Image.BICUBIC,
    "BILINEAR": Image.BILINEAR,
    "NEAREST": Image.NEAREST,
}


@dataclass
class ResultadoVision:
    """Resultado del preprocesamiento de imagen para visión."""

    # Rutas
    ruta_original: str
    ruta_procesada: str          # Ruta de la imagen lista para el proveedor

    # Dimensiones
    ancho_original: int
    alto_original: int
    ancho_final: int
    alto_final: int

    # Estado
    fue_redimensionada: bool
    formato_salida: str          # "PNG", "JPEG", etc.
    tamanio_bytes: int           # Tamaño del archivo procesado

    # Contexto (para PDFs)
    pagina_pdf: Optional[int]    # None si es imagen directa, 1-indexed si es PDF
    dpi_render: Optional[int]    # DPI usado para renderizar PDF

    @property
    def excedia_limite(self) -> bool:
        """True si la imagen original excedía el límite del proveedor."""
        return self.fue_redimensionada

    @property
    def ratio_reduccion(self) -> float:
        """Ratio de reducción aplicado (1.0 = sin cambio)."""
        if not self.fue_redimensionada:
            return 1.0
        return min(
            self.ancho_final / self.ancho_original,
            self.alto_final / self.alto_original,
        )


def _calcular_nuevas_dimensiones(
    ancho: int,
    alto: int,
    max_dim: int,
) -> Tuple[int, int]:
    """Calcula nuevas dimensiones manteniendo aspect ratio.

    Reduce la dimensión mayor a max_dim y escala la otra proporcionalmente.
    Si ambas dimensiones están dentro del límite, retorna las originales.
    """
    if ancho <= max_dim and alto <= max_dim:
        return ancho, alto

    if ancho >= alto:
        nuevo_ancho = max_dim
        nuevo_alto = int(alto * (max_dim / ancho))
    else:
        nuevo_alto = max_dim
        nuevo_ancho = int(ancho * (max_dim / alto))

    # Asegurar mínimo 1px
    nuevo_ancho = max(1, nuevo_ancho)
    nuevo_alto = max(1, nuevo_alto)

    return nuevo_ancho, nuevo_alto


def _obtener_resample():
    """Obtiene el método de resample desde la configuración."""
    metodo = VISION_CONFIG.get("metodo_resample", "LANCZOS")
    return _RESAMPLE_MAP.get(metodo, Image.LANCZOS)


def preparar_imagen(
    ruta_imagen: str,
    max_dimension: Optional[int] = None,
    directorio_salida: Optional[str] = None,
) -> ResultadoVision:
    """Valida y redimensiona una imagen para envío al proveedor de visión.

    Args:
        ruta_imagen: Ruta a la imagen (PNG, JPEG, TIFF, BMP, WEBP).
        max_dimension: Máximo px en ancho o alto. Default: VISION_CONFIG["max_dimension_px"].
        directorio_salida: Carpeta para guardar la imagen procesada.
            Si None, usa un directorio temporal.

    Returns:
        ResultadoVision con la ruta de la imagen lista para el proveedor.

    Raises:
        FileNotFoundError: Si la imagen no existe.
        ValueError: Si el archivo no es una imagen válida.
    """
    max_dim = max_dimension or VISION_CONFIG["max_dimension_px"]
    formato = VISION_CONFIG.get("formato_salida", "PNG")
    ruta = Path(ruta_imagen)

    if not ruta.exists():
        raise FileNotFoundError(f"Imagen no encontrada: {ruta_imagen}")

    try:
        img = Image.open(ruta)
    except Exception as e:
        raise ValueError(f"No es una imagen válida ({ruta.name}): {e}")

    ancho_orig, alto_orig = img.size
    nuevo_ancho, nuevo_alto = _calcular_nuevas_dimensiones(ancho_orig, alto_orig, max_dim)
    necesita_resize = (nuevo_ancho != ancho_orig) or (nuevo_alto != alto_orig)

    logger.info(
        "vision.preparar_imagen: %s original=%dx%d max=%d resize=%s",
        ruta.name, ancho_orig, alto_orig, max_dim, necesita_resize,
    )

    if necesita_resize:
        img_resized = img.resize((nuevo_ancho, nuevo_alto), _obtener_resample())
        logger.info(
            "vision.preparar_imagen: redimensionada %dx%d -> %dx%d (ratio=%.3f)",
            ancho_orig, alto_orig, nuevo_ancho, nuevo_alto,
            min(nuevo_ancho / ancho_orig, nuevo_alto / alto_orig),
        )
    else:
        img_resized = img

    # Guardar imagen procesada (nunca modificar original)
    if directorio_salida:
        dir_out = Path(directorio_salida)
        dir_out.mkdir(parents=True, exist_ok=True)
        sufijo = f".{formato.lower()}"
        ruta_salida = dir_out / f"{ruta.stem}_vision{sufijo}"
    else:
        sufijo = f".{formato.lower()}"
        tmp = tempfile.NamedTemporaryFile(
            prefix=f"{ruta.stem}_vision_",
            suffix=sufijo,
            delete=False,
        )
        ruta_salida = Path(tmp.name)
        tmp.close()

    save_kwargs = {}
    if formato.upper() == "JPEG":
        # Convertir a RGB si tiene canal alpha
        if img_resized.mode in ("RGBA", "LA", "P"):
            img_resized = img_resized.convert("RGB")
        save_kwargs["quality"] = VISION_CONFIG.get("calidad_jpeg", 95)

    img_resized.save(str(ruta_salida), format=formato, **save_kwargs)
    tamanio_final = ruta_salida.stat().st_size

    img.close()
    if necesita_resize and img_resized is not img:
        img_resized.close()

    return ResultadoVision(
        ruta_original=str(ruta),
        ruta_procesada=str(ruta_salida),
        ancho_original=ancho_orig,
        alto_original=alto_orig,
        ancho_final=nuevo_ancho,
        alto_final=nuevo_alto,
        fue_redimensionada=necesita_resize,
        formato_salida=formato,
        tamanio_bytes=tamanio_final,
        pagina_pdf=None,
        dpi_render=None,
    )


def preparar_pagina_pdf(
    ruta_pdf: str,
    pagina: int,
    max_dimension: Optional[int] = None,
    directorio_salida: Optional[str] = None,
    dpi: Optional[int] = None,
) -> ResultadoVision:
    """Renderiza una página de PDF a imagen y la prepara para el proveedor.

    Usa PyMuPDF (fitz) para renderizar la página a la resolución indicada,
    luego aplica la misma validación/redimensionamiento que preparar_imagen.

    Args:
        ruta_pdf: Ruta al archivo PDF.
        pagina: Número de página (1-indexed).
        max_dimension: Máximo px. Default: VISION_CONFIG["max_dimension_px"].
        directorio_salida: Carpeta para la imagen. Si None, usa temporal.
        dpi: DPI para renderizar. Default: VISION_CONFIG["dpi_render_pdf"].

    Returns:
        ResultadoVision con la imagen de la página lista para el proveedor.

    Raises:
        FileNotFoundError: Si el PDF no existe.
        ValueError: Si la página está fuera de rango o no es PDF.
        ImportError: Si PyMuPDF no está instalado.
    """
    try:
        import fitz
    except ImportError:
        raise ImportError(
            "PyMuPDF (fitz) es requerido para renderizar PDFs. "
            "Instalar con: pip install PyMuPDF"
        )

    max_dim = max_dimension or VISION_CONFIG["max_dimension_px"]
    render_dpi = dpi or VISION_CONFIG.get("dpi_render_pdf", 200)
    formato = VISION_CONFIG.get("formato_salida", "PNG")
    ruta = Path(ruta_pdf)

    if not ruta.exists():
        raise FileNotFoundError(f"PDF no encontrado: {ruta_pdf}")

    if ruta.suffix.lower() != ".pdf":
        raise ValueError(f"No es un archivo PDF: {ruta.name}")

    doc = fitz.open(str(ruta))
    total_paginas = len(doc)

    if pagina < 1 or pagina > total_paginas:
        doc.close()
        raise ValueError(
            f"Página {pagina} fuera de rango. El PDF tiene {total_paginas} páginas."
        )

    # Renderizar página (0-indexed internamente)
    page = doc[pagina - 1]
    zoom = render_dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)

    ancho_orig = pix.width
    alto_orig = pix.height

    logger.info(
        "vision.preparar_pagina_pdf: %s pag=%d dpi=%d render=%dx%d max=%d",
        ruta.name, pagina, render_dpi, ancho_orig, alto_orig, max_dim,
    )

    # Convertir pixmap a PIL Image
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()

    # Calcular redimensionamiento
    nuevo_ancho, nuevo_alto = _calcular_nuevas_dimensiones(ancho_orig, alto_orig, max_dim)
    necesita_resize = (nuevo_ancho != ancho_orig) or (nuevo_alto != alto_orig)

    if necesita_resize:
        img_resized = img.resize((nuevo_ancho, nuevo_alto), _obtener_resample())
        logger.info(
            "vision.preparar_pagina_pdf: redimensionada %dx%d -> %dx%d (ratio=%.3f)",
            ancho_orig, alto_orig, nuevo_ancho, nuevo_alto,
            min(nuevo_ancho / ancho_orig, nuevo_alto / alto_orig),
        )
    else:
        img_resized = img

    # Guardar
    if directorio_salida:
        dir_out = Path(directorio_salida)
        dir_out.mkdir(parents=True, exist_ok=True)
        sufijo = f".{formato.lower()}"
        ruta_salida = dir_out / f"{ruta.stem}_p{pagina}_vision{sufijo}"
    else:
        sufijo = f".{formato.lower()}"
        tmp = tempfile.NamedTemporaryFile(
            prefix=f"{ruta.stem}_p{pagina}_vision_",
            suffix=sufijo,
            delete=False,
        )
        ruta_salida = Path(tmp.name)
        tmp.close()

    save_kwargs = {}
    if formato.upper() == "JPEG":
        if img_resized.mode in ("RGBA", "LA", "P"):
            img_resized = img_resized.convert("RGB")
        save_kwargs["quality"] = VISION_CONFIG.get("calidad_jpeg", 95)

    img_resized.save(str(ruta_salida), format=formato, **save_kwargs)
    tamanio_final = ruta_salida.stat().st_size

    img.close()
    if necesita_resize and img_resized is not img:
        img_resized.close()

    return ResultadoVision(
        ruta_original=str(ruta),
        ruta_procesada=str(ruta_salida),
        ancho_original=ancho_orig,
        alto_original=alto_orig,
        ancho_final=nuevo_ancho,
        alto_final=nuevo_alto,
        fue_redimensionada=necesita_resize,
        formato_salida=formato,
        tamanio_bytes=tamanio_final,
        pagina_pdf=pagina,
        dpi_render=render_dpi,
    )
