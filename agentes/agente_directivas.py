# -*- coding: utf-8 -*-
"""
AGENTE DE DIRECTIVAS - ESTÁNDAR PROBATORIO ESTRICTO
====================================================
Agente genérico para consultar 1 o N PDFs de directivas/pautas.

POLÍTICA ANTI-ALUCINACIÓN:
- Solo responde con información LITERAL de los PDFs cargados
- Cita obligatoria: archivo + página + snippet
- Si no encuentra: "No consta en la directiva cargada"

USO:
    from agentes.agente_directivas import AgenteDirectivas
    
    agente = AgenteDirectivas()
    agente.cargar_pdf("directiva_viaticos.pdf")
    agente.cargar_pdf("pautas_pago.pdf")
    
    respuesta = agente.preguntar("¿Cuál es el plazo para rendir viáticos?")
"""

import os
import sys
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

# =============================================================================
# POLÍTICA ANTI-ALUCINACIÓN
# =============================================================================

MENSAJE_NO_CONSTA = "No consta en la directiva cargada."

ANTI_HALLUCINATION_POLICY_DIRECTIVAS = """
REGLAS ESTRICTAS PARA CONSULTA DE DIRECTIVAS:

1. SOLO puedes responder con texto LITERAL de los PDFs cargados.
2. PROHIBIDO inventar, inferir o interpretar información.
3. PROHIBIDO usar conocimiento externo sobre normativas.
4. TODA respuesta DEBE incluir:
   - Archivo fuente (nombre exacto del PDF)
   - Número de página
   - Texto literal (snippet) que sustenta la respuesta
5. Si la información NO está en los PDFs, responder: "{}"
6. NO completar información parcial con suposiciones.

FORMATO OBLIGATORIO:
📄 Fuente: [nombre_archivo.pdf]
📃 Página: [número]
📝 Texto: "[snippet literal del documento]"
""".format(MENSAJE_NO_CONSTA)

SYSTEM_PROMPT_DIRECTIVAS = f"""Eres un asistente especializado en consultar directivas y pautas normativas.
Tu rol es responder preguntas ÚNICAMENTE con base en los documentos PDF proporcionados.

{ANTI_HALLUCINATION_POLICY_DIRECTIVAS}

IMPORTANTE:
- NO uses frases como "generalmente", "normalmente", "según mi conocimiento"
- SOLO cita texto literal de los documentos
- Si no encuentras la información, responde: "{MENSAJE_NO_CONSTA}"
"""


# =============================================================================
# ESTRUCTURAS DE DATOS
# =============================================================================

@dataclass
class PaginaPDF:
    """Contenido de una página de PDF"""
    numero: int
    texto: str
    archivo: str


@dataclass
class DocumentoCargado:
    """Documento PDF cargado"""
    nombre: str
    ruta: str
    paginas: List[PaginaPDF] = field(default_factory=list)
    total_paginas: int = 0


@dataclass
class EvidenciaDirectiva:
    """Evidencia encontrada en una directiva"""
    archivo: str
    pagina: int
    snippet: str
    contexto: str = ""
    relevancia: float = 0.0


@dataclass
class RespuestaDirectiva:
    """Respuesta del agente con evidencia"""
    texto: str
    evidencias: List[EvidenciaDirectiva] = field(default_factory=list)
    tiene_sustento: bool = False
    cumple_estandar: bool = True
    backend_usado: str = "regex"


# =============================================================================
# IMPORTAR DEPENDENCIAS
# =============================================================================

try:
    import fitz  # PyMuPDF
    PYMUPDF_DISPONIBLE = True
except ImportError:
    PYMUPDF_DISPONIBLE = False
    logger.warning("PyMuPDF no disponible. Instalar: pip install pymupdf")

try:
    from utils.llm_local import LocalLLMClient, MENSAJE_INSUFICIENCIA
    LLM_DISPONIBLE = True
except ImportError:
    LLM_DISPONIBLE = False
    LocalLLMClient = None


# =============================================================================
# AGENTE DE DIRECTIVAS
# =============================================================================

class AgenteDirectivas:
    """
    Agente para consultar directivas y pautas con estándar probatorio.
    
    Características:
    - Carga múltiples PDFs
    - Búsqueda por keywords y patrones
    - Integración opcional con LLM
    - Citación obligatoria de fuentes
    """
    
    def __init__(self, backend: str = "auto"):
        """
        Inicializa el agente.
        
        Args:
            backend: "auto", "llm", "regex"
        """
        self.documentos: List[DocumentoCargado] = []
        self.indice_texto: Dict[str, List[Tuple[str, int, str]]] = {}  # palabra -> [(archivo, pagina, contexto)]
        
        self.backend = backend
        self.llm_client = None
        self.llm_modelo = None
        self._inicializar_backend()
    
    def _inicializar_backend(self):
        """Inicializa el backend LLM si está disponible"""
        if self.backend == "regex":
            return
        
        if not LLM_DISPONIBLE:
            logger.info("LLM no disponible, usando regex")
            self.backend = "regex"
            return
        
        try:
            self.llm_client = LocalLLMClient()
            if self.llm_client.disponible:
                self.llm_modelo = self.llm_client.modelo
                logger.info(f"LLM disponible: {self.llm_modelo}")
            elif self.backend == "auto":
                self.backend = "regex"
        except Exception as e:
            logger.warning(f"Error inicializando LLM: {e}")
            if self.backend == "auto":
                self.backend = "regex"
    
    @property
    def usando_llm(self) -> bool:
        return self.llm_client is not None and self.llm_client.disponible
    
    def get_info(self) -> Dict[str, Any]:
        """Retorna información del agente"""
        return {
            "documentos_cargados": len(self.documentos),
            "total_paginas": sum(d.total_paginas for d in self.documentos),
            "backend": self.backend,
            "llm_disponible": self.usando_llm,
            "modelo": self.llm_modelo,
            "archivos": [d.nombre for d in self.documentos]
        }
    
    # =========================================================================
    # CARGA DE PDFs
    # =========================================================================
    
    def cargar_pdf(self, ruta: str) -> bool:
        """
        Carga un PDF de directiva/pauta.
        
        Args:
            ruta: Ruta al archivo PDF
            
        Returns:
            True si se cargó correctamente
        """
        if not PYMUPDF_DISPONIBLE:
            logger.error("PyMuPDF no disponible")
            return False
        
        if not os.path.exists(ruta):
            logger.error(f"Archivo no existe: {ruta}")
            return False
        
        try:
            nombre = os.path.basename(ruta)
            
            # Verificar si ya está cargado
            if any(d.nombre == nombre for d in self.documentos):
                logger.info(f"Documento ya cargado: {nombre}")
                return True
            
            doc = fitz.open(ruta)
            paginas = []
            
            for num_pag in range(len(doc)):
                page = doc[num_pag]
                texto = page.get_text()
                
                if texto.strip():
                    paginas.append(PaginaPDF(
                        numero=num_pag + 1,
                        texto=texto,
                        archivo=nombre
                    ))
                    
                    # Indexar texto para búsqueda
                    self._indexar_pagina(nombre, num_pag + 1, texto)
            
            doc.close()
            
            documento = DocumentoCargado(
                nombre=nombre,
                ruta=ruta,
                paginas=paginas,
                total_paginas=len(paginas)
            )
            
            self.documentos.append(documento)
            logger.info(f"Cargado: {nombre} ({len(paginas)} páginas)")
            
            return True
            
        except Exception as e:
            logger.error(f"Error cargando PDF {ruta}: {e}")
            return False
    
    def cargar_multiples(self, rutas: List[str]) -> int:
        """
        Carga múltiples PDFs.
        
        Args:
            rutas: Lista de rutas a PDFs
            
        Returns:
            Número de PDFs cargados exitosamente
        """
        cargados = 0
        for ruta in rutas:
            if self.cargar_pdf(ruta):
                cargados += 1
        return cargados
    
    def _indexar_pagina(self, archivo: str, pagina: int, texto: str):
        """Indexa el texto de una página para búsqueda rápida"""
        # Normalizar y tokenizar
        texto_norm = texto.lower()
        palabras = re.findall(r'\b\w{3,}\b', texto_norm)
        
        for palabra in set(palabras):
            if palabra not in self.indice_texto:
                self.indice_texto[palabra] = []
            
            # Extraer contexto (snippet)
            match = re.search(rf'\b{re.escape(palabra)}\b', texto_norm)
            if match:
                start = max(0, match.start() - 50)
                end = min(len(texto), match.end() + 100)
                contexto = texto[start:end].strip()
                
                self.indice_texto[palabra].append((archivo, pagina, contexto))
    
    # =========================================================================
    # BÚSQUEDA EN DOCUMENTOS
    # =========================================================================
    
    def buscar_en_documentos(self, 
                              terminos: List[str], 
                              max_resultados: int = 5) -> List[EvidenciaDirectiva]:
        """
        Busca términos en los documentos cargados.
        
        Args:
            terminos: Lista de términos a buscar
            max_resultados: Máximo de resultados
            
        Returns:
            Lista de evidencias encontradas
        """
        resultados = []
        
        for termino in terminos:
            termino_lower = termino.lower()
            
            # Buscar en cada documento
            for doc in self.documentos:
                for pagina in doc.paginas:
                    texto_lower = pagina.texto.lower()
                    
                    if termino_lower in texto_lower:
                        # Extraer snippet
                        snippet = self._extraer_snippet(pagina.texto, termino)
                        
                        if snippet:
                            resultados.append(EvidenciaDirectiva(
                                archivo=doc.nombre,
                                pagina=pagina.numero,
                                snippet=snippet,
                                contexto=termino,
                                relevancia=1.0
                            ))
        
        # Eliminar duplicados y limitar
        vistos = set()
        unicos = []
        for r in resultados:
            key = (r.archivo, r.pagina, r.snippet[:50])
            if key not in vistos:
                vistos.add(key)
                unicos.append(r)
        
        return unicos[:max_resultados]
    
    def _extraer_snippet(self, texto: str, termino: str, contexto: int = 150) -> str:
        """Extrae un snippet alrededor del término encontrado"""
        texto_lower = texto.lower()
        termino_lower = termino.lower()
        
        pos = texto_lower.find(termino_lower)
        if pos == -1:
            return ""
        
        start = max(0, pos - contexto)
        end = min(len(texto), pos + len(termino) + contexto)
        
        snippet = texto[start:end].strip()
        
        # Limpiar saltos de línea excesivos
        snippet = re.sub(r'\s+', ' ', snippet)
        
        return snippet
    
    def buscar_por_patron(self, patron: str) -> List[EvidenciaDirectiva]:
        """Busca usando expresión regular"""
        resultados = []
        
        try:
            regex = re.compile(patron, re.IGNORECASE)
            
            for doc in self.documentos:
                for pagina in doc.paginas:
                    matches = regex.finditer(pagina.texto)
                    
                    for match in matches:
                        start = max(0, match.start() - 100)
                        end = min(len(pagina.texto), match.end() + 100)
                        snippet = pagina.texto[start:end].strip()
                        snippet = re.sub(r'\s+', ' ', snippet)
                        
                        resultados.append(EvidenciaDirectiva(
                            archivo=doc.nombre,
                            pagina=pagina.numero,
                            snippet=snippet,
                            contexto=match.group(),
                            relevancia=1.0
                        ))
        except re.error:
            logger.warning(f"Patrón regex inválido: {patron}")
        
        return resultados[:10]
    
    # =========================================================================
    # PREGUNTAR
    # =========================================================================
    
    def preguntar(self, pregunta: str) -> RespuestaDirectiva:
        """
        Responde una pregunta con estándar probatorio.
        
        POLÍTICA ANTI-ALUCINACIÓN:
        - Solo responde con información de los PDFs
        - Cita obligatoria: archivo + página + snippet
        - Si no encuentra: mensaje estándar
        
        Args:
            pregunta: Pregunta en lenguaje natural
            
        Returns:
            RespuestaDirectiva con evidencias
        """
        if not self.documentos:
            return RespuestaDirectiva(
                texto="⚠️ No hay documentos cargados. Use cargar_pdf() primero.",
                evidencias=[],
                tiene_sustento=False,
                cumple_estandar=True
            )
        
        # Extraer términos clave de la pregunta
        terminos = self._extraer_terminos_clave(pregunta)
        
        # Buscar en documentos
        evidencias = self.buscar_en_documentos(terminos)
        
        # Si no hay evidencias, buscar con patrones más amplios
        if not evidencias:
            # Buscar palabras clave comunes en normativas
            keywords_normativas = self._extraer_keywords_normativos(pregunta)
            if keywords_normativas:
                evidencias = self.buscar_en_documentos(keywords_normativas)
        
        # Si aún no hay evidencias
        if not evidencias:
            return self._respuesta_no_consta(pregunta)
        
        # Si hay LLM disponible y evidencias, usar LLM para sintetizar
        if self.usando_llm and self.backend != "regex":
            return self._responder_con_llm(pregunta, evidencias)
        
        # Respuesta con regex (sin LLM)
        return self._responder_con_evidencias(pregunta, evidencias)
    
    def _extraer_terminos_clave(self, pregunta: str) -> List[str]:
        """Extrae términos clave de una pregunta"""
        # Eliminar palabras vacías
        stopwords = {
            'que', 'cual', 'cuales', 'como', 'cuando', 'donde', 'quien',
            'para', 'por', 'con', 'sin', 'sobre', 'entre', 'desde', 'hasta',
            'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
            'es', 'son', 'esta', 'estan', 'hay', 'tiene', 'tienen',
            'se', 'de', 'del', 'al', 'y', 'o', 'en', 'a', 'no', 'si',
            'mas', 'pero', 'porque', 'segun', 'debe', 'deben', 'puede', 'pueden'
        }
        
        # Normalizar
        pregunta_norm = pregunta.lower()
        pregunta_norm = re.sub(r'[¿?¡!.,;:]', '', pregunta_norm)
        
        # Extraer palabras significativas
        palabras = pregunta_norm.split()
        terminos = [p for p in palabras if len(p) > 2 and p not in stopwords]
        
        return terminos
    
    def _extraer_keywords_normativos(self, pregunta: str) -> List[str]:
        """Extrae keywords específicos de normativas"""
        pregunta_lower = pregunta.lower()
        
        keywords = []
        
        # Detectar conceptos normativos
        conceptos = {
            'plazo': ['plazo', 'días', 'hábiles', 'calendario', 'término'],
            'monto': ['monto', 'importe', 'suma', 'valor', 'límite', 'máximo', 'mínimo'],
            'requisito': ['requisito', 'documento', 'anexo', 'adjuntar', 'presentar'],
            'procedimiento': ['procedimiento', 'proceso', 'trámite', 'etapa', 'paso'],
            'responsable': ['responsable', 'encargado', 'competente', 'autoridad'],
            'penalidad': ['penalidad', 'sanción', 'multa', 'incumplimiento'],
            'viatico': ['viático', 'viáticos', 'pasaje', 'hospedaje', 'alimentación'],
            'rendicion': ['rendición', 'rendir', 'sustento', 'comprobante'],
            'conformidad': ['conformidad', 'aprobación', 'visto bueno'],
        }
        
        for concepto, palabras in conceptos.items():
            for palabra in palabras:
                if palabra in pregunta_lower:
                    keywords.extend(palabras)
                    break
        
        return list(set(keywords))
    
    def _respuesta_no_consta(self, pregunta: str) -> RespuestaDirectiva:
        """Genera respuesta cuando no hay evidencia"""
        texto = f"{MENSAJE_NO_CONSTA}\n\n"
        texto += f"📋 Documentos consultados:\n"
        for doc in self.documentos:
            texto += f"   • {doc.nombre} ({doc.total_paginas} páginas)\n"
        texto += f"\n💡 Sugerencia: Reformule la pregunta con términos más específicos."
        
        return RespuestaDirectiva(
            texto=texto,
            evidencias=[],
            tiene_sustento=False,
            cumple_estandar=True
        )
    
    def _responder_con_evidencias(self, 
                                   pregunta: str, 
                                   evidencias: List[EvidenciaDirectiva]) -> RespuestaDirectiva:
        """Genera respuesta con evidencias (sin LLM)"""
        lineas = [f"📚 **Información encontrada sobre:** {pregunta}\n"]
        
        for i, ev in enumerate(evidencias, 1):
            lineas.append(f"---")
            lineas.append(f"**Fuente {i}:**")
            lineas.append(f"📄 Archivo: `{ev.archivo}`")
            lineas.append(f"📃 Página: {ev.pagina}")
            lineas.append(f"📝 Texto: \"{ev.snippet}\"")
            lineas.append("")
        
        lineas.append(f"---")
        lineas.append(f"📊 Total: {len(evidencias)} referencia(s) encontrada(s)")
        
        return RespuestaDirectiva(
            texto="\n".join(lineas),
            evidencias=evidencias,
            tiene_sustento=True,
            cumple_estandar=all(ev.archivo and ev.pagina and ev.snippet for ev in evidencias),
            backend_usado="regex"
        )
    
    def _responder_con_llm(self, 
                           pregunta: str, 
                           evidencias: List[EvidenciaDirectiva]) -> RespuestaDirectiva:
        """Genera respuesta usando LLM con las evidencias"""
        if not self.usando_llm:
            return self._responder_con_evidencias(pregunta, evidencias)
        
        # Construir contexto para el LLM
        contexto = "INFORMACIÓN DE LAS DIRECTIVAS:\n\n"
        for i, ev in enumerate(evidencias, 1):
            contexto += f"[{i}] Archivo: {ev.archivo}, Página: {ev.pagina}\n"
            contexto += f"    Texto: \"{ev.snippet}\"\n\n"
        
        prompt = f"""Basándote ÚNICAMENTE en la siguiente información de las directivas, responde la pregunta.

{contexto}

PREGUNTA: {pregunta}

INSTRUCCIONES:
1. Responde SOLO con información del contexto proporcionado.
2. CITA OBLIGATORIAMENTE: archivo, página y texto literal.
3. Si la información no está en el contexto, di: "{MENSAJE_NO_CONSTA}"

FORMATO DE RESPUESTA:
📄 Fuente: [archivo]
📃 Página: [número]
📝 Texto: "[snippet]"
[Tu respuesta basada en el texto]
"""
        
        try:
            respuesta_llm = self.llm_client.ask(prompt, SYSTEM_PROMPT_DIRECTIVAS)
            
            # Validar que cite fuentes
            if not self._validar_respuesta_llm(respuesta_llm, evidencias):
                # Si no cita fuentes, usar respuesta regex
                return self._responder_con_evidencias(pregunta, evidencias)
            
            return RespuestaDirectiva(
                texto=f"🤖 **[LLM: {self.llm_modelo}]**\n\n{respuesta_llm}",
                evidencias=evidencias,
                tiene_sustento=True,
                cumple_estandar=True,
                backend_usado="llm"
            )
            
        except Exception as e:
            logger.error(f"Error en LLM: {e}")
            return self._responder_con_evidencias(pregunta, evidencias)
    
    def _validar_respuesta_llm(self, respuesta: str, evidencias: List[EvidenciaDirectiva]) -> bool:
        """Valida que la respuesta del LLM cite fuentes"""
        # Verificar que mencione algún archivo
        menciona_archivo = any(ev.archivo in respuesta for ev in evidencias)
        
        # Verificar patrones de citación
        tiene_citacion = any(patron in respuesta.lower() for patron in [
            "archivo:", "página:", "pág.", "fuente:", "texto:"
        ])
        
        # Si es mensaje de no consta, es válido
        if MENSAJE_NO_CONSTA.lower() in respuesta.lower():
            return True
        
        return menciona_archivo or tiene_citacion
    
    # =========================================================================
    # MODO INTERACTIVO
    # =========================================================================
    
    def modo_interactivo(self):
        """Inicia modo interactivo por consola"""
        print("=" * 70)
        print("📚 AGENTE DE DIRECTIVAS - ESTÁNDAR PROBATORIO")
        print("=" * 70)
        
        info = self.get_info()
        print(f"📄 Documentos: {info['documentos_cargados']}")
        print(f"📃 Páginas totales: {info['total_paginas']}")
        print(f"🔧 Backend: {info['backend']}")
        if info['llm_disponible']:
            print(f"🧠 LLM: {info['modelo']}")
        
        if not self.documentos:
            print("\n⚠️ No hay documentos cargados.")
            return
        
        print(f"\n📋 Archivos cargados:")
        for nombre in info['archivos']:
            print(f"   • {nombre}")
        
        print("\n" + "-" * 70)
        print("💬 Escribe tu pregunta (o 'salir' para terminar)")
        
        while True:
            try:
                pregunta = input("\n🧑 Tú: ").strip()
                
                if not pregunta:
                    continue
                
                if pregunta.lower() in ["salir", "exit", "q"]:
                    print("\n👋 ¡Hasta luego!")
                    break
                
                respuesta = self.preguntar(pregunta)
                print(f"\n🤖 Agente:\n{respuesta.texto}")
                
                if not respuesta.tiene_sustento:
                    print("\n⚠️ [Sin sustento en las directivas cargadas]")
                elif respuesta.evidencias:
                    print(f"\n📎 {len(respuesta.evidencias)} evidencia(s)")
                
            except KeyboardInterrupt:
                print("\n\n👋 ¡Hasta luego!")
                break


# =============================================================================
# FUNCIÓN HELPER
# =============================================================================

def crear_agente_directivas(pdfs: List[str] = None, backend: str = "auto") -> AgenteDirectivas:
    """
    Crea un agente de directivas con PDFs precargados.
    
    Args:
        pdfs: Lista de rutas a PDFs
        backend: "auto", "llm", "regex"
        
    Returns:
        AgenteDirectivas configurado
    """
    agente = AgenteDirectivas(backend=backend)
    
    if pdfs:
        for pdf in pdfs:
            agente.cargar_pdf(pdf)
    
    return agente


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("AGENTE DE DIRECTIVAS - Test básico")
    print("=" * 50)
    
    agente = AgenteDirectivas()
    print(f"Backend: {agente.backend}")
    print(f"LLM disponible: {agente.usando_llm}")
    
    if len(sys.argv) > 1:
        for pdf in sys.argv[1:]:
            if pdf.endswith('.pdf'):
                agente.cargar_pdf(pdf)
        
        if agente.documentos:
            agente.modo_interactivo()
    else:
        print("\nUso: python agente_directivas.py <ruta1.pdf> <ruta2.pdf> ...")



