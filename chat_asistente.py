# -*- coding: utf-8 -*-
"""
AG-EVIDENCE — CHAT ASISTENTE
============================
Asistente conversacional que consulta PDFs y JSONs con estándar probatorio.

🔒 CANDADO FUNCIONAL (ALCANCE DEL SISTEMA):
AG-EVIDENCE solo responde dentro de su dominio: análisis probatorio de expedientes
administrativos. Consultas creativas, personales, filosóficas o técnicas no
relacionadas deben rechazarse con:

    "Esta consulta no se encuentra dentro del alcance funcional de AG-EVIDENCE.
     El sistema está diseñado exclusivamente para análisis probatorio documentado
     de expedientes administrativos."

POLÍTICA ANTI-ALUCINACIÓN:
- Retrieval determinístico ANTES de responder
- Solo responde con evidencia literal de los documentos
- Cita obligatoria: archivo + página + snippet
- Sin evidencia → "No consta en los documentos cargados"

USO:
    python chat_asistente.py --backend llm
    python chat_asistente.py --carpeta data/directivas/vigentes_2025_11_26 --backend auto
    python chat_asistente.py --expediente_json output/informe.json --pdf directiva.pdf

OPCIONES:
    --pdf, -p           Ruta a PDF (puede repetirse)
    --carpeta, -c       Carpeta con PDFs - RELATIVA al proyecto (default: data/directivas/vigentes_2025_11_26)
    --expediente_json   JSON de expediente analizado
    --backend, -b       Backend: auto, llm, regex (default: auto)
    --modelo, -m        Modelo específico de Ollama (opcional)
"""

import os
import sys
import argparse
import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# Directorio raíz del proyecto
PROJECT_ROOT = Path(__file__).parent.absolute()

# Carpeta de directivas por defecto (relativa al proyecto)
DEFAULT_DIRECTIVAS_DIR = "data/directivas/vigentes_2025_11_26"

# Configurar encoding para Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Agregar path del proyecto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTES
# =============================================================================

MENSAJE_NO_CONSTA = "No consta información suficiente en los documentos revisados."

# Mensaje de candado funcional (fuera de alcance)
MENSAJE_FUERA_DE_ALCANCE = """Esta consulta no se encuentra dentro del alcance funcional de AG-EVIDENCE.
El sistema está diseñado exclusivamente para análisis probatorio documentado de expedientes administrativos."""

# Modos de operación
MODO_TECNICO = "tecnico"
MODO_CONVERSACIONAL = "conversacional"

SYSTEM_PROMPT_ASISTENTE = """Eres un asistente especializado en normativas y expedientes administrativos.

REGLAS ESTRICTAS (NO NEGOCIABLES):
1. SOLO puedes responder usando la información proporcionada en el CONTEXTO.
2. PROHIBIDO inventar, inferir o usar conocimiento externo.
3. TODA respuesta DEBE citar: archivo, página y texto literal.
4. Si no hay información en el contexto, responde: "{}"

FORMATO DE RESPUESTA:
- Respuesta breve (2-5 líneas)
- Al final, SIEMPRE citar fuentes así:
  📄 Fuente: [archivo], pág. [N]: "[snippet]"

Si el usuario pide "texto para devolver al área", redacta un párrafo formal citando al final.
""".format(MENSAJE_NO_CONSTA)

# Prompt para MODO CONVERSACIONAL - Reformulación administrativa
SYSTEM_PROMPT_CONVERSACIONAL = """Eres un asistente de Control Previo del sector público peruano.

TU ÚNICA FUNCIÓN: Reformular la información técnica en lenguaje administrativo claro.

REGLAS ABSOLUTAS (VIOLACIÓN = FALLO):
1. SOLO puedes usar la información del RESULTADO TÉCNICO proporcionado.
2. PROHIBIDO TOTALMENTE:
   - Inventar datos, fechas, montos o referencias
   - Inferir o deducir información no explícita
   - Usar conocimiento externo sobre normativas
   - Agregar advertencias o recomendaciones no sustentadas
3. OBLIGATORIO mantener TODAS las citas de archivo y página.
4. Si el resultado técnico no tiene evidencia, responde EXACTAMENTE:
   "No consta información suficiente en los documentos revisados."

REGLA ANTI-ERROR DE NUMERALES (CRÍTICA):
5. PROHIBIDO mencionar "Artículo", "Numeral", "Inciso", "Literal" o números específicos
   de artículos/numerales SI esas palabras NO aparecen LITERALMENTE en el snippet citado.
6. Si el snippet NO contiene numeración explícita, usar frases como:
   - "Según lo establecido en el documento (pág. X)..."
   - "Conforme al apartado referido en pág. X..."
   - "De acuerdo con la normativa citada..."
   NUNCA inventar números de artículo.

FORMATO DE RESPUESTA CONVERSACIONAL:
- Lenguaje formal administrativo
- Párrafos claros para áreas usuarias
- AL FINAL, citar fuentes: 📄 [archivo], pág. [N]
"""

# Palabras de numeración que requieren verificación
PALABRAS_NUMERACION = ['artículo', 'art.', 'numeral', 'inciso', 'literal', 'capítulo', 'título']

MAX_MEMORIA_TURNOS = 5
MAX_SNIPPET_LENGTH = 300
MAX_EVIDENCIAS_CONTEXTO = 8


# =============================================================================
# ESTRUCTURAS DE DATOS
# =============================================================================

@dataclass
class Evidencia:
    """Evidencia encontrada en documentos"""
    archivo: str
    pagina: int
    snippet: str
    match: str  # término que matcheó
    score: float = 1.0
    fuente: str = "pdf"  # "pdf" o "json"


@dataclass
class TurnoConversacion:
    """Un turno de la conversación"""
    pregunta: str
    timestamp: str


@dataclass
class RespuestaAsistente:
    """Respuesta del asistente"""
    texto: str
    evidencias: List[Evidencia] = field(default_factory=list)
    tiene_sustento: bool = False
    backend_usado: str = "regex"
    tiempo_respuesta: float = 0.0


# =============================================================================
# IMPORTAR DEPENDENCIAS
# =============================================================================

try:
    import fitz  # PyMuPDF
    PYMUPDF_DISPONIBLE = True
except ImportError:
    PYMUPDF_DISPONIBLE = False
    logger.error("PyMuPDF no disponible. Instalar: pip install pymupdf")

try:
    from utils.llm_local import LocalLLMClient, verificar_ollama
    LLM_DISPONIBLE = True
except ImportError:
    LLM_DISPONIBLE = False
    LocalLLMClient = None
    verificar_ollama = None


# =============================================================================
# CLASE PRINCIPAL: CHAT ASISTENTE
# =============================================================================

class ChatAsistente:
    """
    Asistente conversacional con estándar probatorio.
    
    Características:
    - Carga múltiples PDFs y JSON de expediente
    - Retrieval determinístico antes de responder
    - Integración con LLM local (Ollama/Qwen)
    - Memoria corta de 5 turnos
    - Citación obligatoria de fuentes
    - Modo técnico vs conversacional
    """
    
    def __init__(self, 
                 backend: str = "auto", 
                 modelo: str = None,
                 modo: str = MODO_TECNICO):
        """
        Inicializa el asistente.
        
        Args:
            backend: "auto", "llm", "regex"
            modelo: Modelo específico de Ollama (opcional)
            modo: "tecnico" (default) o "conversacional"
        """
        self.backend = backend
        self.modelo_solicitado = modelo
        self.modo = modo if modo in [MODO_TECNICO, MODO_CONVERSACIONAL] else MODO_TECNICO
        
        # Almacenamiento de documentos
        self.documentos_pdf: Dict[str, List[Dict]] = {}  # {archivo: [{pagina, texto}]}
        self.expediente_json: Dict = {}
        self.hallazgos_json: List[Dict] = []
        
        # Índice de búsqueda
        self.indice: Dict[str, List[Tuple[str, int, str]]] = {}  # palabra -> [(archivo, pagina, contexto)]
        
        # Memoria de conversación
        self.memoria: List[TurnoConversacion] = []
        
        # LLM
        self.llm_client = None
        self.llm_modelo = None
        self._inicializar_backend()
    
    def _inicializar_backend(self):
        """Inicializa el backend LLM"""
        if self.backend == "regex":
            logger.info("Backend: REGEX (sin LLM)")
            return
        
        if not LLM_DISPONIBLE:
            if self.backend == "llm":
                logger.error("LLM solicitado pero utils/llm_local.py no disponible")
                sys.exit(1)
            logger.warning("LLM no disponible, usando REGEX")
            self.backend = "regex"
            return
        
        try:
            # Verificar Ollama
            info = verificar_ollama()
            disponible = info.get("disponible", False)
            logger.debug(f"Ollama check: disponible={disponible}, modelo={info.get('modelo_seleccionado')}")
            
            if not disponible:
                if self.backend == "llm":
                    logger.error("Ollama no está disponible. Inicie Ollama primero.")
                    sys.exit(1)
                logger.warning("Ollama no disponible, usando REGEX")
                self.backend = "regex"
                return
            
            # Crear cliente
            self.llm_client = LocalLLMClient(modelo=self.modelo_solicitado)
            
            if self.llm_client.disponible:
                self.llm_modelo = self.llm_client.modelo
                self.backend = "llm"
                logger.info(f"Backend: LLM ({self.llm_modelo})")
            elif self.backend == "llm":
                logger.error(f"No se pudo inicializar LLM")
                sys.exit(1)
            else:
                self.backend = "regex"
                logger.warning("LLM no inicializado, usando REGEX")
                
        except Exception as e:
            if self.backend == "llm":
                logger.error(f"Error inicializando LLM: {e}")
                sys.exit(1)
            logger.warning(f"Error con LLM, usando REGEX: {e}")
            self.backend = "regex"
    
    @property
    def usando_llm(self) -> bool:
        return self.backend == "llm" and self.llm_client is not None
    
    def get_info(self) -> Dict[str, Any]:
        """Retorna información del asistente"""
        return {
            "backend": self.backend,
            "modelo": self.llm_modelo,
            "modo": self.modo,
            "pdfs_cargados": len(self.documentos_pdf),
            "paginas_totales": sum(len(p) for p in self.documentos_pdf.values()),
            "expediente_json": bool(self.expediente_json),
            "hallazgos_json": len(self.hallazgos_json),
            "turnos_memoria": len(self.memoria),
            "archivos": list(self.documentos_pdf.keys())
        }
    
    # =========================================================================
    # CARGA DE DOCUMENTOS
    # =========================================================================
    
    def cargar_pdf(self, ruta: str) -> bool:
        """Carga un PDF"""
        if not PYMUPDF_DISPONIBLE:
            logger.error("PyMuPDF no disponible")
            return False
        
        ruta_path = Path(ruta)
        
        if not ruta_path.exists():
            logger.error(f"Archivo no existe: {ruta}")
            return False
        
        # Ignorar PDFs de 0 bytes
        if ruta_path.stat().st_size == 0:
            logger.warning(f"  ⚠ Ignorado (0 bytes): {ruta_path.name}")
            return False
        
        try:
            nombre = ruta_path.name
            
            if nombre in self.documentos_pdf:
                logger.debug(f"PDF ya cargado: {nombre}")
                return True
            
            doc = fitz.open(ruta)
            paginas = []
            
            for num_pag in range(len(doc)):
                page = doc[num_pag]
                texto = page.get_text()
                
                if texto.strip():
                    paginas.append({
                        "pagina": num_pag + 1,
                        "texto": texto
                    })
                    self._indexar_texto(nombre, num_pag + 1, texto)
            
            doc.close()
            
            if paginas:
                self.documentos_pdf[nombre] = paginas
                logger.info(f"  ✓ {nombre} ({len(paginas)} págs)")
                return True
            else:
                logger.warning(f"  ⚠ {nombre} (sin texto extraíble)")
                return False
                
        except Exception as e:
            logger.error(f"  ✗ Error en {ruta}: {e}")
            return False
    
    def cargar_carpeta(self, carpeta: str, recursivo: bool = True) -> Tuple[int, List[str]]:
        """
        Carga PDFs de una carpeta.
        
        Args:
            carpeta: Ruta a la carpeta (absoluta o relativa al proyecto)
            recursivo: Si True, busca en subcarpetas (rglob)
            
        Returns:
            Tuple (número de PDFs cargados, lista de rutas cargadas)
        """
        carpeta_path = Path(carpeta)
        
        # Si la ruta es relativa, resolverla desde el proyecto
        if not carpeta_path.is_absolute():
            carpeta_path = PROJECT_ROOT / carpeta_path
        
        if not carpeta_path.exists():
            logger.error(f"❌ Carpeta no existe: {carpeta_path}")
            return 0, []
        
        # Buscar PDFs (recursivo con rglob)
        if recursivo:
            pdfs = list(carpeta_path.rglob("*.pdf"))
            pdfs.extend(carpeta_path.rglob("*.PDF"))
        else:
            pdfs = list(carpeta_path.glob("*.pdf"))
            pdfs.extend(carpeta_path.glob("*.PDF"))
        
        # Eliminar duplicados y ordenar
        pdfs = sorted(set(pdfs))
        
        # Filtrar PDFs de 0 bytes
        pdfs_validos = [p for p in pdfs if p.stat().st_size > 0]
        pdfs_vacios = len(pdfs) - len(pdfs_validos)
        
        print()
        print(f"📁 Carpeta: {carpeta_path}")
        print(f"📄 PDFs encontrados: {len(pdfs_validos)}", end="")
        if pdfs_vacios > 0:
            print(f" ({pdfs_vacios} vacíos ignorados)")
        else:
            print()
        
        if pdfs_validos:
            print()
            print("📂 Lista de archivos:")
            for pdf in pdfs_validos:
                # Mostrar ruta relativa a la carpeta
                try:
                    ruta_rel = pdf.relative_to(carpeta_path)
                except ValueError:
                    ruta_rel = pdf.name
                print(f"   • {ruta_rel}")
        
        rutas_cargadas = []
        cargados = 0
        
        print()
        print("⏳ Cargando contenido...")
        for pdf in pdfs_validos:
            if self.cargar_pdf(str(pdf)):
                cargados += 1
                rutas_cargadas.append(str(pdf))
        
        return cargados, rutas_cargadas
    
    def cargar_expediente_json(self, ruta: str) -> bool:
        """Carga JSON de expediente analizado"""
        if not os.path.exists(ruta):
            logger.error(f"JSON no existe: {ruta}")
            return False
        
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.expediente_json = data
            self.hallazgos_json = data.get('hallazgos', [])
            
            # Indexar hallazgos
            for h in self.hallazgos_json:
                hallazgo = h.get('hallazgo', '')
                self._indexar_texto("expediente.json", 0, hallazgo, fuente="json")
            
            sinad = data.get('metadata', {}).get('expediente_sinad', 'N/A')
            logger.info(f"  ✓ Expediente JSON cargado (SINAD: {sinad}, {len(self.hallazgos_json)} hallazgos)")
            return True
            
        except Exception as e:
            logger.error(f"Error cargando JSON: {e}")
            return False
    
    def _indexar_texto(self, archivo: str, pagina: int, texto: str, fuente: str = "pdf"):
        """Indexa texto para búsqueda rápida"""
        texto_norm = texto.lower()
        # Extraer palabras de 3+ caracteres
        palabras = set(re.findall(r'\b\w{3,}\b', texto_norm))
        
        for palabra in palabras:
            if palabra not in self.indice:
                self.indice[palabra] = []
            
            # Evitar duplicados
            key = (archivo, pagina)
            if not any(x[0] == archivo and x[1] == pagina for x in self.indice[palabra]):
                # Extraer contexto
                match = re.search(rf'\b{re.escape(palabra)}\b', texto_norm)
                if match:
                    start = max(0, match.start() - 50)
                    end = min(len(texto), match.end() + 100)
                    contexto = texto[start:end].strip()
                    self.indice[palabra].append((archivo, pagina, contexto, fuente))
    
    # =========================================================================
    # RETRIEVAL DETERMINÍSTICO
    # =========================================================================
    
    def retrieval(self, pregunta: str, max_resultados: int = MAX_EVIDENCIAS_CONTEXTO) -> List[Evidencia]:
        """
        Retrieval determinístico sobre documentos cargados.
        
        Args:
            pregunta: Pregunta del usuario
            max_resultados: Máximo de evidencias a retornar
            
        Returns:
            Lista de evidencias ordenadas por relevancia
        """
        evidencias = []
        
        # Extraer términos de búsqueda
        terminos = self._extraer_terminos(pregunta)
        
        # Buscar en PDFs
        for termino in terminos:
            evidencias.extend(self._buscar_en_pdfs(termino))
        
        # Buscar en JSON de expediente
        if self.expediente_json:
            evidencias.extend(self._buscar_en_json(terminos))
        
        # Eliminar duplicados y ordenar por relevancia
        evidencias_unicas = self._deduplicar_evidencias(evidencias)
        evidencias_ordenadas = sorted(evidencias_unicas, key=lambda x: x.score, reverse=True)
        
        return evidencias_ordenadas[:max_resultados]
    
    def _extraer_terminos(self, pregunta: str) -> List[str]:
        """Extrae términos de búsqueda de la pregunta"""
        stopwords = {
            'que', 'cual', 'cuales', 'como', 'cuando', 'donde', 'quien', 'quienes',
            'para', 'por', 'con', 'sin', 'sobre', 'entre', 'desde', 'hasta',
            'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
            'es', 'son', 'esta', 'estan', 'hay', 'tiene', 'tienen',
            'se', 'de', 'del', 'al', 'y', 'o', 'en', 'a', 'no', 'si',
            'mas', 'pero', 'porque', 'segun', 'debe', 'deben', 'puede', 'pueden',
            'dice', 'indica', 'señala', 'establece', 'menciona'
        }
        
        pregunta_norm = pregunta.lower()
        pregunta_norm = re.sub(r'[¿?¡!.,;:\'"()]', '', pregunta_norm)
        
        palabras = pregunta_norm.split()
        terminos = [p for p in palabras if len(p) > 2 and p not in stopwords]
        
        # Agregar frases compuestas relevantes
        if 'plazo' in pregunta_norm:
            terminos.extend(['días', 'hábiles', 'calendario', 'término'])
        if 'monto' in pregunta_norm or 'importe' in pregunta_norm:
            terminos.extend(['soles', 'máximo', 'mínimo', 'límite'])
        if 'viático' in pregunta_norm or 'viatico' in pregunta_norm:
            terminos.extend(['rendición', 'comisión', 'pasaje', 'hospedaje'])
        if 'penalidad' in pregunta_norm:
            terminos.extend(['incumplimiento', 'sanción', 'multa', 'descuento'])
        
        return list(set(terminos))
    
    def _buscar_en_pdfs(self, termino: str) -> List[Evidencia]:
        """Busca un término en los PDFs cargados"""
        evidencias = []
        termino_lower = termino.lower()
        
        for archivo, paginas in self.documentos_pdf.items():
            for pag_data in paginas:
                texto = pag_data['texto']
                texto_lower = texto.lower()
                
                if termino_lower in texto_lower:
                    snippet = self._extraer_snippet(texto, termino)
                    if snippet:
                        evidencias.append(Evidencia(
                            archivo=archivo,
                            pagina=pag_data['pagina'],
                            snippet=snippet,
                            match=termino,
                            score=1.0,
                            fuente="pdf"
                        ))
        
        return evidencias
    
    def _buscar_en_json(self, terminos: List[str]) -> List[Evidencia]:
        """Busca términos en el JSON del expediente"""
        evidencias = []
        
        for hallazgo in self.hallazgos_json:
            texto_hallazgo = hallazgo.get('hallazgo', '').lower()
            
            for termino in terminos:
                if termino.lower() in texto_hallazgo:
                    evidencias.append(Evidencia(
                        archivo="expediente.json",
                        pagina=0,
                        snippet=hallazgo.get('hallazgo', '')[:MAX_SNIPPET_LENGTH],
                        match=termino,
                        score=0.9,
                        fuente="json"
                    ))
                    break
        
        return evidencias
    
    def _extraer_snippet(self, texto: str, termino: str, contexto: int = 150) -> str:
        """Extrae snippet alrededor del término"""
        texto_lower = texto.lower()
        termino_lower = termino.lower()
        
        pos = texto_lower.find(termino_lower)
        if pos == -1:
            return ""
        
        start = max(0, pos - contexto)
        end = min(len(texto), pos + len(termino) + contexto)
        
        snippet = texto[start:end].strip()
        snippet = re.sub(r'\s+', ' ', snippet)
        
        if len(snippet) > MAX_SNIPPET_LENGTH:
            snippet = snippet[:MAX_SNIPPET_LENGTH] + "..."
        
        return snippet
    
    def _deduplicar_evidencias(self, evidencias: List[Evidencia]) -> List[Evidencia]:
        """Elimina evidencias duplicadas"""
        vistos = set()
        unicas = []
        
        for ev in evidencias:
            key = (ev.archivo, ev.pagina, ev.snippet[:50])
            if key not in vistos:
                vistos.add(key)
                unicas.append(ev)
        
        return unicas
    
    # =========================================================================
    # RESPONDER
    # =========================================================================
    
    def preguntar(self, pregunta: str) -> RespuestaAsistente:
        """
        Procesa una pregunta con estándar probatorio.
        
        Args:
            pregunta: Pregunta del usuario
            
        Returns:
            RespuestaAsistente con evidencias
        """
        import time
        inicio = time.time()
        
        # Verificar que hay documentos
        if not self.documentos_pdf and not self.expediente_json:
            return RespuestaAsistente(
                texto="⚠️ No hay documentos cargados. Use --pdf o --carpeta para cargar documentos.",
                evidencias=[],
                tiene_sustento=False
            )
        
        # Agregar a memoria
        self._agregar_memoria(pregunta)
        
        # PASO 1: Retrieval determinístico (SIEMPRE igual en ambos modos)
        evidencias = self.retrieval(pregunta)
        
        # PASO 2: Si no hay evidencias, responder que no consta
        if not evidencias:
            tiempo = time.time() - inicio
            # En modo conversacional, usar mensaje específico
            if self.modo == MODO_CONVERSACIONAL:
                texto = MENSAJE_NO_CONSTA
            else:
                texto = self._formato_no_consta(pregunta)
            return RespuestaAsistente(
                texto=texto,
                evidencias=[],
                tiene_sustento=False,
                backend_usado=self.backend,
                tiempo_respuesta=tiempo
            )
        
        # PASO 3: Generar respuesta según modo
        if self.modo == MODO_CONVERSACIONAL:
            # Modo conversacional: primero obtener resultado técnico, luego reformular
            respuesta = self._responder_modo_conversacional(pregunta, evidencias)
        elif self.usando_llm:
            respuesta = self._responder_con_llm(pregunta, evidencias)
        else:
            respuesta = self._responder_con_regex(pregunta, evidencias)
        
        respuesta.tiempo_respuesta = time.time() - inicio
        return respuesta
    
    def _agregar_memoria(self, pregunta: str):
        """Agrega pregunta a la memoria (máximo 5 turnos)"""
        turno = TurnoConversacion(
            pregunta=pregunta,
            timestamp=datetime.now().isoformat()
        )
        self.memoria.append(turno)
        
        # Mantener solo últimos N turnos
        if len(self.memoria) > MAX_MEMORIA_TURNOS:
            self.memoria = self.memoria[-MAX_MEMORIA_TURNOS:]
    
    def _formato_no_consta(self, pregunta: str) -> str:
        """Formato de respuesta cuando no hay evidencia"""
        texto = f"{MENSAJE_NO_CONSTA}\n\n"
        texto += f"📋 Documentos consultados: {len(self.documentos_pdf)} PDFs"
        if self.expediente_json:
            texto += f", 1 expediente JSON"
        texto += f"\n💡 Sugerencia: Reformule la pregunta con términos más específicos."
        return texto
    
    def _responder_con_regex(self, pregunta: str, evidencias: List[Evidencia]) -> RespuestaAsistente:
        """Genera respuesta sin LLM (solo evidencias)"""
        lineas = [f"📚 **Información encontrada:**\n"]
        
        for i, ev in enumerate(evidencias[:5], 1):
            lineas.append(f"---")
            lineas.append(f"**[{i}] {ev.archivo}** - Pág. {ev.pagina}")
            lineas.append(f"📝 \"{ev.snippet}\"")
            lineas.append("")
        
        lineas.append(f"---")
        lineas.append(f"📊 {len(evidencias)} referencia(s) encontrada(s)")
        
        return RespuestaAsistente(
            texto="\n".join(lineas),
            evidencias=evidencias,
            tiene_sustento=True,
            backend_usado="regex"
        )
    
    def _responder_con_llm(self, pregunta: str, evidencias: List[Evidencia]) -> RespuestaAsistente:
        """Genera respuesta usando LLM"""
        # Construir contexto con evidencias
        contexto = "CONTEXTO (información de los documentos):\n\n"
        for i, ev in enumerate(evidencias, 1):
            if ev.fuente == "pdf":
                contexto += f"[{i}] Archivo: {ev.archivo}, Página: {ev.pagina}\n"
            else:
                contexto += f"[{i}] Fuente: Expediente JSON\n"
            contexto += f"    Texto: \"{ev.snippet}\"\n\n"
        
        # Incluir memoria si hay turnos previos
        memoria_texto = ""
        if len(self.memoria) > 1:
            memoria_texto = "\nPREGUNTAS PREVIAS DEL USUARIO (solo referencia, NO inferir):\n"
            for turno in self.memoria[:-1]:
                memoria_texto += f"- {turno.pregunta}\n"
        
        prompt = f"""{contexto}
{memoria_texto}
PREGUNTA ACTUAL: {pregunta}

INSTRUCCIONES:
1. Responde SOLO con información del CONTEXTO proporcionado.
2. Respuesta breve (2-5 líneas).
3. AL FINAL, CITA las fuentes así: 📄 Fuente: [archivo], pág. [N]: "[snippet corto]"
4. Si no hay información suficiente: "{MENSAJE_NO_CONSTA}"
"""
        
        try:
            respuesta_llm = self.llm_client.ask(prompt, SYSTEM_PROMPT_ASISTENTE)
            
            # Validar que cite fuentes
            if not self._validar_respuesta(respuesta_llm, evidencias):
                # Si no cita, agregar citas automáticamente
                respuesta_llm = self._agregar_citas(respuesta_llm, evidencias)
            
            return RespuestaAsistente(
                texto=respuesta_llm,
                evidencias=evidencias,
                tiene_sustento=True,
                backend_usado="llm"
            )
            
        except Exception as e:
            logger.error(f"Error en LLM: {e}")
            return self._responder_con_regex(pregunta, evidencias)
    
    def _validar_respuesta(self, respuesta: str, evidencias: List[Evidencia]) -> bool:
        """Valida que la respuesta cite fuentes"""
        if MENSAJE_NO_CONSTA.lower() in respuesta.lower():
            return True
        
        # Verificar patrones de citación
        patrones_cita = ['fuente:', 'archivo:', 'pág.', 'página:', '📄']
        tiene_cita = any(p in respuesta.lower() for p in patrones_cita)
        
        # Verificar que mencione algún archivo
        menciona_archivo = any(ev.archivo.lower() in respuesta.lower() for ev in evidencias)
        
        return tiene_cita or menciona_archivo
    
    def _agregar_citas(self, respuesta: str, evidencias: List[Evidencia]) -> str:
        """Agrega citas a una respuesta que no las tiene"""
        citas = "\n\n📎 **Fuentes:**"
        for ev in evidencias[:3]:
            snippet_corto = ev.snippet[:80] + "..." if len(ev.snippet) > 80 else ev.snippet
            citas += f"\n📄 {ev.archivo}, pág. {ev.pagina}: \"{snippet_corto}\""
        
        return respuesta + citas
    
    # =========================================================================
    # MODO CONVERSACIONAL
    # =========================================================================
    
    def _responder_modo_conversacional(self, pregunta: str, evidencias: List[Evidencia]) -> RespuestaAsistente:
        """
        Genera respuesta en modo conversacional.
        
        Flujo:
        1. Construir resultado técnico estructurado con las evidencias
        2. Enviar al LLM SOLO para reformular en lenguaje administrativo
        3. Validar que el LLM mantiene las citas
        4. Si el LLM no está disponible, usar formato técnico mejorado
        
        Args:
            pregunta: Pregunta del usuario
            evidencias: Lista de evidencias del retrieval
            
        Returns:
            RespuestaAsistente con texto reformulado
        """
        # PASO 1: Construir resultado técnico estructurado
        resultado_tecnico = self._construir_resultado_tecnico(pregunta, evidencias)
        
        # PASO 2: Si hay LLM disponible, reformular
        if self.usando_llm:
            try:
                respuesta_reformulada = self._reformular_con_llm(pregunta, resultado_tecnico, evidencias)
                
                # VALIDAR REGLA ANTI-ERROR DE NUMERALES
                respuesta_reformulada = self._validar_numeracion_en_snippet(respuesta_reformulada, evidencias)
                
                # Validar que mantiene citas
                if self._validar_citas_mantenidas(respuesta_reformulada, evidencias):
                    return RespuestaAsistente(
                        texto=respuesta_reformulada,
                        evidencias=evidencias,
                        tiene_sustento=True,
                        backend_usado="llm-conversacional"
                    )
                else:
                    # Si no mantiene citas, agregar automáticamente
                    respuesta_reformulada = self._agregar_citas(respuesta_reformulada, evidencias)
                    return RespuestaAsistente(
                        texto=respuesta_reformulada,
                        evidencias=evidencias,
                        tiene_sustento=True,
                        backend_usado="llm-conversacional"
                    )
            except Exception as e:
                logger.warning(f"Error en reformulación LLM: {e}")
                # Fallback a formato técnico mejorado
        
        # PASO 3: Sin LLM, usar formato técnico mejorado
        return RespuestaAsistente(
            texto=self._formato_tecnico_legible(pregunta, evidencias),
            evidencias=evidencias,
            tiene_sustento=True,
            backend_usado="regex-conversacional"
        )
    
    def _construir_resultado_tecnico(self, pregunta: str, evidencias: List[Evidencia]) -> str:
        """
        Construye un resultado técnico estructurado para el LLM.
        
        El LLM SOLO puede usar esta información, nada más.
        """
        resultado = "RESULTADO DEL ANÁLISIS TÉCNICO:\n"
        resultado += "=" * 50 + "\n\n"
        resultado += f"CONSULTA: {pregunta}\n\n"
        resultado += f"EVIDENCIAS ENCONTRADAS ({len(evidencias)}):\n\n"
        
        for i, ev in enumerate(evidencias, 1):
            resultado += f"[{i}] ARCHIVO: {ev.archivo}\n"
            resultado += f"    PÁGINA: {ev.pagina}\n"
            resultado += f"    TEXTO LITERAL: \"{ev.snippet}\"\n"
            resultado += f"    FUENTE: {ev.fuente.upper()}\n\n"
        
        resultado += "=" * 50 + "\n"
        resultado += "FIN DEL RESULTADO TÉCNICO\n"
        
        return resultado
    
    def _reformular_con_llm(self, pregunta: str, resultado_tecnico: str, evidencias: List[Evidencia]) -> str:
        """
        Envía el resultado técnico al LLM para reformulación.
        
        El LLM SOLO puede reformular, NO puede agregar información.
        """
        # Construir lista de archivos/páginas obligatorias
        citas_obligatorias = ", ".join([f"{ev.archivo} pág.{ev.pagina}" for ev in evidencias[:5]])
        
        prompt = f"""
{resultado_tecnico}

TAREA: Reformula el resultado técnico en lenguaje administrativo claro.

PREGUNTA ORIGINAL: {pregunta}

INSTRUCCIONES ESTRICTAS:
1. USA SOLO la información del RESULTADO TÉCNICO anterior.
2. PROHIBIDO inventar o agregar datos que no estén arriba.
3. OBLIGATORIO citar al menos: {citas_obligatorias}
4. Redacta 2-4 párrafos en lenguaje formal administrativo.
5. Al final, lista las fuentes con formato: 📄 [archivo], pág. [N]

Si el usuario pide "texto para devolver al área", redacta un oficio/memorando formal.
"""
        
        respuesta = self.llm_client.ask(prompt, SYSTEM_PROMPT_CONVERSACIONAL)
        return respuesta
    
    def _validar_citas_mantenidas(self, respuesta: str, evidencias: List[Evidencia]) -> bool:
        """Valida que la respuesta mantenga las citas de evidencias"""
        respuesta_lower = respuesta.lower()
        
        # Debe mencionar al menos un archivo
        menciona_archivo = any(
            ev.archivo.lower() in respuesta_lower or 
            ev.archivo.replace(".pdf", "").lower() in respuesta_lower
            for ev in evidencias
        )
        
        # Debe tener indicadores de citación
        tiene_indicador = any(
            ind in respuesta_lower 
            for ind in ['pág', 'página', 'fuente', '📄', 'archivo']
        )
        
        return menciona_archivo or tiene_indicador
    
    def _formato_tecnico_legible(self, pregunta: str, evidencias: List[Evidencia]) -> str:
        """Formato técnico mejorado cuando no hay LLM"""
        lineas = []
        lineas.append("📋 **Información relevante encontrada:**\n")
        
        for i, ev in enumerate(evidencias[:5], 1):
            lineas.append(f"**{i}. {ev.archivo}** (pág. {ev.pagina})")
            # Limpiar snippet para mejor lectura
            snippet_limpio = ev.snippet.replace('\n', ' ').strip()
            if len(snippet_limpio) > 200:
                snippet_limpio = snippet_limpio[:200] + "..."
            lineas.append(f"   > \"{snippet_limpio}\"")
            lineas.append("")
        
        lineas.append("─" * 50)
        lineas.append("\n📄 **Fuentes:**")
        for ev in evidencias[:5]:
            lineas.append(f"   • {ev.archivo}, pág. {ev.pagina}")
        
        return "\n".join(lineas)
    
    def _validar_numeracion_en_snippet(self, respuesta: str, evidencias: List[Evidencia]) -> str:
        """
        Valida que la respuesta no mencione numeración que no esté en los snippets.
        Si menciona Artículo/Numeral sin que esté en el snippet, lo corrige.
        """
        import re
        
        # Recopilar todo el texto de los snippets
        texto_snippets = " ".join(ev.snippet.lower() for ev in evidencias)
        
        # Buscar menciones de numeración en la respuesta
        patrones_numeracion = [
            r'artículo\s+\d+',
            r'art\.\s*\d+',
            r'numeral\s+[\d\.]+',
            r'inciso\s+[a-z\d]+',
            r'literal\s+[a-z]',
        ]
        
        respuesta_validada = respuesta
        for patron in patrones_numeracion:
            matches = re.findall(patron, respuesta.lower())
            for match in matches:
                # Si la numeración no está en los snippets, reemplazar
                if match not in texto_snippets:
                    # Reemplazar con frase genérica
                    respuesta_validada = re.sub(
                        patron, 
                        "según lo establecido en el documento", 
                        respuesta_validada, 
                        flags=re.IGNORECASE,
                        count=1
                    )
        
        return respuesta_validada
    
    # =========================================================================
    # COMANDOS DE PRODUCTIVIDAD
    # =========================================================================
    
    def comando_resumen(self) -> str:
        """
        Genera resumen de 5 líneas del expediente actual.
        Requiere expediente_json cargado.
        """
        if not self.expediente_json:
            return "⚠️ No hay expediente JSON cargado. Use --expediente_json para cargar uno."
        
        lineas = ["📋 **RESUMEN DEL EXPEDIENTE**\n"]
        
        # Metadata
        meta = self.expediente_json.get('metadata', {})
        sinad = meta.get('expediente_sinad', 'N/A')
        fecha = meta.get('fecha_analisis', 'N/A')
        decision = self.expediente_json.get('decision', {})
        resultado = decision.get('resultado', 'N/A')
        
        lineas.append(f"• SINAD: {sinad}")
        lineas.append(f"• Fecha análisis: {fecha}")
        lineas.append(f"• Decisión: **{resultado}**")
        
        # Contar observaciones
        hallazgos = self.hallazgos_json
        criticas = sum(1 for h in hallazgos if h.get('severidad', '').upper() == 'CRITICA')
        mayores = sum(1 for h in hallazgos if h.get('severidad', '').upper() == 'MAYOR')
        menores = sum(1 for h in hallazgos if h.get('severidad', '').upper() == 'MENOR')
        
        lineas.append(f"• Observaciones: {criticas} críticas, {mayores} mayores, {menores} menores")
        
        # Razón principal si no procede
        if resultado == "NO_PROCEDE" and criticas > 0:
            primera_critica = next((h for h in hallazgos if h.get('severidad', '').upper() == 'CRITICA'), None)
            if primera_critica:
                lineas.append(f"• Razón principal: {primera_critica.get('hallazgo', 'N/A')[:60]}...")
        
        return "\n".join(lineas[:6])  # Máximo 5 líneas + header
    
    def comando_devolver(self) -> str:
        """
        Genera texto formal para devolver al área usuaria (3-6 líneas) + citas.
        """
        if not self.expediente_json:
            return "⚠️ No hay expediente JSON cargado."
        
        meta = self.expediente_json.get('metadata', {})
        sinad = meta.get('expediente_sinad', 'N/A')
        decision = self.expediente_json.get('decision', {})
        resultado = decision.get('resultado', 'N/A')
        
        hallazgos = self.hallazgos_json
        criticas = [h for h in hallazgos if h.get('severidad', '').upper() == 'CRITICA']
        
        lineas = ["📤 **TEXTO PARA DEVOLUCIÓN AL ÁREA USUARIA**\n"]
        lineas.append("─" * 50)
        
        if resultado == "NO_PROCEDE":
            lineas.append(f'"Se devuelve el expediente SINAD N° {sinad}, debido a que')
            if criticas:
                motivos = [h.get('hallazgo', '')[:50] for h in criticas[:2]]
                lineas.append(f'se han identificado observaciones críticas: {"; ".join(motivos)}.')
            lineas.append('Se requiere subsanar las observaciones señaladas antes de continuar')
            lineas.append('con el trámite correspondiente."')
        elif resultado == "PROCEDE_CON_OBSERVACIONES":
            lineas.append(f'"El expediente SINAD N° {sinad} PROCEDE CON OBSERVACIONES.')
            lineas.append('Se recomienda que el área usuaria tome nota de las observaciones')
            lineas.append('menores identificadas para futuros trámites similares."')
        else:
            lineas.append(f'"El expediente SINAD N° {sinad} PROCEDE sin observaciones críticas."')
        
        lineas.append("─" * 50)
        
        # Agregar citas de evidencia
        if criticas:
            lineas.append("\n📄 **Sustento documental:**")
            for h in criticas[:3]:
                evidencia = h.get('evidencia', {})
                archivo = evidencia.get('archivo', 'N/A')
                pagina = evidencia.get('pagina', 'N/A')
                lineas.append(f"   • {archivo}, pág. {pagina}")
        
        return "\n".join(lineas)
    
    def comando_subsanable(self) -> str:
        """
        Lista observaciones subsanables (bullets) + citas.
        """
        if not self.expediente_json:
            return "⚠️ No hay expediente JSON cargado."
        
        hallazgos = self.hallazgos_json
        
        # Filtrar observaciones subsanables (MAYOR y MENOR son típicamente subsanables)
        subsanables = [
            h for h in hallazgos 
            if h.get('severidad', '').upper() in ['MAYOR', 'MENOR', 'INCIERTO']
            or h.get('subsanable', True)
        ]
        
        if not subsanables:
            return "✅ No hay observaciones subsanables pendientes."
        
        lineas = [f"📝 **OBSERVACIONES SUBSANABLES ({len(subsanables)})**\n"]
        
        for i, h in enumerate(subsanables[:10], 1):
            severidad = h.get('severidad', 'N/A')
            hallazgo = h.get('hallazgo', 'N/A')[:60]
            evidencia = h.get('evidencia', {})
            archivo = evidencia.get('archivo', 'N/A')
            pagina = evidencia.get('pagina', 'N/A')
            
            lineas.append(f"  {i}. [{severidad}] {hallazgo}")
            lineas.append(f"     📄 {archivo}, pág. {pagina}")
        
        if len(subsanables) > 10:
            lineas.append(f"\n   ... y {len(subsanables) - 10} más")
        
        return "\n".join(lineas)
    
    def comando_evidencia(self, numero: int) -> str:
        """
        Muestra evidencia N completa (archivo, página, snippet).
        """
        if not self.hallazgos_json:
            return "⚠️ No hay hallazgos cargados."
        
        if numero < 1 or numero > len(self.hallazgos_json):
            return f"⚠️ Evidencia {numero} no existe. Rango válido: 1-{len(self.hallazgos_json)}"
        
        hallazgo = self.hallazgos_json[numero - 1]
        evidencia = hallazgo.get('evidencia', {})
        
        lineas = [f"🔍 **EVIDENCIA #{numero}**\n"]
        lineas.append("─" * 50)
        lineas.append(f"**Hallazgo:** {hallazgo.get('hallazgo', 'N/A')}")
        lineas.append(f"**Severidad:** {hallazgo.get('severidad', 'N/A')}")
        lineas.append(f"**Agente:** {hallazgo.get('agente', 'N/A')}")
        lineas.append("─" * 50)
        lineas.append(f"📄 **Archivo:** {evidencia.get('archivo', 'N/A')}")
        lineas.append(f"📑 **Página:** {evidencia.get('pagina', 'N/A')}")
        lineas.append(f"🔧 **Método:** {evidencia.get('metodo_extraccion', 'N/A')}")
        lineas.append(f"📊 **Confianza:** {evidencia.get('confianza', 'N/A')}")
        lineas.append("─" * 50)
        
        snippet = evidencia.get('snippet', evidencia.get('valor_detectado', 'N/A'))
        lineas.append(f"📝 **Snippet:**\n\"{snippet}\"")
        
        return "\n".join(lineas)


# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Chat Asistente - Consulta documentos con estándar probatorio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Ejemplos:
  python chat_asistente.py --backend llm
  python chat_asistente.py --carpeta {DEFAULT_DIRECTIVAS_DIR} --backend auto
  python chat_asistente.py --expediente_json output/informe.json --pdf directiva.pdf
  
Nota: Las rutas de carpeta pueden ser relativas al proyecto o absolutas.
Carpeta por defecto: {DEFAULT_DIRECTIVAS_DIR}
        """
    )
    
    parser.add_argument(
        "--pdf", "-p",
        action="append",
        default=[],
        help="Ruta a PDF (puede repetirse)"
    )
    
    parser.add_argument(
        "--carpeta", "-c",
        default=None,
        help=f"Carpeta con PDFs - relativa al proyecto o absoluta (default: {DEFAULT_DIRECTIVAS_DIR})"
    )
    
    parser.add_argument(
        "--expediente_json", "-j",
        help="JSON de expediente analizado"
    )
    
    parser.add_argument(
        "--backend", "-b",
        choices=["auto", "llm", "regex"],
        default="auto",
        help="Backend: auto (default), llm, regex"
    )
    
    parser.add_argument(
        "--modelo", "-m",
        help="Modelo específico de Ollama (opcional)"
    )
    
    parser.add_argument(
        "--modo",
        choices=["tecnico", "conversacional"],
        default="tecnico",
        help="Modo: tecnico (default) o conversacional (reformula en lenguaje administrativo)"
    )
    
    args = parser.parse_args()
    
    # Si no se especifica nada, usar carpeta por defecto
    usar_carpeta_default = not args.pdf and not args.carpeta and not args.expediente_json
    if usar_carpeta_default:
        args.carpeta = DEFAULT_DIRECTIVAS_DIR
        print(f"ℹ️  Usando carpeta por defecto: {DEFAULT_DIRECTIVAS_DIR}")
    
    # Crear asistente
    print()
    print("=" * 70)
    modo_label = "CONVERSACIONAL" if args.modo == "conversacional" else "TÉCNICO"
    print(f"🤖 CHAT ASISTENTE - ESTÁNDAR PROBATORIO [{modo_label}]")
    print("=" * 70)
    
    asistente = ChatAsistente(backend=args.backend, modelo=args.modelo, modo=args.modo)
    
    # Cargar documentos
    print()
    print("=" * 70)
    print("📂 CARGANDO DOCUMENTOS")
    print("=" * 70)
    
    total_cargados = 0
    
    # Cargar PDFs individuales
    for pdf in args.pdf:
        if asistente.cargar_pdf(pdf):
            total_cargados += 1
    
    # Cargar carpeta (con mejor logging)
    if args.carpeta:
        cargados, rutas = asistente.cargar_carpeta(args.carpeta, recursivo=True)
        total_cargados += cargados
        
        # VALIDACIÓN CRÍTICA: Si N = 0, error y salir
        if cargados == 0:
            print()
            print("=" * 70)
            print("❌ ERROR: No se encontraron PDFs en la carpeta especificada")
            print("=" * 70)
            print(f"   Carpeta: {args.carpeta}")
            print()
            print("   Posibles causas:")
            print("   1. La carpeta está vacía")
            print("   2. No hay archivos .pdf/.PDF")
            print("   3. Todos los PDFs tienen 0 bytes")
            print()
            print("   Solución:")
            print("   - Copie los PDFs de directivas a la carpeta")
            print(f"   - Ubicación esperada: {PROJECT_ROOT / args.carpeta}")
            print()
            sys.exit(1)
    
    # Cargar JSON de expediente
    if args.expediente_json:
        asistente.cargar_expediente_json(args.expediente_json)
    
    # Mostrar información
    info = asistente.get_info()
    
    print()
    print("─" * 70)
    print("📊 RESUMEN DE CARGA")
    print("─" * 70)
    print(f"🔧 Backend efectivo: {info['backend'].upper()}")
    if info['modelo']:
        print(f"🧠 Modelo: {info['modelo']}")
    print(f"🎯 Modo: {info['modo'].upper()}")
    print(f"📄 PDFs cargados: {info['pdfs_cargados']} ({info['paginas_totales']} páginas)")
    if info['expediente_json']:
        print(f"📋 Expediente JSON: Sí ({info['hallazgos_json']} hallazgos)")
    
    if info['pdfs_cargados'] == 0 and not info['expediente_json']:
        print()
        print("❌ ERROR: No se cargaron documentos. Verifique las rutas.")
        print("   Estándar probatorio exige documentos para responder.")
        sys.exit(1)
    
    # Loop de chat
    print()
    print("=" * 70)
    if args.modo == "conversacional":
        print("💬 CHAT ASISTENTE - MODO CONVERSACIONAL")
        print("   Respuestas en lenguaje administrativo formal")
    else:
        print("💬 CHAT ASISTENTE - MODO TÉCNICO")
        print("   Respuestas con evidencias directas")
    print("=" * 70)
    print("   Escribe tu pregunta (o 'exit' para salir)")
    print()
    print("   📌 Comandos rápidos:")
    print("      info | memoria | modo | exit")
    print("      resumen | devolver | subsanable | evidencia N")
    print()
    print("   Política: Solo respuestas con evidencia documental")
    print("─" * 70)
    
    while True:
        try:
            entrada = input("\n🧑 Tú: ").strip()
            
            if not entrada:
                continue
            
            if entrada.lower() in ["exit", "salir", "q"]:
                print("\n👋 ¡Hasta luego!")
                break
            
            if entrada.lower() == "info":
                info = asistente.get_info()
                print(f"\n📊 Backend: {info['backend']}, PDFs: {info['pdfs_cargados']}, Memoria: {info['turnos_memoria']} turnos")
                continue
            
            if entrada.lower() == "memoria":
                print("\n📝 Memoria de conversación:")
                for i, turno in enumerate(asistente.memoria, 1):
                    print(f"   {i}. {turno.pregunta[:60]}...")
                continue
            
            if entrada.lower() == "modo":
                # Alternar modo
                if asistente.modo == MODO_TECNICO:
                    asistente.modo = MODO_CONVERSACIONAL
                    print("\n🔄 Cambiado a MODO CONVERSACIONAL")
                    print("   Las respuestas se reformularán en lenguaje administrativo.")
                else:
                    asistente.modo = MODO_TECNICO
                    print("\n🔄 Cambiado a MODO TÉCNICO")
                    print("   Las respuestas mostrarán evidencias directas.")
                continue
            
            # ─────────────────────────────────────────────────────────────
            # COMANDOS DE PRODUCTIVIDAD
            # ─────────────────────────────────────────────────────────────
            
            if entrada.lower() == "resumen":
                print(f"\n{asistente.comando_resumen()}")
                continue
            
            if entrada.lower() == "devolver":
                print(f"\n{asistente.comando_devolver()}")
                continue
            
            if entrada.lower() == "subsanable":
                print(f"\n{asistente.comando_subsanable()}")
                continue
            
            # Comando "evidencia N"
            if entrada.lower().startswith("evidencia"):
                import re
                match = re.match(r'evidencia\s+(\d+)', entrada.lower())
                if match:
                    num = int(match.group(1))
                    print(f"\n{asistente.comando_evidencia(num)}")
                else:
                    print("\n⚠️ Uso: evidencia <número>  (ej: evidencia 1)")
                continue
            
            if entrada.lower() == "ayuda" or entrada.lower() == "help":
                print("\n📖 **COMANDOS DISPONIBLES:**")
                print("   resumen     - Resumen de 5 líneas del expediente")
                print("   devolver    - Texto para devolver al área usuaria")
                print("   subsanable  - Lista observaciones subsanables")
                print("   evidencia N - Muestra evidencia N completa")
                print("   info        - Información del sistema")
                print("   memoria     - Historial de preguntas")
                print("   modo        - Alternar técnico/conversacional")
                print("   exit        - Salir del chat")
                continue
            
            # Procesar pregunta
            respuesta = asistente.preguntar(entrada)
            
            print(f"\n🤖 Asistente [{respuesta.backend_usado.upper()}]:")
            print(respuesta.texto)
            
            if respuesta.tiene_sustento:
                print(f"\n   ⏱️ {respuesta.tiempo_respuesta:.2f}s | 📎 {len(respuesta.evidencias)} fuente(s)")
            
        except KeyboardInterrupt:
            print("\n\n👋 ¡Hasta luego!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()


