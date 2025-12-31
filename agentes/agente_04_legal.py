# -*- coding: utf-8 -*-
"""
AGENTE 04 — LEGAL / DIRECTIVAS
==============================
Aplica estrictamente la directiva o pauta correspondiente:
- Viáticos
- Caja Chica
- Encargos
- Pautas (pagos a proveedores)

Detecta incumplimientos normativos.
"""

import os
import sys
import re
from typing import List, Dict, Optional
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    ResultadoAgente, Observacion, NivelObservacion,
    NaturalezaExpediente, TipoProcedimiento, DIRECTIVA_PAUTAS,
    DIRECTIVA_VIATICOS, DIRECTIVA_CAJA_CHICA, DIRECTIVA_ENCARGO,
    LIMITES_NORMATIVOS
)
from utils.pdf_extractor import DocumentoPDF, PDFExtractor, extraer_todos_pdfs


@dataclass
class RequisitoDocumental:
    """Requisito documental según directiva"""
    nombre: str
    obligatorio: bool
    descripcion: str
    patron_busqueda: str


class AgenteLegal:
    """
    Agente 04: Valida cumplimiento de directivas y pautas
    """
    
    AGENTE_ID = "AG04"
    AGENTE_NOMBRE = "Legal / Directivas"
    
    # Requisitos por tipo de procedimiento (según PAUTAS)
    REQUISITOS_CONCURSO_PUBLICO = [
        RequisitoDocumental("TDR", True, "Términos de Referencia", r"t[eé]rminos?\s*de\s*referencia|TDR"),
        RequisitoDocumental("Contrato", True, "Contrato suscrito", r"contrato\s*n[°º]"),
        RequisitoDocumental("Orden de Servicio", True, "Orden de servicio original", r"orden\s*de\s*servicio|O\.?S\.?"),
        RequisitoDocumental("CCI", True, "Carta de autorización CCI", r"CCI|cuenta\s*interbancaria"),
        RequisitoDocumental("Comprobante Pago", True, "Comprobante de pago SUNAT", r"factura|boleta|comprobante"),
        RequisitoDocumental("Conformidad", True, "Conformidad del área usuaria", r"conformidad"),
        RequisitoDocumental("Garantía", False, "Garantía según corresponda", r"garant[ií]a|carta\s*fianza"),
        RequisitoDocumental("Penalidades", False, "Control de penalidades", r"penalidad|mora"),
    ]
    
    REQUISITOS_LICITACION_PUBLICA = [
        RequisitoDocumental("EETT", True, "Especificaciones Técnicas", r"especificaciones?\s*t[eé]cnicas?|EETT"),
        RequisitoDocumental("Contrato", True, "Contrato suscrito", r"contrato\s*n[°º]"),
        RequisitoDocumental("Orden de Compra", True, "Orden de compra original", r"orden\s*de\s*compra|O\.?C\.?"),
        RequisitoDocumental("CCI", True, "Carta de autorización CCI", r"CCI|cuenta\s*interbancaria"),
        RequisitoDocumental("Comprobante Pago", True, "Comprobante de pago SUNAT", r"factura|boleta"),
        RequisitoDocumental("Conformidad Almacén", True, "Conformidad de ingreso a almacén", r"almac[eé]n|ingreso"),
        RequisitoDocumental("Guía Remisión", True, "Guía de remisión", r"gu[ií]a\s*de\s*remisi[oó]n"),
        RequisitoDocumental("Garantía", True, "Garantía de fiel cumplimiento", r"garant[ií]a|carta\s*fianza"),
    ]
    
    REQUISITOS_MENOR_8_UIT = [
        RequisitoDocumental("TDR/EETT", True, "Términos de Referencia o EETT", r"t[eé]rminos|especificaciones"),
        RequisitoDocumental("Cotización", True, "Cotización ganadora", r"cotizaci[oó]n"),
        RequisitoDocumental("Orden", True, "Orden de servicio/compra", r"orden\s*de\s*(servicio|compra)"),
        RequisitoDocumental("CCI", True, "Carta de autorización CCI", r"CCI|cuenta\s*interbancaria"),
        RequisitoDocumental("Comprobante Pago", True, "Comprobante de pago SUNAT", r"factura|boleta"),
        RequisitoDocumental("Conformidad", True, "Conformidad del área usuaria", r"conformidad"),
    ]
    
    REQUISITOS_VIATICOS = [
        RequisitoDocumental("Planilla Viáticos", True, "Planilla de viáticos", r"planilla\s*de\s*vi[aá]ticos|PV"),
        RequisitoDocumental("Autorización", True, "Autorización de comisión", r"autorizaci[oó]n|comisi[oó]n\s*de\s*servicio"),
        RequisitoDocumental("Rendición", True, "Rendición de viáticos", r"rendici[oó]n"),
        RequisitoDocumental("Anexo 3", True, "Anexo 3 - Gastos", r"anexo\s*3|gastos"),
        RequisitoDocumental("Comprobantes", True, "Comprobantes de pago", r"factura|boleta|ticket"),
        RequisitoDocumental("DJ", False, "Declaración jurada", r"declaraci[oó]n\s*jurada|DJ"),
    ]
    
    def __init__(self):
        self.observaciones: List[Observacion] = []
        self.incertidumbres: List[str] = []
        self.datos_extraidos: Dict = {}
        self.directiva_aplicada: str = ""
        
    def analizar(
        self, 
        documentos: List[DocumentoPDF], 
        naturaleza: NaturalezaExpediente,
        tipo_procedimiento: TipoProcedimiento
    ) -> ResultadoAgente:
        """
        Analiza el cumplimiento de la directiva aplicable
        """
        self.observaciones = []
        self.incertidumbres = []
        
        # Determinar directiva aplicable
        self.directiva_aplicada = self._determinar_directiva(naturaleza)
        
        # Obtener requisitos aplicables
        requisitos = self._obtener_requisitos(naturaleza, tipo_procedimiento)
        
        # Verificar cumplimiento de cada requisito
        cumplimiento = self._verificar_requisitos(documentos, requisitos)
        
        # Verificar límites normativos
        verificacion_limites = self._verificar_limites(documentos, naturaleza)
        
        # Generar observaciones por incumplimientos
        for req, estado in cumplimiento.items():
            if not estado["cumple"] and estado["obligatorio"]:
                self.observaciones.append(Observacion(
                    nivel=NivelObservacion.CRITICA if estado["obligatorio"] else NivelObservacion.MAYOR,
                    agente=self.AGENTE_NOMBRE,
                    descripcion=f"Requisito faltante: {req}",
                    evidencia=f"No se encontró {estado['descripcion']} en el expediente",
                    accion_requerida=f"Adjuntar {estado['descripcion']}",
                    area_responsable="Área Usuaria / Logística"
                ))
        
        # Agregar observaciones de límites
        self.observaciones.extend(verificacion_limites)
        
        self.datos_extraidos = {
            "directiva_aplicada": self.directiva_aplicada,
            "naturaleza": naturaleza.value,
            "tipo_procedimiento": tipo_procedimiento.value,
            "requisitos_verificados": len(requisitos),
            "requisitos_cumplidos": sum(1 for v in cumplimiento.values() if v["cumple"]),
            "cumplimiento_detalle": cumplimiento
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
    
    def _determinar_directiva(self, naturaleza: NaturalezaExpediente) -> str:
        """Determina la directiva aplicable según naturaleza"""
        mapeo = {
            NaturalezaExpediente.VIATICOS: "Directiva de Viáticos 011-2020",
            NaturalezaExpediente.CAJA_CHICA: "Directiva de Caja Chica 0023-2025",
            NaturalezaExpediente.ENCARGO: "Directiva de Encargos 261-2018",
            NaturalezaExpediente.PAGO_PROVEEDOR: "Pautas para Remisión de Expedientes de Pago",
            NaturalezaExpediente.CONTRATO: "Pautas para Remisión de Expedientes de Pago",
            NaturalezaExpediente.ORDEN_SERVICIO: "Pautas para Remisión de Expedientes de Pago",
            NaturalezaExpediente.ORDEN_COMPRA: "Pautas para Remisión de Expedientes de Pago",
        }
        return mapeo.get(naturaleza, "Pautas para Remisión de Expedientes de Pago")
    
    def _obtener_requisitos(
        self, 
        naturaleza: NaturalezaExpediente,
        tipo_procedimiento: TipoProcedimiento
    ) -> List[RequisitoDocumental]:
        """Obtiene los requisitos según naturaleza y procedimiento"""
        
        if naturaleza == NaturalezaExpediente.VIATICOS:
            return self.REQUISITOS_VIATICOS
        
        # Para pagos a proveedores, depende del tipo de procedimiento
        if tipo_procedimiento in [TipoProcedimiento.CONCURSO_PUBLICO]:
            return self.REQUISITOS_CONCURSO_PUBLICO
        elif tipo_procedimiento == TipoProcedimiento.LICITACION_PUBLICA:
            return self.REQUISITOS_LICITACION_PUBLICA
        elif tipo_procedimiento == TipoProcedimiento.MENOR_8_UIT:
            return self.REQUISITOS_MENOR_8_UIT
        else:
            # Por defecto, usar requisitos de menor a 8 UIT
            return self.REQUISITOS_MENOR_8_UIT
    
    def _verificar_requisitos(
        self, 
        documentos: List[DocumentoPDF],
        requisitos: List[RequisitoDocumental]
    ) -> Dict[str, Dict]:
        """Verifica el cumplimiento de cada requisito"""
        cumplimiento = {}
        texto_completo = " ".join([d.texto_completo for d in documentos])
        nombres_archivos = " ".join([d.nombre for d in documentos])
        texto_total = texto_completo + " " + nombres_archivos
        
        for req in requisitos:
            encontrado = bool(re.search(req.patron_busqueda, texto_total, re.IGNORECASE))
            cumplimiento[req.nombre] = {
                "cumple": encontrado,
                "obligatorio": req.obligatorio,
                "descripcion": req.descripcion
            }
        
        return cumplimiento
    
    def _verificar_limites(
        self, 
        documentos: List[DocumentoPDF],
        naturaleza: NaturalezaExpediente
    ) -> List[Observacion]:
        """Verifica límites normativos según naturaleza"""
        observaciones = []
        texto_completo = " ".join([d.texto_completo for d in documentos])
        
        if naturaleza == NaturalezaExpediente.VIATICOS:
            # Verificar topes de viáticos
            observaciones.extend(self._verificar_topes_viaticos(texto_completo))
        
        # Verificar si corresponde detracción
        montos = re.findall(r'S/?\.?\s*([\d,]+\.\d{2})', texto_completo)
        if montos:
            try:
                monto_mayor = max(float(m.replace(',', '')) for m in montos)
                if monto_mayor > LIMITES_NORMATIVOS["monto_minimo_detraccion"]:
                    # Verificar si hay mención a detracción
                    if not re.search(r'detracci[oó]n|cuenta\s*de\s*detracci[oó]n', texto_completo, re.IGNORECASE):
                        observaciones.append(Observacion(
                            nivel=NivelObservacion.MAYOR,
                            agente=self.AGENTE_NOMBRE,
                            descripcion=f"Monto supera S/ 700 - Verificar si corresponde detracción",
                            evidencia=f"Monto detectado: S/ {monto_mayor:,.2f}",
                            accion_requerida="Verificar si el servicio está sujeto a detracción y si se consignó la cuenta",
                            area_responsable="Control Previo"
                        ))
            except:
                pass
        
        return observaciones
    
    def _verificar_topes_viaticos(self, texto: str) -> List[Observacion]:
        """Verifica topes específicos de viáticos"""
        observaciones = []
        
        # Buscar montos diarios
        # Esta es una verificación heurística
        patron_dia = r'(\d+)\s*d[ií]as?.*?S/?\.?\s*([\d,]+\.\d{2})'
        matches = re.findall(patron_dia, texto, re.IGNORECASE)
        
        for dias, monto in matches:
            try:
                dias_num = int(dias)
                monto_num = float(monto.replace(',', ''))
                monto_por_dia = monto_num / dias_num if dias_num > 0 else 0
                
                tope_diario = LIMITES_NORMATIVOS["viaticos_lima_dia"]
                if monto_por_dia > tope_diario:
                    observaciones.append(Observacion(
                        nivel=NivelObservacion.MAYOR,
                        agente=self.AGENTE_NOMBRE,
                        descripcion=f"Posible exceso en viático diario",
                        evidencia=f"Monto por día: S/ {monto_por_dia:.2f} (tope: S/ {tope_diario})",
                        accion_requerida="Verificar cálculo de viáticos contra directiva",
                        area_responsable="Control Previo"
                    ))
            except:
                pass
        
        return observaciones


def ejecutar_agente(
    documentos: List[DocumentoPDF],
    naturaleza: NaturalezaExpediente,
    tipo_procedimiento: TipoProcedimiento
) -> ResultadoAgente:
    """Función helper para ejecutar el agente"""
    agente = AgenteLegal()
    return agente.analizar(documentos, naturaleza, tipo_procedimiento)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    carpeta = r"C:\Users\hanns\Downloads"
    documentos = extraer_todos_pdfs(carpeta)
    
    print("=" * 80)
    print("AGENTE 04 — LEGAL / DIRECTIVAS")
    print("=" * 80)
    
    # Simular clasificación previa
    naturaleza = NaturalezaExpediente.PAGO_PROVEEDOR
    tipo_proc = TipoProcedimiento.CONCURSO_PUBLICO
    
    resultado = ejecutar_agente(documentos, naturaleza, tipo_proc)
    
    print(f"\n✅ Éxito: {resultado.exito}")
    print(f"📋 Directiva aplicada: {resultado.datos_extraidos.get('directiva_aplicada', 'N/A')}")
    print(f"📊 Requisitos verificados: {resultado.datos_extraidos.get('requisitos_verificados', 0)}")
    print(f"✓ Requisitos cumplidos: {resultado.datos_extraidos.get('requisitos_cumplidos', 0)}")
    
    if resultado.observaciones:
        print(f"\n⚠️ Observaciones:")
        for obs in resultado.observaciones:
            print(f"   [{obs.nivel.value}] {obs.descripcion}")



