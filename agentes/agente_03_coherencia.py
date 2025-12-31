# -*- coding: utf-8 -*-
"""
AGENTE 03 — COHERENCIA DOCUMENTAL (ESTÁNDAR PROBATORIO)
========================================================
Cruza y valida con evidencia específica:
- N° SINAD
- N° expediente
- N° orden de servicio / compra
- N° contrato
- RUC
- Montos

Cada hallazgo incluye: archivo, página, snippet, confianza, método, regla.
"""

import os
import sys
import re
from typing import List, Dict, Tuple, Set, Optional
from collections import defaultdict
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    ResultadoAgente, Observacion, NivelObservacion,
    EvidenciaProbatoria, OcurrenciaValor, MetodoExtraccion
)
from utils.pdf_extractor import DocumentoPDF


@dataclass
class ReglaValidacion:
    """Regla de validación aplicable"""
    id: str
    nombre: str
    descripcion: str
    campo: str
    nivel_critico: bool = True  # Si True, inconsistencia es CRÍTICA


# Reglas de validación definidas
REGLAS = {
    "R001": ReglaValidacion("R001", "SINAD_UNICO", "El número SINAD debe ser único en todo el expediente", "sinad", True),
    "R002": ReglaValidacion("R002", "RUC_UNICO", "El RUC del proveedor debe ser único (excepto MINEDU)", "ruc", True),
    "R003": ReglaValidacion("R003", "CONTRATO_CONSISTENTE", "El número de contrato debe ser consistente", "contrato", True),
    "R004": ReglaValidacion("R004", "OS_OC_CONSISTENTE", "Número de orden de servicio/compra consistente", "orden", False),
    "R005": ReglaValidacion("R005", "MONTO_CONSISTENTE", "Los montos deben coincidir entre documentos", "monto", False),
    "R006": ReglaValidacion("R006", "CONFORMIDAD_CONSISTENTE", "Número de conformidad consistente", "conformidad", False),
}


class AgenteCoherencia:
    """
    Agente 03: Valida coherencia documental con estándar probatorio
    """
    
    AGENTE_ID = "AG03"
    AGENTE_NOMBRE = "Coherencia Documental"
    
    # Patrones de extracción con contexto
    PATRONES = {
        "sinad": [
            (r"(?:E-?SINAD|SINAD|Sinad)[:\s]*(\d{5,8})", "SINAD_EXPLICITO"),
            (r"EXPEDIENTE[:\s]*\w+-INT-0?(\d+)", "EXPEDIENTE_INT"),
            (r"Sinad\s*0?(\d{5,7})", "SINAD_ARCHIVO"),
        ],
        "ruc": [
            (r"RUC[:\s]*(\d{11})", "RUC_EXPLICITO"),
            (r"\b(10\d{9}|20\d{9})\b", "RUC_PATRON"),
        ],
        "contrato": [
            (r"CONTRATO\s*N[°º]?\s*(\d{1,4}-\d{4}-[\w/\-]+)", "CONTRATO_COMPLETO"),
            (r"CONTRATO\s*N[°º]?\s*0?(\d{1,4}-\d{4})", "CONTRATO_CORTO"),
        ],
        "orden_servicio": [
            (r"(?:ORDEN\s*DE\s*SERVICIO|O\.?S\.?)\s*N[°º]?\s*0?(\d+(?:-\d+)?)", "OS_EXPLICITO"),
        ],
        "orden_compra": [
            (r"(?:ORDEN\s*DE\s*COMPRA|O\.?C\.?)\s*N[°º]?\s*0?(\d+(?:-\d+)?)", "OC_EXPLICITO"),
        ],
        "conformidad": [
            (r"CONFORMIDAD\s*N[°º]?\s*(\d+-\d+-[\w/\-]+)", "CONFORMIDAD_COMPLETA"),
            (r"CONFORMIDAD[:\s]*(\d+-\d+)", "CONFORMIDAD_CORTA"),
        ],
    }
    
    # RUCs a excluir (entidades propias)
    RUCS_EXCLUIDOS = {"20131370998", "20380795907"}  # MINEDU, UE026
    
    def __init__(self):
        self.observaciones: List[Observacion] = []
        self.incertidumbres: List[str] = []
        self.datos_extraidos: Dict = {}
        self.ocurrencias: Dict[str, List[OcurrenciaValor]] = defaultdict(list)
        
    def analizar(self, documentos: List[DocumentoPDF]) -> ResultadoAgente:
        """
        Analiza coherencia documental con evidencia probatoria
        """
        self.observaciones = []
        self.incertidumbres = []
        self.ocurrencias = defaultdict(list)
        
        # 1. Extraer todas las ocurrencias con detalle
        for doc in documentos:
            self._extraer_ocurrencias_documento(doc)
        
        # 2. Analizar inconsistencias por campo
        for campo in self.PATRONES.keys():
            self._analizar_campo(campo)
        
        # 3. Validar y degradar observaciones sin evidencia completa
        for obs in self.observaciones:
            obs.validar_y_degradar()
        
        self.datos_extraidos = {
            "total_ocurrencias": sum(len(v) for v in self.ocurrencias.values()),
            "ocurrencias_por_campo": {k: len(v) for k, v in self.ocurrencias.items()},
            "documentos_analizados": len(documentos),
            "observaciones_generadas": len(self.observaciones)
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
    
    def _extraer_ocurrencias_documento(self, doc: DocumentoPDF):
        """Extrae todas las ocurrencias de un documento con detalle de página"""
        for pagina in doc.paginas:
            texto = pagina.texto
            num_pagina = pagina.numero
            
            for campo, patrones in self.PATRONES.items():
                for patron, tipo_patron in patrones:
                    for match in re.finditer(patron, texto, re.IGNORECASE):
                        valor_original = match.group(1)
                        
                        # Filtrar RUCs excluidos
                        if campo == "ruc" and valor_original in self.RUCS_EXCLUIDOS:
                            continue
                        
                        # Extraer snippet de contexto (50 chars antes y después)
                        inicio = max(0, match.start() - 50)
                        fin = min(len(texto), match.end() + 50)
                        snippet = texto[inicio:fin].replace('\n', ' ').strip()
                        
                        ocurrencia = OcurrenciaValor(
                            archivo=doc.nombre,
                            pagina=num_pagina,
                            valor_original=valor_original,
                            valor_normalizado=self._normalizar_valor(campo, valor_original),
                            snippet=snippet,
                            posicion_inicio=match.start(),
                            confianza=self._calcular_confianza(pagina, tipo_patron),
                            metodo=MetodoExtraccion.REGEX
                        )
                        
                        self.ocurrencias[campo].append(ocurrencia)
    
    def _normalizar_valor(self, campo: str, valor: str) -> str:
        """Normaliza un valor para comparación, conservando original como evidencia"""
        valor = str(valor).strip()
        
        if campo in ["sinad", "siaf"]:
            # Remover ceros iniciales
            return valor.lstrip('0') or '0'
        elif campo == "contrato":
            # Normalizar formato de contrato
            return valor.replace(' ', '').upper()
        elif campo == "monto":
            # Normalizar monto
            return valor.replace(',', '').replace(' ', '')
        
        return valor
    
    def _calcular_confianza(self, pagina, tipo_patron: str) -> float:
        """Calcula nivel de confianza basado en calidad y tipo de patrón"""
        base = 1.0
        
        # Reducir por calidad de página
        if pagina.calidad_texto == "BAJA":
            base *= 0.6
        elif pagina.calidad_texto == "MEDIA":
            base *= 0.8
        
        # Patrones explícitos tienen mayor confianza
        if "EXPLICITO" in tipo_patron or "COMPLETO" in tipo_patron:
            base *= 1.0
        elif "CORTO" in tipo_patron:
            base *= 0.9
        else:
            base *= 0.85
        
        return round(base, 2)
    
    def _analizar_campo(self, campo: str):
        """Analiza inconsistencias en un campo específico"""
        ocurrencias = self.ocurrencias[campo]
        
        if not ocurrencias:
            return
        
        # Agrupar por valor normalizado
        por_valor = defaultdict(list)
        for oc in ocurrencias:
            por_valor[oc.valor_normalizado].append(oc)
        
        # Si hay más de un valor único, hay inconsistencia
        if len(por_valor) > 1:
            self._crear_observacion_inconsistencia(campo, por_valor)
    
    def _crear_observacion_inconsistencia(
        self, 
        campo: str, 
        por_valor: Dict[str, List[OcurrenciaValor]]
    ):
        """Crea una observación con evidencia probatoria completa"""
        
        # Obtener regla aplicable
        regla = self._obtener_regla(campo)
        
        # Determinar nivel
        nivel = NivelObservacion.CRITICA if regla.nivel_critico else NivelObservacion.MAYOR
        
        # Crear descripción
        valores_unicos = list(por_valor.keys())
        descripcion = f"Inconsistencia en {campo.upper()}: "
        
        if self._es_error_digitos(valores_unicos):
            descripcion += f"Error de dígitos detectado ({' vs '.join(valores_unicos)})"
        else:
            descripcion += f"Valores diferentes: {' vs '.join(valores_unicos[:5])}"
        
        # Crear evidencias probatorias
        evidencias = []
        for valor, ocurrencias in por_valor.items():
            # Tomar la ocurrencia con mayor confianza
            mejor = max(ocurrencias, key=lambda x: x.confianza)
            
            evidencia = EvidenciaProbatoria(
                archivo=mejor.archivo,
                pagina=mejor.pagina,
                valor_detectado=mejor.valor_original,
                valor_esperado=valores_unicos[0] if valor != valores_unicos[0] else "",
                snippet=mejor.snippet,
                metodo_extraccion=mejor.metodo,
                confianza=mejor.confianza,
                regla_aplicada=regla.id
            )
            evidencias.append(evidencia)
        
        # Crear observación
        observacion = Observacion(
            nivel=nivel,
            agente=self.AGENTE_NOMBRE,
            descripcion=descripcion,
            accion_requerida=self._generar_accion(campo, regla),
            area_responsable="Oficina de Logística",
            evidencias=evidencias,
            regla_aplicada=regla.id
        )
        
        # Generar evidencia legacy para compatibilidad
        observacion.evidencia = self._generar_evidencia_legacy(por_valor)
        
        self.observaciones.append(observacion)
    
    def _obtener_regla(self, campo: str) -> ReglaValidacion:
        """Obtiene la regla de validación para un campo"""
        mapeo = {
            "sinad": "R001",
            "ruc": "R002",
            "contrato": "R003",
            "orden_servicio": "R004",
            "orden_compra": "R004",
            "monto": "R005",
            "conformidad": "R006",
        }
        regla_id = mapeo.get(campo, "R001")
        return REGLAS.get(regla_id, REGLAS["R001"])
    
    def _generar_accion(self, campo: str, regla: ReglaValidacion) -> str:
        """Genera acción requerida según campo y regla"""
        acciones = {
            "sinad": "Corregir número SINAD en documento(s) incorrecto(s) y re-emitir",
            "ruc": "VERIFICAR RUC del proveedor - posible documento de otro expediente",
            "contrato": "Verificar y unificar número de contrato en todos los documentos",
            "orden_servicio": "Corregir número de orden de servicio",
            "orden_compra": "Corregir número de orden de compra",
            "monto": "Verificar montos - posible error de digitación",
            "conformidad": "Verificar número de conformidad",
        }
        return acciones.get(campo, f"Verificar {campo}")
    
    def _generar_evidencia_legacy(self, por_valor: Dict[str, List[OcurrenciaValor]]) -> str:
        """Genera string de evidencia para compatibilidad"""
        partes = []
        for valor, ocurrencias in list(por_valor.items())[:3]:
            archivos = list(set(oc.archivo for oc in ocurrencias))[:2]
            partes.append(f"{valor} en {archivos}")
        return str(partes)
    
    def _es_error_digitos(self, valores: List[str]) -> bool:
        """Detecta si la inconsistencia es por error de dígitos"""
        if len(valores) != 2:
            return False
        
        v1, v2 = sorted(valores, key=len)
        
        # Uno contiene al otro
        if v1 in v2 or v2 in v1:
            return True
        
        # Difieren en un solo carácter
        if abs(len(v1) - len(v2)) <= 1:
            diferencias = sum(1 for a, b in zip(v1.ljust(len(v2)), v2) if a != b)
            return diferencias <= 1
        
        return False


def ejecutar_agente(documentos: List[DocumentoPDF]) -> ResultadoAgente:
    """Función helper para ejecutar el agente"""
    agente = AgenteCoherencia()
    return agente.analizar(documentos)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    from utils.pdf_extractor import extraer_todos_pdfs
    
    carpeta = r"C:\Users\hanns\Downloads"
    documentos = extraer_todos_pdfs(carpeta)
    
    print("=" * 80)
    print("AGENTE 03 — COHERENCIA DOCUMENTAL (ESTÁNDAR PROBATORIO)")
    print("=" * 80)
    
    resultado = ejecutar_agente(documentos)
    
    print(f"\n✅ Éxito: {resultado.exito}")
    print(f"📄 Documentos analizados: {resultado.datos_extraidos.get('documentos_analizados', 0)}")
    print(f"⚠️ Observaciones: {len(resultado.observaciones)}")
    
    for obs in resultado.observaciones:
        print(f"\n[{obs.nivel.value}] {obs.descripcion}")
        print(f"   Regla: {obs.regla_aplicada}")
        print(f"   Requiere revisión humana: {obs.requiere_revision_humana}")
        if obs.evidencias:
            for ev in obs.evidencias[:2]:
                print(f"   📎 {ev.archivo} pág.{ev.pagina} -> \"{ev.snippet[:60]}...\"")
                print(f"      Valor: {ev.valor_detectado} | Confianza: {ev.confianza}")
