# -*- coding: utf-8 -*-
"""
AGENTE 07 — PENALIDADES
=======================
Evalúa si corresponde aplicar penalidad.
Detecta omisiones de penalidades.
Verifica cálculos de penalidad por mora.
"""

import os
import sys
import re
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    ResultadoAgente, Observacion, NivelObservacion
)
from utils.pdf_extractor import DocumentoPDF


@dataclass
class AnalisisPenalidad:
    """Resultado del análisis de penalidades"""
    aplica_penalidad: bool
    tipo: str  # MORA, OTRAS, NINGUNA
    dias_atraso: int
    monto_penalidad: float
    monto_base: float
    justificacion: str
    documentado: bool


class AgentePenalidades:
    """
    Agente 07: Evalúa aplicación de penalidades
    """
    
    AGENTE_ID = "AG07"
    AGENTE_NOMBRE = "Penalidades"
    
    # Fórmula estándar de penalidad por mora
    # Penalidad = 0.10 x monto / (F x plazo)
    # donde F = 0.40 para servicios
    FACTOR_F = 0.40
    PORCENTAJE_PENALIDAD = 0.10
    TOPE_PENALIDAD = 0.10  # 10% máximo
    
    def __init__(self):
        self.observaciones: List[Observacion] = []
        self.incertidumbres: List[str] = []
        self.datos_extraidos: Dict = {}
        
    def analizar(self, documentos: List[DocumentoPDF]) -> ResultadoAgente:
        """
        Analiza si corresponde aplicar penalidades
        """
        self.observaciones = []
        self.incertidumbres = []
        
        # Extraer información relevante
        info_contrato = self._extraer_info_contrato(documentos)
        info_conformidad = self._extraer_info_conformidad(documentos)
        
        # Analizar penalidad por mora
        analisis_mora = self._analizar_mora(info_contrato, info_conformidad)
        
        # Analizar otras penalidades
        analisis_otras = self._analizar_otras_penalidades(documentos)
        
        # Verificar si se documentó la no aplicación
        documentacion_ok = self._verificar_documentacion_penalidad(documentos)
        
        # Generar observaciones
        if analisis_mora.aplica_penalidad and not documentacion_ok:
            self.observaciones.append(Observacion(
                nivel=NivelObservacion.CRITICA,
                agente=self.AGENTE_NOMBRE,
                descripcion=f"Posible penalidad por mora no aplicada: {analisis_mora.dias_atraso} días de atraso",
                evidencia=f"Monto penalidad estimado: S/ {analisis_mora.monto_penalidad:.2f}",
                accion_requerida="Aplicar penalidad o justificar su no aplicación",
                area_responsable="Área Usuaria / Logística"
            ))
        
        if analisis_mora.aplica_penalidad and documentacion_ok:
            # Verificar si el monto aplicado es correcto
            self._verificar_calculo_penalidad(documentos, analisis_mora)
        
        self.datos_extraidos = {
            "aplica_penalidad_mora": analisis_mora.aplica_penalidad,
            "dias_atraso": analisis_mora.dias_atraso,
            "monto_penalidad_estimado": analisis_mora.monto_penalidad,
            "info_contrato": info_contrato,
            "info_conformidad": info_conformidad,
            "penalidad_documentada": documentacion_ok,
            "otras_penalidades": analisis_otras
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
    
    def _extraer_info_contrato(self, documentos: List[DocumentoPDF]) -> Dict:
        """Extrae información del contrato/orden relevante para penalidades"""
        info = {
            "plazo_dias": 0,
            "fecha_inicio": None,
            "fecha_fin": None,
            "monto": 0.0,
            "tiene_clausula_penalidad": False
        }
        
        texto_total = " ".join([d.texto_completo for d in documentos])
        
        # Buscar plazo
        match_plazo = re.search(r"plazo.*?(\d+)\s*d[ií]as?\s*calendar", texto_total, re.IGNORECASE)
        if match_plazo:
            info["plazo_dias"] = int(match_plazo.group(1))
        
        # Buscar fechas
        patron_fecha = r"(\d{1,2})\s*(?:de\s*)?([a-záéíóú]+)\s*(?:de[l]?\s*)?(\d{4})"
        
        match_inicio = re.search(r"fecha\s*(?:de\s*)?inicio.*?" + patron_fecha, texto_total, re.IGNORECASE)
        if match_inicio:
            info["fecha_inicio"] = f"{match_inicio.group(1)}/{match_inicio.group(2)}/{match_inicio.group(3)}"
        
        match_fin = re.search(r"fecha\s*(?:de\s*)?fin.*?" + patron_fecha, texto_total, re.IGNORECASE)
        if match_fin:
            info["fecha_fin"] = f"{match_fin.group(1)}/{match_fin.group(2)}/{match_fin.group(3)}"
        
        # Buscar monto
        match_monto = re.search(r"monto.*?S/?\.?\s*([\d,]+\.\d{2})", texto_total, re.IGNORECASE)
        if match_monto:
            info["monto"] = float(match_monto.group(1).replace(',', ''))
        
        # Verificar cláusula de penalidad
        info["tiene_clausula_penalidad"] = bool(re.search(
            r"penalidad|mora|retraso\s*injustificado", texto_total, re.IGNORECASE
        ))
        
        return info
    
    def _extraer_info_conformidad(self, documentos: List[DocumentoPDF]) -> Dict:
        """Extrae información de la conformidad relevante para penalidades"""
        info = {
            "fecha_entrega": None,
            "fecha_conformidad": None,
            "menciona_mora": False,
            "menciona_no_penalidad": False,
            "menciona_si_penalidad": False,
            "documento_fuente": None
        }
        
        for doc in documentos:
            nombre_lower = doc.nombre.lower()
            # Buscar en conformidad E informe técnico
            if any(kw in nombre_lower for kw in ["conformidad", "informe", "tecnico", "técnico"]):
                texto = doc.texto_completo
                
                # Buscar fecha de entrega
                match_entrega = re.search(
                    r"fecha.*?entrega.*?(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})", 
                    texto, re.IGNORECASE
                )
                if match_entrega:
                    info["fecha_entrega"] = match_entrega.group(1)
                
                # Buscar mención a mora/atraso
                if re.search(r"mora|retraso|atraso|fuera\s*de\s*plazo|despu[eé]s\s*del\s*plazo", texto, re.IGNORECASE):
                    info["menciona_mora"] = True
                    info["documento_fuente"] = doc.nombre
                
                # Patrones ampliados para NO aplica penalidad
                patrones_no_penalidad = [
                    r"no\s*(?:incurri[oó]|aplic[aó]|corresponde).*penalidad",
                    r"sin\s*(?:aplicaci[oó]n\s*de\s*)?penalidad",
                    r"cumpli[oó].*(?:dentro\s*del\s*)?plazo",
                    r"no\s*(?:ha\s*)?incurri[oó]\s*en\s*mora",
                    r"penalidad.*(?:cero|0\.00|no\s*aplica)"
                ]
                for patron in patrones_no_penalidad:
                    if re.search(patron, texto, re.IGNORECASE):
                        info["menciona_no_penalidad"] = True
                        info["documento_fuente"] = doc.nombre
                        break
                
                # Patrones ampliados para SÍ aplica penalidad
                patrones_si_penalidad = [
                    r"se\s*recomienda\s*aplicar\s*penalidad",
                    r"aplicar\s*(?:la\s*)?penalidad",
                    r"corresponde\s*(?:aplicar\s*)?penalidad",
                    r"c[aá]lculo\s*(?:de\s*)?penalidad",
                    r"monto\s*(?:de\s*)?(?:la\s*)?penalidad.*S/?\.?",
                    r"penalidad\s*(?:por\s*)?(?:mora|atraso)",
                    r"(?:descuento|deducci[oó]n)\s*(?:por\s*)?penalidad"
                ]
                for patron in patrones_si_penalidad:
                    if re.search(patron, texto, re.IGNORECASE):
                        info["menciona_si_penalidad"] = True
                        info["documento_fuente"] = doc.nombre
                        break
        
        return info
    
    def _analizar_mora(self, info_contrato: Dict, info_conformidad: Dict) -> AnalisisPenalidad:
        """
        Analiza si hay mora y calcula penalidad.
        
        REGLA: Si el informe/conformidad menciona explícitamente que SÍ o NO aplica,
        eso prevalece sobre el cálculo automático.
        """
        
        # 1. Si el informe indica explícitamente que SÍ aplica penalidad
        if info_conformidad.get("menciona_si_penalidad"):
            doc_fuente = info_conformidad.get("documento_fuente", "documento de conformidad")
            return AnalisisPenalidad(
                aplica_penalidad=True,
                tipo="MORA",
                dias_atraso=0,  # No calculamos días, confiamos en el informe
                monto_penalidad=0.0,  # Debe verificarse en el documento
                monto_base=info_contrato.get("monto", 0),
                justificacion=f"Penalidad documentada en {doc_fuente}",
                documentado=True
            )
        
        # 2. Si el informe indica explícitamente que NO aplica penalidad
        if info_conformidad.get("menciona_no_penalidad"):
            doc_fuente = info_conformidad.get("documento_fuente", "documento de conformidad")
            return AnalisisPenalidad(
                aplica_penalidad=False,
                tipo="NINGUNA",
                dias_atraso=0,
                monto_penalidad=0.0,
                monto_base=info_contrato.get("monto", 0),
                justificacion=f"No aplica penalidad según {doc_fuente}",
                documentado=True
            )
        
        # 3. Si menciona mora/atraso pero no dice explícitamente si aplica o no
        if info_conformidad.get("menciona_mora"):
            doc_fuente = info_conformidad.get("documento_fuente", "documento")
            self.incertidumbres.append(
                f"Se menciona mora/atraso en {doc_fuente} pero no se indica claramente si aplica penalidad"
            )
            return AnalisisPenalidad(
                aplica_penalidad=True,  # Por seguridad, asumir que podría aplicar
                tipo="POSIBLE_MORA",
                dias_atraso=0,
                monto_penalidad=0.0,
                monto_base=info_contrato.get("monto", 0),
                justificacion=f"Posible mora detectada en {doc_fuente}, requiere verificación",
                documentado=False  # No está claramente documentado
            )
        
        # 4. Intentar calcular días de atraso si hay fechas
        dias_atraso = 0
        # (Aquí se implementaría la lógica de cálculo de fechas si están disponibles)
        
        # 5. Si no podemos determinar, marcar incertidumbre
        if not info_contrato.get("plazo_dias") or not info_contrato.get("fecha_fin"):
            self.incertidumbres.append(
                "No se pudo determinar el plazo o fechas para calcular mora"
            )
            return AnalisisPenalidad(
                aplica_penalidad=False,
                tipo="INCERTIDUMBRE",
                dias_atraso=0,
                monto_penalidad=0.0,
                monto_base=info_contrato.get("monto", 0),
                justificacion="No hay suficiente información para determinar mora",
                documentado=False
            )
        
        # 6. Calcular penalidad si hay atraso detectado numéricamente
        monto_penalidad = 0.0
        if dias_atraso > 0:
            monto = info_contrato.get("monto", 0)
            plazo = info_contrato.get("plazo_dias", 1)
            
            penalidad_diaria = (self.PORCENTAJE_PENALIDAD * monto) / (self.FACTOR_F * plazo)
            monto_penalidad = penalidad_diaria * dias_atraso
            
            # Aplicar tope
            tope = monto * self.TOPE_PENALIDAD
            monto_penalidad = min(monto_penalidad, tope)
        
        return AnalisisPenalidad(
            aplica_penalidad=dias_atraso > 0,
            tipo="MORA" if dias_atraso > 0 else "NINGUNA",
            dias_atraso=dias_atraso,
            monto_penalidad=monto_penalidad,
            monto_base=info_contrato.get("monto", 0),
            justificacion=f"Atraso de {dias_atraso} días" if dias_atraso > 0 else "Sin atraso detectado",
            documentado=False
        )
    
    def _analizar_otras_penalidades(self, documentos: List[DocumentoPDF]) -> List[Dict]:
        """Analiza otras penalidades del contrato"""
        otras = []
        texto_total = " ".join([d.texto_completo for d in documentos])
        
        # Buscar tabla de otras penalidades
        if re.search(r"otras\s*penalidades|penalidades\s*adicionales", texto_total, re.IGNORECASE):
            # Extraer supuestos de penalidad
            patron = r"(?:EL CONTRATISTA|Si|Cuando).*?(no cumple|incumple).*?(UIT|soles)"
            matches = re.findall(patron, texto_total, re.IGNORECASE)
            
            for match in matches:
                otras.append({
                    "descripcion": "Otra penalidad detectada en contrato",
                    "requiere_verificacion": True
                })
        
        return otras
    
    def _verificar_documentacion_penalidad(self, documentos: List[DocumentoPDF]) -> bool:
        """
        Verifica si la penalidad (o su no aplicación) está documentada.
        
        Busca en documentos clave (conformidad, informe técnico) primero,
        luego en texto total si no encuentra.
        """
        # Buscar primero en documentos clave (conformidad / informe técnico)
        texto_docs_clave = ""
        for doc in documentos:
            nombre_lower = doc.nombre.lower()
            if any(kw in nombre_lower for kw in ["conformidad", "informe", "tecnico", "técnico"]):
                texto_docs_clave += " " + doc.texto_completo
        
        # Si no hay docs clave, usar todo
        if not texto_docs_clave.strip():
            texto_docs_clave = " ".join([d.texto_completo for d in documentos])
        
        # Patrones ampliados para detectar documentación de penalidad
        # Incluye tanto "aplica" como "no aplica"
        patrones_documentacion = [
            # NO aplica penalidad
            r"no\s*(?:incurri[oó]|aplic[aó]|corresponde).*penalidad",
            r"sin\s*(?:aplicaci[oó]n\s*de\s*)?penalidad",
            r"penalidad.*(?:cero|0\.00|no\s*aplica)",
            r"no\s*(?:ha\s*)?incurri[oó]\s*en\s*mora",
            r"(?:cumpli[oó]|entreg[oó]).*(?:dentro\s*del\s*)?plazo",
            r"no\s*existe\s*(?:atraso|mora|penalidad)",
            r"exento\s*de\s*penalidad",
            
            # SÍ aplica penalidad (también es documentación válida)
            r"se\s*recomienda\s*aplicar\s*penalidad",
            r"aplicar\s*(?:la\s*)?penalidad",
            r"penalidad\s*(?:a\s*)?aplic(?:ar|ada)",
            r"penalidad\s*(?:por\s*)?(?:mora|atraso|retraso)",
            r"corresponde\s*(?:aplicar\s*)?penalidad",
            r"c[aá]lculo\s*(?:de\s*)?penalidad",
            r"monto\s*(?:de\s*)?(?:la\s*)?penalidad",
            r"penalidad\s*(?:de\s*)?S/?\.?\s*[\d,]+",
            r"(?:descuento|deducci[oó]n)\s*(?:por\s*)?penalidad",
            r"d[ií]as?\s*de\s*(?:atraso|mora|retraso)",
            
            # Menciones genéricas que indican análisis de penalidad
            r"respecto\s*(?:a\s*)?(?:la\s*)?penalidad",
            r"en\s*cuanto\s*(?:a\s*)?(?:la\s*)?penalidad",
            r"sobre\s*(?:la\s*)?penalidad",
        ]
        
        for patron in patrones_documentacion:
            if re.search(patron, texto_docs_clave, re.IGNORECASE):
                return True
        
        return False
    
    def _detectar_tipo_penalidad(self, documentos: List[DocumentoPDF]) -> Dict:
        """
        Detecta si la penalidad aplica o no, y el tipo.
        
        Returns:
            Dict con claves: 'aplica', 'documentado', 'tipo', 'evidencia'
        """
        resultado = {
            "aplica": None,  # True/False/None (indeterminado)
            "documentado": False,
            "tipo": "INDETERMINADO",
            "evidencia": []
        }
        
        # Buscar en documentos clave
        for doc in documentos:
            nombre_lower = doc.nombre.lower()
            if any(kw in nombre_lower for kw in ["conformidad", "informe", "tecnico", "técnico"]):
                texto = doc.texto_completo
                
                # Patrones que indican SÍ aplica
                if re.search(r"se\s*recomienda\s*aplicar\s*penalidad|aplicar\s*(?:la\s*)?penalidad|corresponde\s*(?:aplicar\s*)?penalidad", texto, re.IGNORECASE):
                    resultado["aplica"] = True
                    resultado["documentado"] = True
                    resultado["tipo"] = "MORA"
                    resultado["evidencia"].append({
                        "archivo": doc.nombre,
                        "tipo": "RECOMIENDA_APLICAR"
                    })
                
                # Patrones que indican NO aplica
                elif re.search(r"sin\s*(?:aplicaci[oó]n\s*de\s*)?penalidad|no\s*(?:incurri[oó]|aplic[aó]|corresponde).*penalidad|cumpli[oó].*plazo", texto, re.IGNORECASE):
                    resultado["aplica"] = False
                    resultado["documentado"] = True
                    resultado["tipo"] = "NINGUNA"
                    resultado["evidencia"].append({
                        "archivo": doc.nombre,
                        "tipo": "NO_APLICA"
                    })
        
        return resultado
    
    def _verificar_calculo_penalidad(self, documentos: List[DocumentoPDF], analisis: AnalisisPenalidad):
        """Verifica si el cálculo de penalidad aplicado es correcto"""
        texto_total = " ".join([d.texto_completo for d in documentos])
        
        # Buscar monto de penalidad aplicado
        match = re.search(r"penalidad.*?S/?\.?\s*([\d,]+\.\d{2})", texto_total, re.IGNORECASE)
        if match:
            monto_aplicado = float(match.group(1).replace(',', ''))
            
            # Comparar con cálculo
            diferencia = abs(monto_aplicado - analisis.monto_penalidad)
            if diferencia > 1.0:  # Tolerancia de S/ 1.00
                self.observaciones.append(Observacion(
                    nivel=NivelObservacion.MAYOR,
                    agente=self.AGENTE_NOMBRE,
                    descripcion=f"Diferencia en cálculo de penalidad",
                    evidencia=f"Aplicado: S/ {monto_aplicado:.2f}, Calculado: S/ {analisis.monto_penalidad:.2f}",
                    accion_requerida="Verificar cálculo de penalidad",
                    area_responsable="Logística"
                ))


def ejecutar_agente(documentos: List[DocumentoPDF]) -> ResultadoAgente:
    """Función helper para ejecutar el agente"""
    agente = AgentePenalidades()
    return agente.analizar(documentos)



