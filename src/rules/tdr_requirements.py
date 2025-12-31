# -*- coding: utf-8 -*-
"""
TDR REQUIREMENTS — Extractor y Validador de Requisitos del Proveedor
=====================================================================
Implementa la regla "Documentos requeridos en los TDR" de las Pautas
para la Remisión de Expedientes de Pago (11/07/2020).

PRINCIPIO CLAVE:
CV/Perfil/Experiencia NO es requisito universal de la Pauta.
Solo se exige si el TDR lo solicita explícitamente.

ALCANCE:
- Extrae requisitos del proveedor mencionados en el TDR
- Solo genera observaciones por requisitos que el TDR pide
- Si el TDR NO menciona CV/experiencia, NO se observa por ello

REGLA DE GOBERNANZA (AGENT_GOVERNANCE_RULES.md Art. 8):
- Si no hay pauta identificada, NO exigir documentos específicos
"""

import os
import sys
import re
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field

# Agregar path del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import (
    Observacion, NivelObservacion, EvidenciaProbatoria, MetodoExtraccion
)


# =============================================================================
# ESTRUCTURAS DE DATOS
# =============================================================================

@dataclass
class RequisitoTDR:
    """Requisito del proveedor extraído del TDR"""
    tipo: str                          # CV, EXPERIENCIA, TITULO, COLEGIATURA, etc.
    descripcion: str                   # Descripción del requisito
    texto_fuente: str                  # Texto literal del TDR que lo menciona
    obligatorio: bool = True           # Si es obligatorio o deseable
    pagina: int = 1                    # Página donde se encontró
    confianza: float = 0.9             # Confianza en la extracción
    
    def to_dict(self) -> Dict:
        return {
            "tipo": self.tipo,
            "descripcion": self.descripcion,
            "texto_fuente": self.texto_fuente[:200],
            "obligatorio": self.obligatorio,
            "pagina": self.pagina,
            "confianza": self.confianza
        }


@dataclass
class ResultadoExtraccionTDR:
    """Resultado de la extracción de requisitos del TDR"""
    requisitos: List[RequisitoTDR] = field(default_factory=list)
    archivo_tdr: str = ""
    total_requisitos: int = 0
    requisitos_perfil: int = 0        # Cantidad de requisitos de perfil/CV
    
    def tiene_requisito_cv(self) -> bool:
        return any(r.tipo == "CV" for r in self.requisitos)
    
    def tiene_requisito_experiencia(self) -> bool:
        return any(r.tipo == "EXPERIENCIA" for r in self.requisitos)
    
    def tiene_requisito_titulo(self) -> bool:
        return any(r.tipo == "TITULO" for r in self.requisitos)


# =============================================================================
# CLASE PRINCIPAL
# =============================================================================

class TDRRequirementExtractor:
    """
    Extractor de requisitos del proveedor desde TDR.
    
    Solo extrae requisitos que el TDR menciona explícitamente.
    NO asume requisitos que no estén escritos.
    """
    
    REGLA_ID = "TDR-001"
    REGLA_NOMBRE = "Requisitos del proveedor según TDR"
    
    # Patrones por tipo de requisito
    PATRONES_REQUISITOS = {
        "CV": [
            r"(?:presentar|adjuntar|incluir)?\s*(?:el\s+)?(?:curriculum|curr[ií]culum|curr[ií]culo|CV)\s*(?:vitae)?",
            r"(?:hoja\s+de\s+)?vida\s+(?:documentada|actualizada)",
            r"curr[ií]culum\s+(?:vitae\s+)?(?:documentado|actualizado)",
        ],
        "EXPERIENCIA": [
            r"experiencia\s+(?:profesional|laboral|m[ií]nima)?\s*(?:de\s+)?(\d+)\s*(?:a[ñn]os?|meses?)",
            r"(?:acreditar|demostrar|contar\s+con)\s+experiencia",
            r"(\d+)\s*(?:a[ñn]os?|meses?)\s+de\s+experiencia",
            r"experiencia\s+(?:no\s+)?menor\s+(?:a|de)\s+(\d+)",
            r"experiencia\s+en\s+(?:el\s+)?(?:sector|rubro|cargo|puesto|[aá]rea)",
        ],
        "TITULO": [
            r"t[ií]tulo\s+(?:profesional|universitario|t[eé]cnico)",
            r"(?:grado\s+(?:acad[eé]mico|de)\s+)?(?:bachiller|licenciado|ingeniero|abogado|contador|economista)",
            r"(?:con\s+)?estudios\s+(?:universitarios|superiores|t[eé]cnicos)",
            r"diploma\s+(?:de|en)",
        ],
        "COLEGIATURA": [
            r"colegiatura\s+(?:vigente|activa|habilitada)",
            r"colegiado\s+(?:y\s+)?habilitado",
            r"habilitaci[oó]n\s+(?:profesional|del\s+colegio)",
            r"constancia\s+de\s+(?:colegiatura|habilitaci[oó]n)",
        ],
        "CAPACITACION": [
            r"capacitaci[oó]n\s+en",
            r"certificaci[oó]n\s+en",
            r"curso\s+(?:de|en)\s+(?:especializaci[oó]n|actualizaci[oó]n)",
            r"diplomado\s+en",
        ],
        "REGISTRO_RNP": [
            r"registro\s+nacional\s+de\s+proveedores",
            r"inscripci[oó]n\s+(?:en\s+)?(?:el\s+)?RNP",
            r"RNP\s+vigente",
        ],
        "DECLARACION_JURADA": [
            r"declaraci[oó]n\s+jurada",
            r"DJ\s+(?:de|que)",
        ],
        "DOCUMENTO_IDENTIDAD": [
            r"copia\s+(?:simple\s+)?(?:de\s+)?(?:DNI|documento\s+de\s+identidad)",
            r"DNI\s+(?:del\s+)?(?:consultor|profesional|contratista)",
        ],
    }
    
    # Keywords que indican obligatoriedad
    KEYWORDS_OBLIGATORIO = [
        "debe", "deberá", "obligatorio", "indispensable", "requisito",
        "exige", "exigible", "presentar", "adjuntar", "acreditar"
    ]
    
    # Keywords que indican deseable/opcional
    KEYWORDS_DESEABLE = [
        "deseable", "preferible", "valorable", "opcional", "adicional",
        "de preferencia", "se valorará"
    ]
    
    def __init__(self):
        self.requisitos_encontrados: List[RequisitoTDR] = []
    
    def extraer_requisitos(
        self, 
        texto_tdr: str, 
        nombre_archivo: str = "TDR.pdf",
        paginas: List[Tuple[int, str]] = None
    ) -> ResultadoExtraccionTDR:
        """
        Extrae requisitos del proveedor desde el texto del TDR.
        
        Args:
            texto_tdr: Texto completo del TDR
            nombre_archivo: Nombre del archivo TDR
            paginas: Lista de tuplas (num_pagina, texto_pagina) opcional
        
        Returns:
            ResultadoExtraccionTDR con los requisitos encontrados
        """
        self.requisitos_encontrados = []
        texto_lower = texto_tdr.lower()
        
        # Buscar cada tipo de requisito
        for tipo, patrones in self.PATRONES_REQUISITOS.items():
            for patron in patrones:
                for match in re.finditer(patron, texto_lower, re.IGNORECASE):
                    # Extraer contexto
                    inicio = max(0, match.start() - 100)
                    fin = min(len(texto_tdr), match.end() + 100)
                    contexto = texto_tdr[inicio:fin].strip()
                    
                    # Determinar si es obligatorio
                    obligatorio = self._es_obligatorio(contexto)
                    
                    # Encontrar página
                    pagina = self._encontrar_pagina(paginas, match.start()) if paginas else 1
                    
                    # Crear requisito
                    requisito = RequisitoTDR(
                        tipo=tipo,
                        descripcion=self._generar_descripcion(tipo, match.group(0)),
                        texto_fuente=contexto,
                        obligatorio=obligatorio,
                        pagina=pagina,
                        confianza=0.9 if obligatorio else 0.75
                    )
                    
                    # Evitar duplicados
                    if not self._es_duplicado(requisito):
                        self.requisitos_encontrados.append(requisito)
        
        # Crear resultado
        resultado = ResultadoExtraccionTDR(
            requisitos=self.requisitos_encontrados,
            archivo_tdr=nombre_archivo,
            total_requisitos=len(self.requisitos_encontrados),
            requisitos_perfil=sum(1 for r in self.requisitos_encontrados 
                                  if r.tipo in ["CV", "EXPERIENCIA", "TITULO", "COLEGIATURA"])
        )
        
        return resultado
    
    def _es_obligatorio(self, contexto: str) -> bool:
        """Determina si el requisito es obligatorio basándose en el contexto"""
        contexto_lower = contexto.lower()
        
        # Si tiene keywords de deseable, no es obligatorio
        if any(kw in contexto_lower for kw in self.KEYWORDS_DESEABLE):
            return False
        
        # Si tiene keywords de obligatorio, es obligatorio
        if any(kw in contexto_lower for kw in self.KEYWORDS_OBLIGATORIO):
            return True
        
        # Por defecto, asumir obligatorio (principio de precaución)
        return True
    
    def _generar_descripcion(self, tipo: str, texto_match: str) -> str:
        """Genera descripción legible del requisito"""
        descripciones = {
            "CV": "Currículum Vitae del profesional/consultor",
            "EXPERIENCIA": f"Experiencia profesional ({texto_match})",
            "TITULO": "Título profesional o grado académico",
            "COLEGIATURA": "Colegiatura y habilitación profesional vigente",
            "CAPACITACION": "Capacitación o certificación especializada",
            "REGISTRO_RNP": "Inscripción vigente en el RNP",
            "DECLARACION_JURADA": "Declaración jurada",
            "DOCUMENTO_IDENTIDAD": "Documento de identidad (DNI)",
        }
        return descripciones.get(tipo, texto_match)
    
    def _encontrar_pagina(self, paginas: List[Tuple[int, str]], posicion: int) -> int:
        """Encuentra el número de página para una posición en el texto"""
        if not paginas:
            return 1
        
        pos_acum = 0
        for num_pag, texto_pag in paginas:
            pos_acum += len(texto_pag)
            if posicion <= pos_acum:
                return num_pag
        
        return paginas[-1][0] if paginas else 1
    
    def _es_duplicado(self, nuevo: RequisitoTDR) -> bool:
        """Verifica si el requisito ya fue encontrado"""
        for existente in self.requisitos_encontrados:
            if existente.tipo == nuevo.tipo:
                # Mismo tipo y texto similar = duplicado
                if existente.texto_fuente[:50] == nuevo.texto_fuente[:50]:
                    return True
        return False


# =============================================================================
# VALIDADOR DE REQUISITOS
# =============================================================================

def validar_requisitos_tdr(
    requisitos: List[RequisitoTDR],
    documentos_presentes: Set[str],
    nombre_archivo_tdr: str = "TDR.pdf"
) -> List[Observacion]:
    """
    Valida que los requisitos del TDR estén presentes en el expediente.
    
    REGLA CRÍTICA: Solo observa por requisitos que el TDR pide.
    Si el TDR no pide CV, NO observar por falta de CV.
    
    Args:
        requisitos: Lista de RequisitoTDR extraídos
        documentos_presentes: Conjunto de tipos de documentos detectados en el expediente
                             Ej: {"CV", "FACTURA", "CONFORMIDAD", "DNI"}
        nombre_archivo_tdr: Nombre del archivo TDR para evidencia
    
    Returns:
        Lista de observaciones por requisitos faltantes
    """
    observaciones = []
    
    for req in requisitos:
        # Solo validar requisitos obligatorios
        if not req.obligatorio:
            continue
        
        # Verificar si el documento está presente
        tipo_normalizado = req.tipo.upper()
        
        # Mapeo de tipos de requisito a documentos esperados
        documento_esperado = _mapear_requisito_a_documento(tipo_normalizado)
        
        if documento_esperado and documento_esperado not in documentos_presentes:
            # Requisito solicitado pero documento no encontrado
            evidencia = EvidenciaProbatoria(
                archivo=nombre_archivo_tdr,
                pagina=req.pagina,
                valor_detectado=req.tipo,
                valor_esperado=documento_esperado,
                snippet=req.texto_fuente[:150],
                metodo_extraccion=MetodoExtraccion.REGEX,
                confianza=req.confianza,
                regla_aplicada=f"TDR-001: Requisito '{req.tipo}' solicitado en TDR"
            )
            
            obs = Observacion(
                nivel=NivelObservacion.MAYOR,
                agente="TDRRequirementValidator",
                descripcion=f"TDR requiere {req.descripcion}, pero no se encontró en el expediente",
                accion_requerida=f"Adjuntar {documento_esperado} según lo solicitado en TDR",
                area_responsable="Área Usuaria / Proveedor",
                evidencias=[evidencia],
                regla_aplicada="TDR-001"
            )
            observaciones.append(obs)
    
    return observaciones


def _mapear_requisito_a_documento(tipo_requisito: str) -> Optional[str]:
    """Mapea un tipo de requisito a un tipo de documento esperado"""
    mapeo = {
        "CV": "CV",
        "EXPERIENCIA": "CV",  # La experiencia se acredita con CV
        "TITULO": "TITULO_PROFESIONAL",
        "COLEGIATURA": "CONSTANCIA_COLEGIATURA",
        "CAPACITACION": "CERTIFICADO_CAPACITACION",
        "REGISTRO_RNP": "CONSTANCIA_RNP",
        "DECLARACION_JURADA": "DECLARACION_JURADA",
        "DOCUMENTO_IDENTIDAD": "DNI",
    }
    return mapeo.get(tipo_requisito)


# =============================================================================
# FUNCIONES HELPER PÚBLICAS
# =============================================================================

def extraer_requisitos_tdr(
    texto_tdr: str,
    nombre_archivo: str = "TDR.pdf",
    paginas: List[Tuple[int, str]] = None
) -> List[RequisitoTDR]:
    """
    Función helper para extraer requisitos del TDR.
    
    Returns:
        Lista de RequisitoTDR encontrados
    """
    extractor = TDRRequirementExtractor()
    resultado = extractor.extraer_requisitos(texto_tdr, nombre_archivo, paginas)
    return resultado.requisitos


def tdr_requiere_cv(texto_tdr: str) -> bool:
    """
    Helper rápido para saber si el TDR requiere CV.
    
    Returns:
        True si el TDR menciona CV/currículum, False si no
    """
    extractor = TDRRequirementExtractor()
    resultado = extractor.extraer_requisitos(texto_tdr)
    return resultado.tiene_requisito_cv()


def tdr_requiere_experiencia(texto_tdr: str) -> Tuple[bool, Optional[str]]:
    """
    Helper para saber si el TDR requiere experiencia y cuánta.
    
    Returns:
        Tupla (requiere: bool, detalle: str o None)
    """
    extractor = TDRRequirementExtractor()
    resultado = extractor.extraer_requisitos(texto_tdr)
    
    for req in resultado.requisitos:
        if req.tipo == "EXPERIENCIA":
            return True, req.descripcion
    
    return False, None


# =============================================================================
# TESTS INTEGRADOS
# =============================================================================

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 70)
    print("TEST: TDRRequirementExtractor")
    print("=" * 70)
    
    # Test 1: TDR que pide CV y experiencia
    print("\n📋 Test 1: TDR con requisitos de CV y experiencia")
    texto_tdr_1 = """
    TÉRMINOS DE REFERENCIA
    CONTRATACIÓN DE CONSULTOR
    
    III. PERFIL DEL CONSULTOR
    
    El consultor deberá cumplir con los siguientes requisitos:
    
    - Título profesional de Ingeniero de Sistemas o afines
    - Experiencia profesional mínima de 5 años en desarrollo de software
    - Presentar currículum vitae documentado
    - Colegiatura y habilitación vigente
    
    La experiencia se acreditará mediante contratos u órdenes de servicio.
    """
    
    extractor = TDRRequirementExtractor()
    resultado = extractor.extraer_requisitos(texto_tdr_1, "TDR_consultor.pdf")
    
    print(f"   Requisitos encontrados: {resultado.total_requisitos}")
    for req in resultado.requisitos:
        print(f"   - {req.tipo}: {req.descripcion} (obligatorio: {req.obligatorio})")
    
    assert resultado.tiene_requisito_cv(), "Debería detectar requisito de CV"
    assert resultado.tiene_requisito_experiencia(), "Debería detectar requisito de experiencia"
    print("   ✅ PASÓ")
    
    # Test 2: TDR sin requisitos de perfil
    print("\n📋 Test 2: TDR sin requisitos de CV/experiencia")
    texto_tdr_2 = """
    TÉRMINOS DE REFERENCIA
    SERVICIO DE LIMPIEZA
    
    I. OBJETO
    Contratación del servicio de limpieza de oficinas.
    
    II. ALCANCE
    El servicio incluye limpieza diaria de pisos y ventanas.
    
    III. PLAZO
    30 días calendario.
    
    IV. FORMA DE PAGO
    Pago mensual contra conformidad.
    """
    
    resultado2 = extractor.extraer_requisitos(texto_tdr_2, "TDR_limpieza.pdf")
    
    print(f"   Requisitos encontrados: {resultado2.total_requisitos}")
    assert not resultado2.tiene_requisito_cv(), "NO debería detectar requisito de CV"
    assert not resultado2.tiene_requisito_experiencia(), "NO debería detectar requisito de experiencia"
    print("   ✅ PASÓ - TDR sin requisitos de perfil no genera observaciones")
    
    # Test 3: Validación de requisitos
    print("\n📋 Test 3: Validación de requisitos faltantes")
    
    # Simular documentos presentes (sin CV ni título)
    docs_presentes = {"FACTURA", "CONFORMIDAD", "ORDEN_SERVICIO"}
    
    observaciones = validar_requisitos_tdr(
        resultado.requisitos,  # Requisitos del TDR 1 (pide CV, exp, título)
        docs_presentes,
        "TDR_consultor.pdf"
    )
    
    print(f"   Observaciones generadas: {len(observaciones)}")
    for obs in observaciones:
        print(f"   - [{obs.nivel.value}] {obs.descripcion[:60]}...")
    
    assert len(observaciones) > 0, "Debería generar observaciones por CV faltante"
    print("   ✅ PASÓ")
    
    # Test 4: Si TDR no pide CV, no se observa
    print("\n📋 Test 4: Sin observaciones si TDR no pide requisitos")
    
    observaciones2 = validar_requisitos_tdr(
        resultado2.requisitos,  # Requisitos del TDR 2 (no pide nada de perfil)
        docs_presentes,
        "TDR_limpieza.pdf"
    )
    
    print(f"   Observaciones generadas: {len(observaciones2)}")
    assert len(observaciones2) == 0, "NO debería generar observaciones si TDR no pide CV"
    print("   ✅ PASÓ - Principio clave respetado: solo observar lo que TDR pide")
    
    print("\n" + "=" * 70)
    print("✅ Todos los tests pasaron")
    print("=" * 70)


