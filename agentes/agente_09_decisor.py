# -*- coding: utf-8 -*-
"""
AGENTE 09 — DECISOR FINAL
=========================
Consolida hallazgos de todos los agentes.
Determina:
- PROCEDE
- PROCEDE CON OBSERVACIONES
- NO PROCEDE (bloquea pago)

Genera informe estructurado de Control Previo.
"""

import os
import sys
from typing import List, Dict
from datetime import datetime
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    ResultadoAgente, Observacion, NivelObservacion,
    DecisionFinal, InformeControlPrevio, NaturalezaExpediente
)


class AgenteDecisor:
    """
    Agente 09: Consolida resultados y genera decisión final
    """
    
    AGENTE_ID = "AG09"
    AGENTE_NOMBRE = "Decisor Final"
    
    def __init__(self):
        self.observaciones: List[Observacion] = []
        self.datos_extraidos: Dict = {}
        
    def decidir(
        self,
        resultados_agentes: List[ResultadoAgente],
        naturaleza: NaturalezaExpediente,
        directiva_aplicada: str
    ) -> InformeControlPrevio:
        """
        Consolida todos los resultados y genera el informe final
        """
        # Consolidar todas las observaciones
        todas_observaciones = []
        for resultado in resultados_agentes:
            todas_observaciones.extend(resultado.observaciones)
        
        # Clasificar observaciones por nivel
        criticas = [o for o in todas_observaciones if o.nivel == NivelObservacion.CRITICA]
        mayores = [o for o in todas_observaciones if o.nivel == NivelObservacion.MAYOR]
        menores = [o for o in todas_observaciones if o.nivel == NivelObservacion.MENOR]
        informativas = [o for o in todas_observaciones if o.nivel == NivelObservacion.INFORMATIVA]
        
        # Determinar decisión
        decision = self._determinar_decision(criticas, mayores)
        
        # Generar resumen ejecutivo
        resumen = self._generar_resumen(resultados_agentes, decision, criticas, mayores)
        
        # Extraer riesgos SUNAT
        riesgos_sunat = self._extraer_riesgos_sunat(resultados_agentes)
        
        # Determinar acción requerida y área responsable
        accion, area = self._determinar_accion(decision, criticas, mayores)
        
        # Extraer SINAD del expediente
        sinad = self._extraer_sinad(resultados_agentes)
        
        return InformeControlPrevio(
            fecha_analisis=datetime.now().strftime("%d/%m/%Y %H:%M"),
            expediente_sinad=sinad,
            naturaleza=naturaleza,
            directiva_aplicada=directiva_aplicada,
            resumen_ejecutivo=resumen,
            observaciones_criticas=criticas,
            observaciones_mayores=mayores,
            observaciones_menores=menores + informativas,
            riesgos_sunat=riesgos_sunat,
            decision=decision,
            recomendacion_final=self._generar_recomendacion(decision),
            accion_requerida=accion,
            area_responsable=area,
            resultados_agentes=resultados_agentes
        )
    
    def _determinar_decision(
        self, 
        criticas: List[Observacion],
        mayores: List[Observacion]
    ) -> DecisionFinal:
        """Determina la decisión final según observaciones"""
        
        if criticas:
            return DecisionFinal.NO_PROCEDE
        elif mayores:
            return DecisionFinal.PROCEDE_CON_OBSERVACIONES
        else:
            return DecisionFinal.PROCEDE
    
    def _generar_resumen(
        self,
        resultados: List[ResultadoAgente],
        decision: DecisionFinal,
        criticas: List[Observacion],
        mayores: List[Observacion]
    ) -> str:
        """Genera el resumen ejecutivo"""
        
        lineas = []
        
        # Estado general
        if decision == DecisionFinal.PROCEDE:
            lineas.append("✅ El expediente cumple con los requisitos para el trámite de devengado.")
        elif decision == DecisionFinal.PROCEDE_CON_OBSERVACIONES:
            lineas.append("⚠️ El expediente puede proceder con subsanación de observaciones.")
            lineas.append(f"   Se detectaron {len(mayores)} observaciones mayores a subsanar.")
        else:
            lineas.append("❌ El expediente NO PROCEDE por observaciones críticas.")
            lineas.append(f"   Se detectaron {len(criticas)} observaciones que bloquean el pago.")
        
        # Resumen por agente
        lineas.append("\nResumen por módulo de verificación:")
        for r in resultados:
            estado = "✓" if r.exito else "✗"
            obs_count = len(r.observaciones)
            lineas.append(f"   {estado} {r.agente_nombre}: {obs_count} observaciones")
        
        return "\n".join(lineas)
    
    def _extraer_riesgos_sunat(self, resultados: List[ResultadoAgente]) -> List[str]:
        """Extrae riesgos informativos de SUNAT"""
        riesgos = []
        
        for r in resultados:
            if r.agente_id == "AG08":  # Agente SUNAT
                datos = r.datos_extraidos
                
                # Agregar resultados de RUC
                for ruc, info in datos.get('resultados_ruc', {}).items():
                    if info.get('estado') != 'ACTIVO':
                        riesgos.append(f"[INFORMATIVO] RUC {ruc}: Estado {info.get('estado')}")
                    if info.get('condicion') == 'NO HABIDO':
                        riesgos.append(f"[INFORMATIVO] RUC {ruc}: Condición NO HABIDO")
                
                # Agregar coherencia tributaria
                coherencia = datos.get('coherencia_tributaria', {})
                if not coherencia.get('coherente', True):
                    for obs in coherencia.get('observaciones', []):
                        riesgos.append(f"[INFORMATIVO] {obs}")
        
        return riesgos
    
    def _determinar_accion(
        self, 
        decision: DecisionFinal,
        criticas: List[Observacion],
        mayores: List[Observacion]
    ) -> tuple:
        """Determina acción requerida y área responsable"""
        
        if decision == DecisionFinal.NO_PROCEDE:
            # Agrupar por área responsable
            areas = set(o.area_responsable for o in criticas if o.area_responsable)
            area = " / ".join(areas) if areas else "Área Usuaria"
            
            acciones = list(set(o.accion_requerida for o in criticas))
            accion = "; ".join(acciones[:3])  # Máximo 3 acciones
            
            return accion, area
        
        elif decision == DecisionFinal.PROCEDE_CON_OBSERVACIONES:
            areas = set(o.area_responsable for o in mayores if o.area_responsable)
            area = " / ".join(areas) if areas else "Control Previo"
            
            acciones = list(set(o.accion_requerida for o in mayores))
            accion = "; ".join(acciones[:3])
            
            return accion, area
        
        else:
            return "Continuar con trámite de devengado", "Oficina de Tesorería"
    
    def _generar_recomendacion(self, decision: DecisionFinal) -> str:
        """Genera recomendación final según decisión"""
        
        recomendaciones = {
            DecisionFinal.PROCEDE: 
                "Se recomienda aprobar el devengado y continuar con el giro.",
            DecisionFinal.PROCEDE_CON_OBSERVACIONES:
                "Se recomienda subsanar las observaciones indicadas antes de aprobar el devengado. "
                "El expediente puede proceder una vez levantadas las observaciones mayores.",
            DecisionFinal.NO_PROCEDE:
                "Se recomienda DEVOLVER el expediente al área correspondiente para subsanación "
                "de las observaciones críticas antes de continuar con el trámite."
        }
        
        return recomendaciones.get(decision, "Revisar observaciones y determinar acción.")
    
    def _extraer_sinad(self, resultados: List[ResultadoAgente]) -> str:
        """Extrae el número de SINAD del expediente"""
        for r in resultados:
            datos = r.datos_extraidos
            
            # Buscar en datos del clasificador
            if 'datos_expediente' in datos:
                sinads = datos['datos_expediente'].get('sinad', [])
                if sinads:
                    return sinads[0]
            
            # Buscar en valores consolidados
            if 'valores_consolidados' in datos:
                sinads = datos['valores_consolidados'].get('sinad', set())
                if sinads:
                    return list(sinads)[0]
        
        return "NO IDENTIFICADO"


def generar_informe_texto(informe: InformeControlPrevio) -> str:
    """Genera el informe en formato texto legible"""
    
    lineas = []
    lineas.append("=" * 100)
    lineas.append("INFORME DE CONTROL PREVIO")
    lineas.append("Sistema Multi-Agente de Revisión de Expedientes")
    lineas.append("=" * 100)
    
    # Encabezado
    lineas.append(f"\n📅 Fecha de análisis: {informe.fecha_analisis}")
    lineas.append(f"📋 Expediente SINAD: {informe.expediente_sinad}")
    lineas.append(f"📁 Naturaleza: {informe.naturaleza.value}")
    lineas.append(f"📖 Directiva aplicada: {informe.directiva_aplicada}")
    
    # Decisión
    lineas.append("\n" + "=" * 100)
    if informe.decision == DecisionFinal.PROCEDE:
        lineas.append("🟢 DECISIÓN: PROCEDE")
    elif informe.decision == DecisionFinal.PROCEDE_CON_OBSERVACIONES:
        lineas.append("🟡 DECISIÓN: PROCEDE CON OBSERVACIONES")
    else:
        lineas.append("🔴 DECISIÓN: NO PROCEDE")
    lineas.append("=" * 100)
    
    # Resumen ejecutivo
    lineas.append("\n📝 RESUMEN EJECUTIVO:")
    lineas.append("-" * 50)
    lineas.append(informe.resumen_ejecutivo)
    
    # Observaciones críticas
    if informe.observaciones_criticas:
        lineas.append("\n🔴 OBSERVACIONES CRÍTICAS (Bloquean pago):")
        lineas.append("-" * 50)
        for i, obs in enumerate(informe.observaciones_criticas, 1):
            lineas.append(f"\n{i}. {obs.descripcion}")
            lineas.append(f"   📌 Evidencia: {obs.evidencia}")
            lineas.append(f"   ⚡ Acción: {obs.accion_requerida}")
            lineas.append(f"   👤 Responsable: {obs.area_responsable}")
    
    # Observaciones mayores
    if informe.observaciones_mayores:
        lineas.append("\n🟡 OBSERVACIONES MAYORES (Subsanables):")
        lineas.append("-" * 50)
        for i, obs in enumerate(informe.observaciones_mayores, 1):
            lineas.append(f"\n{i}. {obs.descripcion}")
            lineas.append(f"   📌 Evidencia: {obs.evidencia}")
            lineas.append(f"   ⚡ Acción: {obs.accion_requerida}")
    
    # Observaciones menores
    if informe.observaciones_menores:
        lineas.append("\n🟢 OBSERVACIONES MENORES / INFORMATIVAS:")
        lineas.append("-" * 50)
        for i, obs in enumerate(informe.observaciones_menores, 1):
            lineas.append(f"{i}. {obs.descripcion}")
    
    # Riesgos SUNAT
    if informe.riesgos_sunat:
        lineas.append("\n⚠️ RIESGOS TRIBUTARIOS (INFORMATIVOS):")
        lineas.append("-" * 50)
        for riesgo in informe.riesgos_sunat:
            lineas.append(f"   • {riesgo}")
    
    # Recomendación final
    lineas.append("\n" + "=" * 100)
    lineas.append("📋 RECOMENDACIÓN FINAL:")
    lineas.append(informe.recomendacion_final)
    lineas.append(f"\n⚡ Acción requerida: {informe.accion_requerida}")
    lineas.append(f"👤 Área responsable: {informe.area_responsable}")
    lineas.append("=" * 100)
    
    return "\n".join(lineas)


def ejecutar_decisor(
    resultados_agentes: List[ResultadoAgente],
    naturaleza: NaturalezaExpediente,
    directiva_aplicada: str
) -> InformeControlPrevio:
    """Función helper para ejecutar el decisor"""
    decisor = AgenteDecisor()
    return decisor.decidir(resultados_agentes, naturaleza, directiva_aplicada)



