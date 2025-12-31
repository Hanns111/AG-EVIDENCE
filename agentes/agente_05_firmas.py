# -*- coding: utf-8 -*-
"""
AGENTE 05 — FIRMAS Y COMPETENCIA (ESTÁNDAR PROBATORIO)
======================================================
Verifica firmas distinguiendo:
a) Firma digital (extraíble vía metadatos del PDF) - VERIFICABLE
b) Firma manuscrita/imagen - NO VERIFICABLE AUTOMÁTICAMENTE

REGLAS:
- Si hay firma digital verificable → validar competencia
- Si NO hay firma digital verificable → NO reportar como CRÍTICA
- Firma manuscrita → MAYOR o INCIERTO con requiere_revision_humana=True
"""

import os
import sys
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    ResultadoAgente, Observacion, NivelObservacion,
    EvidenciaProbatoria, MetodoExtraccion
)
from utils.pdf_extractor import DocumentoPDF


class TipoFirma(Enum):
    """Tipos de firma detectables"""
    DIGITAL_VERIFICABLE = "DIGITAL_VERIFICABLE"      # Firma digital con metadatos
    DIGITAL_TEXTO = "DIGITAL_TEXTO"                  # Mención a firma digital en texto
    MANUSCRITA = "MANUSCRITA"                        # Firma manuscrita (imagen)
    NO_DETECTADA = "NO_DETECTADA"


@dataclass
class FirmaDetectada:
    """Información de una firma detectada con evidencia"""
    documento: str
    pagina: int
    tipo: TipoFirma
    firmante: str
    cargo: str
    fecha: str
    snippet: str                    # Contexto de texto
    confianza: float
    metodo: MetodoExtraccion
    es_verificable: bool            # True solo si es digital verificable
    es_competente: Optional[bool]   # None si no se puede determinar


@dataclass
class ReglaFirma:
    """Regla de validación de firma"""
    id: str
    documento_tipo: str             # Tipo de documento (conformidad, contrato, etc.)
    cargos_validos: List[str]       # Cargos que pueden firmar
    es_obligatoria: bool


# Reglas de firma por tipo de documento
REGLAS_FIRMA = {
    "RF001": ReglaFirma("RF001", "conformidad", 
                        ["director", "directora", "jefe", "jefa", "coordinador", "coordinadora"], 
                        True),
    "RF002": ReglaFirma("RF002", "contrato", 
                        ["director", "directora", "jefe", "jefa", "representante legal"], 
                        True),
    "RF003": ReglaFirma("RF003", "proveido", 
                        ["coordinador", "coordinadora", "jefe", "jefa", "especialista"], 
                        True),
    "RF004": ReglaFirma("RF004", "informe", 
                        ["especialista", "analista", "coordinador", "jefe"], 
                        False),
}


class AgenteFirmas:
    """
    Agente 05: Verifica firmas con estándar probatorio
    """
    
    AGENTE_ID = "AG05"
    AGENTE_NOMBRE = "Firmas y Competencia"
    
    # Patrones para firma digital verificable (metadatos en texto)
    PATRONES_FIRMA_DIGITAL = [
        (r"FAU\s*(\d{11})\s*(soft|hard)", "FAU_CERTIFICADO"),
        (r"Firmado\s*digitalmente\s*por[:\s]*([A-ZÁÉÍÓÚÑ\s]+)", "FIRMADO_DIGITALMENTE"),
        (r"FIRMA\s*DIGITAL[:\s]*([A-ZÁÉÍÓÚÑ\s]+)", "FIRMA_DIGITAL_EXPLICITA"),
    ]
    
    # Patrones para detectar mención de firma (no necesariamente verificable)
    PATRONES_MENCION_FIRMA = [
        (r"Soy\s*el\s*autor\s*del\s*documento", "SOY_AUTOR"),
        (r"En\s*señal\s*de\s*conformidad", "SENAL_CONFORMIDAD"),
        (r"Doy\s*V[°º]\s*B[°º]", "VOB"),
        (r"Atentamente", "ATENTAMENTE"),
    ]
    
    # Patrón para extraer cargo
    PATRON_CARGO = r"(Director[a]?\s*(?:General|de\s+\w+)?|Jef[eoa]\s*(?:de\s+\w+)?|Coordinador[a]?\s*(?:de\s+\w+)?|Especialista\s*(?:de\s+\w+)?)"
    
    def __init__(self):
        self.observaciones: List[Observacion] = []
        self.incertidumbres: List[str] = []
        self.datos_extraidos: Dict = {}
        self.firmas_detectadas: List[FirmaDetectada] = []
        
    def analizar(self, documentos: List[DocumentoPDF]) -> ResultadoAgente:
        """
        Analiza firmas con estándar probatorio
        """
        self.observaciones = []
        self.incertidumbres = []
        self.firmas_detectadas = []
        
        for doc in documentos:
            # Solo analizar documentos que requieren firma
            if self._documento_requiere_firma(doc.nombre):
                firmas = self._detectar_firmas_documento(doc)
                self.firmas_detectadas.extend(firmas)
                
                # Evaluar cada firma
                for firma in firmas:
                    self._evaluar_firma(firma, doc)
                
                # Verificar si falta firma en documento crítico
                if not firmas and self._es_documento_critico(doc.nombre):
                    self._reportar_sin_firma(doc)
        
        # Validar y degradar observaciones sin evidencia completa
        for obs in self.observaciones:
            obs.validar_y_degradar()
        
        self.datos_extraidos = {
            "total_firmas_detectadas": len(self.firmas_detectadas),
            "firmas_digitales_verificables": sum(1 for f in self.firmas_detectadas if f.tipo == TipoFirma.DIGITAL_VERIFICABLE),
            "firmas_texto": sum(1 for f in self.firmas_detectadas if f.tipo == TipoFirma.DIGITAL_TEXTO),
            "firmas_no_verificables": sum(1 for f in self.firmas_detectadas if not f.es_verificable),
            "observaciones_generadas": len(self.observaciones)
        }
        
        # No hay críticas si no hay firmas digitales verificables
        hay_criticas = any(
            obs.nivel == NivelObservacion.CRITICA 
            for obs in self.observaciones
        )
        
        return ResultadoAgente(
            agente_id=self.AGENTE_ID,
            agente_nombre=self.AGENTE_NOMBRE,
            exito=not hay_criticas,
            observaciones=self.observaciones,
            datos_extraidos=self.datos_extraidos,
            incertidumbres=self.incertidumbres
        )
    
    def _detectar_firmas_documento(self, doc: DocumentoPDF) -> List[FirmaDetectada]:
        """Detecta firmas en un documento con clasificación de tipo"""
        firmas = []
        
        for pagina in doc.paginas:
            texto = pagina.texto
            num_pagina = pagina.numero
            
            # 1. Buscar firma digital verificable (con FAU)
            for patron, tipo in self.PATRONES_FIRMA_DIGITAL:
                for match in re.finditer(patron, texto, re.IGNORECASE):
                    snippet = self._extraer_snippet(texto, match)
                    firmante, cargo = self._extraer_firmante_cargo(texto, match.end())
                    
                    firma = FirmaDetectada(
                        documento=doc.nombre,
                        pagina=num_pagina,
                        tipo=TipoFirma.DIGITAL_VERIFICABLE if "FAU" in tipo else TipoFirma.DIGITAL_TEXTO,
                        firmante=firmante,
                        cargo=cargo,
                        fecha=self._extraer_fecha_firma(texto, match.end()),
                        snippet=snippet,
                        confianza=0.95 if "FAU" in tipo else 0.8,
                        metodo=MetodoExtraccion.REGEX,
                        es_verificable="FAU" in tipo,
                        es_competente=None
                    )
                    firmas.append(firma)
            
            # 2. Buscar menciones de firma (no verificables)
            if not firmas:  # Solo si no encontró firma digital
                for patron, tipo in self.PATRONES_MENCION_FIRMA:
                    for match in re.finditer(patron, texto, re.IGNORECASE):
                        snippet = self._extraer_snippet(texto, match)
                        firmante, cargo = self._extraer_firmante_cargo(texto, match.end())
                        
                        firma = FirmaDetectada(
                            documento=doc.nombre,
                            pagina=num_pagina,
                            tipo=TipoFirma.DIGITAL_TEXTO,
                            firmante=firmante,
                            cargo=cargo,
                            fecha="",
                            snippet=snippet,
                            confianza=0.6,
                            metodo=MetodoExtraccion.HEURISTICA,
                            es_verificable=False,
                            es_competente=None
                        )
                        firmas.append(firma)
                        break  # Solo una por página
        
        return firmas
    
    def _extraer_snippet(self, texto: str, match) -> str:
        """Extrae snippet de contexto"""
        inicio = max(0, match.start() - 30)
        fin = min(len(texto), match.end() + 100)
        return texto[inicio:fin].replace('\n', ' ').strip()
    
    def _extraer_firmante_cargo(self, texto: str, posicion: int) -> Tuple[str, str]:
        """Extrae nombre y cargo del firmante"""
        # Buscar en el texto después del match
        texto_siguiente = texto[posicion:posicion+300]
        
        # Buscar cargo
        cargo = "NO IDENTIFICADO"
        match_cargo = re.search(self.PATRON_CARGO, texto_siguiente, re.IGNORECASE)
        if match_cargo:
            cargo = match_cargo.group(1).strip()
        
        # Buscar nombre (mayúsculas después del cargo)
        firmante = "NO IDENTIFICADO"
        patron_nombre = r"([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ]+){1,3})"
        match_nombre = re.search(patron_nombre, texto_siguiente)
        if match_nombre:
            firmante = match_nombre.group(1).strip()
        
        return firmante, cargo
    
    def _extraer_fecha_firma(self, texto: str, posicion: int) -> str:
        """Extrae fecha de firma si existe"""
        texto_siguiente = texto[posicion:posicion+200]
        patron = r"(\d{4}/\d{2}/\d{2}\s*\d{2}:\d{2}:\d{2})"
        match = re.search(patron, texto_siguiente)
        return match.group(1) if match else ""
    
    def _evaluar_firma(self, firma: FirmaDetectada, doc: DocumentoPDF):
        """Evalúa una firma y genera observación si es necesario"""
        
        # Obtener regla aplicable
        regla = self._obtener_regla(doc.nombre)
        
        # Verificar competencia
        es_competente = self._verificar_competencia(firma.cargo, regla)
        firma.es_competente = es_competente
        
        # Generar observación según el caso
        if firma.es_verificable:
            # Firma digital verificable
            if not es_competente:
                self._crear_observacion_firma(
                    firma, 
                    NivelObservacion.CRITICA,
                    f"Firma digital de cargo no competente: {firma.cargo}",
                    regla
                )
        else:
            # Firma NO verificable automáticamente
            if firma.firmante == "NO IDENTIFICADO":
                self._crear_observacion_firma(
                    firma,
                    NivelObservacion.INCIERTO,  # NO CRÍTICA
                    "Firma no verificable automáticamente - firmante no identificado",
                    regla,
                    requiere_revision=True
                )
            elif not es_competente:
                self._crear_observacion_firma(
                    firma,
                    NivelObservacion.MAYOR,  # NO CRÍTICA
                    f"Firma no verificable - cargo posiblemente no competente: {firma.cargo}",
                    regla,
                    requiere_revision=True
                )
    
    def _obtener_regla(self, nombre_doc: str) -> ReglaFirma:
        """Obtiene la regla aplicable según tipo de documento"""
        nombre_lower = nombre_doc.lower()
        
        if "conformidad" in nombre_lower:
            return REGLAS_FIRMA["RF001"]
        elif "contrato" in nombre_lower:
            return REGLAS_FIRMA["RF002"]
        elif "proveido" in nombre_lower or "proveído" in nombre_lower:
            return REGLAS_FIRMA["RF003"]
        else:
            return REGLAS_FIRMA["RF004"]
    
    def _verificar_competencia(self, cargo: str, regla: ReglaFirma) -> bool:
        """Verifica si el cargo es competente según la regla"""
        if cargo == "NO IDENTIFICADO":
            return False
        
        cargo_lower = cargo.lower()
        return any(c in cargo_lower for c in regla.cargos_validos)
    
    def _crear_observacion_firma(
        self, 
        firma: FirmaDetectada,
        nivel: NivelObservacion,
        descripcion: str,
        regla: ReglaFirma,
        requiere_revision: bool = False
    ):
        """Crea observación con evidencia probatoria"""
        
        evidencia = EvidenciaProbatoria(
            archivo=firma.documento,
            pagina=firma.pagina,
            valor_detectado=f"{firma.firmante} ({firma.cargo})",
            snippet=firma.snippet,
            metodo_extraccion=firma.metodo,
            confianza=firma.confianza,
            regla_aplicada=regla.id
        )
        
        observacion = Observacion(
            nivel=nivel,
            agente=self.AGENTE_NOMBRE,
            descripcion=descripcion,
            accion_requerida="Verificar competencia del firmante o re-emitir documento con firma válida",
            area_responsable="Área Usuaria",
            evidencias=[evidencia],
            regla_aplicada=regla.id,
            requiere_revision_humana=requiere_revision
        )
        
        # Evidencia legacy
        observacion.evidencia = f"Documento: {firma.documento}, Firmante: {firma.firmante}, Tipo: {firma.tipo.value}"
        
        self.observaciones.append(observacion)
    
    def _reportar_sin_firma(self, doc: DocumentoPDF):
        """Reporta documento sin firma detectable"""
        
        regla = self._obtener_regla(doc.nombre)
        
        # Determinar página más probable (última)
        pagina = doc.total_paginas
        snippet = doc.paginas[-1].texto[-200:] if doc.paginas else ""
        
        evidencia = EvidenciaProbatoria(
            archivo=doc.nombre,
            pagina=pagina,
            valor_detectado="SIN FIRMA DETECTADA",
            snippet=snippet.replace('\n', ' ').strip(),
            metodo_extraccion=MetodoExtraccion.HEURISTICA,
            confianza=0.5,
            regla_aplicada=regla.id
        )
        
        # Si es documento crítico pero no hay firma digital verificable
        # NO es CRÍTICA, es MAYOR con revisión humana
        observacion = Observacion(
            nivel=NivelObservacion.MAYOR,
            agente=self.AGENTE_NOMBRE,
            descripcion=f"No se detectó firma en documento: {doc.nombre}",
            accion_requerida="Verificar manualmente que el documento esté firmado",
            area_responsable="Control Previo",
            evidencias=[evidencia],
            regla_aplicada=regla.id,
            requiere_revision_humana=True
        )
        
        observacion.evidencia = f"Documento: {doc.nombre} - Sin firma digital detectada"
        
        self.observaciones.append(observacion)
    
    def _documento_requiere_firma(self, nombre: str) -> bool:
        """Determina si un documento requiere firma"""
        nombre_lower = nombre.lower()
        return any(t in nombre_lower for t in [
            "conformidad", "informe", "proveido", "proveído",
            "contrato", "orden", "memorandum", "memorándum"
        ])
    
    def _es_documento_critico(self, nombre: str) -> bool:
        """Determina si es documento crítico (que DEBE tener firma)"""
        nombre_lower = nombre.lower()
        return any(t in nombre_lower for t in ["conformidad", "contrato"])


def ejecutar_agente(documentos: List[DocumentoPDF]) -> ResultadoAgente:
    """Función helper para ejecutar el agente"""
    agente = AgenteFirmas()
    return agente.analizar(documentos)
