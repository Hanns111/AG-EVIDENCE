# -*- coding: utf-8 -*-
"""
AGENTE 08 — SUNAT PÚBLICO (FASE EXPERIMENTAL)
=============================================
Este agente NO usa SOL ni SIRE autenticado.

Funciones:
1. Consulta de RUC (vía APIs públicas / terceros gratuitos)
2. Validación INFORMATIVA de comprobantes
3. Análisis de coherencia tributaria

RESTRICCIONES ESTRICTAS:
- NO usar Clave SOL
- NO integrar SIRE autenticado
- NO usar servicios de pago
- NO actuar como proveedor autorizado SUNAT
- Todo resultado es INFORMATIVO
- Si hay duda → reportar INCERTIDUMBRE
"""

import os
import sys
import re
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import urllib.request
import urllib.parse
import ssl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    ResultadoAgente, Observacion, NivelObservacion,
    EstadoRUC, CondicionRUC, ResultadoSUNAT, SUNAT_CONFIG
)
from utils.pdf_extractor import DocumentoPDF


@dataclass
class ComprobanteDetectado:
    """Comprobante de pago detectado en el expediente"""
    tipo: str  # FACTURA, BOLETA, NOTA_CREDITO
    serie: str
    numero: str
    ruc_emisor: str
    fecha: str
    monto: float
    validado: bool
    mensaje_validacion: str


class AgenteSUNAT:
    """
    Agente 08: Consultas públicas SUNAT
    
    IMPORTANTE: Este agente solo usa información pública.
    NO accede a SIRE ni usa Clave SOL.
    Todos los resultados son INFORMATIVOS.
    """
    
    AGENTE_ID = "AG08"
    AGENTE_NOMBRE = "SUNAT Público (Experimental)"
    
    # Actividades económicas relacionadas con servicios comunes
    CIIU_SERVICIOS = {
        "4791": "Venta por correo y por Internet",
        "5221": "Actividades de servicios vinculadas al transporte terrestre",
        "5590": "Otros tipos de alojamiento",
        "5610": "Restaurantes y servicio móvil de comidas",
        "6201": "Actividades de programación informática",
        "6311": "Procesamiento de datos",
        "7020": "Actividades de consultoría de gestión",
        "7110": "Actividades de arquitectura e ingeniería",
        "7310": "Publicidad",
        "7490": "Otras actividades profesionales",
        "8211": "Actividades combinadas de servicios administrativos",
        "8299": "Otras actividades de servicios de apoyo a las empresas",
        "8549": "Otros tipos de enseñanza",
    }
    
    def __init__(self):
        self.observaciones: List[Observacion] = []
        self.incertidumbres: List[str] = []
        self.datos_extraidos: Dict = {}
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE
        
    def analizar(self, documentos: List[DocumentoPDF]) -> ResultadoAgente:
        """
        Realiza análisis SUNAT con información pública
        """
        self.observaciones = []
        self.incertidumbres = []
        
        # 1. Extraer RUCs del expediente
        rucs = self._extraer_rucs(documentos)
        
        # 2. Consultar cada RUC
        resultados_ruc: Dict[str, ResultadoSUNAT] = {}
        for ruc in rucs:
            resultado = self._consultar_ruc_publico(ruc)
            resultados_ruc[ruc] = resultado
            
            # Generar observaciones según resultado
            self._evaluar_resultado_ruc(resultado)
        
        # 3. Extraer comprobantes
        comprobantes = self._extraer_comprobantes(documentos)
        
        # 4. Análisis de coherencia tributaria
        coherencia = self._analizar_coherencia_tributaria(documentos, resultados_ruc)
        
        # 5. Verificar detracción (informativo)
        detraccion = self._verificar_detraccion(documentos)
        
        self.datos_extraidos = {
            "rucs_consultados": list(rucs),
            "resultados_ruc": {
                ruc: {
                    "estado": r.estado.value,
                    "condicion": r.condicion.value,
                    "razon_social": r.razon_social,
                    "actividad": r.actividad_economica
                }
                for ruc, r in resultados_ruc.items()
            },
            "comprobantes_detectados": len(comprobantes),
            "coherencia_tributaria": coherencia,
            "verificacion_detraccion": detraccion,
            "es_informativo": True,  # SIEMPRE
            "disclaimer": "Los resultados de SUNAT son INFORMATIVOS. Verificar en fuente oficial."
        }
        
        return ResultadoAgente(
            agente_id=self.AGENTE_ID,
            agente_nombre=self.AGENTE_NOMBRE,
            exito=True,  # El agente siempre "funciona", solo reporta
            observaciones=self.observaciones,
            datos_extraidos=self.datos_extraidos,
            incertidumbres=self.incertidumbres
        )
    
    def _extraer_rucs(self, documentos: List[DocumentoPDF]) -> set:
        """Extrae RUCs únicos del expediente"""
        rucs = set()
        
        for doc in documentos:
            # Buscar RUC en texto
            matches = re.findall(r'\b(10|20)\d{9}\b', doc.texto_completo)
            rucs.update(matches)
            
            # Excluir RUC del MINEDU
            rucs.discard("20131370998")
            rucs.discard("20380795907")  # UE 026
        
        return rucs
    
    def _consultar_ruc_publico(self, ruc: str) -> ResultadoSUNAT:
        """
        Consulta RUC usando APIs públicas gratuitas
        
        NOTA: Esta función intenta múltiples fuentes públicas.
        Si todas fallan, retorna INCERTIDUMBRE.
        """
        
        # Intentar con API Peru (gratuita limitada)
        resultado = self._consultar_api_peru(ruc)
        if resultado.estado != EstadoRUC.INCERTIDUMBRE:
            return resultado
        
        # Intentar web scraping de SUNAT pública (fallback)
        resultado = self._consultar_sunat_web(ruc)
        if resultado.estado != EstadoRUC.INCERTIDUMBRE:
            return resultado
        
        # Si todo falla
        self.incertidumbres.append(f"No se pudo consultar RUC {ruc} - Verificar manualmente")
        
        return ResultadoSUNAT(
            ruc=ruc,
            estado=EstadoRUC.INCERTIDUMBRE,
            condicion=CondicionRUC.INCERTIDUMBRE,
            es_informativo=True,
            mensaje_incertidumbre="No se pudo consultar. Verificar en SUNAT."
        )
    
    def _consultar_api_peru(self, ruc: str) -> ResultadoSUNAT:
        """Intenta consultar API Peru (gratuita con límites)"""
        try:
            url = f"https://api.apis.net.pe/v1/ruc?numero={ruc}"
            
            req = urllib.request.Request(url)
            req.add_header('Accept', 'application/json')
            req.add_header('User-Agent', 'Mozilla/5.0')
            
            with urllib.request.urlopen(req, timeout=10, context=self._ssl_context) as response:
                data = json.loads(response.read().decode('utf-8'))
                
                if data and 'numeroDocumento' in data:
                    # Mapear estado
                    estado_str = data.get('estado', '').upper()
                    estado = EstadoRUC.ACTIVO if 'ACTIVO' in estado_str else EstadoRUC.BAJA_DEFINITIVA
                    
                    # Mapear condición
                    condicion_str = data.get('condicion', '').upper()
                    if 'HABIDO' in condicion_str:
                        condicion = CondicionRUC.HABIDO
                    elif 'NO HABIDO' in condicion_str:
                        condicion = CondicionRUC.NO_HABIDO
                    else:
                        condicion = CondicionRUC.INCERTIDUMBRE
                    
                    return ResultadoSUNAT(
                        ruc=ruc,
                        estado=estado,
                        condicion=condicion,
                        razon_social=data.get('nombre', data.get('razonSocial', '')),
                        actividad_economica=data.get('actividadEconomica', ''),
                        direccion=data.get('direccion', ''),
                        es_informativo=True
                    )
        except Exception as e:
            pass  # Silenciar errores, intentar siguiente fuente
        
        return ResultadoSUNAT(
            ruc=ruc,
            estado=EstadoRUC.INCERTIDUMBRE,
            condicion=CondicionRUC.INCERTIDUMBRE,
            es_informativo=True,
            mensaje_incertidumbre="API no disponible"
        )
    
    def _consultar_sunat_web(self, ruc: str) -> ResultadoSUNAT:
        """
        Fallback: Intenta obtener info básica de web pública SUNAT
        NOTA: Esto es solo informativo y puede no funcionar siempre
        """
        # Esta función es un placeholder - en producción se implementaría
        # web scraping de la página pública de SUNAT
        return ResultadoSUNAT(
            ruc=ruc,
            estado=EstadoRUC.INCERTIDUMBRE,
            condicion=CondicionRUC.INCERTIDUMBRE,
            es_informativo=True,
            mensaje_incertidumbre="Consulta web no implementada"
        )
    
    def _evaluar_resultado_ruc(self, resultado: ResultadoSUNAT):
        """Genera observaciones según resultado de consulta RUC"""
        
        if resultado.estado == EstadoRUC.INCERTIDUMBRE:
            self.observaciones.append(Observacion(
                nivel=NivelObservacion.INFORMATIVA,
                agente=self.AGENTE_NOMBRE,
                descripcion=f"[INFORMATIVO] No se pudo verificar RUC {resultado.ruc}",
                evidencia=resultado.mensaje_incertidumbre,
                accion_requerida="Verificar estado del RUC en portal SUNAT",
                area_responsable="Control Previo"
            ))
            return
        
        if resultado.estado != EstadoRUC.ACTIVO:
            self.observaciones.append(Observacion(
                nivel=NivelObservacion.CRITICA,
                agente=self.AGENTE_NOMBRE,
                descripcion=f"[INFORMATIVO] RUC {resultado.ruc} NO está ACTIVO",
                evidencia=f"Estado: {resultado.estado.value}",
                accion_requerida="VERIFICAR EN SUNAT - Proveedor podría no estar habilitado para facturar",
                area_responsable="Control Previo / Logística"
            ))
        
        if resultado.condicion == CondicionRUC.NO_HABIDO:
            self.observaciones.append(Observacion(
                nivel=NivelObservacion.CRITICA,
                agente=self.AGENTE_NOMBRE,
                descripcion=f"[INFORMATIVO] RUC {resultado.ruc} figura como NO HABIDO",
                evidencia=f"Condición: {resultado.condicion.value}",
                accion_requerida="VERIFICAR EN SUNAT - Podría haber riesgo tributario",
                area_responsable="Control Previo"
            ))
    
    def _extraer_comprobantes(self, documentos: List[DocumentoPDF]) -> List[ComprobanteDetectado]:
        """Extrae comprobantes de pago del expediente"""
        comprobantes = []
        
        for doc in documentos:
            texto = doc.texto_completo
            
            # Buscar facturas electrónicas
            patron_factura = r'(F\w{3})-(\d+)|factura.*?([A-Z]\d{3})-(\d+)'
            matches = re.findall(patron_factura, texto, re.IGNORECASE)
            
            for match in matches:
                serie = match[0] or match[2]
                numero = match[1] or match[3]
                if serie and numero:
                    comprobantes.append(ComprobanteDetectado(
                        tipo="FACTURA",
                        serie=serie,
                        numero=numero,
                        ruc_emisor="",  # Se extrae por separado
                        fecha="",
                        monto=0.0,
                        validado=False,
                        mensaje_validacion="No validado (requiere SIRE)"
                    ))
        
        return comprobantes
    
    def _analizar_coherencia_tributaria(
        self, 
        documentos: List[DocumentoPDF],
        resultados_ruc: Dict[str, ResultadoSUNAT]
    ) -> Dict:
        """
        Analiza si la actividad económica del proveedor
        es coherente con el objeto del servicio
        """
        coherencia = {
            "analizado": False,
            "coherente": True,
            "observaciones": []
        }
        
        # Extraer objeto del servicio/contrato
        texto_total = " ".join([d.texto_completo for d in documentos])
        
        objeto_match = re.search(
            r"(?:objeto|descripci[oó]n|servicio de)[:\s]*([^\n]{20,200})",
            texto_total, re.IGNORECASE
        )
        
        if not objeto_match:
            coherencia["observaciones"].append("No se pudo extraer el objeto del servicio")
            return coherencia
        
        objeto = objeto_match.group(1).lower()
        coherencia["analizado"] = True
        
        # Comparar con actividad económica de cada proveedor
        for ruc, resultado in resultados_ruc.items():
            if resultado.actividad_economica:
                actividad = resultado.actividad_economica.lower()
                
                # Verificar coherencia básica
                keywords_objeto = set(re.findall(r'\b\w{4,}\b', objeto))
                keywords_actividad = set(re.findall(r'\b\w{4,}\b', actividad))
                
                # Si no hay intersección significativa
                interseccion = keywords_objeto & keywords_actividad
                if len(interseccion) < 2:
                    coherencia["coherente"] = False
                    coherencia["observaciones"].append(
                        f"RUC {ruc}: Actividad económica '{actividad}' podría no coincidir con objeto del servicio"
                    )
                    
                    self.observaciones.append(Observacion(
                        nivel=NivelObservacion.INFORMATIVA,
                        agente=self.AGENTE_NOMBRE,
                        descripcion=f"[INFORMATIVO] Posible incoherencia entre actividad SUNAT y objeto contratado",
                        evidencia=f"RUC {ruc} - Actividad: {resultado.actividad_economica[:50]}...",
                        accion_requerida="Verificar que el proveedor esté habilitado para el servicio contratado",
                        area_responsable="Control Previo"
                    ))
        
        return coherencia
    
    def _verificar_detraccion(self, documentos: List[DocumentoPDF]) -> Dict:
        """Verifica información relacionada con detracción"""
        resultado = {
            "monto_detectado": 0.0,
            "aplica_detraccion": False,
            "cuenta_detraccion_encontrada": False
        }
        
        texto_total = " ".join([d.texto_completo for d in documentos])
        
        # Buscar montos
        montos = re.findall(r'S/?\.?\s*([\d,]+\.\d{2})', texto_total)
        if montos:
            try:
                resultado["monto_detectado"] = max(float(m.replace(',', '')) for m in montos)
            except:
                pass
        
        # Verificar si aplica detracción (monto > 700)
        if resultado["monto_detectado"] > 700:
            resultado["aplica_detraccion"] = True
            
            # Buscar cuenta de detracción
            if re.search(r'detracci[oó]n|cuenta.*banco.*naci[oó]n', texto_total, re.IGNORECASE):
                resultado["cuenta_detraccion_encontrada"] = True
            else:
                self.observaciones.append(Observacion(
                    nivel=NivelObservacion.MAYOR,
                    agente=self.AGENTE_NOMBRE,
                    descripcion=f"[INFORMATIVO] Monto supera S/ 700 - Verificar si aplica detracción",
                    evidencia=f"Monto detectado: S/ {resultado['monto_detectado']:,.2f}",
                    accion_requerida="Verificar si el servicio está sujeto a detracción según Res. SUNAT 183-2004",
                    area_responsable="Control Previo"
                ))
        
        return resultado


def ejecutar_agente(documentos: List[DocumentoPDF]) -> ResultadoAgente:
    """Función helper para ejecutar el agente"""
    agente = AgenteSUNAT()
    return agente.analizar(documentos)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    from utils.pdf_extractor import extraer_todos_pdfs
    
    carpeta = r"C:\Users\hanns\Downloads"
    documentos = extraer_todos_pdfs(carpeta)
    
    print("=" * 80)
    print("AGENTE 08 — SUNAT PÚBLICO (EXPERIMENTAL)")
    print("=" * 80)
    print("⚠️ TODOS LOS RESULTADOS SON INFORMATIVOS")
    print("=" * 80)
    
    resultado = ejecutar_agente(documentos)
    
    print(f"\n✅ Éxito: {resultado.exito}")
    print(f"📋 RUCs consultados: {resultado.datos_extraidos.get('rucs_consultados', [])}")
    
    for ruc, info in resultado.datos_extraidos.get('resultados_ruc', {}).items():
        print(f"\n   RUC {ruc}:")
        print(f"      Estado: {info['estado']}")
        print(f"      Condición: {info['condicion']}")
        print(f"      Razón Social: {info['razon_social'][:50]}..." if info['razon_social'] else "      Razón Social: N/A")
    
    if resultado.observaciones:
        print(f"\n⚠️ Observaciones:")
        for obs in resultado.observaciones:
            print(f"   [{obs.nivel.value}] {obs.descripcion}")



