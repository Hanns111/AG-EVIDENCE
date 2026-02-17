# -*- coding: utf-8 -*-
"""
OCR Core — Motor OCR con PaddleOCR PP-OCRv5 + Tesseract Fallback
=================================================================
Modulo central de OCR para AG-EVIDENCE v2.0.

Motor primario: PaddleOCR 2.9.1 (CPU, API 2.x — ADR-007)
Motor fallback: Tesseract via pytesseract (si PaddleOCR no disponible)
Nota: RTX 5090 (sm_120) no compatible con PaddlePaddle CUDA 12.6

La interfaz publica se mantiene identica para compatibilidad con
pdf_text_extractor.py y futuros consumidores.

Referencia: ADR-006, ADR-007, Tarea #13, Tarea #14.

Version: 3.2.0
Fecha: 2026-02-17
"""

import io
import time
import subprocess
import logging
from dataclasses import dataclass
from collections import defaultdict
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

logger = logging.getLogger(__name__)

# =============================================================================
# DETECCION DE DEPENDENCIAS
# =============================================================================

PADDLEOCR_DISPONIBLE = False
TESSERACT_DISPONIBLE = False
CV2_DISPONIBLE = True
_ERRORES_DEPS = []

# PaddleOCR (motor primario)
try:
    from paddleocr import PaddleOCR as _PaddleOCRClass
    PADDLEOCR_DISPONIBLE = True
except ImportError:
    _PaddleOCRClass = None
    _ERRORES_DEPS.append("paddleocr no instalado")

# PyMuPDF (renderizado PDF)
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
    _ERRORES_DEPS.append("PyMuPDF no instalado")

# Pillow (imagenes)
try:
    from PIL import Image
except ImportError:
    Image = None
    _ERRORES_DEPS.append("Pillow no instalado")

# Tesseract (motor fallback)
try:
    import pytesseract
    TESSERACT_DISPONIBLE = True
except ImportError:
    pytesseract = None
    _ERRORES_DEPS.append("pytesseract no instalado")

# OpenCV + NumPy (metricas de imagen, deskew)
try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None
    CV2_DISPONIBLE = False

# numpy puede venir de paddleocr sin cv2
if np is None:
    try:
        import numpy as np
    except ImportError:
        pass

# Motor activo
if PADDLEOCR_DISPONIBLE:
    _ACTIVE_ENGINE = "paddleocr"
elif TESSERACT_DISPONIBLE:
    _ACTIVE_ENGINE = "tesseract"
else:
    _ACTIVE_ENGINE = "none"


__version__ = "3.2.0"


# =============================================================================
# DATACLASS — LINEA OCR CON BBOX Y CONFIANZA
# =============================================================================

@dataclass
class LineaOCR:
    """
    Una linea de texto detectada por OCR con ubicacion y confianza.

    Attributes:
        texto: Texto de la linea.
        bbox: Bounding box (x_min, y_min, x_max, y_max) en pixeles, o None
              si el motor no provee datos de ubicacion.
        confianza: Score de confianza 0.0–1.0, o None si no disponible.
        motor: Motor que produjo esta linea ("paddleocr" o "tesseract").
    """
    texto: str
    bbox: Optional[Tuple[float, float, float, float]]  # (x_min, y_min, x_max, y_max) o None
    confianza: Optional[float]                          # 0.0 - 1.0 o None
    motor: str = ""                                     # "paddleocr" o "tesseract"

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a dict JSON-compatible."""
        return {
            "texto": self.texto,
            "bbox": list(self.bbox) if self.bbox is not None else None,
            "confianza": round(self.confianza, 4) if self.confianza is not None else None,
            "motor": self.motor,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LineaOCR":
        """Deserializa desde dict."""
        data = dict(data)
        if "bbox" in data and isinstance(data["bbox"], list):
            data["bbox"] = tuple(data["bbox"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# =============================================================================
# HELPERS PRIVADOS — BBOX Y TRACELOGGER
# =============================================================================

def _polygon_to_bbox(polygon: List[List[float]]) -> Tuple[float, float, float, float]:
    """
    Convierte poligono PaddleOCR [[x1,y1],[x2,y2],...] a (x_min, y_min, x_max, y_max).

    PaddleOCR retorna dt_polys como lista de 4 puntos [x,y] que forman un
    cuadrilatero. Esta funcion extrae el rectangulo envolvente.
    """
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return (min(xs), min(ys), max(xs), max(ys))


def _agrupar_palabras_en_lineas(data: Dict[str, Any]) -> List[LineaOCR]:
    """
    Agrupa palabras Tesseract en lineas usando block_num/line_num.

    Tesseract retorna datos por palabra individual. Esta funcion:
    1. Agrupa palabras por (block_num, line_num)
    2. Une los textos de cada linea con espacios
    3. Calcula la union de bboxes por linea
    4. Promedia las confianzas por linea

    Limitacion conocida: documentos multi-columna pueden generar lineas
    incorrectas si Tesseract asigna el mismo block_num a columnas distintas.

    Args:
        data: Dict de pytesseract.image_to_data(output_type=Output.DICT)

    Returns:
        List[LineaOCR] con una entrada por linea detectada.
    """
    # Agrupar por (block_num, line_num)
    lineas_agrupadas: Dict[Tuple[int, int], List[int]] = defaultdict(list)

    n = len(data.get("text", []))
    for i in range(n):
        texto = data["text"][i]
        if not texto.strip():
            continue
        block = data.get("block_num", [0] * n)[i]
        line = data.get("line_num", [0] * n)[i]
        lineas_agrupadas[(block, line)].append(i)

    resultado: List[LineaOCR] = []
    for key in sorted(lineas_agrupadas.keys()):
        indices = lineas_agrupadas[key]
        textos = [data["text"][i] for i in indices]
        texto_linea = " ".join(textos)

        # Union de bboxes
        x_mins, y_mins, x_maxs, y_maxs = [], [], [], []
        for i in indices:
            left = data.get("left", [0] * n)[i]
            top = data.get("top", [0] * n)[i]
            width = data.get("width", [0] * n)[i]
            height = data.get("height", [0] * n)[i]
            x_mins.append(float(left))
            y_mins.append(float(top))
            x_maxs.append(float(left + width))
            y_maxs.append(float(top + height))

        bbox: Optional[Tuple[float, float, float, float]] = None
        if x_mins:
            bbox = (min(x_mins), min(y_mins), max(x_maxs), max(y_maxs))

        # Promedio de confianzas (Tesseract: 0-100, normalizar a 0-1)
        confs = []
        for i in indices:
            conf = data.get("conf", [-1] * n)[i]
            if conf != -1:
                confs.append(conf / 100.0)

        confianza: Optional[float] = None
        if confs:
            confianza = sum(confs) / len(confs)

        resultado.append(LineaOCR(
            texto=texto_linea,
            bbox=bbox,
            confianza=confianza,
            motor="tesseract",
        ))

    return resultado


def _log_ocr(trace_logger: Any, level: str, message: str, context: Optional[Dict] = None) -> None:
    """
    Log OCR event via TraceLogger (duck typing). Silent on error.

    No importa TraceLogger directamente — se recibe como parametro opcional.
    Patron copiado de abstencion.py.
    """
    if not trace_logger:
        return
    try:
        log_method = getattr(trace_logger, level.lower(), None)
        if log_method is None:
            log_method = getattr(trace_logger, "info", None)
        if log_method is None:
            return
        log_method(
            message,
            agent_id="AG-OCR",
            operation="ejecutar_ocr",
            context=context or {},
        )
    except Exception:
        pass  # TraceLogger nunca debe crashear OCR


# =============================================================================
# MAPEO DE IDIOMAS (Tesseract codes -> PaddleOCR codes)
# =============================================================================

_LANG_MAP_TO_PADDLE = {
    "spa": "es",
    "eng": "en",
    "por": "pt",
    "fra": "fr",
    "deu": "de",
    "ita": "it",
    "nld": "nl",
    "pol": "pl",
    "ron": "ro",
    "tur": "tr",
    "cat": "ca",
    "eus": "eu",
    "glg": "gl",
    "lat": "latin",
}

_PADDLE_SUPPORTED_LANGS = {
    "es", "en", "pt", "fr", "de", "it", "nl", "pl", "ro", "tr",
    "ca", "eu", "gl", "latin", "ch", "japan", "korean", "chinese_cht",
    "af", "bs", "cs", "cy", "da", "et", "ga", "hr", "hu", "id",
    "is", "lt", "mi", "ms", "no", "sk", "sl", "sq", "sv", "sw",
    "tl",
}


def _map_lang_to_paddle(lang: str) -> str:
    """Convierte codigo de idioma Tesseract a PaddleOCR."""
    return _LANG_MAP_TO_PADDLE.get(lang, lang)


# =============================================================================
# SINGLETON PADDLEOCR
# =============================================================================

_paddleocr_instances: Dict[str, Any] = {}


def _get_paddleocr_instance(paddle_lang: str) -> Any:
    """
    Obtiene (o crea) una instancia singleton de PaddleOCR por idioma.

    Usa PaddleOCR 2.x API (use_angle_cls, lang, show_log).
    GPU via PaddlePaddle no es compatible con RTX 5090 (sm_120 Blackwell),
    por lo que se usa CPU con PaddleOCR PP-OCRv3 que tiene excelente precision.

    Los modelos se descargan automaticamente en la primera ejecucion.
    """
    if paddle_lang in _paddleocr_instances:
        return _paddleocr_instances[paddle_lang]

    if _PaddleOCRClass is None:
        raise ImportError("paddleocr no esta instalado")

    try:
        instance = _PaddleOCRClass(
            use_angle_cls=True,
            lang=paddle_lang,
            show_log=False,
        )
        logger.info("PaddleOCR inicializado (CPU) para lang=%s", paddle_lang)
    except Exception as e:
        raise RuntimeError(
            f"PaddleOCR no pudo inicializarse: {str(e)[:100]}"
        ) from e

    _paddleocr_instances[paddle_lang] = instance
    return instance


# =============================================================================
# FUNCIONES DE VERIFICACION
# =============================================================================

def _run_cmd(cmd: List[str]) -> Tuple[int, str, str]:
    """Ejecuta un comando y retorna (returncode, stdout, stderr)"""
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = p.communicate(timeout=30)
        return p.returncode, out.strip(), err.strip()
    except Exception as e:
        return -1, "", str(e)


def verificar_tesseract() -> Tuple[bool, str]:
    """Verifica que Tesseract este instalado y accesible."""
    if not TESSERACT_DISPONIBLE:
        return False, "pytesseract no instalado"
    try:
        version = pytesseract.get_tesseract_version()
        return True, f"Tesseract v{version}"
    except Exception as e:
        return False, str(e)


def verificar_paddleocr() -> Tuple[bool, str]:
    """Verifica que PaddleOCR este instalado y funcional."""
    if not PADDLEOCR_DISPONIBLE:
        return False, "paddleocr no instalado"
    try:
        # Verificar que se puede crear instancia
        _get_paddleocr_instance("en")
        return True, "PaddleOCR PP-OCRv5 disponible"
    except Exception as e:
        return False, f"PaddleOCR error: {str(e)[:100]}"


def verificar_ocr() -> Tuple[bool, str, str]:
    """
    Verificacion unificada del motor OCR activo.

    Returns:
        (disponible, mensaje, nombre_motor)
        nombre_motor: "paddleocr" | "tesseract" | "none"
    """
    if PADDLEOCR_DISPONIBLE:
        ok, msg = verificar_paddleocr()
        if ok:
            return True, msg, "paddleocr"
        # PaddleOCR fallo, intentar Tesseract
        logger.warning("PaddleOCR verificacion fallo: %s", msg)

    if TESSERACT_DISPONIBLE:
        ok, msg = verificar_tesseract()
        if ok:
            return True, msg, "tesseract"
        return False, msg, "tesseract"

    return False, "Ningun motor OCR disponible", "none"


# =============================================================================
# IDIOMAS
# =============================================================================

def list_tesseract_langs() -> Dict[str, Any]:
    """Lista los idiomas disponibles en Tesseract."""
    rc, out, err = _run_cmd(["tesseract", "--list-langs"])
    if rc != 0:
        return {"ok": False, "langs": [], "raw": out, "err": err}

    langs = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("List of available languages"):
            continue
        langs.append(line)

    return {"ok": True, "langs": langs, "raw": out, "err": err}


def ensure_lang_available(requested_lang: str) -> Tuple[bool, str, List[str]]:
    """
    Verifica que el idioma solicitado este disponible en el motor activo.

    Para PaddleOCR: verifica contra la tabla de mapeo interna.
    Para Tesseract: verifica contra tesseract --list-langs.
    """
    # PaddleOCR primero
    if PADDLEOCR_DISPONIBLE:
        paddle_lang = _map_lang_to_paddle(requested_lang)
        if paddle_lang in _PADDLE_SUPPORTED_LANGS:
            return True, f"OK (PaddleOCR, lang={paddle_lang})", list(_PADDLE_SUPPORTED_LANGS)
        # Lang no en PaddleOCR, intentar Tesseract

    # Tesseract fallback
    if TESSERACT_DISPONIBLE:
        info = list_tesseract_langs()
        if not info["ok"]:
            return False, f"No se pudo ejecutar 'tesseract --list-langs': {info['err']}", []

        langs = info["langs"]
        if requested_lang not in langs:
            return False, (
                f"Idioma '{requested_lang}' NO esta disponible. "
                f"Idiomas disponibles: {langs}."
            ), langs

        return True, "OK (Tesseract)", langs

    return False, "Ningun motor OCR disponible para verificar idiomas", []


# =============================================================================
# RENDERIZADO PDF — con validacion obligatoria de dimensiones (Regla 2)
# =============================================================================

def _validar_dimensiones(img: "Image.Image", max_dim: Optional[int] = None) -> "Image.Image":
    """
    Valida y redimensiona imagen si excede el limite del proveedor.

    Regla 2: Ningun imagen renderizada puede continuar en el pipeline
    sin pasar por esta validacion. El original no se modifica — se
    retorna una copia redimensionada si es necesario.

    Args:
        img: Imagen PIL a validar.
        max_dim: Limite maximo en px (ancho o alto). Si None, usa VISION_CONFIG.

    Returns:
        Imagen PIL dentro del limite (puede ser la misma si no excede).
    """
    from config.settings import VISION_CONFIG

    if max_dim is None:
        max_dim = VISION_CONFIG.get("max_dimension_px", 2000)

    ancho, alto = img.size

    if ancho <= max_dim and alto <= max_dim:
        return img

    # Calcular nuevas dimensiones manteniendo aspect ratio
    if ancho >= alto:
        nuevo_ancho = max_dim
        nuevo_alto = max(1, int(alto * (max_dim / ancho)))
    else:
        nuevo_alto = max_dim
        nuevo_ancho = max(1, int(ancho * (max_dim / alto)))

    logger.info(
        "vision_check: redimensionando %dx%d -> %dx%d (max=%dpx)",
        ancho, alto, nuevo_ancho, nuevo_alto, max_dim,
    )

    resample = Image.LANCZOS if hasattr(Image, "LANCZOS") else Image.BICUBIC
    return img.resize((nuevo_ancho, nuevo_alto), resample)


def renderizar_pagina(pdf_path: Path, page_num: int, dpi: int = 200) -> Optional["Image.Image"]:
    """
    Renderiza una pagina PDF a imagen PIL usando PyMuPDF.

    Incluye validacion obligatoria de dimensiones (Regla 2):
    si la imagen renderizada excede el limite configurado en
    VISION_CONFIG["max_dimension_px"], se redimensiona automaticamente
    antes de retornarla. El PDF original no se modifica.

    Args:
        pdf_path: Ruta al archivo PDF (Path o str)
        page_num: Numero de pagina (1-indexed)
        dpi: Resolucion de renderizado

    Returns:
        Imagen PIL (dentro del limite de dimensiones) o None si hay error
    """
    if fitz is None or Image is None:
        return None

    try:
        doc = fitz.open(str(pdf_path))

        if page_num < 1 or page_num > len(doc):
            doc.close()
            return None

        page = doc[page_num - 1]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))

        doc.close()

        # Regla 2: validacion obligatoria de dimensiones
        img = _validar_dimensiones(img)

        return img

    except Exception:
        return None


# =============================================================================
# ROTACION Y DESKEW (Tesseract-only helpers, usados en fallback)
# =============================================================================

def _detectar_rotacion_osd(img: "Image.Image") -> Tuple[int, str]:
    """Detecta rotacion usando Tesseract OSD."""
    if not TESSERACT_DISPONIBLE:
        return 0, "no_tesseract"
    try:
        osd = pytesseract.image_to_osd(img, output_type=pytesseract.Output.DICT)
        rotate = osd.get("rotate", 0)
        return int(rotate), "osd"
    except Exception as e:
        return 0, f"osd_failed:{str(e)[:50]}"


def _detectar_rotacion_bruteforce(img: "Image.Image", lang: str = "eng") -> Tuple[int, str]:
    """Detecta rotacion probando 0, 90, 180, 270."""
    if not TESSERACT_DISPONIBLE:
        return 0, "no_tesseract"

    mejor_angulo = 0
    mejor_palabras = 0
    mejor_confianza = 0.0

    for angulo in [0, 90, 180, 270]:
        if angulo == 0:
            img_rotada = img
        else:
            img_rotada = img.rotate(-angulo, expand=True)

        try:
            data = pytesseract.image_to_data(
                img_rotada, lang=lang,
                output_type=pytesseract.Output.DICT,
                config='--psm 6'
            )

            palabras = sum(1 for t in data['text'] if t.strip())
            confianzas = [c for c in data['conf'] if c != -1 and c > 0]
            confianza = sum(confianzas) / len(confianzas) / 100 if confianzas else 0

            if palabras > mejor_palabras or (palabras == mejor_palabras and confianza > mejor_confianza):
                mejor_angulo = angulo
                mejor_palabras = palabras
                mejor_confianza = confianza

            if palabras >= 20 and confianza >= 0.75:
                return angulo, "bruteforce_early"

        except Exception:
            continue

    return mejor_angulo, "bruteforce"


def _detectar_deskew(img: "Image.Image") -> float:
    """Detecta inclinacion leve (deskew)."""
    if not CV2_DISPONIBLE:
        return 0.0

    try:
        img_gray = img.convert('L')
        img_array = np.array(img_gray)

        binary = cv2.adaptiveThreshold(
            img_array, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )

        coords = np.column_stack(np.where(binary > 0))
        if len(coords) < 100:
            return 0.0

        rect = cv2.minAreaRect(coords)
        angle = rect[-1]

        if angle < -45:
            angle = 90 + angle
        elif angle > 45:
            angle = angle - 90

        if abs(angle) <= 15:
            return round(angle, 2)
        return 0.0

    except Exception:
        return 0.0


def _aplicar_rotacion(img: "Image.Image", angulo: int) -> "Image.Image":
    """Aplica rotacion de 0, 90, 180 o 270 grados."""
    if angulo == 0:
        return img
    elif angulo == 90:
        return img.rotate(-90, expand=True)
    elif angulo == 180:
        return img.rotate(180, expand=True)
    elif angulo == 270:
        return img.rotate(-270, expand=True)
    return img


def _aplicar_deskew(img: "Image.Image", angulo: float) -> "Image.Image":
    """Aplica correccion de inclinacion leve."""
    if not CV2_DISPONIBLE or abs(angulo) < 0.5:
        return img

    try:
        img_array = np.array(img)
        h, w = img_array.shape[:2]
        center = (w // 2, h // 2)

        M = cv2.getRotationMatrix2D(center, angulo, 1.0)
        rotated = cv2.warpAffine(
            img_array, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )

        return Image.fromarray(rotated)
    except Exception:
        return img


def preprocesar_rotacion(img: "Image.Image", lang: str = "eng") -> Tuple["Image.Image", Dict[str, Any]]:
    """
    Preprocesa la imagen detectando y corrigiendo rotacion.

    Si PaddleOCR es el motor activo, delega la rotacion a PaddleOCR
    (use_doc_orientation_classify=True) y retorna info dict indicando
    metodo "paddleocr_builtin".

    Si Tesseract es el motor activo, usa la logica manual de OSD/bruteforce.

    Returns:
        (imagen_corregida, info_rotacion)
    """
    info = {
        "rotacion_grados": 0,
        "rotacion_metodo": "none",
        "deskew_grados": 0.0,
        "rotacion_aplicada": False
    }

    # PaddleOCR maneja rotacion internamente
    if _ACTIVE_ENGINE == "paddleocr":
        info["rotacion_metodo"] = "paddleocr_builtin"
        # No modificamos la imagen; PaddleOCR la corrige en predict()
        return img, info

    # Tesseract: deteccion manual
    rotacion, metodo = _detectar_rotacion_osd(img)

    if "osd_failed" in metodo or metodo == "no_tesseract":
        rotacion, metodo = _detectar_rotacion_bruteforce(img, lang)

    info["rotacion_metodo"] = metodo

    if rotacion != 0:
        img = _aplicar_rotacion(img, rotacion)
        info["rotacion_grados"] = rotacion
        info["rotacion_aplicada"] = True

    deskew = _detectar_deskew(img)
    if abs(deskew) >= 0.5:
        img = _aplicar_deskew(img, deskew)
        info["deskew_grados"] = deskew
        info["rotacion_aplicada"] = True
        info["rotacion_grados"] = rotacion + deskew

    info["rotacion_grados"] = round(info["rotacion_grados"], 2)

    return img, info


# =============================================================================
# METRICAS DE IMAGEN (SIN CAMBIOS — solo usa cv2)
# =============================================================================

def calcular_metricas_imagen(img: "Image.Image", dpi_render: int = 200) -> Dict[str, Any]:
    """Calcula metricas de calidad de imagen."""
    metricas = {
        "dpi_estimado": dpi_render,
        "width_px": img.width,
        "height_px": img.height,
        "contraste": None,
        "blur_score": None,
    }

    if not CV2_DISPONIBLE:
        metricas["advertencia"] = "opencv no disponible"
        return metricas

    try:
        img_gray = img.convert('L')
        img_array = np.array(img_gray)

        p5 = np.percentile(img_array, 5)
        p95 = np.percentile(img_array, 95)
        metricas["contraste"] = round((p95 - p5) / 255.0, 3)

        laplacian = cv2.Laplacian(img_array, cv2.CV_64F)
        metricas["blur_score"] = round(laplacian.var(), 2)
    except Exception:
        pass

    return metricas


# =============================================================================
# OCR — IMPLEMENTACIONES POR MOTOR
# =============================================================================

def _ejecutar_ocr_paddleocr(img: "Image.Image", lang: str = "eng") -> Dict[str, Any]:
    """
    Ejecuta OCR usando PaddleOCR PP-OCRv5.

    Returns:
        Dict con: lang, texto_completo, snippet_200, confianza_promedio,
                  num_palabras, tiempo_ms, error, motor_ocr, lineas
    """
    resultado = {
        "lang": lang,
        "texto_completo": "",
        "snippet_200": "",
        "confianza_promedio": 0.0,
        "num_palabras": 0,
        "tiempo_ms": 0,
        "error": None,
        "motor_ocr": "paddleocr",
        "lineas": [],
    }

    paddle_lang = _map_lang_to_paddle(lang)
    ocr_instance = _get_paddleocr_instance(paddle_lang)

    inicio = time.time()

    # PaddleOCR 2.x acepta numpy arrays
    if np is not None:
        img_input = np.array(img)
    else:
        # Fallback: guardar a bytes y pasar
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img.save(f, format="PNG")
            img_input = f.name

    # PaddleOCR 2.x API: ocr.ocr(img, cls=True)
    # Retorna: [[[box, (text, score)], ...]] (lista de paginas, cada una lista de lineas)
    result = ocr_instance.ocr(img_input, cls=True)

    resultado["tiempo_ms"] = int((time.time() - inicio) * 1000)

    textos = []
    confianzas = []
    lineas_ocr: List[LineaOCR] = []

    if result and result[0]:
        for line in result[0]:
            box = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            text = line[1][0]
            score = line[1][1]

            textos.append(text)
            confianzas.append(score)

            # Convertir polygon (4 puntos) a bbox
            bbox = _polygon_to_bbox(box) if box else None
            lineas_ocr.append(LineaOCR(
                texto=text,
                bbox=bbox,
                confianza=score,
                motor="paddleocr",
            ))

    # Filtrar textos vacios
    textos_filtrados = [t for t in textos if t.strip()]
    texto_completo = " ".join(textos_filtrados)

    resultado["texto_completo"] = texto_completo
    resultado["snippet_200"] = texto_completo[:200] if texto_completo else ""
    resultado["num_palabras"] = len(textos_filtrados)
    resultado["lineas"] = [l.to_dict() for l in lineas_ocr]

    if confianzas:
        # PaddleOCR scores ya estan en rango 0-1
        resultado["confianza_promedio"] = round(
            sum(confianzas) / len(confianzas), 3
        )

    return resultado


def _ejecutar_ocr_tesseract(img: "Image.Image", lang: str = "eng") -> Dict[str, Any]:
    """
    Ejecuta OCR usando Tesseract (motor fallback).

    Returns:
        Dict con: lang, texto_completo, snippet_200, confianza_promedio,
                  num_palabras, tiempo_ms, error, motor_ocr, lineas
    """
    resultado = {
        "lang": lang,
        "texto_completo": "",
        "snippet_200": "",
        "confianza_promedio": 0.0,
        "num_palabras": 0,
        "tiempo_ms": 0,
        "error": None,
        "motor_ocr": "tesseract",
        "lineas": [],
    }

    if not TESSERACT_DISPONIBLE:
        resultado["error"] = "pytesseract no disponible"
        return resultado

    try:
        inicio = time.time()

        data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)

        resultado["tiempo_ms"] = int((time.time() - inicio) * 1000)

        textos = []
        confianzas = []

        for i, texto in enumerate(data['text']):
            if texto.strip():
                textos.append(texto)
                conf = data['conf'][i]
                if conf != -1:
                    confianzas.append(conf)

        texto_completo = " ".join(textos)
        resultado["texto_completo"] = texto_completo
        resultado["snippet_200"] = texto_completo[:200] if texto_completo else ""
        resultado["num_palabras"] = len(textos)

        if confianzas:
            # Tesseract retorna 0-100, normalizamos a 0-1
            resultado["confianza_promedio"] = round(sum(confianzas) / len(confianzas) / 100, 3)

        # Agrupar palabras en lineas con bbox y confianza
        lineas_ocr = _agrupar_palabras_en_lineas(data)
        resultado["lineas"] = [l.to_dict() for l in lineas_ocr]

    except Exception as e:
        resultado["error"] = str(e)

    return resultado


# =============================================================================
# FUNCION PUBLICA — DISPATCH CON FALLBACK
# =============================================================================

def ejecutar_ocr(
    img: "Image.Image",
    lang: str = "eng",
    trace_logger: Any = None,
) -> Dict[str, Any]:
    """
    Ejecuta OCR con el motor disponible (PaddleOCR primario, Tesseract fallback).

    Logica de dispatch:
    1. Si PaddleOCR disponible: intentar PaddleOCR
       a. Si falla en runtime: auto-fallback a Tesseract
    2. Si solo Tesseract: usar Tesseract
    3. Si ninguno: retornar error

    Args:
        img: Imagen PIL a procesar.
        lang: Codigo de idioma Tesseract (ej: "spa", "eng").
        trace_logger: Instancia opcional de TraceLogger (duck typing).
                      Si se provee, registra eventos OCR. Si es None, silencioso.

    Returns:
        Dict con: lang, texto_completo, snippet_200, confianza_promedio,
                  num_palabras, tiempo_ms, error, motor_ocr, lineas

        motor_ocr puede ser: "paddleocr", "tesseract", "tesseract_fallback", "none"
        lineas: List[Dict] con bbox + confianza por linea detectada
    """
    # Log inicio
    img_dims = None
    try:
        img_dims = {"width": img.size[0], "height": img.size[1]}
    except Exception:
        pass
    _log_ocr(trace_logger, "info", "OCR iniciado", {
        "lang": lang,
        "imagen": img_dims,
        "motor_activo": _ACTIVE_ENGINE,
    })

    # Ruta 1: PaddleOCR primario
    if PADDLEOCR_DISPONIBLE:
        try:
            result = _ejecutar_ocr_paddleocr(img, lang)
            _log_ocr(trace_logger, "info", "OCR completado", {
                "motor": result.get("motor_ocr"),
                "num_palabras": result.get("num_palabras"),
                "confianza_promedio": result.get("confianza_promedio"),
                "num_lineas": len(result.get("lineas", [])),
                "tiempo_ms": result.get("tiempo_ms"),
            })
            return result
        except Exception as e:
            logger.warning(
                "PaddleOCR fallo en runtime (%s), fallback a Tesseract...",
                str(e)[:100]
            )
            _log_ocr(trace_logger, "warning", f"PaddleOCR fallo, fallback a Tesseract: {str(e)[:100]}")
            # Auto-fallback a Tesseract
            if TESSERACT_DISPONIBLE:
                result = _ejecutar_ocr_tesseract(img, lang)
                result["motor_ocr"] = "tesseract_fallback"
                _log_ocr(trace_logger, "info", "OCR completado via fallback", {
                    "motor": "tesseract_fallback",
                    "num_palabras": result.get("num_palabras"),
                    "confianza_promedio": result.get("confianza_promedio"),
                    "num_lineas": len(result.get("lineas", [])),
                    "tiempo_ms": result.get("tiempo_ms"),
                })
                return result
            else:
                _log_ocr(trace_logger, "error", "PaddleOCR fallo y Tesseract no disponible")
                return {
                    "lang": lang,
                    "texto_completo": "",
                    "snippet_200": "",
                    "confianza_promedio": 0.0,
                    "num_palabras": 0,
                    "tiempo_ms": 0,
                    "error": f"PaddleOCR fallo y Tesseract no disponible: {str(e)[:100]}",
                    "motor_ocr": "none",
                    "lineas": [],
                }

    # Ruta 2: Tesseract unico motor
    if TESSERACT_DISPONIBLE:
        result = _ejecutar_ocr_tesseract(img, lang)
        _log_ocr(trace_logger, "info", "OCR completado", {
            "motor": result.get("motor_ocr"),
            "num_palabras": result.get("num_palabras"),
            "confianza_promedio": result.get("confianza_promedio"),
            "num_lineas": len(result.get("lineas", [])),
            "tiempo_ms": result.get("tiempo_ms"),
        })
        return result

    # Ruta 3: Ningun motor disponible
    _log_ocr(trace_logger, "error", "Ningun motor OCR disponible")
    return {
        "lang": lang,
        "texto_completo": "",
        "snippet_200": "",
        "confianza_promedio": 0.0,
        "num_palabras": 0,
        "tiempo_ms": 0,
        "error": "Ningun motor OCR disponible (instalar paddleocr o pytesseract)",
        "motor_ocr": "none",
        "lineas": [],
    }
