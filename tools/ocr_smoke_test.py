# -*- coding: utf-8 -*-
"""
OCR SMOKE TEST — Fase 1a/1b/1c
==============================
Script aislado para probar OCR con Tesseract.
NO modifica agentes, orquestador ni pipeline.

Uso:
    python tools/ocr_smoke_test.py --pdf "ruta/archivo.pdf" --page 1
    python tools/ocr_smoke_test.py --pdf "ruta/archivo.pdf" --page 1 --lang spa --dpi 300

Requisitos:
    - PyMuPDF (fitz)
    - pytesseract
    - Tesseract-OCR instalado en el sistema (con idioma requerido + osd)
    - opencv-python (para métricas de imagen y rotación)
    - Pillow
"""

import argparse
import json
import sys
import os
import time
import subprocess
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

# Agregar path del proyecto para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Verificar dependencias
DEPENDENCIAS_OK = True
ERRORES_DEPENDENCIAS = []

try:
    import fitz  # PyMuPDF
except ImportError:
    DEPENDENCIAS_OK = False
    ERRORES_DEPENDENCIAS.append("PyMuPDF (fitz) no instalado: pip install PyMuPDF")

try:
    from PIL import Image
except ImportError:
    DEPENDENCIAS_OK = False
    ERRORES_DEPENDENCIAS.append("Pillow no instalado: pip install Pillow")

try:
    import pytesseract
except ImportError:
    DEPENDENCIAS_OK = False
    ERRORES_DEPENDENCIAS.append("pytesseract no instalado: pip install pytesseract")

try:
    import cv2
    import numpy as np
    CV2_DISPONIBLE = True
except ImportError:
    CV2_DISPONIBLE = False
    ERRORES_DEPENDENCIAS.append("opencv-python no instalado (métricas limitadas): pip install opencv-python")


def run_cmd(cmd: List[str]) -> Tuple[int, str, str]:
    """Ejecuta un comando y retorna (returncode, stdout, stderr)"""
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = p.communicate(timeout=30)
        return p.returncode, out.strip(), err.strip()
    except Exception as e:
        return -1, "", str(e)


def list_tesseract_langs() -> Dict[str, Any]:
    """Lista los idiomas disponibles en Tesseract"""
    rc, out, err = run_cmd(["tesseract", "--list-langs"])
    if rc != 0:
        return {"ok": False, "langs": [], "raw": out, "err": err}
    
    langs = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("List of available languages"):
            continue
        langs.append(line)
    
    return {"ok": True, "langs": langs, "raw": out, "err": err}


def ensure_lang_available(requested_lang: str) -> Tuple[bool, str, List[str]]:
    """Verifica que el idioma solicitado esté disponible"""
    info = list_tesseract_langs()
    if not info["ok"]:
        return False, f"No se pudo ejecutar 'tesseract --list-langs': {info['err']}", []
    
    langs = info["langs"]
    if requested_lang not in langs:
        return False, (
            f"Idioma '{requested_lang}' NO está instalado. "
            f"Idiomas disponibles: {langs}. "
            f"Instala '{requested_lang}.traineddata' en la carpeta tessdata."
        ), langs
    
    return True, "OK", langs


def verificar_tesseract() -> Tuple[bool, str]:
    """Verifica que Tesseract esté instalado y accesible"""
    try:
        version = pytesseract.get_tesseract_version()
        return True, f"Tesseract v{version}"
    except Exception as e:
        return False, str(e)


def renderizar_pagina(pdf_path: str, page_num: int, dpi: int = 200) -> Optional[Image.Image]:
    """
    Renderiza una página PDF a imagen PIL usando PyMuPDF.
    
    Args:
        pdf_path: Ruta al archivo PDF
        page_num: Número de página (1-indexed)
        dpi: Resolución de renderizado
        
    Returns:
        Imagen PIL o None si hay error
    """
    try:
        doc = fitz.open(pdf_path)
        
        if page_num < 1 or page_num > len(doc):
            print(f"Error: Página {page_num} fuera de rango (1-{len(doc)})")
            doc.close()
            return None
        
        page = doc[page_num - 1]  # 0-indexed internamente
        
        # Renderizar a imagen con el DPI especificado
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        
        # Convertir a PIL Image
        img_data = pix.tobytes("png")
        import io
        img = Image.open(io.BytesIO(img_data))
        
        doc.close()
        return img
        
    except Exception as e:
        print(f"Error renderizando página: {e}")
        return None


# =============================================================================
# FASE 1c: ROTACIÓN Y DESKEW
# =============================================================================

def detectar_rotacion_osd(img: Image.Image) -> Tuple[int, str]:
    """
    Detecta rotación usando Tesseract OSD (Orientation and Script Detection).
    
    Returns:
        (angulo, metodo) donde angulo es 0, 90, 180 o 270
    """
    try:
        osd = pytesseract.image_to_osd(img, output_type=pytesseract.Output.DICT)
        rotate = osd.get("rotate", 0)
        # OSD retorna el ángulo que HAY QUE rotar para corregir
        # Si rotate=90, significa que la imagen está rotada 90° y hay que rotarla -90° (o 270°)
        return int(rotate), "osd"
    except Exception as e:
        # OSD puede fallar si no hay suficiente texto o el script no es reconocido
        return 0, f"osd_failed:{str(e)[:50]}"


def detectar_rotacion_bruteforce(img: Image.Image, lang: str = "eng") -> Tuple[int, str]:
    """
    Detecta rotación probando 0, 90, 180, 270 y eligiendo la que maximiza palabras.
    Early exit si encontramos buena confianza.
    
    Returns:
        (angulo_correccion, metodo)
    """
    mejor_angulo = 0
    mejor_palabras = 0
    mejor_confianza = 0.0
    
    for angulo in [0, 90, 180, 270]:
        # Rotar imagen
        if angulo == 0:
            img_rotada = img
        else:
            img_rotada = img.rotate(-angulo, expand=True)  # Rotate CCW para corregir
        
        try:
            # OCR rápido para contar palabras
            data = pytesseract.image_to_data(
                img_rotada, 
                lang=lang, 
                output_type=pytesseract.Output.DICT,
                config='--psm 6'  # Assume uniform block of text
            )
            
            palabras = sum(1 for t in data['text'] if t.strip())
            confianzas = [c for c in data['conf'] if c != -1 and c > 0]
            confianza = sum(confianzas) / len(confianzas) / 100 if confianzas else 0
            
            if palabras > mejor_palabras or (palabras == mejor_palabras and confianza > mejor_confianza):
                mejor_angulo = angulo
                mejor_palabras = palabras
                mejor_confianza = confianza
            
            # Early exit si encontramos buena confianza con muchas palabras
            if palabras >= 20 and confianza >= 0.75:
                return angulo, "bruteforce_early"
                
        except Exception:
            continue
    
    return mejor_angulo, "bruteforce"


def detectar_deskew(img: Image.Image) -> float:
    """
    Detecta inclinación leve (deskew) usando análisis de líneas.
    Solo para ángulos pequeños (|angulo| <= 15°).
    
    Returns:
        Ángulo de inclinación en grados (positivo = CW, negativo = CCW)
    """
    if not CV2_DISPONIBLE:
        return 0.0
    
    try:
        # Convertir a grayscale y binarizar
        img_gray = img.convert('L')
        img_array = np.array(img_gray)
        
        # Binarización adaptativa
        binary = cv2.adaptiveThreshold(
            img_array, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 11, 2
        )
        
        # Encontrar contornos y calcular minAreaRect
        coords = np.column_stack(np.where(binary > 0))
        if len(coords) < 100:
            return 0.0
        
        # minAreaRect retorna ((cx, cy), (w, h), angle)
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]
        
        # Normalizar ángulo
        if angle < -45:
            angle = 90 + angle
        elif angle > 45:
            angle = angle - 90
        
        # Solo corregir si es inclinación leve
        if abs(angle) <= 15:
            return round(angle, 2)
        else:
            return 0.0
            
    except Exception:
        return 0.0


def aplicar_rotacion(img: Image.Image, angulo: int) -> Image.Image:
    """
    Aplica rotación de 0, 90, 180 o 270 grados.
    """
    if angulo == 0:
        return img
    elif angulo == 90:
        return img.rotate(-90, expand=True)
    elif angulo == 180:
        return img.rotate(180, expand=True)
    elif angulo == 270:
        return img.rotate(-270, expand=True)
    return img


def aplicar_deskew(img: Image.Image, angulo: float) -> Image.Image:
    """
    Aplica corrección de inclinación leve.
    """
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


def preprocesar_rotacion(img: Image.Image, lang: str = "eng") -> Tuple[Image.Image, Dict[str, Any]]:
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
    
    # 1. Intentar OSD primero
    rotacion, metodo = detectar_rotacion_osd(img)
    
    if "osd_failed" in metodo:
        # Fallback a bruteforce
        rotacion, metodo = detectar_rotacion_bruteforce(img, lang)
    
    info["rotacion_metodo"] = metodo
    
    # 2. Aplicar rotación si es necesaria
    if rotacion != 0:
        img = aplicar_rotacion(img, rotacion)
        info["rotacion_grados"] = rotacion
        info["rotacion_aplicada"] = True
    
    # 3. Detectar y aplicar deskew (solo después de rotación principal)
    deskew = detectar_deskew(img)
    if abs(deskew) >= 0.5:
        img = aplicar_deskew(img, deskew)
        info["deskew_grados"] = deskew
        info["rotacion_aplicada"] = True
        # Actualizar rotacion_grados total
        info["rotacion_grados"] = rotacion + deskew
    
    # Redondear rotacion_grados final
    info["rotacion_grados"] = round(info["rotacion_grados"], 2)
    
    return img, info


# =============================================================================
# MÉTRICAS Y OCR
# =============================================================================

def calcular_metricas(img: Image.Image, dpi_render: int, rotacion_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calcula métricas de calidad de imagen.
    """
    metricas = {
        "dpi_estimado": dpi_render,
        "width_px": img.width,
        "height_px": img.height,
        "contraste": None,
        "blur_score": None,
        "rotacion_grados": rotacion_info.get("rotacion_grados", 0),
        "rotacion_metodo": rotacion_info.get("rotacion_metodo", "none"),
        "deskew_grados": rotacion_info.get("deskew_grados", 0.0)
    }
    
    if not CV2_DISPONIBLE:
        metricas["advertencia"] = "opencv-python no disponible, métricas limitadas"
        return metricas
    
    # Convertir a grayscale para análisis
    img_gray = img.convert('L')
    img_array = np.array(img_gray)
    
    # === CONTRASTE ===
    p5 = np.percentile(img_array, 5)
    p95 = np.percentile(img_array, 95)
    contraste = (p95 - p5) / 255.0
    metricas["contraste"] = round(contraste, 3)
    
    # === BLUR SCORE (Laplacian Variance) ===
    laplacian = cv2.Laplacian(img_array, cv2.CV_64F)
    blur_score = laplacian.var()
    metricas["blur_score"] = round(blur_score, 2)
    
    # Interpretación del blur
    if blur_score < 50:
        metricas["blur_interpretacion"] = "MUY_BORROSO"
    elif blur_score < 100:
        metricas["blur_interpretacion"] = "BORROSO"
    elif blur_score < 500:
        metricas["blur_interpretacion"] = "ACEPTABLE"
    else:
        metricas["blur_interpretacion"] = "NITIDO"
    
    return metricas


def ejecutar_ocr(img: Image.Image, lang: str = "eng") -> Dict[str, Any]:
    """
    Ejecuta OCR con Tesseract y obtiene texto y confianza.
    """
    resultado = {
        "lang": lang,
        "texto_completo": "",
        "snippet_200": "",
        "confianza_promedio": None,
        "num_palabras": 0,
        "tiempo_ms": 0,
        "error": None
    }
    
    try:
        inicio = time.time()
        
        # Obtener datos detallados con confianza
        data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
        
        fin = time.time()
        resultado["tiempo_ms"] = int((fin - inicio) * 1000)
        
        # Extraer texto y confianzas
        textos = []
        confianzas = []
        
        for i, texto in enumerate(data['text']):
            if texto.strip():
                textos.append(texto)
                conf = data['conf'][i]
                if conf != -1:  # -1 significa sin confianza
                    confianzas.append(conf)
        
        texto_completo = " ".join(textos)
        resultado["texto_completo"] = texto_completo
        resultado["snippet_200"] = texto_completo[:200] if texto_completo else ""
        resultado["num_palabras"] = len(textos)
        
        if confianzas:
            resultado["confianza_promedio"] = round(sum(confianzas) / len(confianzas) / 100, 3)
        else:
            resultado["confianza_promedio"] = 0.0
            
    except Exception as e:
        resultado["error"] = str(e)
    
    return resultado


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Función principal del smoke test"""
    
    parser = argparse.ArgumentParser(
        description="OCR Smoke Test - Fase 1a/1b/1c",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
    python tools/ocr_smoke_test.py --pdf "documento.pdf" --page 1
    python tools/ocr_smoke_test.py --pdf "documento.pdf" --page 1 --lang spa
    python tools/ocr_smoke_test.py --pdf "documento.pdf" --page 3 --dpi 300 --lang spa
        """
    )
    parser.add_argument("--pdf", required=True, help="Ruta al archivo PDF")
    parser.add_argument("--page", type=int, required=True, help="Número de página (1-indexed)")
    parser.add_argument("--dpi", type=int, default=200, help="DPI para renderizado (default: 200)")
    parser.add_argument("--lang", default="eng", help="Idioma Tesseract: eng, spa, etc. (default: eng)")
    parser.add_argument("--out", default="", help="Ruta de salida JSON (opcional)")
    
    args = parser.parse_args()
    
    # Configurar encoding para Windows
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    
    print("=" * 70)
    print("OCR SMOKE TEST — Fase 1c (con rotación/deskew)")
    print("=" * 70)
    
    # Verificar dependencias
    if not DEPENDENCIAS_OK:
        print("\n❌ ERRORES DE DEPENDENCIAS:")
        for error in ERRORES_DEPENDENCIAS:
            print(f"   - {error}")
        sys.exit(1)
    
    if ERRORES_DEPENDENCIAS:
        print("\n⚠️ ADVERTENCIAS:")
        for adv in ERRORES_DEPENDENCIAS:
            print(f"   - {adv}")
    
    # Verificar Tesseract
    print("\n📋 Verificando Tesseract...")
    tesseract_ok, tesseract_info = verificar_tesseract()
    if not tesseract_ok:
        print(f"❌ Tesseract no disponible: {tesseract_info}")
        print("\n   Instalación en Windows:")
        print("   1. Descargar: https://github.com/UB-Mannheim/tesseract/wiki")
        print("   2. Instalar y agregar al PATH: C:\\Program Files\\Tesseract-OCR")
        print("   3. Reiniciar terminal")
        sys.exit(1)
    
    print(f"   ✅ {tesseract_info}")
    
    # Verificar idioma disponible
    print(f"\n🌐 Verificando idioma '{args.lang}'...")
    lang_ok, lang_msg, langs_disponibles = ensure_lang_available(args.lang)
    
    # Preparar reporte base
    reporte = {
        "archivo": os.path.basename(args.pdf),
        "pagina": args.page,
        "dpi_render": args.dpi,
        "metricas": {},
        "ocr": {
            "lang": args.lang,
            "snippet_200": "",
            "num_palabras": 0,
            "confianza_promedio": None,
            "tiempo_ms": 0,
            "error": None
        },
        "fase": "1c",
        "nota": "Smoke test aislado con rotación/deskew. NO integrado al pipeline.",
        "tesseract": {
            "version": tesseract_info,
            "TESSDATA_PREFIX": os.environ.get("TESSDATA_PREFIX"),
            "langs_disponibles": langs_disponibles
        }
    }
    
    if not lang_ok:
        print(f"   ❌ {lang_msg}")
        reporte["ocr"]["error"] = lang_msg
        print("\n" + "=" * 70)
        print("📝 REPORTE JSON:")
        print("=" * 70)
        print(json.dumps(reporte, indent=2, ensure_ascii=False))
        print("\n❌ Smoke test completado (con error): falta idioma OCR")
        sys.exit(1)
    
    print(f"   ✅ Idioma '{args.lang}' disponible")
    print(f"   📦 Idiomas instalados: {langs_disponibles}")
    
    # Verificar archivo PDF
    if not os.path.exists(args.pdf):
        print(f"\n❌ Archivo no encontrado: {args.pdf}")
        sys.exit(1)
    
    print(f"\n📄 PDF: {os.path.basename(args.pdf)}")
    print(f"   Página: {args.page}")
    print(f"   DPI: {args.dpi}")
    print(f"   Idioma: {args.lang}")
    
    # Paso 1: Renderizar página
    print("\n🖼️ Renderizando página a imagen...")
    img = renderizar_pagina(args.pdf, args.page, args.dpi)
    if img is None:
        print("❌ Error al renderizar página")
        sys.exit(1)
    
    print(f"   ✅ Imagen original: {img.width}x{img.height} px")
    
    # Paso 2: FASE 1c - Detectar y corregir rotación
    print("\n🔄 Detectando rotación...")
    img_corregida, rotacion_info = preprocesar_rotacion(img, args.lang)
    
    if rotacion_info["rotacion_aplicada"]:
        print(f"   ✅ Rotación detectada: {rotacion_info['rotacion_grados']}° (método: {rotacion_info['rotacion_metodo']})")
        if rotacion_info["deskew_grados"] != 0:
            print(f"   ✅ Deskew aplicado: {rotacion_info['deskew_grados']}°")
        print(f"   📐 Imagen corregida: {img_corregida.width}x{img_corregida.height} px")
    else:
        print(f"   ℹ️ Sin rotación necesaria (método: {rotacion_info['rotacion_metodo']})")
    
    # Paso 3: Calcular métricas (con info de rotación)
    print("\n📊 Calculando métricas de calidad...")
    metricas = calcular_metricas(img_corregida, args.dpi, rotacion_info)
    reporte["metricas"] = metricas
    print(f"   DPI: {metricas['dpi_estimado']}")
    print(f"   Contraste: {metricas.get('contraste', 'N/A')}")
    print(f"   Blur Score: {metricas.get('blur_score', 'N/A')} ({metricas.get('blur_interpretacion', 'N/A')})")
    print(f"   Rotación: {metricas.get('rotacion_grados', 0)}° ({metricas.get('rotacion_metodo', 'none')})")
    
    # Paso 4: Ejecutar OCR sobre imagen corregida
    print(f"\n🔍 Ejecutando OCR con Tesseract (lang={args.lang})...")
    ocr_result = ejecutar_ocr(img_corregida, args.lang)
    reporte["ocr"] = ocr_result
    
    if ocr_result.get("error"):
        print(f"   ❌ Error: {ocr_result['error']}")
    else:
        print(f"   ✅ Tiempo: {ocr_result['tiempo_ms']} ms")
        print(f"   Palabras: {ocr_result['num_palabras']}")
        print(f"   Confianza: {ocr_result['confianza_promedio']}")
    
    # Guardar JSON si se especificó ruta
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n💾 JSON guardado en: {args.out}")
    
    # Generar reporte JSON
    print("\n" + "=" * 70)
    print("📝 REPORTE JSON:")
    print("=" * 70)
    print(json.dumps(reporte, indent=2, ensure_ascii=False))
    
    # Mostrar snippet
    if ocr_result.get("snippet_200"):
        print("\n" + "-" * 70)
        print("📖 SNIPPET (primeros 200 caracteres):")
        print("-" * 70)
        print(ocr_result["snippet_200"])
    
    if ocr_result.get("error"):
        print("\n🟡 Smoke test completado con observación (ver 'ocr.error').")
        sys.exit(0)
    
    print("\n✅ Smoke test Fase 1c completado")


if __name__ == "__main__":
    main()
