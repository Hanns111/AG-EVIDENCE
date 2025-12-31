# -*- coding: utf-8 -*-
"""
UTILIDAD DE EXTRACCIÓN DE PDF
=============================
Maneja la extracción de texto e imágenes de documentos PDF.
Incluye soporte para OCR cuando el texto no es extraíble directamente.
"""

import os
import sys
import fitz  # PyMuPDF
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from PIL import Image
import io
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class PaginaPDF:
    """Estructura para almacenar datos de una página PDF"""
    numero: int
    texto: str
    tiene_imagenes: bool = False
    imagenes: List[bytes] = field(default_factory=list)
    calidad_texto: str = "BUENA"  # BUENA, MEDIA, BAJA, SIN_TEXTO
    es_escaneado: bool = False


@dataclass
class DocumentoPDF:
    """Estructura para un documento PDF completo"""
    ruta: str
    nombre: str
    total_paginas: int
    paginas: List[PaginaPDF] = field(default_factory=list)
    texto_completo: str = ""
    metadatos: Dict = field(default_factory=dict)
    tiene_firmas_digitales: bool = False
    es_formulario: bool = False


class PDFExtractor:
    """Clase para extraer contenido de archivos PDF"""
    
    def __init__(self, ruta_pdf: str):
        self.ruta = ruta_pdf
        self.nombre = os.path.basename(ruta_pdf)
        self.doc = None
        
    def abrir(self) -> bool:
        """Abre el documento PDF"""
        try:
            self.doc = fitz.open(self.ruta)
            return True
        except Exception as e:
            print(f"Error al abrir {self.nombre}: {e}")
            return False
    
    def cerrar(self):
        """Cierra el documento PDF"""
        if self.doc:
            self.doc.close()
            
    def extraer_texto_pagina(self, num_pagina: int) -> PaginaPDF:
        """Extrae texto de una página específica"""
        if not self.doc or num_pagina >= len(self.doc):
            return PaginaPDF(numero=num_pagina, texto="", calidad_texto="SIN_TEXTO")
        
        page = self.doc[num_pagina]
        texto = page.get_text()
        
        # Evaluar calidad del texto
        calidad = self._evaluar_calidad_texto(texto, page)
        
        # Detectar si tiene imágenes
        imagenes = page.get_images()
        tiene_imagenes = len(imagenes) > 0
        
        # Detectar si es página escaneada (mucho imagen, poco texto)
        es_escaneado = tiene_imagenes and len(texto.strip()) < 100
        
        return PaginaPDF(
            numero=num_pagina + 1,  # 1-indexed para usuario
            texto=texto,
            tiene_imagenes=tiene_imagenes,
            calidad_texto=calidad,
            es_escaneado=es_escaneado
        )
    
    def _evaluar_calidad_texto(self, texto: str, page) -> str:
        """Evalúa la calidad del texto extraído"""
        if not texto or len(texto.strip()) == 0:
            return "SIN_TEXTO"
        
        # Contar caracteres especiales/basura
        caracteres_raros = len(re.findall(r'[^\w\s\.\,\;\:\-\(\)\[\]\/\°\ª\º]', texto))
        total_caracteres = len(texto)
        
        if total_caracteres == 0:
            return "SIN_TEXTO"
        
        ratio_basura = caracteres_raros / total_caracteres
        
        if ratio_basura > 0.3:
            return "BAJA"
        elif ratio_basura > 0.1:
            return "MEDIA"
        else:
            return "BUENA"
    
    def extraer_documento_completo(self) -> DocumentoPDF:
        """Extrae todo el contenido del documento"""
        if not self.doc:
            if not self.abrir():
                return DocumentoPDF(
                    ruta=self.ruta,
                    nombre=self.nombre,
                    total_paginas=0
                )
        
        paginas = []
        texto_completo = []
        
        for i in range(len(self.doc)):
            pagina = self.extraer_texto_pagina(i)
            paginas.append(pagina)
            texto_completo.append(pagina.texto)
        
        # Obtener metadatos
        metadatos = self.doc.metadata if self.doc.metadata else {}
        
        # Detectar firmas digitales (heurística simple)
        texto_total = "\n".join(texto_completo)
        tiene_firmas = any(kw in texto_total.lower() for kw in [
            "firma digital", "firmado digitalmente", "firma electrónica",
            "certificado digital", "fau 20131370998"
        ])
        
        return DocumentoPDF(
            ruta=self.ruta,
            nombre=self.nombre,
            total_paginas=len(self.doc),
            paginas=paginas,
            texto_completo=texto_total,
            metadatos=metadatos,
            tiene_firmas_digitales=tiene_firmas
        )
    
    def extraer_imagenes_pagina(self, num_pagina: int, dpi: int = 150) -> List[Image.Image]:
        """Extrae imágenes de una página como objetos PIL"""
        if not self.doc or num_pagina >= len(self.doc):
            return []
        
        page = self.doc[num_pagina]
        imagenes = []
        
        # Renderizar página completa como imagen
        mat = fitz.Matrix(dpi/72, dpi/72)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        imagenes.append(img)
        
        return imagenes
    
    def buscar_texto(self, patron: str, case_sensitive: bool = False) -> List[Tuple[int, str]]:
        """Busca un patrón en todo el documento"""
        if not self.doc:
            return []
        
        resultados = []
        flags = 0 if case_sensitive else re.IGNORECASE
        
        for i in range(len(self.doc)):
            page = self.doc[i]
            texto = page.get_text()
            
            matches = re.findall(f".{{0,50}}{patron}.{{0,50}}", texto, flags)
            for match in matches:
                resultados.append((i + 1, match.strip()))
        
        return resultados
    
    def extraer_tablas(self, num_pagina: int) -> List[List[str]]:
        """Intenta extraer tablas de una página (heurística básica)"""
        if not self.doc or num_pagina >= len(self.doc):
            return []
        
        page = self.doc[num_pagina]
        texto = page.get_text("text")
        
        # Heurística simple: buscar líneas con múltiples columnas separadas por espacios
        lineas = texto.split('\n')
        tablas = []
        tabla_actual = []
        
        for linea in lineas:
            # Si la línea tiene múltiples espacios, podría ser una fila de tabla
            partes = re.split(r'\s{2,}', linea.strip())
            if len(partes) > 1:
                tabla_actual.append(partes)
            elif tabla_actual:
                if len(tabla_actual) > 1:
                    tablas.append(tabla_actual)
                tabla_actual = []
        
        if tabla_actual and len(tabla_actual) > 1:
            tablas.append(tabla_actual)
        
        return tablas


def extraer_todos_pdfs(carpeta: str) -> List[DocumentoPDF]:
    """Extrae contenido de todos los PDFs en una carpeta"""
    documentos = []
    
    if not os.path.exists(carpeta):
        print(f"Carpeta no existe: {carpeta}")
        return documentos
    
    for archivo in os.listdir(carpeta):
        if archivo.lower().endswith('.pdf') and not archivo.startswith('~'):
            ruta_completa = os.path.join(carpeta, archivo)
            
            try:
                extractor = PDFExtractor(ruta_completa)
                doc = extractor.extraer_documento_completo()
                documentos.append(doc)
                extractor.cerrar()
            except Exception as e:
                print(f"Error procesando {archivo}: {e}")
    
    return documentos


def buscar_en_documentos(documentos: List[DocumentoPDF], patron: str) -> Dict[str, List[Tuple[int, str]]]:
    """Busca un patrón en múltiples documentos"""
    resultados = {}
    
    for doc in documentos:
        extractor = PDFExtractor(doc.ruta)
        if extractor.abrir():
            matches = extractor.buscar_texto(patron)
            if matches:
                resultados[doc.nombre] = matches
            extractor.cerrar()
    
    return resultados


if __name__ == "__main__":
    # Prueba básica
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    carpeta_test = r"C:\Users\hanns\Downloads"
    
    print("Extrayendo PDFs de prueba...")
    docs = extraer_todos_pdfs(carpeta_test)
    
    for doc in docs[:3]:  # Solo primeros 3
        print(f"\n📄 {doc.nombre}")
        print(f"   Páginas: {doc.total_paginas}")
        print(f"   Firmas digitales: {doc.tiene_firmas_digitales}")
        if doc.paginas:
            print(f"   Calidad texto pág 1: {doc.paginas[0].calidad_texto}")



