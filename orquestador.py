# -*- coding: utf-8 -*-
"""
AG-EVIDENCE — ORQUESTADOR PRINCIPAL
===================================
Coordina la ejecución de todos los agentes y genera el informe final.

🔒 ALCANCE DEL SISTEMA:
AG-EVIDENCE solo analiza expedientes administrativos con estándar probatorio.
Toda observación crítica/mayor requiere evidencia: archivo + página + snippet.

Flujo de ejecución:
1. Inventario de documentos (Agente 01 - Clasificador)
2. OCR y calidad (Agente 02 - OCR)
3. Coherencia documental (Agente 03 - Coherencia)
4. Cumplimiento legal (Agente 04 - Legal)
5. Firmas y competencia (Agente 05 - Firmas)
6. Integridad expediente (Agente 06 - Integridad)
7. Penalidades (Agente 07 - Penalidades)
8. Verificación SUNAT (Agente 08 - SUNAT)
9. Decisión final (Agente 09 - Decisor)
"""

import os
import sys
from typing import List, Optional
from datetime import datetime

# Configurar encoding
sys.stdout.reconfigure(encoding='utf-8')

# Agregar rutas
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import (
    NaturalezaExpediente, TipoProcedimiento, ResultadoAgente,
    InformeControlPrevio, DOWNLOADS_DIR, OUTPUT_DIR
)
from utils.pdf_extractor import extraer_todos_pdfs, DocumentoPDF

# Importar agentes
from agentes.agente_01_clasificador import AgenteClasificador
from agentes.agente_02_ocr import AgenteOCR
from agentes.agente_03_coherencia import AgenteCoherencia
from agentes.agente_04_legal import AgenteLegal
from agentes.agente_05_firmas import AgenteFirmas
from agentes.agente_06_integridad import AgenteIntegridad
from agentes.agente_07_penalidades import AgentePenalidades
from agentes.agente_08_sunat import AgenteSUNAT
from agentes.agente_09_decisor import AgenteDecisor, generar_informe_texto
from utils.exportador_json import ExportadorProbatorio, exportar_informe_json, exportar_informe_txt
from utils.validador_evidencia import ValidadorEvidencia

# Importar módulo de reglas adicionales (SPOT/TDR)
try:
    from src.rules.integrador import crear_resultado_agente_reglas
    REGLAS_DISPONIBLES = True
except ImportError:
    REGLAS_DISPONIBLES = False


class OrquestadorControlPrevio:
    """
    Orquestador principal del sistema multi-agente
    """
    
    def __init__(self, carpeta_expediente: str = None):
        """
        Inicializa el orquestador
        
        Args:
            carpeta_expediente: Ruta a la carpeta con los documentos.
                               Si es None, usa la carpeta Downloads.
        """
        self.carpeta = carpeta_expediente or DOWNLOADS_DIR
        self.documentos: List[DocumentoPDF] = []
        self.resultados_agentes: List[ResultadoAgente] = []
        self.informe_final: Optional[InformeControlPrevio] = None
        
        # Datos del expediente (se llenan durante el análisis)
        self.naturaleza = NaturalezaExpediente.NO_DETERMINADO
        self.tipo_procedimiento = TipoProcedimiento.NO_DETERMINADO
        self.directiva_aplicada = ""
        self.es_primera_armada = True
        
    def ejecutar(self, verbose: bool = True) -> InformeControlPrevio:
        """
        Ejecuta el flujo completo de análisis
        
        Args:
            verbose: Si True, imprime progreso en consola
            
        Returns:
            InformeControlPrevio con el resultado del análisis
        """
        inicio = datetime.now()
        
        if verbose:
            self._imprimir_encabezado()
        
        # PASO 1: Cargar documentos
        if verbose:
            print("\n📂 PASO 1: Cargando documentos...")
        self.documentos = extraer_todos_pdfs(self.carpeta)
        
        if not self.documentos:
            print("❌ No se encontraron documentos PDF en la carpeta")
            return None
        
        if verbose:
            print(f"   ✓ {len(self.documentos)} documentos cargados")
        
        # PASO 2: Clasificar naturaleza (Agente 01)
        if verbose:
            print("\n🔍 PASO 2: Clasificando naturaleza del expediente...")
        resultado_clasificador = self._ejecutar_agente_01()
        self.resultados_agentes.append(resultado_clasificador)
        
        if verbose:
            print(f"   ✓ Naturaleza: {self.naturaleza.value}")
            print(f"   ✓ Procedimiento: {self.tipo_procedimiento.value}")
        
        # PASO 3: Análisis OCR (Agente 02)
        if verbose:
            print("\n📷 PASO 3: Analizando calidad de documentos...")
        resultado_ocr = self._ejecutar_agente_02()
        self.resultados_agentes.append(resultado_ocr)
        
        if verbose:
            datos_ocr = resultado_ocr.datos_extraidos
            print(f"   ✓ Páginas analizadas: {datos_ocr.get('total_paginas_analizadas', 0)}")
            print(f"   ✓ Baja calidad: {datos_ocr.get('paginas_baja_calidad', 0)}")
        
        # PASO 4: Coherencia documental (Agente 03)
        if verbose:
            print("\n🔗 PASO 4: Verificando coherencia documental...")
        resultado_coherencia = self._ejecutar_agente_03()
        self.resultados_agentes.append(resultado_coherencia)
        
        if verbose:
            print(f"   ✓ Inconsistencias: {resultado_coherencia.datos_extraidos.get('inconsistencias_detectadas', 0)}")
        
        # PASO 5: Cumplimiento legal (Agente 04)
        if verbose:
            print("\n⚖️ PASO 5: Verificando cumplimiento de directiva...")
        resultado_legal = self._ejecutar_agente_04()
        self.resultados_agentes.append(resultado_legal)
        
        if verbose:
            datos_legal = resultado_legal.datos_extraidos
            print(f"   ✓ Directiva: {self.directiva_aplicada[:50]}...")
            print(f"   ✓ Requisitos cumplidos: {datos_legal.get('requisitos_cumplidos', 0)}/{datos_legal.get('requisitos_verificados', 0)}")
        
        # PASO 6: Firmas (Agente 05)
        if verbose:
            print("\n✍️ PASO 6: Verificando firmas y competencia...")
        resultado_firmas = self._ejecutar_agente_05()
        self.resultados_agentes.append(resultado_firmas)
        
        if verbose:
            print(f"   ✓ Firmas detectadas: {resultado_firmas.datos_extraidos.get('total_firmas_detectadas', 0)}")
        
        # PASO 7: Integridad (Agente 06)
        if verbose:
            print("\n📋 PASO 7: Verificando integridad del expediente...")
        resultado_integridad = self._ejecutar_agente_06()
        self.resultados_agentes.append(resultado_integridad)
        
        if verbose:
            faltantes = resultado_integridad.datos_extraidos.get('documentos_faltantes', [])
            print(f"   ✓ Documentos faltantes: {len(faltantes)}")
        
        # PASO 8: Penalidades (Agente 07)
        if verbose:
            print("\n💰 PASO 8: Evaluando penalidades...")
        resultado_penalidades = self._ejecutar_agente_07()
        self.resultados_agentes.append(resultado_penalidades)
        
        if verbose:
            aplica = resultado_penalidades.datos_extraidos.get('aplica_penalidad_mora', False)
            print(f"   ✓ Aplica penalidad: {'Sí' if aplica else 'No'}")
        
        # PASO 9: SUNAT (Agente 08)
        if verbose:
            print("\n🏛️ PASO 9: Consultando SUNAT (informativo)...")
        resultado_sunat = self._ejecutar_agente_08()
        self.resultados_agentes.append(resultado_sunat)
        
        if verbose:
            rucs = resultado_sunat.datos_extraidos.get('rucs_consultados', [])
            print(f"   ✓ RUCs consultados: {len(rucs)}")
        
        # PASO 9.5: Reglas adicionales SPOT/TDR (si están disponibles)
        if REGLAS_DISPONIBLES:
            if verbose:
                print("\n📜 PASO 9.5: Validando reglas SPOT/TDR...")
            resultado_reglas = self._ejecutar_reglas_spot_tdr()
            self.resultados_agentes.append(resultado_reglas)
            
            if verbose:
                datos = resultado_reglas.datos_extraidos
                spot_aplica = datos.get('spot', {}).get('aplica', False)
                tdr_reqs = datos.get('tdr', {}).get('requisitos_count', 0)
                print(f"   ✓ SPOT aplica: {'Sí' if spot_aplica else 'No'}")
                print(f"   ✓ Requisitos TDR detectados: {tdr_reqs}")
                print(f"   ✓ Observaciones: {len(resultado_reglas.observaciones)}")
        
        # PASO 10: Decisión final (Agente 09)
        if verbose:
            print("\n🎯 PASO 10: Generando decisión final...")
        self.informe_final = self._ejecutar_agente_09()
        
        fin = datetime.now()
        duracion = (fin - inicio).total_seconds()
        
        if verbose:
            print(f"\n⏱️ Análisis completado en {duracion:.2f} segundos")
            print("\n" + "=" * 100)
            print(generar_informe_texto(self.informe_final))
        
        return self.informe_final
    
    def _ejecutar_agente_01(self) -> ResultadoAgente:
        """Ejecuta el Agente Clasificador"""
        agente = AgenteClasificador()
        resultado = agente.analizar(self.documentos)
        
        # Extraer datos para uso posterior
        datos = resultado.datos_extraidos
        self.naturaleza = NaturalezaExpediente(datos.get('naturaleza', 'NO DETERMINADO'))
        self.tipo_procedimiento = TipoProcedimiento(datos.get('tipo_procedimiento', 'NO DETERMINADO'))
        
        # Detectar si es primera armada
        datos_exp = datos.get('datos_expediente', {})
        for doc in self.documentos:
            if '1 de 1' in doc.texto_completo or 'primera armada' in doc.texto_completo.lower():
                self.es_primera_armada = True
            elif '2 de' in doc.texto_completo or 'segunda armada' in doc.texto_completo.lower():
                self.es_primera_armada = False
        
        return resultado
    
    def _ejecutar_agente_02(self) -> ResultadoAgente:
        """Ejecuta el Agente OCR"""
        agente = AgenteOCR()
        return agente.analizar(self.documentos)
    
    def _ejecutar_agente_03(self) -> ResultadoAgente:
        """Ejecuta el Agente de Coherencia"""
        agente = AgenteCoherencia()
        return agente.analizar(self.documentos)
    
    def _ejecutar_agente_04(self) -> ResultadoAgente:
        """Ejecuta el Agente Legal"""
        agente = AgenteLegal()
        resultado = agente.analizar(self.documentos, self.naturaleza, self.tipo_procedimiento)
        self.directiva_aplicada = resultado.datos_extraidos.get('directiva_aplicada', '')
        return resultado
    
    def _ejecutar_agente_05(self) -> ResultadoAgente:
        """Ejecuta el Agente de Firmas"""
        agente = AgenteFirmas()
        return agente.analizar(self.documentos)
    
    def _ejecutar_agente_06(self) -> ResultadoAgente:
        """Ejecuta el Agente de Integridad"""
        agente = AgenteIntegridad()
        return agente.analizar(
            self.documentos, 
            self.naturaleza, 
            self.tipo_procedimiento,
            self.es_primera_armada
        )
    
    def _ejecutar_agente_07(self) -> ResultadoAgente:
        """Ejecuta el Agente de Penalidades"""
        agente = AgentePenalidades()
        return agente.analizar(self.documentos)
    
    def _ejecutar_agente_08(self) -> ResultadoAgente:
        """Ejecuta el Agente SUNAT"""
        agente = AgenteSUNAT()
        return agente.analizar(self.documentos)
    
    def _ejecutar_agente_09(self) -> InformeControlPrevio:
        """Ejecuta el Agente Decisor"""
        decisor = AgenteDecisor()
        return decisor.decidir(
            self.resultados_agentes,
            self.naturaleza,
            self.directiva_aplicada
        )
    
    def _ejecutar_reglas_spot_tdr(self) -> ResultadoAgente:
        """
        Ejecuta las reglas adicionales SPOT y TDR.
        
        - SPOT: Valida si corresponde detracción según RS 183-2004/SUNAT
        - TDR: Valida requisitos del proveedor según TDR (solo primera armada)
        """
        return crear_resultado_agente_reglas(
            self.documentos,
            es_primera_armada=self.es_primera_armada,
            naturaleza=self.naturaleza
        )
    
    def _imprimir_encabezado(self):
        """Imprime el encabezado del sistema"""
        print("=" * 100)
        print("🏛️ SISTEMA MULTI-AGENTE DE CONTROL PREVIO PREMIUM")
        print("   Ministerio de Educación del Perú")
        print("=" * 100)
        print(f"📂 Carpeta de análisis: {self.carpeta}")
        print(f"📅 Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        print("=" * 100)
    
    def guardar_informe(self, ruta: str = None) -> str:
        """
        Guarda el informe en formatos TXT y JSON con estándar probatorio
        
        Args:
            ruta: Ruta del archivo. Si es None, usa la carpeta output.
            
        Returns:
            Ruta del archivo TXT guardado
        """
        if not self.informe_final:
            raise ValueError("No hay informe para guardar. Ejecute primero el análisis.")
        
        if ruta is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre = f"informe_control_previo_{timestamp}.txt"
            ruta = os.path.join(OUTPUT_DIR, nombre)
        
        # Validar evidencias antes de exportar
        validador = ValidadorEvidencia()
        stats = validador.validar_informe(self.informe_final)
        
        if stats["degradadas"] > 0:
            print(f"⚠️  {stats['degradadas']} observaciones degradadas por falta de evidencia")
        
        # Asegurar que existe el directorio
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        
        # Usar exportador probatorio
        exportador = ExportadorProbatorio(self.informe_final)
        
        # Guardar TXT probatorio
        texto = exportador.generar_txt_probatorio()
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(texto)
        print(f"\n📄 Informe TXT (probatorio) guardado en: {ruta}")
        
        # Guardar JSON estructurado
        ruta_json = ruta.replace('.txt', '.json')
        exportador.guardar_json(ruta_json)
        print(f"📋 Informe JSON (probatorio) guardado en: {ruta_json}")
        
        return ruta
    
    def obtener_hallazgos_json(self) -> list:
        """
        Obtiene los hallazgos en formato JSON estructurado con evidencia probatoria
        
        Returns:
            Lista de hallazgos estructurados
        """
        if not self.informe_final:
            raise ValueError("No hay informe. Ejecute primero el análisis.")
        
        exportador = ExportadorProbatorio(self.informe_final)
        return exportador.exportar_hallazgos()
    
    def validar_evidencias(self) -> dict:
        """
        Valida que todas las observaciones críticas/mayores tengan evidencia completa
        
        Returns:
            Estadísticas de validación
        """
        if not self.informe_final:
            raise ValueError("No hay informe. Ejecute primero el análisis.")
        
        validador = ValidadorEvidencia()
        return validador.validar_informe(self.informe_final)


def ejecutar_control_previo(carpeta: str = None, verbose: bool = True) -> InformeControlPrevio:
    """
    Función principal para ejecutar el control previo
    
    Args:
        carpeta: Ruta a la carpeta con documentos (None = Downloads)
        verbose: Si True, imprime progreso
        
    Returns:
        InformeControlPrevio con el resultado
    """
    orquestador = OrquestadorControlPrevio(carpeta)
    return orquestador.ejecutar(verbose)


if __name__ == "__main__":
    # Ejecutar sobre la carpeta de descargas
    carpeta = DOWNLOADS_DIR
    
    print(f"Analizando expedientes en: {carpeta}")
    
    orquestador = OrquestadorControlPrevio(carpeta)
    informe = orquestador.ejecutar(verbose=True)
    
    if informe:
        # Guardar informe
        ruta_guardado = orquestador.guardar_informe()
        print(f"\n✅ Análisis completado. Informe guardado en: {ruta_guardado}")

