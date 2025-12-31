# -*- coding: utf-8 -*-
"""
EXPORTADOR JSON/TXT ESTRUCTURADO (ESTÁNDAR PROBATORIO)
======================================================
Convierte los hallazgos del sistema a formato JSON/TXT con evidencia probatoria:
- archivo + pagina + snippet + confianza + metodo_extraccion + regla_aplicada
"""

import os
import sys
import json
from typing import List, Dict, Any
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    InformeControlPrevio, Observacion, NivelObservacion,
    DecisionFinal, NaturalezaExpediente, EvidenciaProbatoria
)


class ExportadorProbatorio:
    """
    Exporta hallazgos en formato probatorio (JSON y TXT)
    """
    
    # Mapeo de impacto según tipo de hallazgo
    IMPACTOS = {
        "sinad": "Bloquea trazabilidad SIAF/SINAD",
        "siaf": "Inconsistencia con expediente SIAF",
        "ruc": "Posible pago a proveedor incorrecto",
        "contrato": "Referencia contractual inconsistente",
        "monto": "Diferencia en importes a pagar",
        "conformidad": "Incongruencia en documento de conformidad",
        "firma": "Validez de firma en cuestión",
        "penalidad": "Posible omisión de penalidad",
        "documento": "Expediente incompleto",
        "default": "Requiere verificación"
    }
    
    def __init__(self, informe: InformeControlPrevio):
        self.informe = informe
        
    def exportar_hallazgo(self, obs: Observacion) -> Dict[str, Any]:
        """
        Exporta un hallazgo con formato probatorio completo
        """
        # Obtener tipo de hallazgo
        tipo = self._detectar_tipo(obs.descripcion)
        
        # Base del hallazgo
        hallazgo = {
            "agente": self._normalizar_agente(obs.agente),
            "hallazgo": obs.descripcion,
            "severidad": obs.nivel.value,
            "impacto": self.IMPACTOS.get(tipo, self.IMPACTOS["default"]),
            "accion": obs.accion_requerida,
            "area_responsable": obs.area_responsable,
            "regla_aplicada": obs.regla_aplicada,
            "requiere_revision_humana": obs.requiere_revision_humana,
            "tipo": tipo,
            "bloquea_pago": obs.nivel == NivelObservacion.CRITICA
        }
        
        # Agregar evidencias probatorias
        if obs.evidencias:
            hallazgo["evidencias"] = [
                self._exportar_evidencia(ev) for ev in obs.evidencias
            ]
            # Evidencia principal para formato simplificado
            ev_principal = obs.evidencias[0]
            hallazgo["archivo"] = ev_principal.archivo
            hallazgo["pagina"] = ev_principal.pagina
            hallazgo["snippet"] = ev_principal.snippet[:200] if ev_principal.snippet else ""
            hallazgo["confianza"] = ev_principal.confianza
            hallazgo["metodo_extraccion"] = ev_principal.metodo_extraccion.value
        else:
            # Sin evidencia probatoria
            hallazgo["evidencias"] = []
            hallazgo["archivo"] = ""
            hallazgo["pagina"] = 0
            hallazgo["snippet"] = obs.evidencia or ""
            hallazgo["confianza"] = 0.0
            hallazgo["metodo_extraccion"] = "NO_DISPONIBLE"
        
        return hallazgo
    
    def _exportar_evidencia(self, ev: EvidenciaProbatoria) -> Dict[str, Any]:
        """Exporta una evidencia probatoria individual"""
        return {
            "archivo": ev.archivo,
            "pagina": ev.pagina,
            "valor_detectado": ev.valor_detectado,
            "valor_esperado": ev.valor_esperado,
            "snippet": ev.snippet[:200] if ev.snippet else "",
            "metodo_extraccion": ev.metodo_extraccion.value,
            "confianza": ev.confianza,
            "nivel_confianza": ev.nivel_confianza.value,
            "regla_aplicada": ev.regla_aplicada
        }
    
    def exportar_hallazgos(self) -> List[Dict[str, Any]]:
        """Exporta todos los hallazgos"""
        hallazgos = []
        
        # Todas las observaciones
        todas = (
            self.informe.observaciones_criticas +
            self.informe.observaciones_mayores +
            self.informe.observaciones_menores
        )
        
        for obs in todas:
            hallazgo = self.exportar_hallazgo(obs)
            hallazgos.append(hallazgo)
        
        return hallazgos
    
    def exportar_resumen(self) -> Dict[str, Any]:
        """Exporta resumen ejecutivo completo"""
        return {
            "metadata": {
                "fecha_analisis": self.informe.fecha_analisis,
                "expediente_sinad": self.informe.expediente_sinad,
                "sistema": "AG-EVIDENCE v2.0.0 (Estándar Probatorio)",
                "version_formato": "2.0"
            },
            "clasificacion": {
                "naturaleza": self.informe.naturaleza.value,
                "directiva_aplicada": self.informe.directiva_aplicada
            },
            "decision": {
                "resultado": self.informe.decision.value,
                "procede": self.informe.decision == DecisionFinal.PROCEDE,
                "bloquea_pago": self.informe.decision == DecisionFinal.NO_PROCEDE
            },
            "estadisticas": {
                "total_observaciones": (
                    len(self.informe.observaciones_criticas) +
                    len(self.informe.observaciones_mayores) +
                    len(self.informe.observaciones_menores)
                ),
                "criticas": len(self.informe.observaciones_criticas),
                "mayores": len(self.informe.observaciones_mayores),
                "menores": len(self.informe.observaciones_menores),
                "requieren_revision_humana": sum(
                    1 for obs in (
                        self.informe.observaciones_criticas +
                        self.informe.observaciones_mayores +
                        self.informe.observaciones_menores
                    ) if obs.requiere_revision_humana
                ),
                "riesgos_sunat": len(self.informe.riesgos_sunat)
            },
            "recomendacion": {
                "texto": self.informe.recomendacion_final,
                "accion_requerida": self.informe.accion_requerida,
                "area_responsable": self.informe.area_responsable
            },
            "hallazgos": self.exportar_hallazgos()
        }
    
    def generar_txt_probatorio(self) -> str:
        """Genera informe TXT con formato probatorio"""
        lineas = []
        
        # Encabezado
        lineas.append("=" * 100)
        lineas.append("INFORME DE CONTROL PREVIO (ESTÁNDAR PROBATORIO)")
        lineas.append("Sistema Multi-Agente de Revisión de Expedientes v2.0")
        lineas.append("=" * 100)
        
        # Metadatos
        lineas.append(f"\n📅 Fecha de análisis: {self.informe.fecha_analisis}")
        lineas.append(f"📋 Expediente SINAD: {self.informe.expediente_sinad}")
        lineas.append(f"📁 Naturaleza: {self.informe.naturaleza.value}")
        lineas.append(f"📖 Directiva aplicada: {self.informe.directiva_aplicada}")
        
        # Decisión
        lineas.append("\n" + "=" * 100)
        if self.informe.decision == DecisionFinal.PROCEDE:
            lineas.append("🟢 DECISIÓN: PROCEDE")
        elif self.informe.decision == DecisionFinal.PROCEDE_CON_OBSERVACIONES:
            lineas.append("🟡 DECISIÓN: PROCEDE CON OBSERVACIONES")
        else:
            lineas.append("🔴 DECISIÓN: NO PROCEDE")
        lineas.append("=" * 100)
        
        # Resumen ejecutivo
        lineas.append("\n📝 RESUMEN EJECUTIVO:")
        lineas.append("-" * 50)
        lineas.append(self.informe.resumen_ejecutivo)
        
        # Observaciones CRÍTICAS
        if self.informe.observaciones_criticas:
            lineas.append("\n🔴 OBSERVACIONES CRÍTICAS (Bloquean pago):")
            lineas.append("-" * 50)
            for i, obs in enumerate(self.informe.observaciones_criticas, 1):
                lineas.extend(self._formatear_observacion_txt(i, obs))
        
        # Observaciones MAYORES
        if self.informe.observaciones_mayores:
            lineas.append("\n🟡 OBSERVACIONES MAYORES (Subsanables):")
            lineas.append("-" * 50)
            for i, obs in enumerate(self.informe.observaciones_mayores, 1):
                lineas.extend(self._formatear_observacion_txt(i, obs))
        
        # Observaciones MENORES
        if self.informe.observaciones_menores:
            lineas.append("\n🟢 OBSERVACIONES MENORES / INFORMATIVAS:")
            lineas.append("-" * 50)
            for i, obs in enumerate(self.informe.observaciones_menores, 1):
                lineas.extend(self._formatear_observacion_txt(i, obs, reducido=True))
        
        # Recomendación final
        lineas.append("\n" + "=" * 100)
        lineas.append("📋 RECOMENDACIÓN FINAL:")
        lineas.append(self.informe.recomendacion_final)
        lineas.append(f"\n⚡ Acción requerida: {self.informe.accion_requerida}")
        lineas.append(f"👤 Área responsable: {self.informe.area_responsable}")
        lineas.append("=" * 100)
        
        return "\n".join(lineas)
    
    def _formatear_observacion_txt(
        self, 
        num: int, 
        obs: Observacion, 
        reducido: bool = False
    ) -> List[str]:
        """Formatea una observación para TXT con evidencia probatoria"""
        lineas = []
        
        # Descripción
        flag_revision = "⚠️ [REQUIERE REVISIÓN HUMANA] " if obs.requiere_revision_humana else ""
        lineas.append(f"\n{num}. {flag_revision}{obs.descripcion}")
        
        if reducido:
            return lineas
        
        # Regla aplicada
        if obs.regla_aplicada:
            lineas.append(f"   📏 Regla: {obs.regla_aplicada}")
        
        # Evidencias probatorias (NUEVO FORMATO)
        if obs.evidencias:
            lineas.append("   📎 Evidencia:")
            for ev in obs.evidencias[:3]:  # Máximo 3
                lineas.append(f"      • {ev.archivo} pág. {ev.pagina} -> \"{ev.snippet[:80]}...\"")
                lineas.append(f"        Método: {ev.metodo_extraccion.value} | Confianza: {ev.nivel_confianza.value} ({ev.confianza:.0%})")
                if ev.valor_detectado:
                    lineas.append(f"        Valor detectado: {ev.valor_detectado}")
        else:
            lineas.append(f"   📎 Evidencia: {obs.evidencia or 'Sin evidencia específica'}")
        
        # Acción requerida
        lineas.append(f"   ⚡ Acción: {obs.accion_requerida}")
        lineas.append(f"   👤 Responsable: {obs.area_responsable}")
        
        return lineas
    
    def _detectar_tipo(self, descripcion: str) -> str:
        """Detecta el tipo de hallazgo desde la descripción"""
        desc_lower = descripcion.lower()
        
        if "sinad" in desc_lower:
            return "sinad"
        elif "siaf" in desc_lower:
            return "siaf"
        elif "ruc" in desc_lower:
            return "ruc"
        elif "contrato" in desc_lower:
            return "contrato"
        elif "monto" in desc_lower:
            return "monto"
        elif "conformidad" in desc_lower:
            return "conformidad"
        elif "firma" in desc_lower:
            return "firma"
        elif "penalidad" in desc_lower:
            return "penalidad"
        elif "faltante" in desc_lower or "documento" in desc_lower:
            return "documento"
        else:
            return "otro"
    
    def _normalizar_agente(self, agente: str) -> str:
        """Normaliza el nombre del agente a formato snake_case"""
        mapeo = {
            "Clasificador de Naturaleza": "clasificador_naturaleza",
            "OCR Avanzado": "ocr_avanzado",
            "Coherencia Documental": "coherencia_documental",
            "Legal / Directivas": "legal_directivas",
            "Firmas y Competencia": "firmas_competencia",
            "Integridad del Expediente": "integridad_expediente",
            "Penalidades": "penalidades",
            "SUNAT Público (Experimental)": "sunat_publico",
            "Decisor Final": "decisor_final"
        }
        return mapeo.get(agente, agente.lower().replace(" ", "_"))
    
    def guardar_json(self, ruta: str = None) -> str:
        """Guarda el resumen completo en archivo JSON"""
        if ruta is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre = f"control_previo_{timestamp}.json"
            ruta = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "output",
                nombre
            )
        
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        
        datos = self.exportar_resumen()
        
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        
        return ruta
    
    def guardar_txt(self, ruta: str = None) -> str:
        """Guarda el informe en formato TXT probatorio"""
        if ruta is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre = f"control_previo_{timestamp}.txt"
            ruta = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "output",
                nombre
            )
        
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        
        texto = self.generar_txt_probatorio()
        
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(texto)
        
        return ruta


def exportar_informe_json(informe: InformeControlPrevio, ruta: str = None) -> str:
    """Función helper para exportar informe a JSON"""
    exportador = ExportadorProbatorio(informe)
    return exportador.guardar_json(ruta)


def exportar_informe_txt(informe: InformeControlPrevio, ruta: str = None) -> str:
    """Función helper para exportar informe a TXT probatorio"""
    exportador = ExportadorProbatorio(informe)
    return exportador.guardar_txt(ruta)


# Mantener compatibilidad con versión anterior
ExportadorJSON = ExportadorProbatorio
