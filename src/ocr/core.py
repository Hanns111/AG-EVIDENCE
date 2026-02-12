# -*- coding: utf-8 -*-
"""
OCR Core — Motor OCR con PaddleOCR PP-OCRv5 + Tesseract Fallback
=================================================================
Modulo central de OCR para AG-EVIDENCE v2.0.

Motor primario: PaddleOCR PP-OCRv5 (GPU acelerado via RTX 5090)
Motor fallback: Tesseract via pytesseract (si PaddleOCR no disponible)

La interfaz publica se mantiene identica para compatibilidad con
pdf_text_extractor.py y futuros consumidores.

Referencia: ADR-006, Tarea #13.

Version: 3.0.0
Fecha: 2026-02-11
"""

import io
import time
import subprocess
import logging
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


__version__ = "3.0.0"


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

    Intenta GPU primero, si falla usa CPU.
    Los modelos se descargan automaticamente en la primera ejecucion.
    """
    if paddle_lang in _paddleocr_instances:
        return _paddleocr_instances[paddle_lang]

    if _PaddleOCRClass is None:
        raise ImportError("paddleocr no esta instalado")

    # Intentar con GPU
    try:
        instance = _PaddleOCRClass(
            lang=paddle_lang,
            text_detection_model_name="PP-OCRv5_server_det",
            text_recognition_model_name="PP-OCRv5_server_rec",
            use_doc_orientation_classify=True,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device="gpu:0",
        )
        logger.info("PaddleOCR inicializado con GPU para lang=%s", paddle_lang)
    except Exception as e_gpu:
        logger.warning("PaddleOCR GPU fallo (%s), intentando CPU...", str(e_gpu)[:80])
        try:
            instance = _PaddleOCRClass(
                lang=paddle_lang,
                text_detection_model_name="PP-OCRv5_server_det",
                text_recognition_model_name="PP-OCRv5_server_rec",
                use_doc_orientation_classify=True,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                device="cpu",
            )
            logger.info("PaddleOCR inicializado con CPU para lang=%s", paddle_lang)
        except Exception as e_cpu:
            raise RuntimeError(
                f"PaddleOCR no pudo inicializarse ni con GPU ni CPU: "
                f"GPU={str(e_gpu)[:60]}, CPU={str(e_cpu)[:60]}"
            ) from e_cpu

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
# RENDERIZADO PDF (SIN CAMBIOS — solo usa PyMuPDF)
# =============================================================================

def renderizar_pagina(pdf_path: Path, page_num: int, dpi: int = 200) -> Optional["Image.Image"]:
    """
    Renderiza una pagina PDF a imagen PIL usando PyMuPDF.

    Args:
        pdf_path: Ruta al archivo PDF (Path o str)
        page_num: Numero de pagina (1-indexed)
        dpi: Resolucion de renderizado

    Returns:
        Imagen PIL o None si hay error
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
                  num_palabras, tiempo_ms, error, motor_ocr
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
    }

    paddle_lang = _map_lang_to_paddle(lang)
    ocr_instance = _get_paddleocr_instance(paddle_lang)

    inicio = time.time()

    # PaddleOCR acepta numpy arrays
    if np is not None:
        img_input = np.array(img)
    else:
        # Fallback: guardar a bytes y pasar
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img.save(f, format="PNG")
            img_input = f.name

    result = ocr_instance.predict(img_input)

    resultado["tiempo_ms"] = int((time.time() - inicio) * 1000)

    textos = []
    confianzas = []

    for res in result:
        json_data = res.json
        rec_texts = json_data.get("rec_texts", [])
        rec_scores = json_data.get("rec_scores", [])
        textos.extend(rec_texts)
        confianzas.extend(rec_scores)

    # Filtrar textos vacios
    textos_filtrados = [t for t in textos if t.strip()]
    texto_completo = " ".join(textos_filtrados)

    resultado["texto_completo"] = texto_completo
    resultado["snippet_200"] = texto_completo[:200] if texto_completo else ""
    resultado["num_palabras"] = len(textos_filtrados)

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
                  num_palabras, tiempo_ms, error, motor_ocr
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

    except Exception as e:
        resultado["error"] = str(e)

    return resultado


# =============================================================================
# FUNCION PUBLICA — DISPATCH CON FALLBACK
# =============================================================================

def ejecutar_ocr(img: "Image.Image", lang: str = "eng") -> Dict[str, Any]:
    """
    Ejecuta OCR con el motor disponible (PaddleOCR primario, Tesseract fallback).

    Logica de dispatch:
    1. Si PaddleOCR disponible: intentar PaddleOCR
       a. Si falla en runtime: auto-fallback a Tesseract
    2. Si solo Tesseract: usar Tesseract
    3. Si ninguno: retornar error

    Returns:
        Dict con: lang, texto_completo, snippet_200, confianza_promedio,
                  num_palabras, tiempo_ms, error, motor_ocr

        motor_ocr puede ser: "paddleocr", "tesseract", "tesseract_fallback", "none"
    """
    # Ruta 1: PaddleOCR primario
    if PADDLEOCR_DISPONIBLE:
        try:
            return _ejecutar_ocr_paddleocr(img, lang)
        except Exception as e:
            logger.warning(
                "PaddleOCR fallo en runtime (%s), fallback a Tesseract...",
                str(e)[:100]
            )
            # Auto-fallback a Tesseract
            if TESSERACT_DISPONIBLE:
                result = _ejecutar_ocr_tesseract(img, lang)
                result["motor_ocr"] = "tesseract_fallback"
                return result
            else:
                return {
                    "lang": lang,
                    "texto_completo": "",
                    "snippet_200": "",
                    "confianza_promedio": 0.0,
                    "num_palabras": 0,
                    "tiempo_ms": 0,
                    "error": f"PaddleOCR fallo y Tesseract no disponible: {str(e)[:100]}",
                    "motor_ocr": "none",
                }

    # Ruta 2: Tesseract unico motor
    if TESSERACT_DISPONIBLE:
        return _ejecutar_ocr_tesseract(img, lang)

    # Ruta 3: Ningun motor disponible
    return {
        "lang": lang,
        "texto_completo": "",
        "snippet_200": "",
        "confianza_promedio": 0.0,
        "num_palabras": 0,
        "tiempo_ms": 0,
        "error": "Ningun motor OCR disponible (instalar paddleocr o pytesseract)",
        "motor_ocr": "none",
    }
