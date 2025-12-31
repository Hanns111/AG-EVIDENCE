# -*- coding: utf-8 -*-
"""
AGENTE 01 — CLASIFICADOR DE NATURALEZA
======================================
Detecta la naturaleza del expediente:
- Viáticos
- Caja Chica
- Encargo
- Pago a Proveedor (OS/OC/Contrato)
- Otro

Usa: nombres de archivos, contenido de proveído, TDR, conformidad.
"""

import os
import sys
import re
from typing import List, Dict, Tuple
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    NaturalezaExpediente, TipoProcedimiento, ResultadoAgente, 
    Observacion, NivelObservacion, KEYWORDS_NATURALEZA, DatosExpediente
)
from utils.pdf_extractor import DocumentoPDF, extraer_todos_pdfs


class AgenteClasificador:
    """
    Agente 01: Clasifica la naturaleza del expediente
    """
    
    AGENTE_ID = "AG01"
    AGENTE_NOMBRE = "Clasificador de Naturaleza"
    
    # Patrones para detectar tipo de procedimiento
    PATRONES_PROCEDIMIENTO = {
        TipoProcedimiento.LICITACION_PUBLICA: [
            r"licitaci[oó]n p[uú]blica", r"LP[- ]\d+", r"LP N[°º]"
        ],
        TipoProcedimiento.CONCURSO_PUBLICO: [
            r"concurso p[uú]blico", r"CP[- ]\d+", r"CPA[- ]\d+",
            r"concurso p[uú]blico abreviado"
        ],
        TipoProcedimiento.ADJUDICACION_SIMPLIFICADA: [
            r"adjudicaci[oó]n simplificada", r"AS[- ]\d+"
        ],
        TipoProcedimiento.SELECCION_CONSULTORES: [
            r"selecci[oó]n de consultores", r"consultor[ií]a individual"
        ],
        TipoProcedimiento.SUBASTA_INVERSA: [
            r"subasta inversa", r"SIE[- ]\d+"
        ],
        TipoProcedimiento.COMPARACION_PRECIOS: [
            r"comparaci[oó]n de precios", r"CM[- ]\d+"
        ],
        TipoProcedimiento.CONTRATACION_DIRECTA: [
            r"contrataci[oó]n directa", r"CD[- ]\d+"
        ],
        TipoProcedimiento.ACUERDO_MARCO: [
            r"acuerdo marco", r"cat[aá]logo electr[oó]nico", r"OC[- ]?AM"
        ],
        TipoProcedimiento.MENOR_8_UIT: [
            r"menor a 8 ?UIT", r"menores a ocho", r"< ?8 ?UIT",
            r"contrat[oa] menor"
        ]
    }
    
    def __init__(self):
        self.observaciones: List[Observacion] = []
        self.incertidumbres: List[str] = []
        self.datos_extraidos: Dict = {}
        
    def analizar(self, documentos: List[DocumentoPDF]) -> ResultadoAgente:
        """
        Analiza los documentos y determina la naturaleza del expediente
        """
        self.observaciones = []
        self.incertidumbres = []
        self.datos_extraidos = {}
        
        if not documentos:
            return ResultadoAgente(
                agente_id=self.AGENTE_ID,
                agente_nombre=self.AGENTE_NOMBRE,
                exito=False,
                errores=["No se encontraron documentos para analizar"]
            )
        
        # 1. Analizar nombres de archivos
        naturaleza_por_nombre = self._analizar_nombres_archivos(documentos)
        
        # 2. Analizar contenido de documentos
        naturaleza_por_contenido = self._analizar_contenido(documentos)
        
        # 3. Detectar tipo de procedimiento (si aplica)
        tipo_procedimiento = self._detectar_procedimiento(documentos)
        
        # 4. Determinar naturaleza final
        naturaleza_final = self._determinar_naturaleza_final(
            naturaleza_por_nombre, 
            naturaleza_por_contenido
        )
        
        # 5. Extraer datos básicos del expediente
        datos_expediente = self._extraer_datos_basicos(documentos)
        
        # Guardar resultados
        self.datos_extraidos = {
            "naturaleza": naturaleza_final.value,
            "tipo_procedimiento": tipo_procedimiento.value,
            "analisis_nombres": naturaleza_por_nombre,
            "analisis_contenido": naturaleza_por_contenido,
            "datos_expediente": datos_expediente,
            "total_documentos": len(documentos),
            "documentos_analizados": [d.nombre for d in documentos]
        }
        
        # Generar observaciones si hay incertidumbre
        if naturaleza_final == NaturalezaExpediente.NO_DETERMINADO:
            self.observaciones.append(Observacion(
                nivel=NivelObservacion.MAYOR,
                agente=self.AGENTE_NOMBRE,
                descripcion="No se pudo determinar la naturaleza del expediente",
                evidencia="Análisis de nombres y contenido no concluyente",
                accion_requerida="Verificar manualmente el tipo de expediente",
                area_responsable="Control Previo"
            ))
        
        return ResultadoAgente(
            agente_id=self.AGENTE_ID,
            agente_nombre=self.AGENTE_NOMBRE,
            exito=naturaleza_final != NaturalezaExpediente.NO_DETERMINADO,
            observaciones=self.observaciones,
            datos_extraidos=self.datos_extraidos,
            incertidumbres=self.incertidumbres
        )
    
    def _analizar_nombres_archivos(self, documentos: List[DocumentoPDF]) -> Dict[NaturalezaExpediente, int]:
        """Analiza los nombres de archivos para inferir naturaleza"""
        conteo = Counter()
        
        for doc in documentos:
            nombre_lower = doc.nombre.lower()
            
            for naturaleza, keywords in KEYWORDS_NATURALEZA.items():
                for keyword in keywords:
                    if keyword.lower() in nombre_lower:
                        conteo[naturaleza] += 1
                        break
        
        return dict(conteo)
    
    def _analizar_contenido(self, documentos: List[DocumentoPDF]) -> Dict[NaturalezaExpediente, int]:
        """Analiza el contenido de los documentos"""
        conteo = Counter()
        
        for doc in documentos:
            texto_lower = doc.texto_completo.lower()
            
            for naturaleza, keywords in KEYWORDS_NATURALEZA.items():
                peso = 0
                for keyword in keywords:
                    # Contar ocurrencias del keyword
                    ocurrencias = texto_lower.count(keyword.lower())
                    peso += ocurrencias
                
                if peso > 0:
                    conteo[naturaleza] += peso
        
        return dict(conteo)
    
    def _detectar_procedimiento(self, documentos: List[DocumentoPDF]) -> TipoProcedimiento:
        """Detecta el tipo de procedimiento de selección"""
        texto_completo = " ".join([d.texto_completo for d in documentos]).lower()
        
        for procedimiento, patrones in self.PATRONES_PROCEDIMIENTO.items():
            for patron in patrones:
                if re.search(patron, texto_completo, re.IGNORECASE):
                    return procedimiento
        
        return TipoProcedimiento.NO_DETERMINADO
    
    def _determinar_naturaleza_final(
        self, 
        por_nombre: Dict[NaturalezaExpediente, int],
        por_contenido: Dict[NaturalezaExpediente, int]
    ) -> NaturalezaExpediente:
        """Determina la naturaleza final combinando análisis"""
        
        # Combinar scores (contenido tiene más peso)
        scores_combinados = Counter()
        
        for nat, score in por_nombre.items():
            scores_combinados[nat] += score * 2  # Nombre tiene peso 2
        
        for nat, score in por_contenido.items():
            scores_combinados[nat] += score  # Contenido tiene peso 1
        
        if not scores_combinados:
            return NaturalezaExpediente.NO_DETERMINADO
        
        # Obtener el más común
        mas_comun = scores_combinados.most_common(1)[0]
        
        # Si hay muy pocas coincidencias, marcar incertidumbre
        if mas_comun[1] < 3:
            self.incertidumbres.append(
                f"Baja confianza en clasificación: {mas_comun[0].value} (score: {mas_comun[1]})"
            )
        
        return mas_comun[0]
    
    def _extraer_datos_basicos(self, documentos: List[DocumentoPDF]) -> Dict:
        """Extrae datos básicos identificables del expediente"""
        datos = {
            "sinad": [],
            "siaf": [],
            "ruc": [],
            "contrato": [],
            "orden_servicio": [],
            "orden_compra": [],
            "conformidad": [],
            "monto": []
        }
        
        patrones = {
            "sinad": [
                r"E-?SINAD[:\s]*(\d{5,8})",
                r"SINAD[:\s]*(\d{5,8})",
                r"EXPEDIENTE[:\s]*\w+-INT-(\d+)"
            ],
            "siaf": [
                r"SIAF[:\s]*(\d+)",
                r"EXP\.?\s*SIAF[:\s]*(\d+)"
            ],
            "ruc": [
                r"RUC[:\s]*(\d{11})"
            ],
            "contrato": [
                r"CONTRATO\s*N[°º]?\s*(\d+-\d+-\w+)",
                r"CONTRATO\s*N[°º]?\s*(\d+-\d+)"
            ],
            "orden_servicio": [
                r"ORDEN\s*DE\s*SERVICIO\s*N[°º]?\s*(\d+-\d+)",
                r"O/?S\s*N[°º]?\s*(\d+)"
            ],
            "orden_compra": [
                r"ORDEN\s*DE\s*COMPRA\s*N[°º]?\s*(\d+-\d+)",
                r"O/?C\s*N[°º]?\s*(\d+)"
            ],
            "conformidad": [
                r"CONFORMIDAD\s*N[°º]?\s*(\d+-\d+-\w+)",
                r"CONFORMIDAD[:\s]*(\d+-\d+)"
            ],
            "monto": [
                r"S/?\.?\s*([\d,]+\.\d{2})",
                r"MONTO[:\s]*S/?\.?\s*([\d,]+\.\d{2})"
            ]
        }
        
        for doc in documentos:
            texto = doc.texto_completo
            
            for campo, lista_patrones in patrones.items():
                for patron in lista_patrones:
                    matches = re.findall(patron, texto, re.IGNORECASE)
                    datos[campo].extend(matches)
        
        # Limpiar duplicados y ordenar
        for campo in datos:
            datos[campo] = list(set(datos[campo]))
        
        return datos


def ejecutar_agente(carpeta_expediente: str) -> ResultadoAgente:
    """Función helper para ejecutar el agente"""
    documentos = extraer_todos_pdfs(carpeta_expediente)
    agente = AgenteClasificador()
    return agente.analizar(documentos)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    # Prueba con carpeta de descargas
    carpeta = r"C:\Users\hanns\Downloads"
    
    print("=" * 80)
    print("AGENTE 01 — CLASIFICADOR DE NATURALEZA")
    print("=" * 80)
    
    resultado = ejecutar_agente(carpeta)
    
    print(f"\n✅ Éxito: {resultado.exito}")
    print(f"📋 Naturaleza detectada: {resultado.datos_extraidos.get('naturaleza', 'N/A')}")
    print(f"📋 Tipo procedimiento: {resultado.datos_extraidos.get('tipo_procedimiento', 'N/A')}")
    print(f"📄 Documentos analizados: {resultado.datos_extraidos.get('total_documentos', 0)}")
    
    if resultado.observaciones:
        print(f"\n⚠️ Observaciones: {len(resultado.observaciones)}")
        for obs in resultado.observaciones:
            print(f"   - [{obs.nivel.value}] {obs.descripcion}")
    
    if resultado.incertidumbres:
        print(f"\n❓ Incertidumbres: {len(resultado.incertidumbres)}")
        for inc in resultado.incertidumbres:
            print(f"   - {inc}")
    
    # Mostrar datos extraídos
    datos = resultado.datos_extraidos.get("datos_expediente", {})
    print("\n📊 Datos extraídos:")
    for campo, valores in datos.items():
        if valores:
            print(f"   {campo}: {valores[:3]}...")  # Solo primeros 3



