	# -*- coding: utf-8 -*-
"""
CLIENTE LLM LOCAL (Ollama) - ESTÁNDAR PROBATORIO ESTRICTO
=========================================================
Módulo para interactuar con modelos LLM locales via Ollama.

POLÍTICA ANTI-ALUCINACIÓN:
- El LLM solo reformula texto del JSON probatorio
- NO inventa, infiere ni interpreta información
- Si no hay evidencia, retorna mensaje estándar de insuficiencia
- Toda respuesta debe citar: archivo, página, snippet

USO:
    from utils.llm_local import LocalLLMClient
    
    client = LocalLLMClient()
    if client.disponible:
        respuesta = client.ask_with_context(pregunta, json_data)
"""

import json
import logging
import urllib.request
import urllib.error
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# =============================================================================
# POLÍTICA ANTI-ALUCINACIÓN (NO NEGOCIABLE)
# =============================================================================

ANTI_HALLUCINATION_POLICY = """
REGLAS ESTRICTAS (OBLIGATORIAS):

1. SOLO puedes responder con información LITERAL del JSON proporcionado.
2. PROHIBIDO usar conocimiento externo, sentido común o inferencias.
3. PROHIBIDO inventar, completar o interpretar datos no presentes.
4. Si la pregunta NO puede responderse con evidencia del JSON, responde EXACTAMENTE:
   "No consta información suficiente en el expediente analizado."

5. TODA respuesta válida DEBE incluir:
   - Número de observación
   - Severidad (CRÍTICA/MAYOR/MENOR)
   - Impacto (bloquea pago o no)
   - Archivo (nombre exacto)
   - Página (número)
   - Texto (snippet literal del documento)

6. Si falta cualquiera de esos elementos, NO emitir respuesta.

7. FORMATO OBLIGATORIO de respuesta:
   Observación: N°X
   Severidad: [CRÍTICA/MAYOR/MENOR]
   Impacto: [Bloquea pago / No bloquea]
   Evidencia:
   - Archivo: <nombre exacto>
   - Página: <número>
   - Texto: "<snippet literal>"

8. PREGUNTAS PROHIBIDAS (responder con insuficiencia):
   - Opiniones personales
   - Interpretaciones subjetivas
   - Predicciones o suposiciones
   - Cualquier cosa que requiera inferencia
"""

MENSAJE_INSUFICIENCIA = "No consta información suficiente en el expediente analizado."

SYSTEM_PROMPT_ESTRICTO = f"""Eres un asistente de Control Previo del sector público peruano.
Tu rol es responder preguntas sobre expedientes administrativos CON ESTÁNDAR PROBATORIO.

{ANTI_HALLUCINATION_POLICY}

IMPORTANTE:
- NO uses frases como "según mi análisis", "creo que", "posiblemente"
- SOLO cita información literal del JSON
- Si dudas, responde: "{MENSAJE_INSUFICIENCIA}"
"""


@dataclass
class ModeloInfo:
    """Información de un modelo disponible en Ollama"""
    nombre: str
    tamaño: str
    modificado: str
    familia: str = ""


@dataclass
class RespuestaLLM:
    """Respuesta validada del LLM"""
    texto: str
    tiene_evidencia: bool
    archivos_citados: List[str]
    paginas_citadas: List[int]
    es_valida: bool
    razon_invalida: str = ""


class LocalLLMClient:
    """
    Cliente para LLM local via Ollama con política anti-alucinación.
    
    El LLM solo puede reformular información del JSON probatorio.
    NO puede inventar, inferir ni interpretar datos.
    """
    
    BASE_URL = "http://localhost:11434"
    
    MODELOS_PREFERIDOS = [
        "qwen3:32b",
        "llama3.2:3b",
        "llama3.1:8b",
        "mistral:7b",
    ]
    
    TIMEOUT_CONEXION = 5
    TIMEOUT_GENERACION = 120
    
    def __init__(self, modelo: str = None, base_url: str = None):
        self.base_url = base_url or self.BASE_URL
        self.modelo_seleccionado: Optional[str] = modelo
        self.modelos_disponibles: List[ModeloInfo] = []
        self._disponible: Optional[bool] = None
        self._verificar_disponibilidad()
    
    @property
    def disponible(self) -> bool:
        if self._disponible is None:
            self._verificar_disponibilidad()
        return self._disponible
    
    @property
    def modelo(self) -> Optional[str]:
        return self.modelo_seleccionado
    
    def _verificar_disponibilidad(self) -> bool:
        try:
            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url, method='GET')
            
            with urllib.request.urlopen(req, timeout=self.TIMEOUT_CONEXION) as response:
                data = json.loads(response.read().decode('utf-8'))
                
                self.modelos_disponibles = []
                for m in data.get("models", []):
                    nombre = m.get("name", "")
                    familia = nombre.split(":")[0] if ":" in nombre else nombre
                    
                    self.modelos_disponibles.append(ModeloInfo(
                        nombre=nombre,
                        tamaño=self._formatear_tamaño(m.get("size", 0)),
                        modificado=m.get("modified_at", ""),
                        familia=familia
                    ))
                
                if not self.modelo_seleccionado and self.modelos_disponibles:
                    self.modelo_seleccionado = self._seleccionar_mejor_modelo()
                
                self._disponible = bool(self.modelo_seleccionado)
                return self._disponible
                
        except Exception as e:
            logger.debug(f"Ollama no disponible: {e}")
            self._disponible = False
            return False
    
    def _formatear_tamaño(self, bytes_size: int) -> str:
        if bytes_size < 1024 * 1024 * 1024:
            return f"{bytes_size / (1024 * 1024):.1f} MB"
        return f"{bytes_size / (1024 * 1024 * 1024):.1f} GB"
    
    def _seleccionar_mejor_modelo(self) -> Optional[str]:
        nombres_disponibles = [m.nombre for m in self.modelos_disponibles]
        
        for preferido in self.MODELOS_PREFERIDOS:
            if preferido in nombres_disponibles:
                return preferido
            familia = preferido.split(":")[0]
            for nombre in nombres_disponibles:
                if nombre.startswith(familia):
                    return nombre
        
        return nombres_disponibles[0] if nombres_disponibles else None
    
    def listar_modelos(self) -> List[str]:
        return [m.nombre for m in self.modelos_disponibles]
    
    def ask(self, prompt: str, system_prompt: str = None, temperature: float = 0.1) -> str:
        """Envía un prompt al LLM (uso interno)"""
        if not self.disponible:
            raise RuntimeError("Ollama no está disponible")
        
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
        
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.modelo_seleccionado,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 1500,
            }
        }
        
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url, data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=self.TIMEOUT_GENERACION) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result.get("response", "").strip()
                
        except Exception as e:
            logger.error(f"Error en LLM: {e}")
            raise RuntimeError(f"Error generando respuesta: {e}")
    
    def ask_with_context_strict(self, 
                                 pregunta: str, 
                                 contexto_json: Dict[str, Any]) -> RespuestaLLM:
        """
        Pregunta al LLM con ESTÁNDAR PROBATORIO ESTRICTO.
        
        - Valida que la respuesta cite evidencia
        - Si no hay evidencia, retorna mensaje de insuficiencia
        - Descarta respuestas sin archivo/página
        """
        # Verificar si la pregunta es prohibida
        if self._es_pregunta_prohibida(pregunta):
            return RespuestaLLM(
                texto=MENSAJE_INSUFICIENCIA,
                tiene_evidencia=False,
                archivos_citados=[],
                paginas_citadas=[],
                es_valida=True,
                razon_invalida="Pregunta requiere interpretación subjetiva"
            )
        
        hallazgos = contexto_json.get("hallazgos", [])
        
        # Si no hay hallazgos, no hay evidencia
        if not hallazgos:
            return RespuestaLLM(
                texto=MENSAJE_INSUFICIENCIA,
                tiene_evidencia=False,
                archivos_citados=[],
                paginas_citadas=[],
                es_valida=True,
                razon_invalida="No hay hallazgos en el JSON"
            )
        
        # Formatear hallazgos para el prompt
        hallazgos_texto = self._formatear_hallazgos_estricto(hallazgos)
        metadata = contexto_json.get("metadata", {})
        decision = contexto_json.get("decision", {})
        
        user_prompt = f"""DATOS DEL EXPEDIENTE (ÚNICOS DATOS PERMITIDOS):
- SINAD: {metadata.get('expediente_sinad', 'N/A')}
- Decisión: {decision.get('resultado', 'N/A')}
- Total observaciones: {len(hallazgos)}

HALLAZGOS CON EVIDENCIA:
{hallazgos_texto}

PREGUNTA:
{pregunta}

INSTRUCCIÓN: Responde SOLO con información de los hallazgos anteriores.
USA OBLIGATORIAMENTE el formato:
Observación: N°X
Severidad: [valor]
Impacto: [valor]
Evidencia:
- Archivo: [nombre]
- Página: [número]
- Texto: "[snippet]"

Si no puedes llenar el formato completo, responde: "{MENSAJE_INSUFICIENCIA}"
"""
        
        try:
            respuesta_raw = self.ask(user_prompt, SYSTEM_PROMPT_ESTRICTO)
            
            # Validar respuesta
            return self._validar_respuesta_estricta(respuesta_raw, hallazgos)
            
        except Exception as e:
            logger.error(f"Error en LLM: {e}")
            return RespuestaLLM(
                texto=MENSAJE_INSUFICIENCIA,
                tiene_evidencia=False,
                archivos_citados=[],
                paginas_citadas=[],
                es_valida=False,
                razon_invalida=f"Error LLM: {e}"
            )
    
    def _es_pregunta_prohibida(self, pregunta: str) -> bool:
        """Detecta preguntas que requieren interpretación subjetiva"""
        pregunta_lower = pregunta.lower()
        
        patrones_prohibidos = [
            r"qu[eé]\s*opinas",
            r"qu[eé]\s*har[ií]as",
            r"qu[eé]\s*crees",
            r"qu[eé]\s*piensas",
            r"est[aá]\s*bien\s*o\s*mal",
            r"qu[eé]\s*quiso\s*decir",
            r"por\s*qu[eé]\s*crees",
            r"tu\s*opini[oó]n",
            r"qu[eé]\s*recomiendas\s*t[uú]",
            r"deber[ií]a\s*(yo|hacer)",
        ]
        
        for patron in patrones_prohibidos:
            if re.search(patron, pregunta_lower):
                return True
        
        return False
    
    def _formatear_hallazgos_estricto(self, hallazgos: List[Dict]) -> str:
        """Formatea hallazgos con toda la evidencia disponible"""
        if not hallazgos:
            return "No hay hallazgos."
        
        lineas = []
        for i, h in enumerate(hallazgos, 1):
            severidad = h.get("severidad", "N/A")
            tipo = h.get("tipo", "N/A")
            descripcion = h.get("hallazgo", "N/A")
            impacto = h.get("impacto", "N/A")
            bloquea = "Bloquea pago" if h.get("bloquea_pago") else "No bloquea"
            
            lineas.append(f"[{i}] OBSERVACIÓN:")
            lineas.append(f"    Severidad: {severidad}")
            lineas.append(f"    Tipo: {tipo}")
            lineas.append(f"    Descripción: {descripcion}")
            lineas.append(f"    Impacto: {impacto}")
            lineas.append(f"    Bloquea pago: {bloquea}")
            
            evidencias = h.get("evidencias", [])
            if evidencias:
                lineas.append(f"    EVIDENCIAS:")
                for j, ev in enumerate(evidencias[:5], 1):
                    archivo = ev.get("archivo", "N/A")
                    pagina = ev.get("pagina", "N/A")
                    valor = ev.get("valor_detectado", "")
                    snippet = ev.get("snippet", "")[:150]
                    
                    lineas.append(f"      [{j}] Archivo: {archivo}")
                    lineas.append(f"          Página: {pagina}")
                    if valor:
                        lineas.append(f"          Valor: {valor}")
                    if snippet:
                        lineas.append(f"          Texto: \"{snippet}\"")
            else:
                lineas.append(f"    EVIDENCIAS: Sin evidencia detallada")
            
            lineas.append("")
        
        return "\n".join(lineas)
    
    def _validar_respuesta_estricta(self, respuesta: str, hallazgos: List[Dict]) -> RespuestaLLM:
        """
        Valida que la respuesta del LLM cumpla estándar probatorio.
        Si no cumple, la descarta.
        """
        # Si es mensaje de insuficiencia, es válido
        if MENSAJE_INSUFICIENCIA.lower() in respuesta.lower():
            return RespuestaLLM(
                texto=MENSAJE_INSUFICIENCIA,
                tiene_evidencia=False,
                archivos_citados=[],
                paginas_citadas=[],
                es_valida=True,
                razon_invalida=""
            )
        
        # Extraer archivos citados
        archivos_citados = []
        for h in hallazgos:
            for ev in h.get("evidencias", []):
                archivo = ev.get("archivo", "")
                if archivo and archivo in respuesta:
                    archivos_citados.append(archivo)
        
        # Extraer páginas citadas
        paginas_citadas = []
        paginas_match = re.findall(r'[Pp][aá]gina[:\s]*(\d+)|[Pp][aá]g\.?\s*(\d+)', respuesta)
        for match in paginas_match:
            num = match[0] or match[1]
            if num:
                paginas_citadas.append(int(num))
        
        # Verificar si tiene evidencia
        tiene_evidencia = bool(archivos_citados) and bool(paginas_citadas)
        
        # Verificar formato obligatorio
        tiene_formato = all([
            "observación" in respuesta.lower() or "observacion" in respuesta.lower(),
            "severidad" in respuesta.lower(),
            "archivo" in respuesta.lower(),
        ])
        
        if not tiene_evidencia:
            # Descartar respuesta y devolver insuficiencia
            return RespuestaLLM(
                texto=f"{MENSAJE_INSUFICIENCIA}\n\n[Respuesta descartada por falta de evidencia probatoria]",
                tiene_evidencia=False,
                archivos_citados=[],
                paginas_citadas=[],
                es_valida=False,
                razon_invalida="Respuesta sin archivo o página"
            )
        
        return RespuestaLLM(
            texto=respuesta,
            tiene_evidencia=True,
            archivos_citados=list(set(archivos_citados)),
            paginas_citadas=list(set(paginas_citadas)),
            es_valida=True,
            razon_invalida=""
        )


def verificar_ollama() -> Dict[str, Any]:
    """Verifica el estado de Ollama"""
    client = LocalLLMClient()
    return {
        "disponible": client.disponible,
        "modelos": client.listar_modelos(),
        "modelo_seleccionado": client.modelo,
        "url": client.base_url
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 60)
    print("VERIFICACIÓN DE OLLAMA - MODO ESTRICTO")
    print("=" * 60)
    
    info = verificar_ollama()
    
    if info["disponible"]:
        print(f"✅ Ollama DISPONIBLE")
        print(f"📦 Modelo: {info['modelo_seleccionado']}")
        print(f"📋 Modelos: {', '.join(info['modelos'])}")
    else:
        print("❌ Ollama NO disponible")
        print("\nPara instalar:")
        print("  1. https://ollama.ai/download")
        print("  2. ollama pull qwen3:32b")



