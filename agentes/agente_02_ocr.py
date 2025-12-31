# -*- coding: utf-8 -*-
"""
AGENTE 02 — OCR AVANZADO
========================
Mejora la extracción de texto de PDFs escaneados.
Detecta texto ilegible, firmas manuscritas, sellos.
Marca incertidumbre si la calidad es baja.
"""

import os
import sys
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    ResultadoAgente, Observacion, NivelObservacion
)
from utils.pdf_extractor import DocumentoPDF, PDFExtractor

# Intentar importar OCR (opcional)
TESSERACT_DISPONIBLE = False
EASYOCR_DISPONIBLE = False

try:
    import pytesseract
    from PIL import Image
    TESSERACT_DISPONIBLE = True
except (ImportError, OSError):
    pass

try:
    import easyocr
    EASYOCR_DISPONIBLE = True
except (ImportError, OSError, Exception):
    # EasyOCR puede fallar por DLLs de PyTorch
    pass


@dataclass
class ResultadoOCR:
    """Resultado del análisis OCR de una página"""
    pagina: int
    texto_original: str
    texto_mejorado: str
    calidad_original: str
    calidad_mejorada: str
    requirio_ocr: bool
    confianza: float  # 0.0 a 1.0
    tiene_firma_manuscrita: bool
    tiene_sello: bool
    areas_ilegibles: List[str]


class AgenteOCR:
    """
    Agente 02: Mejora OCR y detecta problemas de calidad
    """
    
    AGENTE_ID = "AG02"
    AGENTE_NOMBRE = "OCR Avanzado"
    
    # Patrones que indican firma manuscrita
    PATRONES_FIRMA = [
        r"firma[do]?",
        r"suscrito",
        r"v[°º]\s*b[°º]",
        r"rúbrica"
    ]
    
    # Patrones que indican sello
    PATRONES_SELLO = [
        r"sello",
        r"timbre",
        r"membrete"
    ]
    
    def __init__(self):
        self.observaciones: List[Observacion] = []
        self.incertidumbres: List[str] = []
        self.datos_extraidos: Dict = {}
        self.ocr_reader = None
        
        # Inicializar OCR si está disponible
        if EASYOCR_DISPONIBLE:
            try:
                self.ocr_reader = easyocr.Reader(['es', 'en'], gpu=False, verbose=False)
            except:
                pass
    
    def analizar(self, documentos: List[DocumentoPDF]) -> ResultadoAgente:
        """
        Analiza la calidad de los documentos y mejora con OCR si es necesario
        """
        self.observaciones = []
        self.incertidumbres = []
        
        resultados_ocr: List[ResultadoOCR] = []
        documentos_problematicos = []
        paginas_escaneadas = 0
        paginas_baja_calidad = 0
        
        for doc in documentos:
            for pagina in doc.paginas:
                resultado = self._analizar_pagina(doc, pagina)
                resultados_ocr.append(resultado)
                
                if resultado.requirio_ocr:
                    paginas_escaneadas += 1
                
                if resultado.calidad_original in ["BAJA", "SIN_TEXTO"]:
                    paginas_baja_calidad += 1
                    if resultado.confianza < 0.5:
                        documentos_problematicos.append({
                            "documento": doc.nombre,
                            "pagina": pagina.numero,
                            "calidad": resultado.calidad_original,
                            "confianza": resultado.confianza
                        })
        
        # Generar observaciones
        if paginas_baja_calidad > 0:
            self.observaciones.append(Observacion(
                nivel=NivelObservacion.MENOR if paginas_baja_calidad < 3 else NivelObservacion.MAYOR,
                agente=self.AGENTE_NOMBRE,
                descripcion=f"Se detectaron {paginas_baja_calidad} páginas con baja calidad de texto",
                evidencia=f"Documentos: {[d['documento'] for d in documentos_problematicos[:3]]}",
                accion_requerida="Verificar manualmente las páginas con problemas de legibilidad",
                area_responsable="Control Previo"
            ))
        
        # Detectar documentos sin texto extraíble
        docs_sin_texto = [r for r in resultados_ocr if r.calidad_original == "SIN_TEXTO"]
        if docs_sin_texto:
            self.incertidumbres.append(
                f"{len(docs_sin_texto)} páginas no tienen texto extraíble (posibles imágenes escaneadas)"
            )
        
        self.datos_extraidos = {
            "total_paginas_analizadas": len(resultados_ocr),
            "paginas_escaneadas": paginas_escaneadas,
            "paginas_baja_calidad": paginas_baja_calidad,
            "documentos_problematicos": documentos_problematicos,
            "ocr_disponible": EASYOCR_DISPONIBLE or TESSERACT_DISPONIBLE,
            "firmas_detectadas": sum(1 for r in resultados_ocr if r.tiene_firma_manuscrita),
            "sellos_detectados": sum(1 for r in resultados_ocr if r.tiene_sello)
        }
        
        return ResultadoAgente(
            agente_id=self.AGENTE_ID,
            agente_nombre=self.AGENTE_NOMBRE,
            exito=True,
            observaciones=self.observaciones,
            datos_extraidos=self.datos_extraidos,
            incertidumbres=self.incertidumbres
        )
    
    def _analizar_pagina(self, doc: DocumentoPDF, pagina) -> ResultadoOCR:
        """Analiza una página individual"""
        texto = pagina.texto
        calidad = pagina.calidad_texto
        requirio_ocr = False
        texto_mejorado = texto
        confianza = 1.0
        
        # Si la calidad es baja, intentar OCR
        if calidad in ["BAJA", "SIN_TEXTO"] and pagina.es_escaneado:
            requirio_ocr = True
            texto_mejorado, confianza = self._aplicar_ocr(doc.ruta, pagina.numero - 1)
        
        # Detectar firma manuscrita
        tiene_firma = self._detectar_firma(texto)
        
        # Detectar sello
        tiene_sello = self._detectar_sello(texto)
        
        # Detectar áreas ilegibles
        areas_ilegibles = self._detectar_areas_ilegibles(texto)
        
        # Evaluar calidad mejorada
        calidad_mejorada = self._evaluar_calidad(texto_mejorado) if requirio_ocr else calidad
        
        return ResultadoOCR(
            pagina=pagina.numero,
            texto_original=texto[:500],  # Solo primeros 500 chars
            texto_mejorado=texto_mejorado[:500],
            calidad_original=calidad,
            calidad_mejorada=calidad_mejorada,
            requirio_ocr=requirio_ocr,
            confianza=confianza,
            tiene_firma_manuscrita=tiene_firma,
            tiene_sello=tiene_sello,
            areas_ilegibles=areas_ilegibles
        )
    
    def _aplicar_ocr(self, ruta_pdf: str, num_pagina: int) -> Tuple[str, float]:
        """Aplica OCR a una página"""
        if not self.ocr_reader:
            return "", 0.0
        
        try:
            extractor = PDFExtractor(ruta_pdf)
            if extractor.abrir():
                imagenes = extractor.extraer_imagenes_pagina(num_pagina, dpi=200)
                extractor.cerrar()
                
                if imagenes:
                    # Usar EasyOCR
                    import numpy as np
                    img_array = np.array(imagenes[0])
                    resultados = self.ocr_reader.readtext(img_array)
                    
                    textos = [r[1] for r in resultados]
                    confianzas = [r[2] for r in resultados]
                    
                    texto = " ".join(textos)
                    confianza_promedio = sum(confianzas) / len(confianzas) if confianzas else 0.0
                    
                    return texto, confianza_promedio
        except Exception as e:
            self.incertidumbres.append(f"Error en OCR: {str(e)}")
        
        return "", 0.0
    
    def _detectar_firma(self, texto: str) -> bool:
        """Detecta indicadores de firma manuscrita"""
        texto_lower = texto.lower()
        for patron in self.PATRONES_FIRMA:
            if re.search(patron, texto_lower):
                return True
        return False
    
    def _detectar_sello(self, texto: str) -> bool:
        """Detecta indicadores de sello"""
        texto_lower = texto.lower()
        for patron in self.PATRONES_SELLO:
            if re.search(patron, texto_lower):
                return True
        return False
    
    def _detectar_areas_ilegibles(self, texto: str) -> List[str]:
        """Detecta posibles áreas con texto ilegible"""
        areas = []
        
        # Buscar secuencias de caracteres extraños
        patron_basura = r'[^\w\s]{5,}'
        matches = re.findall(patron_basura, texto)
        if matches:
            areas.append(f"Caracteres ilegibles: {len(matches)} secuencias")
        
        # Buscar muchos espacios consecutivos (posible tabla mal extraída)
        if re.search(r'\s{10,}', texto):
            areas.append("Posible tabla mal extraída")
        
        return areas
    
    def _evaluar_calidad(self, texto: str) -> str:
        """Evalúa la calidad del texto"""
        if not texto or len(texto.strip()) < 10:
            return "SIN_TEXTO"
        
        # Ratio de caracteres válidos
        chars_validos = len(re.findall(r'[\w\s]', texto))
        ratio = chars_validos / len(texto) if texto else 0
        
        if ratio > 0.9:
            return "BUENA"
        elif ratio > 0.7:
            return "MEDIA"
        else:
            return "BAJA"


def ejecutar_agente(documentos: List[DocumentoPDF]) -> ResultadoAgente:
    """Función helper para ejecutar el agente"""
    agente = AgenteOCR()
    return agente.analizar(documentos)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    from utils.pdf_extractor import extraer_todos_pdfs
    
    carpeta = r"C:\Users\hanns\Downloads"
    documentos = extraer_todos_pdfs(carpeta)
    
    print("=" * 80)
    print("AGENTE 02 — OCR AVANZADO")
    print("=" * 80)
    
    resultado = ejecutar_agente(documentos)
    
    print(f"\n✅ Éxito: {resultado.exito}")
    print(f"📄 Páginas analizadas: {resultado.datos_extraidos.get('total_paginas_analizadas', 0)}")
    print(f"📷 Páginas escaneadas: {resultado.datos_extraidos.get('paginas_escaneadas', 0)}")
    print(f"⚠️ Baja calidad: {resultado.datos_extraidos.get('paginas_baja_calidad', 0)}")
    print(f"✍️ Firmas detectadas: {resultado.datos_extraidos.get('firmas_detectadas', 0)}")
    print(f"🔖 Sellos detectados: {resultado.datos_extraidos.get('sellos_detectados', 0)}")

