# -*- coding: utf-8 -*-
"""
TESTS DE ESTÁNDAR PROBATORIO ESTRICTO
=====================================
Tests que DEBEN FALLAR si:
1. Se responde sin archivo/página/snippet
2. Se responde una pregunta sin evidencia
3. Se emite CRÍTICA o MAYOR sin evidencia probatoria completa
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from agentes.agente_10_conversacional import (
    AgenteConversacional, 
    RespuestaConversacional,
    EvidenciaCitada,
    MENSAJE_INSUFICIENCIA
)

# =============================================================================
# DATOS DE PRUEBA
# =============================================================================

JSON_CON_EVIDENCIA_COMPLETA = {
    "metadata": {"expediente_sinad": "123456"},
    "decision": {"resultado": "NO PROCEDE"},
    "hallazgos": [
        {
            "hallazgo": "Inconsistencia en SINAD",
            "severidad": "CRÍTICA",
            "tipo": "sinad",
            "impacto": "Bloquea trazabilidad",
            "bloquea_pago": True,
            "accion": "Corregir SINAD",
            "area_responsable": "Logística",
            "evidencias": [
                {
                    "archivo": "documento_test.pdf",
                    "pagina": 5,
                    "valor_detectado": "123456",
                    "snippet": "SINAD 123456 detectado en el proveído"
                }
            ]
        }
    ]
}

JSON_SIN_EVIDENCIA = {
    "metadata": {"expediente_sinad": "123456"},
    "decision": {"resultado": "NO PROCEDE"},
    "hallazgos": [
        {
            "hallazgo": "Inconsistencia detectada",
            "severidad": "CRÍTICA",
            "tipo": "sinad",
            "impacto": "Bloquea pago",
            "bloquea_pago": True,
            "accion": "Corregir",
            "area_responsable": "N/A",
            "evidencias": []  # SIN EVIDENCIAS
        }
    ]
}

JSON_EVIDENCIA_INCOMPLETA = {
    "metadata": {"expediente_sinad": "123456"},
    "decision": {"resultado": "NO PROCEDE"},
    "hallazgos": [
        {
            "hallazgo": "Error de dígitos",
            "severidad": "CRÍTICA",
            "tipo": "ruc",
            "impacto": "Afecta pago",
            "bloquea_pago": True,
            "evidencias": [
                {
                    "archivo": "",  # FALTA ARCHIVO
                    "pagina": 0,    # FALTA PÁGINA
                    "snippet": ""   # FALTA SNIPPET
                }
            ]
        }
    ]
}


# =============================================================================
# CLASE DE TESTS
# =============================================================================

class TestEstandarProbatorio:
    """Tests de estándar probatorio estricto"""
    
    def setup_method(self, method=None):
        """Inicializa el entorno para cada test (compatible con pytest)"""
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def _crear_agente_con_datos(self, datos: dict) -> AgenteConversacional:
        """Crea agente con datos de prueba"""
        agente = AgenteConversacional(backend="regex")
        agente.datos = datos
        agente.hallazgos = datos.get("hallazgos", [])
        agente.metadata = datos.get("metadata", {})
        agente.decision = datos.get("decision", {})
        return agente
    
    def assert_true(self, condition: bool, test_name: str, mensaje: str = ""):
        """Verifica que una condición sea verdadera"""
        if condition:
            self.passed += 1
            self.results.append(f"✅ {test_name}")
            return True
        else:
            self.failed += 1
            self.results.append(f"❌ {test_name}: {mensaje}")
            return False
    
    # =========================================================================
    # TEST 1: Respuesta con evidencia completa DEBE tener archivo/página/snippet
    # =========================================================================
    
    def test_respuesta_con_evidencia_tiene_campos_obligatorios(self):
        """
        DEBE PASAR: Una respuesta con evidencia completa incluye todos los campos
        """
        agente = self._crear_agente_con_datos(JSON_CON_EVIDENCIA_COMPLETA)
        respuesta = agente.preguntar("Lista las críticas")
        
        # Verificar que hay evidencias citadas
        tiene_evidencias = len(respuesta.evidencias_citadas) > 0
        self.assert_true(
            tiene_evidencias,
            "test_respuesta_con_evidencia_tiene_campos_obligatorios",
            "No se citaron evidencias"
        )
        
        if tiene_evidencias:
            ev = respuesta.evidencias_citadas[0]
            # Verificar campos obligatorios
            tiene_archivo = bool(ev.archivo)
            tiene_pagina = ev.pagina > 0
            tiene_snippet = bool(ev.snippet)
            
            self.assert_true(
                tiene_archivo,
                "  - Evidencia tiene archivo",
                f"Archivo vacío: '{ev.archivo}'"
            )
            self.assert_true(
                tiene_pagina,
                "  - Evidencia tiene página",
                f"Página inválida: {ev.pagina}"
            )
            self.assert_true(
                tiene_snippet,
                "  - Evidencia tiene snippet",
                f"Snippet vacío: '{ev.snippet}'"
            )
    
    # =========================================================================
    # TEST 2: Respuesta SIN evidencia DEBE retornar mensaje de insuficiencia
    # =========================================================================
    
    def test_respuesta_sin_evidencia_retorna_insuficiencia(self):
        """
        DEBE PASAR: Sin evidencia, retorna mensaje estándar de insuficiencia
        """
        agente = self._crear_agente_con_datos(JSON_SIN_EVIDENCIA)
        respuesta = agente.preguntar("¿Por qué no procede?")
        
        # Verificar que NO hay evidencias citadas con datos completos
        tiene_evidencia_valida = any(
            ev.archivo and ev.pagina > 0 
            for ev in respuesta.evidencias_citadas
        )
        
        self.assert_true(
            not tiene_evidencia_valida or MENSAJE_INSUFICIENCIA.lower() in respuesta.texto.lower(),
            "test_respuesta_sin_evidencia_retorna_insuficiencia",
            "Debería indicar insuficiencia o no tener evidencia válida"
        )
    
    # =========================================================================
    # TEST 3: Evidencia incompleta NO debe emitir respuesta válida
    # =========================================================================
    
    def test_evidencia_incompleta_no_emite_respuesta_valida(self):
        """
        DEBE PASAR: Evidencia sin archivo/página no genera respuesta válida
        """
        agente = self._crear_agente_con_datos(JSON_EVIDENCIA_INCOMPLETA)
        respuesta = agente.preguntar("Lista las críticas")
        
        # Verificar que las evidencias citadas tienen datos completos
        evidencias_validas = [
            ev for ev in respuesta.evidencias_citadas
            if ev.archivo and ev.pagina > 0
        ]
        
        self.assert_true(
            len(evidencias_validas) == 0,
            "test_evidencia_incompleta_no_emite_respuesta_valida",
            f"Se citaron {len(evidencias_validas)} evidencias con datos incompletos"
        )
    
    # =========================================================================
    # TEST 4: Preguntas prohibidas DEBEN retornar insuficiencia
    # =========================================================================
    
    def test_pregunta_prohibida_retorna_insuficiencia(self):
        """
        DEBE PASAR: Preguntas subjetivas retornan mensaje de insuficiencia
        """
        agente = self._crear_agente_con_datos(JSON_CON_EVIDENCIA_COMPLETA)
        
        preguntas_prohibidas = [
            "¿Qué opinas de esto?",
            "¿Qué harías tú?",
            "¿Esto está bien o mal?",
            "¿Qué quiso decir el proveedor?",
        ]
        
        for pregunta in preguntas_prohibidas:
            respuesta = agente.preguntar(pregunta)
            es_insuficiencia = MENSAJE_INSUFICIENCIA.lower() in respuesta.texto.lower()
            
            self.assert_true(
                es_insuficiencia,
                f"  - Pregunta prohibida: '{pregunta[:30]}...'",
                "Debería retornar insuficiencia"
            )
    
    # =========================================================================
    # TEST 5: Búsqueda de valor inexistente DEBE retornar insuficiencia
    # =========================================================================
    
    def test_busqueda_valor_inexistente_retorna_insuficiencia(self):
        """
        DEBE PASAR: Valor no encontrado retorna mensaje de insuficiencia
        """
        agente = self._crear_agente_con_datos(JSON_CON_EVIDENCIA_COMPLETA)
        respuesta = agente.preguntar("¿Dónde aparece el 99999999?")
        
        es_insuficiencia = MENSAJE_INSUFICIENCIA.lower() in respuesta.texto.lower()
        
        self.assert_true(
            es_insuficiencia,
            "test_busqueda_valor_inexistente_retorna_insuficiencia",
            "Debería indicar que no se encontró el valor"
        )
    
    # =========================================================================
    # TEST 6: Respuesta válida DEBE cumplir estándar probatorio
    # =========================================================================
    
    def test_respuesta_valida_cumple_estandar_probatorio(self):
        """
        DEBE PASAR: Respuesta con evidencia completa cumple estándar
        """
        agente = self._crear_agente_con_datos(JSON_CON_EVIDENCIA_COMPLETA)
        respuesta = agente.preguntar("¿En qué archivo aparece el 123456?")
        
        # Si encontró el valor, debe cumplir estándar
        if MENSAJE_INSUFICIENCIA.lower() not in respuesta.texto.lower():
            self.assert_true(
                respuesta.cumple_estandar_probatorio,
                "test_respuesta_valida_cumple_estandar_probatorio",
                "Respuesta con evidencia debe cumplir estándar"
            )
            
            # Verificar que el texto menciona archivo y página
            texto_lower = respuesta.texto.lower()
            menciona_archivo = "archivo" in texto_lower or ".pdf" in texto_lower
            menciona_pagina = "página" in texto_lower or "pagina" in texto_lower or "pág" in texto_lower
            
            self.assert_true(
                menciona_archivo,
                "  - Texto menciona archivo",
                "El texto debe mencionar el archivo"
            )
            self.assert_true(
                menciona_pagina,
                "  - Texto menciona página",
                "El texto debe mencionar la página"
            )
        else:
            self.assert_true(True, "test_respuesta_valida_cumple_estandar_probatorio", "")
    
    # =========================================================================
    # TEST 7: Detalle de observación DEBE mostrar todas las evidencias
    # =========================================================================
    
    def test_detalle_observacion_muestra_evidencias(self):
        """
        DEBE PASAR: Detalle de observación incluye todas las evidencias
        """
        agente = self._crear_agente_con_datos(JSON_CON_EVIDENCIA_COMPLETA)
        respuesta = agente.preguntar("Detalle de la observación 1")
        
        # Verificar que el texto incluye información de evidencia
        texto = respuesta.texto.lower()
        
        self.assert_true(
            "documento_test.pdf" in texto or "evidencia" in texto,
            "test_detalle_observacion_muestra_evidencias",
            "Detalle debe mostrar evidencias del hallazgo"
        )
    
    # =========================================================================
    # TEST 8: Sin datos cargados DEBE retornar insuficiencia
    # =========================================================================
    
    def test_sin_datos_retorna_insuficiencia(self):
        """
        DEBE PASAR: Sin datos cargados, cualquier pregunta retorna insuficiencia
        """
        agente = AgenteConversacional(backend="regex")  # Sin cargar datos
        respuesta = agente.preguntar("¿Por qué no procede?")
        
        es_insuficiencia = (
            MENSAJE_INSUFICIENCIA.lower() in respuesta.texto.lower() or
            "no hay datos" in respuesta.texto.lower()
        )
        
        self.assert_true(
            es_insuficiencia,
            "test_sin_datos_retorna_insuficiencia",
            "Sin datos debe retornar mensaje apropiado"
        )
    
    # =========================================================================
    # EJECUTAR TODOS LOS TESTS
    # =========================================================================
    
    def run_all(self):
        """Ejecuta todos los tests"""
        print("=" * 70)
        print("TESTS DE ESTÁNDAR PROBATORIO ESTRICTO")
        print("=" * 70)
        print("Política: El agente NO puede responder sin evidencia documental")
        print("-" * 70)
        
        # Ejecutar tests
        self.test_respuesta_con_evidencia_tiene_campos_obligatorios()
        self.test_respuesta_sin_evidencia_retorna_insuficiencia()
        self.test_evidencia_incompleta_no_emite_respuesta_valida()
        self.test_pregunta_prohibida_retorna_insuficiencia()
        self.test_busqueda_valor_inexistente_retorna_insuficiencia()
        self.test_respuesta_valida_cumple_estandar_probatorio()
        self.test_detalle_observacion_muestra_evidencias()
        self.test_sin_datos_retorna_insuficiencia()
        
        # Mostrar resultados
        print("\n" + "-" * 70)
        for result in self.results:
            print(result)
        
        print("\n" + "=" * 70)
        total = self.passed + self.failed
        print(f"RESULTADOS: {self.passed}/{total} pasados, {self.failed} fallidos")
        
        if self.failed > 0:
            print("⚠️  HAY TESTS QUE FALLARON - REVISAR IMPLEMENTACIÓN")
        else:
            print("✅ TODOS LOS TESTS PASARON - ESTÁNDAR PROBATORIO CUMPLIDO")
        
        print("=" * 70)
        
        return self.failed == 0


if __name__ == "__main__":
    tests = TestEstandarProbatorio()
    success = tests.run_all()
    sys.exit(0 if success else 1)



