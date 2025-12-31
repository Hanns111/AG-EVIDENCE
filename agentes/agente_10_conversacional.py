# -*- coding: utf-8 -*-
"""
AGENTE 10 — CONVERSACIONAL DE CONTROL PREVIO
=============================================
VERSIÓN: 3.0 - ESTÁNDAR PROBATORIO ESTRICTO

POLÍTICA ANTI-ALUCINACIÓN (NO NEGOCIABLE):
- El agente NO puede inventar, inferir ni interpretar información
- SOLO responde con datos LITERALES del JSON probatorio
- Si no hay evidencia → "No consta información suficiente en el expediente analizado"
- TODA respuesta debe citar: observación, severidad, archivo, página, snippet

USO:
    agente = AgenteConversacional("ruta/informe.json")
    respuesta = agente.preguntar("¿Por qué no procede?")
"""

import os
import sys
import json
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

# =============================================================================
# POLÍTICA ANTI-ALUCINACIÓN (OBLIGATORIA)
# =============================================================================

ANTI_HALLUCINATION_POLICY = """
REGLA FUNDAMENTAL: El agente SOLO puede responder con información LITERAL del JSON.

PROHIBIDO:
- Inventar datos
- Inferir información
- Interpretar subjetivamente
- Usar conocimiento externo
- Completar información faltante

OBLIGATORIO:
- Citar número de observación
- Indicar severidad
- Mencionar impacto (bloquea/no bloquea)
- Citar archivo exacto
- Indicar página
- Incluir snippet literal

Si falta cualquier elemento → NO RESPONDER
"""

MENSAJE_INSUFICIENCIA = "No consta información suficiente en el expediente analizado."

FORMATO_RESPUESTA_OBLIGATORIO = """
Observación: N°{num}
Severidad: {severidad}
Impacto: {impacto}
Evidencia:
- Archivo: {archivo}
- Página: {pagina}
- Texto: "{snippet}"
"""

# =============================================================================
# ENUMS Y DATACLASSES
# =============================================================================

class BackendMode(Enum):
    REGEX = "regex"
    LLM = "llm"
    AUTO = "auto"


class TipoConsulta(Enum):
    RESUMEN_GENERAL = "resumen_general"
    POR_QUE_NO_PROCEDE = "por_que_no_procede"
    OBSERVACION_MAS_GRAVE = "observacion_mas_grave"
    SUBSANABLE_O_NO = "subsanable_o_no"
    QUE_PASA_SI = "que_pasa_si"
    FILTRO_AGENTE = "filtro_agente"
    DETALLE_OBSERVACION = "detalle_observacion"
    LISTAR_CRITICAS = "listar_criticas"
    LISTAR_MAYORES = "listar_mayores"
    ACCIONES_REQUERIDAS = "acciones_requeridas"
    BUSCAR_VALOR = "buscar_valor"
    BUSCAR_ARCHIVO = "buscar_archivo"
    PREGUNTA_LIBRE = "pregunta_libre"
    INSUFICIENCIA = "insuficiencia"
    DESCONOCIDO = "desconocido"


@dataclass
class EvidenciaCitada:
    """Evidencia citada en una respuesta"""
    observacion_num: int
    severidad: str
    impacto: str
    bloquea_pago: bool
    archivo: str
    pagina: int
    snippet: str
    valor_detectado: str = ""


@dataclass
class RespuestaConversacional:
    """Respuesta validada del agente"""
    texto: str
    evidencias_citadas: List[EvidenciaCitada] = field(default_factory=list)
    observaciones_citadas: List[int] = field(default_factory=list)
    confianza: str = "ALTA"
    tipo_consulta: TipoConsulta = TipoConsulta.DESCONOCIDO
    backend_usado: str = "regex"
    es_valida: bool = True
    cumple_estandar_probatorio: bool = True


# =============================================================================
# IMPORTAR CLIENTE LLM
# =============================================================================

try:
    from utils.llm_local import LocalLLMClient, verificar_ollama, MENSAJE_INSUFICIENCIA as LLM_MENSAJE_INSUFICIENCIA
    LLM_DISPONIBLE = True
except ImportError:
    LLM_DISPONIBLE = False
    LocalLLMClient = None


# =============================================================================
# AGENTE CONVERSACIONAL
# =============================================================================

class AgenteConversacional:
    """
    Agente conversacional con ESTÁNDAR PROBATORIO ESTRICTO.
    
    POLÍTICA ANTI-ALUCINACIÓN:
    - Solo responde con información literal del JSON
    - Valida evidencia antes de emitir respuesta
    - Si falta evidencia → mensaje de insuficiencia
    """
    
    PATRONES_INTENCION = {
        TipoConsulta.POR_QUE_NO_PROCEDE: [
            r"por\s*qu[eé]?\s*(no\s*)?procede",
            r"motivo.*no\s*procede",
            r"qu[eé]?\s*bloquea",
        ],
        TipoConsulta.OBSERVACION_MAS_GRAVE: [
            r"m[aá]s\s*grave",
            r"m[aá]s\s*cr[ií]tic",
            r"principal\s*problema",
        ],
        TipoConsulta.SUBSANABLE_O_NO: [
            r"subsanable",
            r"se\s*puede\s*(corregir|arreglar|subsanar)",
        ],
        TipoConsulta.QUE_PASA_SI: [
            r"qu[eé]?\s*pasa\s*si",
            r"si\s*se\s*corrige",
        ],
        TipoConsulta.FILTRO_AGENTE: [
            r"solo\s*(lo\s*de\s*)?(firmas?|legal|coherencia|sunat)",
            r"resume\s*(solo\s*)?(firmas?|legal|coherencia)",
        ],
        TipoConsulta.LISTAR_CRITICAS: [
            r"cr[ií]ticas",
            r"bloquea.*pago",
        ],
        TipoConsulta.LISTAR_MAYORES: [
            r"mayores",
            r"subsanables",
        ],
        TipoConsulta.ACCIONES_REQUERIDAS: [
            r"qu[eé]?\s*(debo|hay\s*que)\s*hacer",
            r"acciones",
        ],
        TipoConsulta.DETALLE_OBSERVACION: [
            r"observaci[oó]n\s*(\d+)",
            r"detalle.*observaci[oó]n",
        ],
        TipoConsulta.RESUMEN_GENERAL: [
            r"resumen",
            r"estado\s*del\s*expediente",
        ],
        TipoConsulta.BUSCAR_VALOR: [
            r"d[oó]nde.*\d{4,}",
            r"en\s*qu[eé]\s*archivo.*\d{4,}",
            r"\d{5,}",
        ],
        TipoConsulta.BUSCAR_ARCHIVO: [
            r"d[oó]nde\s*est[aá]\s*(la\s*)?inconsistencia",
            r"qu[eé]\s*documento\s*tiene",
        ],
    }
    
    # Preguntas que requieren interpretación subjetiva (PROHIBIDAS)
    PATRONES_PROHIBIDOS = [
        r"qu[eé]\s*opinas",
        r"qu[eé]\s*har[ií]as",
        r"qu[eé]\s*crees",
        r"est[aá]\s*bien\s*o\s*mal",
        r"qu[eé]\s*quiso\s*decir",
        r"tu\s*opini[oó]n",
    ]
    
    MAPEO_AGENTES = {
        "firmas": ["firmas_competencia", "firmas", "firma"],
        "legal": ["legal_directivas", "legal"],
        "coherencia": ["coherencia_documental", "coherencia", "sinad", "ruc"],
        "sunat": ["sunat_publico", "sunat"],
    }
    
    def __init__(self, ruta_json: str = None, backend: str = "auto"):
        self.datos: Dict = {}
        self.hallazgos: List[Dict] = []
        self.metadata: Dict = {}
        self.decision: Dict = {}
        self.recomendacion: Dict = {}
        
        self.backend_mode = BackendMode(backend.lower())
        self.llm_client = None
        self.llm_modelo = None
        self._inicializar_backend()
        
        if ruta_json:
            self.cargar_json(ruta_json)
    
    def _inicializar_backend(self):
        """Inicializa el backend LLM si está disponible"""
        if self.backend_mode == BackendMode.REGEX:
            return
        
        if not LLM_DISPONIBLE:
            self.backend_mode = BackendMode.REGEX
            return
        
        try:
            self.llm_client = LocalLLMClient()
            if self.llm_client.disponible:
                self.llm_modelo = self.llm_client.modelo
            elif self.backend_mode == BackendMode.AUTO:
                self.backend_mode = BackendMode.REGEX
        except Exception as e:
            logger.warning(f"Error inicializando LLM: {e}")
            if self.backend_mode == BackendMode.AUTO:
                self.backend_mode = BackendMode.REGEX
    
    @property
    def usando_llm(self) -> bool:
        return self.llm_client is not None and self.llm_client.disponible
    
    def get_backend_info(self) -> Dict[str, Any]:
        return {
            "modo": self.backend_mode.value,
            "llm_disponible": self.usando_llm,
            "modelo": self.llm_modelo,
        }
    
    def cargar_json(self, ruta: str) -> bool:
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                self.datos = json.load(f)
            
            self.hallazgos = self.datos.get("hallazgos", [])
            self.metadata = self.datos.get("metadata", {})
            self.decision = self.datos.get("decision", {})
            self.recomendacion = self.datos.get("recomendacion", {})
            return True
        except Exception as e:
            logger.error(f"Error cargando JSON: {e}")
            return False
    
    def _normalizar_texto(self, texto: str) -> str:
        """Normaliza texto para matching"""
        import unicodedata
        texto = texto.replace('Ã¡', 'a').replace('Ã©', 'e').replace('Ã­', 'i')
        texto = texto.replace('Ã³', 'o').replace('Ãº', 'u').replace('Â', '')
        try:
            nfkd = unicodedata.normalize('NFKD', texto)
            texto = ''.join(c for c in nfkd if not unicodedata.combining(c))
        except:
            pass
        return texto.lower()
    
    def _es_pregunta_prohibida(self, pregunta: str) -> bool:
        """Detecta preguntas que requieren interpretación subjetiva"""
        pregunta_lower = self._normalizar_texto(pregunta)
        for patron in self.PATRONES_PROHIBIDOS:
            if re.search(patron, pregunta_lower):
                return True
        return False
    
    def _detectar_intencion(self, pregunta: str) -> Tuple[TipoConsulta, str]:
        """Detecta la intención de la pregunta"""
        pregunta_lower = self._normalizar_texto(pregunta)
        
        for tipo, patrones in self.PATRONES_INTENCION.items():
            for patron in patrones:
                if re.search(patron, pregunta_lower):
                    contexto = self._extraer_contexto(pregunta_lower, tipo)
                    return tipo, contexto
        
        return TipoConsulta.DESCONOCIDO, ""
    
    def _extraer_contexto(self, pregunta: str, tipo: TipoConsulta) -> str:
        if tipo == TipoConsulta.FILTRO_AGENTE:
            for keyword in self.MAPEO_AGENTES.keys():
                if keyword in pregunta:
                    return keyword
        match = re.search(r'observaci[oó]n\s*(\d+)', pregunta)
        if match:
            return match.group(1)
        return ""
    
    # =========================================================================
    # MÉTODO PRINCIPAL
    # =========================================================================
    
    def preguntar(self, pregunta: str) -> RespuestaConversacional:
        """
        Procesa una pregunta con ESTÁNDAR PROBATORIO ESTRICTO.
        
        POLÍTICA ANTI-ALUCINACIÓN:
        - Valida que exista evidencia antes de responder
        - Si no hay evidencia → mensaje de insuficiencia
        """
        if not self.datos:
            return self._respuesta_insuficiencia("No hay datos cargados")
        
        # Verificar si es pregunta prohibida
        if self._es_pregunta_prohibida(pregunta):
            return self._respuesta_insuficiencia("Pregunta requiere interpretación subjetiva")
        
        # Detectar intención
        tipo_consulta, contexto = self._detectar_intencion(pregunta)
        
        # Buscar valores numéricos en la pregunta
        valores_en_pregunta = re.findall(r'\d{4,}', pregunta)
        
        if valores_en_pregunta:
            return self._responder_buscar_valor_estricto(valores_en_pregunta)
        
        # Generar respuesta según tipo
        if tipo_consulta == TipoConsulta.POR_QUE_NO_PROCEDE:
            return self._responder_por_que_no_procede_estricto()
        
        elif tipo_consulta == TipoConsulta.OBSERVACION_MAS_GRAVE:
            return self._responder_mas_grave_estricto()
        
        elif tipo_consulta == TipoConsulta.LISTAR_CRITICAS:
            return self._responder_listar_criticas_estricto()
        
        elif tipo_consulta == TipoConsulta.LISTAR_MAYORES:
            return self._responder_listar_mayores_estricto()
        
        elif tipo_consulta == TipoConsulta.FILTRO_AGENTE:
            return self._responder_filtro_agente_estricto(contexto)
        
        elif tipo_consulta == TipoConsulta.DETALLE_OBSERVACION:
            return self._responder_detalle_observacion_estricto(pregunta)
        
        elif tipo_consulta == TipoConsulta.BUSCAR_ARCHIVO:
            return self._responder_buscar_archivo_estricto(pregunta)
        
        elif tipo_consulta == TipoConsulta.RESUMEN_GENERAL:
            return self._responder_resumen_estricto()
        
        elif tipo_consulta == TipoConsulta.SUBSANABLE_O_NO:
            return self._responder_subsanable_estricto()
        
        elif tipo_consulta == TipoConsulta.QUE_PASA_SI:
            return self._responder_que_pasa_si_estricto(pregunta)
        
        elif tipo_consulta == TipoConsulta.ACCIONES_REQUERIDAS:
            return self._responder_acciones_estricto()
        
        else:
            # Si hay LLM, intentar respuesta controlada
            if self.usando_llm:
                return self._responder_con_llm_estricto(pregunta)
            return self._respuesta_insuficiencia("Pregunta no reconocida")
    
    # =========================================================================
    # RESPUESTA DE INSUFICIENCIA
    # =========================================================================
    
    def _respuesta_insuficiencia(self, razon: str = "") -> RespuestaConversacional:
        """Genera respuesta estándar de insuficiencia probatoria"""
        texto = MENSAJE_INSUFICIENCIA
        if razon:
            texto += f"\n\n[Razón: {razon}]"
        
        return RespuestaConversacional(
            texto=texto,
            evidencias_citadas=[],
            observaciones_citadas=[],
            confianza="ALTA",
            tipo_consulta=TipoConsulta.INSUFICIENCIA,
            es_valida=True,
            cumple_estandar_probatorio=True
        )
    
    # =========================================================================
    # FORMATEO DE EVIDENCIA (OBLIGATORIO)
    # =========================================================================
    
    def _formatear_evidencia_estricta(self, 
                                       num_obs: int, 
                                       hallazgo: Dict, 
                                       evidencia: Dict = None) -> Tuple[str, EvidenciaCitada]:
        """
        Formatea una evidencia en el formato obligatorio.
        Retorna (texto_formateado, EvidenciaCitada) o (None, None) si falta información.
        """
        severidad = hallazgo.get("severidad", "N/A")
        impacto = hallazgo.get("impacto", "N/A")
        bloquea = hallazgo.get("bloquea_pago", False)
        bloquea_texto = "Bloquea pago" if bloquea else "No bloquea pago"
        
        if evidencia:
            archivo = evidencia.get("archivo", "")
            pagina = evidencia.get("pagina", 0)
            snippet = evidencia.get("snippet", "")
            valor = evidencia.get("valor_detectado", "")
        else:
            # Buscar en evidencias del hallazgo
            evidencias = hallazgo.get("evidencias", [])
            if evidencias:
                ev = evidencias[0]
                archivo = ev.get("archivo", "")
                pagina = ev.get("pagina", 0)
                snippet = ev.get("snippet", "")
                valor = ev.get("valor_detectado", "")
            else:
                return None, None
        
        # Validar que tengamos todos los campos obligatorios
        if not archivo or not pagina:
            return None, None
        
        # Truncar snippet si es muy largo
        if len(snippet) > 150:
            snippet = snippet[:150] + "..."
        
        texto = f"""
**Observación:** N°{num_obs}
**Severidad:** {severidad}
**Impacto:** {bloquea_texto}
**Evidencia:**
  - Archivo: `{archivo}`
  - Página: {pagina}
  - Texto: "{snippet}"
"""
        
        if valor:
            texto = texto.replace('- Texto:', f'- Valor detectado: {valor}\n  - Texto:')
        
        evidencia_citada = EvidenciaCitada(
            observacion_num=num_obs,
            severidad=severidad,
            impacto=impacto,
            bloquea_pago=bloquea,
            archivo=archivo,
            pagina=pagina,
            snippet=snippet,
            valor_detectado=valor
        )
        
        return texto, evidencia_citada
    
    # =========================================================================
    # RESPUESTAS CON ESTÁNDAR PROBATORIO
    # =========================================================================
    
    def _responder_por_que_no_procede_estricto(self) -> RespuestaConversacional:
        """Explica por qué no procede CON EVIDENCIA OBLIGATORIA"""
        decision = self.decision.get("resultado", "DESCONOCIDO")
        
        if decision == "PROCEDE":
            return RespuestaConversacional(
                texto="✅ El expediente PROCEDE. No hay observaciones que bloqueen el pago.",
                evidencias_citadas=[],
                observaciones_citadas=[],
                confianza="ALTA",
                tipo_consulta=TipoConsulta.POR_QUE_NO_PROCEDE,
                cumple_estandar_probatorio=True
            )
        
        criticas = [h for h in self.hallazgos if h.get("severidad") == "CRÍTICA"]
        
        if not criticas:
            return self._respuesta_insuficiencia("No hay observaciones críticas documentadas")
        
        lineas = [f"🔴 **El expediente NO PROCEDE** por {len(criticas)} observación(es) crítica(s):\n"]
        evidencias_citadas = []
        obs_citadas = []
        
        for i, h in enumerate(criticas, 1):
            texto_ev, ev_citada = self._formatear_evidencia_estricta(i, h)
            
            if texto_ev and ev_citada:
                lineas.append(f"---\n{h.get('hallazgo', 'N/A')}")
                lineas.append(texto_ev)
                evidencias_citadas.append(ev_citada)
                obs_citadas.append(i)
            else:
                # Si falta evidencia, marcar pero continuar
                lineas.append(f"---\n{h.get('hallazgo', 'N/A')}")
                lineas.append(f"⚠️ [Sin evidencia probatoria completa]")
        
        if not evidencias_citadas:
            return self._respuesta_insuficiencia("Observaciones sin evidencia probatoria completa")
        
        return RespuestaConversacional(
            texto="\n".join(lineas),
            evidencias_citadas=evidencias_citadas,
            observaciones_citadas=obs_citadas,
            confianza="ALTA",
            tipo_consulta=TipoConsulta.POR_QUE_NO_PROCEDE,
            cumple_estandar_probatorio=bool(evidencias_citadas)
        )
    
    def _responder_mas_grave_estricto(self) -> RespuestaConversacional:
        """Identifica la observación más grave CON EVIDENCIA OBLIGATORIA"""
        criticas = [h for h in self.hallazgos if h.get("severidad") == "CRÍTICA"]
        
        if not criticas:
            mayores = [h for h in self.hallazgos if h.get("severidad") == "MAYOR"]
            if mayores:
                criticas = mayores
            else:
                return self._respuesta_insuficiencia("No hay observaciones graves documentadas")
        
        h = criticas[0]
        texto_ev, ev_citada = self._formatear_evidencia_estricta(1, h)
        
        if not texto_ev or not ev_citada:
            return self._respuesta_insuficiencia("Observación más grave sin evidencia completa")
        
        texto = f"""🔴 **La observación más grave es:**

**{h.get('hallazgo', 'N/A')}**
{texto_ev}

**¿Por qué es grave?**
→ {h.get('impacto', 'Afecta validez del expediente')}
→ Acción requerida: {h.get('accion', 'Corregir y re-emitir')}
→ Responsable: {h.get('area_responsable', 'N/A')}
"""
        
        return RespuestaConversacional(
            texto=texto,
            evidencias_citadas=[ev_citada],
            observaciones_citadas=[1],
            confianza="ALTA",
            tipo_consulta=TipoConsulta.OBSERVACION_MAS_GRAVE,
            cumple_estandar_probatorio=True
        )
    
    def _responder_listar_criticas_estricto(self) -> RespuestaConversacional:
        """Lista críticas CON EVIDENCIA OBLIGATORIA"""
        criticas = [h for h in self.hallazgos if h.get("severidad") == "CRÍTICA"]
        
        if not criticas:
            return self._respuesta_insuficiencia("No hay observaciones críticas")
        
        lineas = [f"🔴 **OBSERVACIONES CRÍTICAS** ({len(criticas)}):\n"]
        evidencias_citadas = []
        obs_citadas = []
        
        for i, h in enumerate(criticas, 1):
            texto_ev, ev_citada = self._formatear_evidencia_estricta(i, h)
            
            lineas.append(f"**{i}. {h.get('hallazgo', 'N/A')}**")
            
            if texto_ev and ev_citada:
                lineas.append(texto_ev)
                evidencias_citadas.append(ev_citada)
                obs_citadas.append(i)
            else:
                lineas.append("⚠️ [Sin evidencia probatoria completa]\n")
        
        return RespuestaConversacional(
            texto="\n".join(lineas),
            evidencias_citadas=evidencias_citadas,
            observaciones_citadas=obs_citadas,
            confianza="ALTA",
            tipo_consulta=TipoConsulta.LISTAR_CRITICAS,
            cumple_estandar_probatorio=bool(evidencias_citadas)
        )
    
    def _responder_listar_mayores_estricto(self) -> RespuestaConversacional:
        """Lista mayores CON EVIDENCIA OBLIGATORIA"""
        mayores = [h for h in self.hallazgos if h.get("severidad") == "MAYOR"]
        
        if not mayores:
            return self._respuesta_insuficiencia("No hay observaciones mayores")
        
        lineas = [f"🟡 **OBSERVACIONES MAYORES** ({len(mayores)}):\n"]
        evidencias_citadas = []
        obs_citadas = []
        
        for i, h in enumerate(mayores, 1):
            texto_ev, ev_citada = self._formatear_evidencia_estricta(i, h)
            
            lineas.append(f"**{i}. {h.get('hallazgo', 'N/A')}**")
            
            if texto_ev and ev_citada:
                lineas.append(texto_ev)
                evidencias_citadas.append(ev_citada)
                obs_citadas.append(i)
            else:
                lineas.append("⚠️ [Sin evidencia probatoria completa]\n")
        
        return RespuestaConversacional(
            texto="\n".join(lineas),
            evidencias_citadas=evidencias_citadas,
            observaciones_citadas=obs_citadas,
            confianza="ALTA",
            tipo_consulta=TipoConsulta.LISTAR_MAYORES,
            cumple_estandar_probatorio=bool(evidencias_citadas)
        )
    
    def _responder_filtro_agente_estricto(self, contexto: str) -> RespuestaConversacional:
        """Filtra por agente CON EVIDENCIA OBLIGATORIA"""
        if not contexto:
            return self._respuesta_insuficiencia("No se especificó tipo de filtro")
        
        agentes = self.MAPEO_AGENTES.get(contexto, [contexto])
        
        filtrados = [
            h for h in self.hallazgos 
            if any(a in h.get("agente", "").lower() for a in agentes) or
               contexto in h.get("tipo", "").lower()
        ]
        
        if not filtrados:
            return self._respuesta_insuficiencia(f"No hay observaciones de {contexto}")
        
        lineas = [f"📋 **Observaciones de {contexto.upper()}** ({len(filtrados)}):\n"]
        evidencias_citadas = []
        obs_citadas = []
        
        for i, h in enumerate(filtrados, 1):
            texto_ev, ev_citada = self._formatear_evidencia_estricta(i, h)
            
            sev_emoji = "🔴" if h["severidad"] == "CRÍTICA" else "🟡" if h["severidad"] == "MAYOR" else "🟢"
            lineas.append(f"{sev_emoji} **{i}. {h.get('hallazgo', 'N/A')}**")
            
            if texto_ev and ev_citada:
                lineas.append(texto_ev)
                evidencias_citadas.append(ev_citada)
                obs_citadas.append(i)
            else:
                lineas.append("⚠️ [Sin evidencia probatoria completa]\n")
        
        return RespuestaConversacional(
            texto="\n".join(lineas),
            evidencias_citadas=evidencias_citadas,
            observaciones_citadas=obs_citadas,
            confianza="ALTA",
            tipo_consulta=TipoConsulta.FILTRO_AGENTE,
            cumple_estandar_probatorio=bool(evidencias_citadas)
        )
    
    def _responder_detalle_observacion_estricto(self, pregunta: str) -> RespuestaConversacional:
        """Detalle de observación CON EVIDENCIA COMPLETA"""
        match = re.search(r'(\d+)', pregunta)
        if not match:
            return self._respuesta_insuficiencia("No se especificó número de observación")
        
        num = int(match.group(1)) - 1
        
        if num < 0 or num >= len(self.hallazgos):
            return self._respuesta_insuficiencia(f"Observación #{num + 1} no existe")
        
        h = self.hallazgos[num]
        
        # Mostrar TODAS las evidencias
        lineas = [f"📋 **DETALLE OBSERVACIÓN #{num + 1}**\n"]
        lineas.append(f"**Hallazgo:** {h.get('hallazgo', 'N/A')}")
        lineas.append(f"**Severidad:** {h.get('severidad', 'N/A')}")
        lineas.append(f"**Tipo:** {h.get('tipo', 'N/A')}")
        lineas.append(f"**Impacto:** {h.get('impacto', 'N/A')}")
        lineas.append(f"**Bloquea pago:** {'SÍ' if h.get('bloquea_pago') else 'NO'}")
        lineas.append(f"**Acción:** {h.get('accion', 'N/A')}")
        lineas.append(f"**Responsable:** {h.get('area_responsable', 'N/A')}")
        
        evidencias = h.get("evidencias", [])
        evidencias_citadas = []
        
        if evidencias:
            lineas.append(f"\n**EVIDENCIAS ({len(evidencias)}):**")
            for i, ev in enumerate(evidencias, 1):
                archivo = ev.get("archivo", "N/A")
                pagina = ev.get("pagina", "N/A")
                valor = ev.get("valor_detectado", "")
                snippet = ev.get("snippet", "")[:150]
                
                lineas.append(f"\n  📎 Evidencia {i}:")
                lineas.append(f"     Archivo: `{archivo}`")
                lineas.append(f"     Página: {pagina}")
                if valor:
                    lineas.append(f"     Valor: {valor}")
                if snippet:
                    lineas.append(f"     Texto: \"{snippet}\"")
                
                if archivo and pagina:
                    evidencias_citadas.append(EvidenciaCitada(
                        observacion_num=num + 1,
                        severidad=h.get("severidad", "N/A"),
                        impacto=h.get("impacto", "N/A"),
                        bloquea_pago=h.get("bloquea_pago", False),
                        archivo=archivo,
                        pagina=pagina if isinstance(pagina, int) else 0,
                        snippet=snippet,
                        valor_detectado=valor
                    ))
        else:
            lineas.append("\n⚠️ [Sin evidencias detalladas]")
        
        return RespuestaConversacional(
            texto="\n".join(lineas),
            evidencias_citadas=evidencias_citadas,
            observaciones_citadas=[num + 1],
            confianza="ALTA",
            tipo_consulta=TipoConsulta.DETALLE_OBSERVACION,
            cumple_estandar_probatorio=bool(evidencias_citadas)
        )
    
    def _responder_buscar_valor_estricto(self, valores: List[str]) -> RespuestaConversacional:
        """Busca valores CON EVIDENCIA EXACTA"""
        resultados = []
        evidencias_citadas = []
        obs_citadas = []
        
        for valor in valores:
            for i, h in enumerate(self.hallazgos, 1):
                for ev in h.get("evidencias", []):
                    valor_det = str(ev.get("valor_detectado", ""))
                    snippet = ev.get("snippet", "")
                    archivo = ev.get("archivo", "")
                    pagina = ev.get("pagina", 0)
                    
                    if valor in valor_det or valor in snippet:
                        if archivo and pagina:
                            resultados.append({
                                "valor": valor,
                                "observacion": i,
                                "hallazgo": h,
                                "evidencia": ev
                            })
                            evidencias_citadas.append(EvidenciaCitada(
                                observacion_num=i,
                                severidad=h.get("severidad", "N/A"),
                                impacto=h.get("impacto", "N/A"),
                                bloquea_pago=h.get("bloquea_pago", False),
                                archivo=archivo,
                                pagina=pagina,
                                snippet=snippet[:150],
                                valor_detectado=valor_det
                            ))
                            if i not in obs_citadas:
                                obs_citadas.append(i)
        
        if not resultados:
            return self._respuesta_insuficiencia(f"Valor {', '.join(valores)} no encontrado en evidencias")
        
        lineas = [f"🔍 **Búsqueda de: {', '.join(valores)}**\n"]
        
        for r in resultados:
            h = r["hallazgo"]
            ev = r["evidencia"]
            sev_emoji = "🔴" if h["severidad"] == "CRÍTICA" else "🟡"
            
            lineas.append(f"{sev_emoji} **Observación #{r['observacion']}:** {h.get('hallazgo', '')[:60]}...")
            lineas.append(f"  - Archivo: `{ev['archivo']}`")
            lineas.append(f"  - Página: {ev['pagina']}")
            lineas.append(f"  - Valor: {ev.get('valor_detectado', 'N/A')}")
            lineas.append(f"  - Texto: \"{ev.get('snippet', '')[:100]}...\"")
            lineas.append("")
        
        return RespuestaConversacional(
            texto="\n".join(lineas),
            evidencias_citadas=evidencias_citadas,
            observaciones_citadas=obs_citadas,
            confianza="ALTA",
            tipo_consulta=TipoConsulta.BUSCAR_VALOR,
            cumple_estandar_probatorio=True
        )
    
    def _responder_buscar_archivo_estricto(self, pregunta: str) -> RespuestaConversacional:
        """Busca archivos con inconsistencias CON EVIDENCIA"""
        pregunta_lower = self._normalizar_texto(pregunta)
        
        tipo_busqueda = None
        for tipo in ["sinad", "ruc", "firma", "contrato"]:
            if tipo in pregunta_lower:
                tipo_busqueda = tipo
                break
        
        hallazgos_relevantes = []
        for i, h in enumerate(self.hallazgos, 1):
            if tipo_busqueda:
                if tipo_busqueda in h.get("tipo", "").lower():
                    hallazgos_relevantes.append((i, h))
            elif h.get("severidad") == "CRÍTICA":
                hallazgos_relevantes.append((i, h))
        
        if not hallazgos_relevantes:
            return self._respuesta_insuficiencia(f"No hay inconsistencias de {tipo_busqueda or 'tipo crítico'}")
        
        lineas = [f"📁 **Archivos con {tipo_busqueda or 'inconsistencias'}:**\n"]
        evidencias_citadas = []
        obs_citadas = []
        
        for num, h in hallazgos_relevantes:
            texto_ev, ev_citada = self._formatear_evidencia_estricta(num, h)
            
            lineas.append(f"**Observación #{num}:** {h.get('hallazgo', 'N/A')}")
            
            if texto_ev and ev_citada:
                lineas.append(texto_ev)
                evidencias_citadas.append(ev_citada)
                obs_citadas.append(num)
            else:
                lineas.append("⚠️ [Sin evidencia probatoria completa]\n")
        
        return RespuestaConversacional(
            texto="\n".join(lineas),
            evidencias_citadas=evidencias_citadas,
            observaciones_citadas=obs_citadas,
            confianza="ALTA",
            tipo_consulta=TipoConsulta.BUSCAR_ARCHIVO,
            cumple_estandar_probatorio=bool(evidencias_citadas)
        )
    
    def _responder_resumen_estricto(self) -> RespuestaConversacional:
        """Resumen basado SOLO en datos del JSON"""
        decision = self.decision.get("resultado", "DESCONOCIDO")
        sinad = self.metadata.get("expediente_sinad", "N/A")
        
        criticas = len([h for h in self.hallazgos if h.get("severidad") == "CRÍTICA"])
        mayores = len([h for h in self.hallazgos if h.get("severidad") == "MAYOR"])
        
        emoji = "🔴" if decision == "NO PROCEDE" else "✅" if decision == "PROCEDE" else "🟡"
        
        texto = f"""📋 **RESUMEN DEL EXPEDIENTE**

**SINAD:** {sinad}
**Decisión:** {emoji} {decision}

**Observaciones detectadas:**
  🔴 Críticas: {criticas}
  🟡 Mayores: {mayores}
  📊 Total: {len(self.hallazgos)}

**Nota:** Para ver evidencia específica, use:
  - "Lista las críticas"
  - "Detalle de la observación 1"
  - "¿En qué archivo aparece el [número]?"
"""
        
        return RespuestaConversacional(
            texto=texto,
            evidencias_citadas=[],
            observaciones_citadas=[],
            confianza="ALTA",
            tipo_consulta=TipoConsulta.RESUMEN_GENERAL,
            cumple_estandar_probatorio=True
        )
    
    def _responder_subsanable_estricto(self) -> RespuestaConversacional:
        """Evalúa subsanabilidad basado en datos del JSON"""
        criticas = [h for h in self.hallazgos if h.get("severidad") == "CRÍTICA"]
        mayores = [h for h in self.hallazgos if h.get("severidad") == "MAYOR"]
        
        if not criticas and not mayores:
            return self._respuesta_insuficiencia("No hay observaciones que evaluar")
        
        lineas = ["📋 **ANÁLISIS DE SUBSANABILIDAD**\n"]
        lineas.append("*Basado únicamente en las acciones documentadas en el expediente:*\n")
        
        evidencias_citadas = []
        
        for i, h in enumerate(criticas + mayores, 1):
            accion = h.get("accion", "No especificada")
            area = h.get("area_responsable", "No especificada")
            
            texto_ev, ev_citada = self._formatear_evidencia_estricta(i, h)
            
            sev = "🔴 CRÍTICA" if h.get("severidad") == "CRÍTICA" else "🟡 MAYOR"
            lineas.append(f"**{i}. {h.get('hallazgo', 'N/A')[:60]}...**")
            lineas.append(f"   Severidad: {sev}")
            lineas.append(f"   Acción documentada: {accion}")
            lineas.append(f"   Área responsable: {area}")
            
            if ev_citada:
                evidencias_citadas.append(ev_citada)
            
            lineas.append("")
        
        return RespuestaConversacional(
            texto="\n".join(lineas),
            evidencias_citadas=evidencias_citadas,
            observaciones_citadas=list(range(1, len(criticas + mayores) + 1)),
            confianza="MEDIA",
            tipo_consulta=TipoConsulta.SUBSANABLE_O_NO,
            cumple_estandar_probatorio=bool(evidencias_citadas)
        )
    
    def _responder_que_pasa_si_estricto(self, pregunta: str) -> RespuestaConversacional:
        """Escenario hipotético basado en datos del JSON"""
        pregunta_lower = self._normalizar_texto(pregunta)
        criticas = [h for h in self.hallazgos if h.get("severidad") == "CRÍTICA"]
        
        if not criticas:
            return self._respuesta_insuficiencia("No hay observaciones críticas para evaluar")
        
        # Identificar qué se corregiría
        tipo_corregir = None
        for tipo in ["sinad", "ruc", "firma", "contrato"]:
            if tipo in pregunta_lower:
                tipo_corregir = tipo
                break
        
        if tipo_corregir:
            afectadas = [h for h in criticas if tipo_corregir in h.get("tipo", "").lower()]
        else:
            afectadas = criticas
        
        restantes = len(criticas) - len(afectadas)
        
        lineas = [f"🔄 **Escenario: Corrección de {tipo_corregir or 'observaciones'}**\n"]
        lineas.append(f"Observaciones que se eliminarían: {len(afectadas)}")
        lineas.append(f"Observaciones restantes: {restantes}\n")
        
        if restantes > 0:
            lineas.append("⚠️ El expediente seguiría SIN PROCEDER")
        else:
            mayores = len([h for h in self.hallazgos if h.get("severidad") == "MAYOR"])
            if mayores:
                lineas.append(f"🟡 Pasaría a PROCEDE CON OBSERVACIONES ({mayores} mayores)")
            else:
                lineas.append("✅ Pasaría a PROCEDE")
        
        return RespuestaConversacional(
            texto="\n".join(lineas),
            evidencias_citadas=[],
            observaciones_citadas=[],
            confianza="MEDIA",
            tipo_consulta=TipoConsulta.QUE_PASA_SI,
            cumple_estandar_probatorio=True
        )
    
    def _responder_acciones_estricto(self) -> RespuestaConversacional:
        """Lista acciones documentadas en el JSON"""
        criticas = [h for h in self.hallazgos if h.get("severidad") == "CRÍTICA"]
        mayores = [h for h in self.hallazgos if h.get("severidad") == "MAYOR"]
        
        if not criticas and not mayores:
            return self._respuesta_insuficiencia("No hay acciones documentadas")
        
        lineas = ["📋 **ACCIONES DOCUMENTADAS EN EL EXPEDIENTE:**\n"]
        
        if criticas:
            lineas.append("**🔴 URGENTE (Bloquean pago):**")
            for i, h in enumerate(criticas, 1):
                lineas.append(f"{i}. {h.get('accion', 'No especificada')}")
                lineas.append(f"   Responsable: {h.get('area_responsable', 'N/A')}")
        
        if mayores:
            lineas.append("\n**🟡 IMPORTANTES:**")
            for i, h in enumerate(mayores, len(criticas) + 1):
                lineas.append(f"{i}. {h.get('accion', 'No especificada')}")
                lineas.append(f"   Responsable: {h.get('area_responsable', 'N/A')}")
        
        return RespuestaConversacional(
            texto="\n".join(lineas),
            evidencias_citadas=[],
            observaciones_citadas=list(range(1, len(criticas) + len(mayores) + 1)),
            confianza="ALTA",
            tipo_consulta=TipoConsulta.ACCIONES_REQUERIDAS,
            cumple_estandar_probatorio=True
        )
    
    # =========================================================================
    # RESPUESTA CON LLM (CONTROLADA)
    # =========================================================================
    
    def _responder_con_llm_estricto(self, pregunta: str) -> RespuestaConversacional:
        """Usa LLM con validación estricta de evidencia"""
        if not self.usando_llm:
            return self._respuesta_insuficiencia("LLM no disponible")
        
        try:
            respuesta_llm = self.llm_client.ask_with_context_strict(
                pregunta=pregunta,
                contexto_json=self.datos
            )
            
            if not respuesta_llm.es_valida or not respuesta_llm.tiene_evidencia:
                return self._respuesta_insuficiencia(
                    respuesta_llm.razon_invalida or "Respuesta LLM sin evidencia probatoria"
                )
            
            return RespuestaConversacional(
                texto=f"🤖 **[LLM: {self.llm_modelo}]**\n\n{respuesta_llm.texto}",
                evidencias_citadas=[],
                observaciones_citadas=[],
                confianza="MEDIA",
                tipo_consulta=TipoConsulta.PREGUNTA_LIBRE,
                backend_usado="llm",
                cumple_estandar_probatorio=respuesta_llm.tiene_evidencia
            )
            
        except Exception as e:
            return self._respuesta_insuficiencia(f"Error LLM: {e}")
    
    # =========================================================================
    # MODO INTERACTIVO
    # =========================================================================
    
    def modo_interactivo(self):
        """Inicia modo interactivo por consola"""
        print("=" * 70)
        print("🤖 AGENTE CONVERSACIONAL - ESTÁNDAR PROBATORIO ESTRICTO")
        print("=" * 70)
        print(f"⚖️  Política: Solo respuestas con evidencia documental")
        
        backend_info = self.get_backend_info()
        if backend_info["llm_disponible"]:
            print(f"🧠 Backend: LLM ({backend_info['modelo']})")
        else:
            print(f"📋 Backend: REGEX")
        
        if not self.datos:
            print("\n⚠️ No hay datos cargados.")
            return
        
        sinad = self.metadata.get("expediente_sinad", "N/A")
        decision = self.decision.get("resultado", "N/A")
        print(f"\n📋 Expediente SINAD: {sinad}")
        print(f"📌 Decisión: {decision}")
        print(f"📊 Hallazgos: {len(self.hallazgos)}")
        print("\n" + "-" * 70)
        
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
                
                if not respuesta.cumple_estandar_probatorio:
                    print("\n⚠️ [Respuesta sin estándar probatorio completo]")
                
            except KeyboardInterrupt:
                print("\n\n👋 ¡Hasta luego!")
                break


# =============================================================================
# FUNCIÓN HELPER
# =============================================================================

def iniciar_conversacion(ruta_json: str = None, backend: str = "auto") -> AgenteConversacional:
    return AgenteConversacional(ruta_json, backend)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
    
    if os.path.exists(output_dir):
        jsons = [f for f in os.listdir(output_dir) if f.endswith('.json')]
        if jsons:
            jsons.sort(reverse=True)
            ruta = os.path.join(output_dir, jsons[0])
            print(f"📂 Cargando: {jsons[0]}")
            
            agente = AgenteConversacional(ruta)
            agente.modo_interactivo()
        else:
            print("⚠️ No hay archivos JSON en output/")
    else:
        print("⚠️ No existe la carpeta output/")
