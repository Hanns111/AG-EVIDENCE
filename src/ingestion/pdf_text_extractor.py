# -*- coding: utf-8 -*-
"""
PDF Text Extractor con Gating Automático
=========================================
Fase 2 del pipeline OCR — Integración controlada.

Decide automáticamente entre:
- direct_text: PDF nativo con texto embebido
- ocr: PDF escaneado procesado con Tesseract
- fallback_manual: Cuando ambos fallan, requiere revisión humana

Principio de gobernanza: NUNCA inventa contenido. Si falla, retorna
estado NECESITA_REVISION_MANUAL con evidencia del fallo.
"""

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Union

from .config import GatingThresholds, DEFAULT_THRESHOLDS

# Importar módulo OCR
try:
    from src.ocr.core import (
        renderizar_pagina,
        ejecutar_ocr,
        preprocesar_rotacion,
        calcular_metricas_imagen,
        verificar_tesseract,
        TESSERACT_DISPONIBLE,
    )
    OCR_DISPONIBLE = TESSERACT_DISPONIBLE
except ImportError:
    OCR_DISPONIBLE = False

# Importar PyMuPDF para extracción directa
try:
    import fitz
    FITZ_DISPONIBLE = True
except ImportError:
    FITZ_DISPONIBLE = False


__version__ = "2.0.0"


def _extraer_texto_directo(pdf_path: Path) -> Dict[str, Any]:
    """
    Extrae texto directamente del PDF usando PyMuPDF.
    
    Returns:
        Dict con: texto, num_chars, num_words, num_paginas, tiempo_ms, error
    """
    resultado = {
        "texto": "",
        "num_chars": 0,
        "num_words": 0,
        "num_paginas": 0,
        "tiempo_ms": 0,
        "error": None
    }
    
    if not FITZ_DISPONIBLE:
        resultado["error"] = "PyMuPDF no disponible"
        return resultado
    
    try:
        inicio = time.time()
        doc = fitz.open(str(pdf_path))
        resultado["num_paginas"] = len(doc)
        
        textos_paginas = []
        for page in doc:
            texto_pagina = page.get_text("text")
            textos_paginas.append(texto_pagina)
        
        doc.close()
        
        texto_completo = "\n".join(textos_paginas)
        resultado["texto"] = texto_completo
        resultado["num_chars"] = len(texto_completo)
        resultado["num_words"] = len(texto_completo.split())
        resultado["tiempo_ms"] = int((time.time() - inicio) * 1000)
        
    except Exception as e:
        resultado["error"] = str(e)
    
    return resultado


def _extraer_texto_ocr(
    pdf_path: Path, 
    lang: str = "spa",
    dpi: int = 200,
    sample_pages: int = 1
) -> Dict[str, Any]:
    """
    Extrae texto usando OCR (Tesseract) en páginas de muestra.
    
    Returns:
        Dict con campos del OCR + metricas de rotación
    """
    resultado = {
        "texto": "",
        "snippet_200": "",
        "num_chars": 0,
        "num_words": 0,
        "confianza_promedio": 0.0,
        "tiempo_ms": 0,
        "paginas_procesadas": [],
        "rotacion_info": {},
        "error": None
    }
    
    if not OCR_DISPONIBLE:
        resultado["error"] = "OCR (Tesseract) no disponible"
        return resultado
    
    try:
        inicio = time.time()
        
        # Verificar Tesseract
        tess_ok, tess_msg = verificar_tesseract()
        if not tess_ok:
            resultado["error"] = f"Tesseract no disponible: {tess_msg}"
            return resultado
        
        # Abrir PDF para contar páginas
        doc = fitz.open(str(pdf_path))
        num_paginas = len(doc)
        doc.close()
        
        # Determinar qué páginas procesar
        paginas_a_procesar = list(range(1, min(sample_pages + 1, num_paginas + 1)))
        
        textos = []
        confianzas = []
        palabras_total = 0
        rotacion_info_ultima = {}
        
        for page_num in paginas_a_procesar:
            # Renderizar página
            img = renderizar_pagina(pdf_path, page_num, dpi)
            if img is None:
                continue
            
            # Preprocesar rotación
            img_corregida, rot_info = preprocesar_rotacion(img, lang)
            rotacion_info_ultima = rot_info
            
            # Ejecutar OCR
            ocr_result = ejecutar_ocr(img_corregida, lang)
            
            if ocr_result.get("error"):
                continue
            
            textos.append(ocr_result["texto_completo"])
            palabras_total += ocr_result["num_palabras"]
            if ocr_result["confianza_promedio"]:
                confianzas.append(ocr_result["confianza_promedio"])
            
            resultado["paginas_procesadas"].append({
                "pagina": page_num,
                "num_palabras": ocr_result["num_palabras"],
                "confianza": ocr_result["confianza_promedio"]
            })
        
        texto_completo = "\n\n".join(textos)
        resultado["texto"] = texto_completo
        resultado["snippet_200"] = texto_completo[:200] if texto_completo else ""
        resultado["num_chars"] = len(texto_completo)
        resultado["num_words"] = palabras_total
        resultado["confianza_promedio"] = round(sum(confianzas) / len(confianzas), 3) if confianzas else 0.0
        resultado["tiempo_ms"] = int((time.time() - inicio) * 1000)
        resultado["rotacion_info"] = rotacion_info_ultima
        
    except Exception as e:
        resultado["error"] = str(e)
    
    return resultado


def _decidir_metodo(
    direct_result: Dict[str, Any],
    ocr_result: Dict[str, Any],
    thresholds: GatingThresholds
) -> Dict[str, Any]:
    """
    Decide qué método usar basándose en métricas.
    
    Returns:
        Dict con: metodo, razon, metodo_alternativo
    """
    decision = {
        "metodo": "fallback_manual",
        "razon": "",
        "metodo_alternativo": None
    }
    
    # Evaluar direct_text
    direct_ok = (
        direct_result.get("error") is None and
        direct_result.get("num_chars", 0) >= thresholds.direct_text_min_chars and
        direct_result.get("num_words", 0) >= thresholds.direct_text_min_words
    )
    
    # Evaluar OCR
    ocr_ok = (
        ocr_result.get("error") is None and
        ocr_result.get("confianza_promedio", 0) >= thresholds.ocr_min_confidence and
        ocr_result.get("num_words", 0) >= thresholds.ocr_min_words
    )
    
    # Decisión
    if direct_ok:
        decision["metodo"] = "direct_text"
        decision["razon"] = (
            f"direct_text: {direct_result['num_chars']} chars >= {thresholds.direct_text_min_chars}, "
            f"{direct_result['num_words']} words >= {thresholds.direct_text_min_words}"
        )
        if ocr_ok:
            decision["metodo_alternativo"] = "ocr_tambien_disponible"
    
    elif ocr_ok:
        decision["metodo"] = "ocr"
        decision["razon"] = (
            f"ocr: confianza {ocr_result['confianza_promedio']:.2f} >= {thresholds.ocr_min_confidence}, "
            f"{ocr_result['num_words']} words >= {thresholds.ocr_min_words}"
        )
    
    else:
        # Fallback manual
        razones = []
        
        if direct_result.get("error"):
            razones.append(f"direct_text_error: {direct_result['error']}")
        elif direct_result.get("num_chars", 0) < thresholds.direct_text_min_chars:
            razones.append(f"direct_text_insuficiente: {direct_result.get('num_chars', 0)} chars < {thresholds.direct_text_min_chars}")
        
        if ocr_result.get("error"):
            razones.append(f"ocr_error: {ocr_result['error']}")
        elif ocr_result.get("confianza_promedio", 0) < thresholds.ocr_min_confidence:
            razones.append(f"ocr_baja_confianza: {ocr_result.get('confianza_promedio', 0):.2f} < {thresholds.ocr_min_confidence}")
        
        decision["razon"] = " | ".join(razones) if razones else "ambos_metodos_fallaron"
    
    return decision


def extract_text_with_gating(
    pdf_path: Union[str, Path],
    lang: str = "spa",
    thresholds: Optional[GatingThresholds] = None
) -> Dict[str, Any]:
    """
    Extrae texto de un PDF con gating automático.
    
    Decide entre:
    - direct_text: PDF nativo con texto embebido
    - ocr: PDF escaneado procesado con Tesseract
    - fallback_manual: Requiere revisión humana
    
    Args:
        pdf_path: Ruta al archivo PDF
        lang: Idioma para OCR (default: "spa")
        thresholds: Umbrales de decisión (opcional)
        
    Returns:
        Dict con estructura probatoria completa:
        {
            "decision": { "metodo", "razon" },
            "direct_text": { ... },
            "ocr": { ... },
            "metricas_documento": { ... },
            "evidencia": { "thresholds_usados", "version_modulo", "timestamp_iso" }
        }
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS
    
    pdf_path = Path(pdf_path)
    
    # Estructura de resultado
    resultado = {
        "archivo": pdf_path.name,
        "ruta_completa": str(pdf_path.absolute()),
        "decision": {
            "metodo": "fallback_manual",
            "razon": "",
            "metodo_alternativo": None
        },
        "direct_text": {},
        "ocr": {},
        "metricas_documento": {
            "num_paginas": 0,
            "existe": False,
            "tamano_bytes": 0
        },
        "evidencia": {
            "thresholds_usados": {
                "direct_text_min_chars": thresholds.direct_text_min_chars,
                "direct_text_min_words": thresholds.direct_text_min_words,
                "ocr_min_confidence": thresholds.ocr_min_confidence,
                "ocr_min_words": thresholds.ocr_min_words,
                "sample_pages": thresholds.sample_pages,
                "ocr_dpi": thresholds.ocr_dpi,
                "ocr_lang": lang
            },
            "version_modulo": __version__,
            "timestamp_iso": datetime.now(timezone.utc).isoformat(),
            "tesseract_disponible": OCR_DISPONIBLE,
            "pymupdf_disponible": FITZ_DISPONIBLE
        }
    }
    
    # Verificar existencia del archivo
    if not pdf_path.exists():
        resultado["decision"]["metodo"] = "fallback_manual"
        resultado["decision"]["razon"] = f"archivo_no_encontrado: {pdf_path}"
        return resultado
    
    resultado["metricas_documento"]["existe"] = True
    resultado["metricas_documento"]["tamano_bytes"] = pdf_path.stat().st_size
    
    # Paso 1: Intentar extracción directa
    direct_result = _extraer_texto_directo(pdf_path)
    resultado["direct_text"] = direct_result
    resultado["metricas_documento"]["num_paginas"] = direct_result.get("num_paginas", 0)
    
    # Paso 2: Intentar OCR (siempre, para tener métricas completas)
    ocr_result = _extraer_texto_ocr(
        pdf_path, 
        lang=lang,
        dpi=thresholds.ocr_dpi,
        sample_pages=thresholds.sample_pages
    )
    resultado["ocr"] = ocr_result
    
    # Paso 3: Decidir método
    decision = _decidir_metodo(direct_result, ocr_result, thresholds)
    resultado["decision"] = decision
    
    return resultado


def get_texto_extraido(resultado: Dict[str, Any]) -> str:
    """
    Helper para obtener el texto extraído según el método decidido.
    
    Args:
        resultado: Output de extract_text_with_gating()
        
    Returns:
        Texto extraído o string vacío si es fallback_manual
    """
    metodo = resultado.get("decision", {}).get("metodo", "fallback_manual")
    
    if metodo == "direct_text":
        return resultado.get("direct_text", {}).get("texto", "")
    elif metodo == "ocr":
        return resultado.get("ocr", {}).get("texto", "")
    else:
        return ""
