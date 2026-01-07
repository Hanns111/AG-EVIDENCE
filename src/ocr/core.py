# -*- coding: utf-8 -*-
"""
OCR Core — Funciones base para OCR con Tesseract
=================================================
Módulo reutilizable extraído de tools/ocr_smoke_test.py.
"""

import io
import time
import subprocess
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

# Verificar dependencias
TESSERACT_DISPONIBLE = True
CV2_DISPONIBLE = True
_ERRORES_DEPS = []

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
    _ERRORES_DEPS.append("PyMuPDF no instalado")

try:
    from PIL import Image
except ImportError:
    Image = None
    _ERRORES_DEPS.append("Pillow no instalado")

try:
    import pytesseract
except ImportError:
    pytesseract = None
    TESSERACT_DISPONIBLE = False
    _ERRORES_DEPS.append("pytesseract no instalado")

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None
    CV2_DISPONIBLE = False


def _run_cmd(cmd: List[str]) -> Tuple[int, str, str]:
    """Ejecuta un comando y retorna (returncode, stdout, stderr)"""
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = p.communicate(timeout=30)
        return p.returncode, out.strip(), err.strip()
    except Exception as e:
        return -1, "", str(e)


def verificar_tesseract() -> Tuple[bool, str]:
    """Verifica que Tesseract esté instalado y accesible."""
    if not TESSERACT_DISPONIBLE:
        return False, "pytesseract no instalado"
    try:
        version = pytesseract.get_tesseract_version()
        return True, f"Tesseract v{version}"
    except Exception as e:
        return False, str(e)


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
    """Verifica que el idioma solicitado esté disponible."""
    info = list_tesseract_langs()
    if not info["ok"]:
        return False, f"No se pudo ejecutar 'tesseract --list-langs': {info['err']}", []
    
    langs = info["langs"]
    if requested_lang not in langs:
        return False, (
            f"Idioma '{requested_lang}' NO está instalado. "
            f"Idiomas disponibles: {langs}."
        ), langs
    
    return True, "OK", langs


def renderizar_pagina(pdf_path: Path, page_num: int, dpi: int = 200) -> Optional["Image.Image"]:
    """
    Renderiza una página PDF a imagen PIL usando PyMuPDF.
    
    Args:
        pdf_path: Ruta al archivo PDF (Path o str)
        page_num: Número de página (1-indexed)
        dpi: Resolución de renderizado
        
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
# ROTACIÓN Y DESKEW
# =============================================================================

def _detectar_rotacion_osd(img: "Image.Image") -> Tuple[int, str]:
    """Detecta rotación usando Tesseract OSD."""
    if not TESSERACT_DISPONIBLE:
        return 0, "no_tesseract"
    try:
        osd = pytesseract.image_to_osd(img, output_type=pytesseract.Output.DICT)
        rotate = osd.get("rotate", 0)
        return int(rotate), "osd"
    except Exception as e:
        return 0, f"osd_failed:{str(e)[:50]}"


def _detectar_rotacion_bruteforce(img: "Image.Image", lang: str = "eng") -> Tuple[int, str]:
    """Detecta rotación probando 0, 90, 180, 270."""
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
    """Detecta inclinación leve (deskew)."""
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
    """Aplica rotación de 0, 90, 180 o 270 grados."""
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
    """Aplica corrección de inclinación leve."""
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
    Preprocesa la imagen detectando y corrigiendo rotación.
    
    Returns:
        (imagen_corregida, info_rotacion)
    """
    info = {
        "rotacion_grados": 0,
        "rotacion_metodo": "none",
        "deskew_grados": 0.0,
        "rotacion_aplicada": False
    }
    
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
# MÉTRICAS Y OCR
# =============================================================================

def calcular_metricas_imagen(img: "Image.Image", dpi_render: int = 200) -> Dict[str, Any]:
    """Calcula métricas de calidad de imagen."""
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


def ejecutar_ocr(img: "Image.Image", lang: str = "eng") -> Dict[str, Any]:
    """
    Ejecuta OCR con Tesseract y obtiene texto y confianza.
    
    Returns:
        Dict con: texto_completo, snippet_200, confianza_promedio, num_palabras, tiempo_ms, error
    """
    resultado = {
        "lang": lang,
        "texto_completo": "",
        "snippet_200": "",
        "confianza_promedio": 0.0,
        "num_palabras": 0,
        "tiempo_ms": 0,
        "error": None
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
            resultado["confianza_promedio"] = round(sum(confianzas) / len(confianzas) / 100, 3)
            
    except Exception as e:
        resultado["error"] = str(e)
    
    return resultado
