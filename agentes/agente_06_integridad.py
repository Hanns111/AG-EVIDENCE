# -*- coding: utf-8 -*-
"""
AGENTE 06 — INTEGRIDAD DEL EXPEDIENTE
=====================================
Verifica documentación completa según tipo de expediente.
Para primer pago: títulos, certificados, experiencia, perfil.
Detecta faltantes críticos.
"""

import os
import sys
import re
from typing import List, Dict, Set
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    ResultadoAgente, Observacion, NivelObservacion,
    NaturalezaExpediente, TipoProcedimiento
)
from utils.pdf_extractor import DocumentoPDF


@dataclass
class DocumentoEsperado:
    """Documento esperado en el expediente"""
    nombre: str
    patron: str
    obligatorio: bool
    para_primera_armada: bool = True
    para_siguientes_armadas: bool = False


class AgenteIntegridad:
    """
    Agente 06: Verifica integridad y completitud del expediente
    """
    
    AGENTE_ID = "AG06"
    AGENTE_NOMBRE = "Integridad del Expediente"
    
    # =========================================================================
    # DOCUMENTOS ESPERADOS POR NATURALEZA + ARMADA (según PAUTAS vigentes)
    # =========================================================================
    
    # ----- SERVICIOS (OS) - PRIMERA ARMADA -----
    # Contrato NO es obligatorio por defecto en servicios menores
    DOCS_SERVICIOS_PRIMERA_ARMADA = [
        DocumentoEsperado("Términos de Referencia", r"t[eé]rminos|TDR|referencia", True, True, False),
        DocumentoEsperado("Orden de Servicio", r"orden\s*de\s*servicio|O\.?S\.?", True, True, True),
        DocumentoEsperado("Certificación Presupuestal", r"certificaci[oó]n|CCP|cr[eé]dito\s*presupuest", True, True, False),
        DocumentoEsperado("Carta CCI", r"CCI|cuenta\s*interbancaria|autorizaci[oó]n.*banco", True, True, False),
        DocumentoEsperado("Comprobante de Pago", r"factura|boleta|comprobante\s*de\s*pago", True, True, True),
        DocumentoEsperado("Conformidad", r"conformidad", True, True, True),
        DocumentoEsperado("Informe de Conformidad", r"informe.*(conformidad|t[eé]cnico)|informe\s*n[°º]", True, True, True),
        # Contrato: obligatorio solo en procedimientos mayores, se maneja en _obtener_docs_esperados
        DocumentoEsperado("Contrato", r"contrato\s*n[°º]?", False, True, False),
        DocumentoEsperado("Garantía", r"garant[ií]a|carta\s*fianza", False, True, False),
    ]
    
    # ----- SERVICIOS (OS) - ARMADAS POSTERIORES (2da, 3ra, etc.) -----
    DOCS_SERVICIOS_ARMADAS_POSTERIORES = [
        DocumentoEsperado("Orden de Servicio", r"orden\s*de\s*servicio|O\.?S\.?", True, False, True),
        DocumentoEsperado("Comprobante de Pago", r"factura|boleta|comprobante\s*de\s*pago", True, False, True),
        DocumentoEsperado("Conformidad", r"conformidad", True, False, True),
        DocumentoEsperado("Informe de Conformidad", r"informe.*(conformidad|t[eé]cnico)|informe\s*n[°º]", True, False, True),
        # CCI/TDR/Contrato NO se requieren en armadas posteriores
    ]
    
    # ----- BIENES (OC) - PRIMERA ARMADA -----
    # SÍ requiere Guía de Remisión y Conformidad Almacén
    DOCS_BIENES_PRIMERA_ARMADA = [
        DocumentoEsperado("Especificaciones Técnicas", r"especificaciones?\s*t[eé]cnicas?|EETT", True, True, False),
        DocumentoEsperado("Orden de Compra", r"orden\s*de\s*compra|O\.?C\.?", True, True, True),
        DocumentoEsperado("Certificación Presupuestal", r"certificaci[oó]n|CCP|cr[eé]dito\s*presupuest", True, True, False),
        DocumentoEsperado("Carta CCI", r"CCI|cuenta\s*interbancaria|autorizaci[oó]n.*banco", True, True, False),
        DocumentoEsperado("Comprobante de Pago", r"factura|boleta|comprobante\s*de\s*pago", True, True, True),
        DocumentoEsperado("Guía de Remisión", r"gu[ií]a\s*de\s*remisi[oó]n", True, True, True),
        DocumentoEsperado("Conformidad Almacén", r"almac[eé]n|ingreso|pecosa", True, True, True),
        DocumentoEsperado("Contrato", r"contrato\s*n[°º]?", False, True, False),
        DocumentoEsperado("Garantía", r"garant[ií]a|carta\s*fianza", False, True, False),
    ]
    
    # ----- BIENES (OC) - ARMADAS POSTERIORES -----
    DOCS_BIENES_ARMADAS_POSTERIORES = [
        DocumentoEsperado("Orden de Compra", r"orden\s*de\s*compra|O\.?C\.?", True, False, True),
        DocumentoEsperado("Comprobante de Pago", r"factura|boleta|comprobante\s*de\s*pago", True, False, True),
        DocumentoEsperado("Guía de Remisión", r"gu[ií]a\s*de\s*remisi[oó]n", True, False, True),
        DocumentoEsperado("Conformidad Almacén", r"almac[eé]n|ingreso|pecosa", True, False, True),
    ]
    
    # ----- VIÁTICOS -----
    DOCS_VIATICOS = [
        DocumentoEsperado("Planilla de Viáticos", r"planilla.*vi[aá]ticos|PV", True, True, True),
        DocumentoEsperado("Autorización de Comisión", r"autorizaci[oó]n|comisi[oó]n\s*de\s*servicio", True, True, False),
        DocumentoEsperado("Rendición", r"rendici[oó]n", True, True, True),
        DocumentoEsperado("Anexo 3", r"anexo\s*3|relaci[oó]n\s*de\s*gastos", True, True, True),
        DocumentoEsperado("Comprobantes de Gastos", r"factura|boleta|ticket", True, True, True),
        DocumentoEsperado("Informe de Comisión", r"informe.*comisi[oó]n", True, True, True),
    ]
    
    # ----- PERSONA NATURAL (adicionales para primer pago) -----
    DOCS_PRIMER_PAGO_PERSONA_NATURAL = [
        DocumentoEsperado("DNI", r"DNI|documento\s*de\s*identidad", True, True, False),
        DocumentoEsperado("Título Profesional", r"t[ií]tulo|diploma|grado", False, True, False),
        DocumentoEsperado("Constancia RNP", r"RNP|registro\s*nacional\s*de\s*proveedores", False, True, False),
        DocumentoEsperado("Declaración Jurada", r"declaraci[oó]n\s*jurada", False, True, False),
        DocumentoEsperado("Suspensión 4ta Categoría", r"suspensi[oó]n|cuarta\s*categor[ií]a|4ta", False, True, False),
    ]
    
    # Alias de compatibilidad (deprecated)
    DOCS_CONCURSO_PUBLICO_PRIMERA = DOCS_SERVICIOS_PRIMERA_ARMADA
    
    def __init__(self):
        self.observaciones: List[Observacion] = []
        self.incertidumbres: List[str] = []
        self.datos_extraidos: Dict = {}
        
    def analizar(
        self, 
        documentos: List[DocumentoPDF],
        naturaleza: NaturalezaExpediente,
        tipo_procedimiento: TipoProcedimiento,
        es_primera_armada: bool = True
    ) -> ResultadoAgente:
        """
        Analiza la integridad del expediente
        """
        self.observaciones = []
        self.incertidumbres = []
        
        # Obtener documentos esperados
        docs_esperados = self._obtener_docs_esperados(
            naturaleza, tipo_procedimiento, es_primera_armada
        )
        
        # Verificar presencia de documentos
        verificacion = self._verificar_documentos(documentos, docs_esperados)
        
        # Detectar documentos duplicados o de otro expediente
        duplicados = self._detectar_duplicados(documentos)
        
        # Verificar perfil del contratado (si aplica)
        verificacion_perfil = self._verificar_perfil(documentos, naturaleza, es_primera_armada)
        
        # Generar observaciones
        for doc_esperado, estado in verificacion.items():
            if not estado["encontrado"] and estado["obligatorio"]:
                self.observaciones.append(Observacion(
                    nivel=NivelObservacion.CRITICA,
                    agente=self.AGENTE_NOMBRE,
                    descripcion=f"Documento faltante: {doc_esperado}",
                    evidencia="No se encontró en el expediente",
                    accion_requerida=f"Adjuntar {doc_esperado}",
                    area_responsable="Área Usuaria / Logística"
                ))
        
        if duplicados:
            self.observaciones.append(Observacion(
                nivel=NivelObservacion.MENOR,
                agente=self.AGENTE_NOMBRE,
                descripcion=f"Documentos posiblemente duplicados: {len(duplicados)}",
                evidencia=f"Archivos: {duplicados[:3]}",
                accion_requerida="Revisar y eliminar duplicados del expediente",
                area_responsable="Logística"
            ))
        
        self.observaciones.extend(verificacion_perfil)
        
        self.datos_extraidos = {
            "documentos_esperados": len(docs_esperados),
            "documentos_encontrados": sum(1 for v in verificacion.values() if v["encontrado"]),
            "documentos_faltantes": [k for k, v in verificacion.items() if not v["encontrado"] and v["obligatorio"]],
            "documentos_duplicados": duplicados,
            "es_primera_armada": es_primera_armada,
            "verificacion_detalle": verificacion
        }
        
        hay_criticas = any(obs.nivel == NivelObservacion.CRITICA for obs in self.observaciones)
        
        return ResultadoAgente(
            agente_id=self.AGENTE_ID,
            agente_nombre=self.AGENTE_NOMBRE,
            exito=not hay_criticas,
            observaciones=self.observaciones,
            datos_extraidos=self.datos_extraidos,
            incertidumbres=self.incertidumbres
        )
    
    def _obtener_docs_esperados(
        self,
        naturaleza: NaturalezaExpediente,
        tipo_procedimiento: TipoProcedimiento,
        es_primera_armada: bool
    ) -> List[DocumentoEsperado]:
        """
        Obtiene lista de documentos esperados según NATURALEZA + ARMADA.
        
        REGLA CRÍTICA:
        - SERVICIOS (OS): NO requiere Guía de Remisión ni Conformidad Almacén
        - BIENES (OC): SÍ requiere Guía de Remisión y Conformidad Almacén
        - Primera armada vs posteriores: diferentes requisitos
        """
        
        # 1. VIÁTICOS - directiva propia
        if naturaleza == NaturalezaExpediente.VIATICOS:
            return self.DOCS_VIATICOS
        
        # 2. SERVICIOS (Orden de Servicio) - NUNCA hereda requisitos de bienes
        if naturaleza in [
            NaturalezaExpediente.ORDEN_SERVICIO, 
            NaturalezaExpediente.PAGO_PROVEEDOR
        ]:
            if es_primera_armada:
                docs = list(self.DOCS_SERVICIOS_PRIMERA_ARMADA)
                # En procedimientos mayores (concurso/licitación), contrato SÍ es obligatorio
                if tipo_procedimiento in [
                    TipoProcedimiento.CONCURSO_PUBLICO,
                    TipoProcedimiento.ADJUDICACION_SIMPLIFICADA,
                    TipoProcedimiento.SELECCION_CONSULTORES
                ]:
                    # Marcar contrato como obligatorio
                    for doc in docs:
                        if doc.nombre == "Contrato":
                            doc.obligatorio = True
                return docs
            else:
                return list(self.DOCS_SERVICIOS_ARMADAS_POSTERIORES)
        
        # 3. BIENES (Orden de Compra) - SÍ requiere guía remisión y conformidad almacén
        if naturaleza == NaturalezaExpediente.ORDEN_COMPRA:
            if es_primera_armada:
                docs = list(self.DOCS_BIENES_PRIMERA_ARMADA)
                # En procedimientos mayores, contrato es obligatorio
                if tipo_procedimiento in [
                    TipoProcedimiento.LICITACION_PUBLICA,
                    TipoProcedimiento.ADJUDICACION_SIMPLIFICADA,
                    TipoProcedimiento.SUBASTA_INVERSA
                ]:
                    for doc in docs:
                        if doc.nombre == "Contrato":
                            doc.obligatorio = True
                return docs
            else:
                return list(self.DOCS_BIENES_ARMADAS_POSTERIORES)
        
        # 4. CONTRATO - inferir según procedimiento
        if naturaleza == NaturalezaExpediente.CONTRATO:
            if tipo_procedimiento == TipoProcedimiento.LICITACION_PUBLICA:
                return list(self.DOCS_BIENES_PRIMERA_ARMADA) if es_primera_armada else list(self.DOCS_BIENES_ARMADAS_POSTERIORES)
            else:
                return list(self.DOCS_SERVICIOS_PRIMERA_ARMADA) if es_primera_armada else list(self.DOCS_SERVICIOS_ARMADAS_POSTERIORES)
        
        # 5. Fallback: servicios primera armada (el más común)
        return list(self.DOCS_SERVICIOS_PRIMERA_ARMADA) if es_primera_armada else list(self.DOCS_SERVICIOS_ARMADAS_POSTERIORES)
    
    def _verificar_documentos(
        self,
        documentos: List[DocumentoPDF],
        esperados: List[DocumentoEsperado]
    ) -> Dict[str, Dict]:
        """
        Verifica presencia de documentos esperados.
        
        ESTRATEGIA ROBUSTA: Busca en nombre de archivo OR texto completo.
        Esto evita falsos negativos por OCR deficiente.
        """
        verificacion = {}
        
        # Concatenar todos los textos y nombres (por separado para mejor control)
        texto_total = " ".join([d.texto_completo for d in documentos])
        nombres_total = " ".join([d.nombre for d in documentos])
        
        for doc_esp in esperados:
            # Estrategia OR: encontrado si está en nombre O en texto
            encontrado_en_nombre = bool(re.search(doc_esp.patron, nombres_total, re.IGNORECASE))
            encontrado_en_texto = bool(re.search(doc_esp.patron, texto_total, re.IGNORECASE))
            
            # Detección especial para Conformidad (patrón robusto)
            if doc_esp.nombre == "Conformidad":
                # Patrones adicionales específicos para conformidad
                patrones_conformidad = [
                    r"conformidad",
                    r"CONF[\.\-]?\s*\d+",  # CONF.00889, CONF-00889
                    r"CONFORMIDAD[\-_]?\d+",  # CONFORMIDAD-00889
                ]
                for patron in patrones_conformidad:
                    if re.search(patron, nombres_total, re.IGNORECASE):
                        encontrado_en_nombre = True
                        break
                    if re.search(patron, texto_total, re.IGNORECASE):
                        encontrado_en_texto = True
                        break
            
            # Detección especial para Informe de Conformidad / Informe Técnico
            if "Informe" in doc_esp.nombre:
                patrones_informe = [
                    r"informe.*(?:conformidad|t[eé]cnico)",
                    r"INFORME[\-_]TECNICO",
                    r"INFORME_TECNICO[\-_]?\d+",
                ]
                for patron in patrones_informe:
                    if re.search(patron, nombres_total, re.IGNORECASE):
                        encontrado_en_nombre = True
                        break
            
            encontrado = encontrado_en_nombre or encontrado_en_texto
            
            verificacion[doc_esp.nombre] = {
                "encontrado": encontrado,
                "obligatorio": doc_esp.obligatorio,
                "fuente": "nombre" if encontrado_en_nombre else ("texto" if encontrado_en_texto else "no_encontrado")
            }
        
        return verificacion
    
    def _detectar_duplicados(self, documentos: List[DocumentoPDF]) -> List[str]:
        """Detecta documentos posiblemente duplicados"""
        duplicados = []
        nombres_vistos = {}
        
        for doc in documentos:
            # Normalizar nombre
            nombre_base = re.sub(r'\d{10,}', '', doc.nombre.lower())
            nombre_base = re.sub(r'\.pdf$', '', nombre_base)
            
            if nombre_base in nombres_vistos:
                duplicados.append(doc.nombre)
            else:
                nombres_vistos[nombre_base] = doc.nombre
        
        return duplicados
    
    def _verificar_perfil(
        self,
        documentos: List[DocumentoPDF],
        naturaleza: NaturalezaExpediente,
        es_primera_armada: bool
    ) -> List[Observacion]:
        """Verifica requisitos de perfil del contratado (primer pago)"""
        observaciones = []
        
        if not es_primera_armada:
            return observaciones
        
        if naturaleza not in [NaturalezaExpediente.PAGO_PROVEEDOR, NaturalezaExpediente.ORDEN_SERVICIO]:
            return observaciones
        
        texto_total = " ".join([d.texto_completo for d in documentos])
        
        # Detectar si es persona natural
        if re.search(r"persona\s*natural|consultor[ía]?\s*individual", texto_total, re.IGNORECASE):
            # Verificar documentos de persona natural
            for doc_esp in self.DOCS_PRIMER_PAGO_PERSONA_NATURAL:
                if doc_esp.obligatorio:
                    if not re.search(doc_esp.patron, texto_total, re.IGNORECASE):
                        self.incertidumbres.append(
                            f"Verificar si se requiere {doc_esp.nombre} para persona natural"
                        )
        
        # Verificar si el TDR pide experiencia/perfil específico
        if re.search(r"experiencia.*a[ñn]os|perfil.*profesional", texto_total, re.IGNORECASE):
            if not re.search(r"curr[ií]cul|CV|hoja\s*de\s*vida|experiencia\s*laboral", texto_total, re.IGNORECASE):
                observaciones.append(Observacion(
                    nivel=NivelObservacion.MAYOR,
                    agente=self.AGENTE_NOMBRE,
                    descripcion="TDR requiere experiencia pero no se evidencia CV/experiencia en expediente",
                    evidencia="Se detectó requisito de experiencia en TDR",
                    accion_requerida="Verificar que se haya acreditado el perfil del contratado",
                    area_responsable="Área Usuaria"
                ))
        
        return observaciones


def ejecutar_agente(
    documentos: List[DocumentoPDF],
    naturaleza: NaturalezaExpediente,
    tipo_procedimiento: TipoProcedimiento,
    es_primera_armada: bool = True
) -> ResultadoAgente:
    """Función helper para ejecutar el agente"""
    agente = AgenteIntegridad()
    return agente.analizar(documentos, naturaleza, tipo_procedimiento, es_primera_armada)



