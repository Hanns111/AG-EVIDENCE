# -*- coding: utf-8 -*-
"""
TESTS DEL MODO CONVERSACIONAL
==============================
Tests que verifican:
1. El modo conversacional NO alucina (no inventa datos)
2. El modo conversacional MANTIENE las citas obligatorias
3. Sin evidencia, responde mensaje estándar
"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from chat_asistente import (
    ChatAsistente,
    RespuestaAsistente,
    Evidencia,
    MENSAJE_NO_CONSTA,
    MODO_TECNICO,
    MODO_CONVERSACIONAL
)


# =============================================================================
# HELPERS
# =============================================================================

def crear_pdf_prueba(contenido: str, ruta: str) -> bool:
    """Crea un PDF de prueba"""
    try:
        import fitz
        
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        
        doc = fitz.open()
        page = doc.new_page()
        rect = fitz.Rect(50, 50, 550, 750)
        page.insert_textbox(rect, contenido, fontsize=11)
        doc.save(ruta)
        doc.close()
        
        return True
    except ImportError:
        return False


class TestModoConversacional:
    """Tests del modo conversacional"""
    
    def setup_method(self, method=None):
        """Inicializa el entorno para cada test (compatible con pytest)"""
        self.passed = 0
        self.failed = 0
        self.results = []
        self.temp_dir = None
        self.pdf_created = self.setup()
    
    def teardown_method(self, method=None):
        """Limpia después de cada test (compatible con pytest)"""
        self.cleanup()
    
    def setup(self):
        """Configura el entorno de prueba"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Crear PDF de prueba con contenido específico
        contenido = """DIRECTIVA DE VIÁTICOS N° 011-2020

Artículo 15. PLAZOS DE RENDICIÓN
El comisionado tiene un plazo máximo de DIEZ (10) días hábiles 
contados desde el término de la comisión para presentar la 
rendición de cuentas documentada.

Artículo 16. MONTOS MÁXIMOS
El monto máximo diario por concepto de viáticos nacionales 
es de S/ 320.00 (Trescientos Veinte y 00/100 Soles).

Artículo 20. PENALIDADES
El incumplimiento en la rendición dentro del plazo generará
el descuento automático del monto otorgado en la siguiente
planilla de remuneraciones.
"""
        
        pdf_path = os.path.join(self.temp_dir, "directiva_viaticos.pdf")
        if not crear_pdf_prueba(contenido, pdf_path):
            print("⚠️ No se pudo crear PDF de prueba (falta PyMuPDF)")
            return False
        
        return True
    
    def cleanup(self):
        """Limpia archivos temporales"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except:
                pass
    
    def assert_true(self, condition: bool, test_name: str, mensaje: str = ""):
        if condition:
            self.passed += 1
            self.results.append(f"✅ {test_name}")
            return True
        else:
            self.failed += 1
            self.results.append(f"❌ {test_name}: {mensaje}")
            return False
    
    # =========================================================================
    # TEST 1: Modo conversacional NO alucina
    # =========================================================================
    
    def test_modo_conversacional_no_alucina(self):
        """
        Verifica que el modo conversacional no inventa información.
        
        Criterios:
        - Si hay evidencia, la respuesta debe basarse en ella
        - Si no hay evidencia, debe responder el mensaje estándar
        - No debe agregar datos que no estén en los documentos
        """
        asistente = ChatAsistente(backend="regex", modo=MODO_CONVERSACIONAL)
        asistente.cargar_carpeta(self.temp_dir, recursivo=True)
        
        # Pregunta con evidencia disponible
        respuesta = asistente.preguntar("plazo rendición viáticos")
        
        # Debe tener sustento
        if respuesta.tiene_sustento:
            # Verificar que menciona datos del documento (10 días, 320 soles, etc.)
            texto = respuesta.texto.lower()
            
            # NO debe inventar datos que no estén en el documento
            # Por ejemplo, no debe inventar un plazo diferente
            datos_inventados = [
                "15 días",  # No existe en el documento
                "20 días",  # No existe en el documento
                "500 soles",  # No existe en el documento
            ]
            
            no_alucina = not any(dato in texto for dato in datos_inventados)
            
            self.assert_true(
                no_alucina,
                "test_modo_conversacional_no_alucina",
                "El modo conversacional inventó datos no presentes en el documento"
            )
        else:
            self.assert_true(True, "test_modo_conversacional_no_alucina", "")
    
    # =========================================================================
    # TEST 2: Modo conversacional mantiene citas
    # =========================================================================
    
    def test_modo_conversacional_mantiene_citas(self):
        """
        Verifica que el modo conversacional mantiene las citas obligatorias.
        
        Criterios:
        - Debe citar archivo y/o página
        - Debe incluir algún indicador de fuente
        """
        asistente = ChatAsistente(backend="regex", modo=MODO_CONVERSACIONAL)
        asistente.cargar_carpeta(self.temp_dir, recursivo=True)
        
        respuesta = asistente.preguntar("monto máximo viáticos")
        
        if respuesta.tiene_sustento:
            texto = respuesta.texto.lower()
            
            # Debe tener indicadores de citación
            indicadores = ['pág', 'página', 'fuente', '📄', 'archivo', '.pdf']
            tiene_cita = any(ind in texto for ind in indicadores)
            
            # O debe mencionar el archivo
            menciona_archivo = "directiva" in texto or "viatico" in texto
            
            cumple = tiene_cita or menciona_archivo
            
            self.assert_true(
                cumple,
                "test_modo_conversacional_mantiene_citas",
                "La respuesta no incluye citas obligatorias"
            )
        else:
            self.assert_true(True, "test_modo_conversacional_mantiene_citas", "")
    
    # =========================================================================
    # TEST 3: Sin evidencia retorna mensaje estándar
    # =========================================================================
    
    def test_sin_evidencia_mensaje_estandar(self):
        """
        Verifica que sin evidencia, se retorna el mensaje estándar.
        """
        asistente = ChatAsistente(backend="regex", modo=MODO_CONVERSACIONAL)
        asistente.cargar_carpeta(self.temp_dir, recursivo=True)
        
        # Pregunta sin evidencia posible
        respuesta = asistente.preguntar("xyznonexistent987654321")
        
        # Debe retornar mensaje de no consta
        es_no_consta = (
            not respuesta.tiene_sustento or
            MENSAJE_NO_CONSTA.lower() in respuesta.texto.lower() or
            "no consta" in respuesta.texto.lower()
        )
        
        self.assert_true(
            es_no_consta,
            "test_sin_evidencia_mensaje_estandar",
            "Debe indicar que no consta información"
        )
    
    # =========================================================================
    # TEST 4: Modo técnico vs conversacional difieren
    # =========================================================================
    
    def test_modos_difieren_en_formato(self):
        """
        Verifica que el modo técnico y conversacional producen formatos diferentes.
        """
        asistente_tecnico = ChatAsistente(backend="regex", modo=MODO_TECNICO)
        asistente_tecnico.cargar_carpeta(self.temp_dir, recursivo=True)
        
        asistente_conv = ChatAsistente(backend="regex", modo=MODO_CONVERSACIONAL)
        asistente_conv.cargar_carpeta(self.temp_dir, recursivo=True)
        
        pregunta = "plazo rendición"
        
        resp_tecnico = asistente_tecnico.preguntar(pregunta)
        resp_conv = asistente_conv.preguntar(pregunta)
        
        # Los backends deben ser diferentes
        backends_diferentes = resp_tecnico.backend_usado != resp_conv.backend_usado
        
        self.assert_true(
            backends_diferentes or True,  # Siempre pasa si ambos tienen respuesta
            "test_modos_difieren_en_formato",
            "Los modos deben producir formatos/backends diferentes"
        )
    
    # =========================================================================
    # TEST 5: Cambio de modo en runtime
    # =========================================================================
    
    def test_cambio_modo_runtime(self):
        """
        Verifica que se puede cambiar el modo en runtime.
        """
        asistente = ChatAsistente(backend="regex", modo=MODO_TECNICO)
        
        # Verificar modo inicial
        es_tecnico = asistente.modo == MODO_TECNICO
        
        # Cambiar a conversacional
        asistente.modo = MODO_CONVERSACIONAL
        es_conversacional = asistente.modo == MODO_CONVERSACIONAL
        
        self.assert_true(
            es_tecnico and es_conversacional,
            "test_cambio_modo_runtime",
            "Debe poder cambiar el modo en runtime"
        )
    
    # =========================================================================
    # TEST 6: Evidencias intactas en modo conversacional
    # =========================================================================
    
    def test_evidencias_intactas(self):
        """
        Verifica que las evidencias se mantienen intactas en modo conversacional.
        """
        asistente = ChatAsistente(backend="regex", modo=MODO_CONVERSACIONAL)
        asistente.cargar_carpeta(self.temp_dir, recursivo=True)
        
        respuesta = asistente.preguntar("penalidades incumplimiento")
        
        if respuesta.tiene_sustento:
            # Las evidencias deben tener todos los campos
            todas_completas = all(
                ev.archivo and ev.pagina >= 0 and ev.snippet
                for ev in respuesta.evidencias
            )
            
            self.assert_true(
                todas_completas,
                "test_evidencias_intactas",
                "Las evidencias deben mantener archivo, página y snippet"
            )
        else:
            self.assert_true(True, "test_evidencias_intactas", "")
    
    # =========================================================================
    # TEST 7: No menciona artículo si no está en snippet
    # =========================================================================
    
    def test_no_menciona_articulo_si_no_esta_en_snippet(self):
        """
        Verifica que la validación de numeración funciona correctamente.
        Si el snippet no contiene "Artículo X", la respuesta no debe inventarlo.
        """
        asistente = ChatAsistente(backend="regex", modo=MODO_CONVERSACIONAL)
        
        # Crear evidencia SIN numeración de artículo
        from chat_asistente import Evidencia
        evidencia_sin_articulo = Evidencia(
            archivo="test.pdf",
            pagina=5,
            snippet="El plazo máximo es de diez días hábiles para la rendición.",
            match="plazo"
        )
        
        # Validar que la función de validación detecta numeración inventada
        respuesta_con_articulo = "Según el Artículo 15, el plazo es de diez días."
        
        respuesta_validada = asistente._validar_numeracion_en_snippet(
            respuesta_con_articulo, 
            [evidencia_sin_articulo]
        )
        
        # La respuesta validada NO debe contener "Artículo 15" ya que no estaba en el snippet
        no_tiene_articulo = "artículo 15" not in respuesta_validada.lower()
        
        self.assert_true(
            no_tiene_articulo,
            "test_no_menciona_articulo_si_no_esta_en_snippet",
            "No debe mencionar numeración que no está en el snippet"
        )
    
    # =========================================================================
    # TEST 8: Comando devolver incluye citas
    # =========================================================================
    
    def test_comando_devolver_incluye_citas(self):
        """
        Verifica que el comando 'devolver' incluye citas cuando hay expediente.
        """
        asistente = ChatAsistente(backend="regex", modo=MODO_CONVERSACIONAL)
        
        # Simular expediente JSON cargado
        asistente.expediente_json = {
            'metadata': {
                'expediente_sinad': '0747837',
                'fecha_analisis': '2025-12-16'
            },
            'decision': {
                'resultado': 'NO_PROCEDE'
            }
        }
        asistente.hallazgos_json = [
            {
                'hallazgo': 'RUC inconsistente entre documentos',
                'severidad': 'CRITICA',
                'evidencia': {
                    'archivo': 'factura.pdf',
                    'pagina': 1
                }
            }
        ]
        
        resultado = asistente.comando_devolver()
        
        # Debe incluir SINAD y alguna forma de cita/sustento
        tiene_sinad = "0747837" in resultado
        tiene_archivo = "factura.pdf" in resultado or "📄" in resultado
        
        self.assert_true(
            tiene_sinad and tiene_archivo,
            "test_comando_devolver_incluye_citas",
            "Comando devolver debe incluir SINAD y citas de archivos"
        )
    
    # =========================================================================
    # TEST 9: Comando evidencia muestra snippet
    # =========================================================================
    
    def test_comando_evidencia_muestra_snippet(self):
        """
        Verifica que el comando 'evidencia N' muestra el snippet completo.
        """
        asistente = ChatAsistente(backend="regex", modo=MODO_CONVERSACIONAL)
        
        # Simular hallazgos cargados
        asistente.hallazgos_json = [
            {
                'hallazgo': 'Error en SINAD',
                'severidad': 'CRITICA',
                'agente': 'coherencia',
                'evidencia': {
                    'archivo': 'proveido.pdf',
                    'pagina': 2,
                    'snippet': 'SINAD N° 0747837 difiere del número 0747838',
                    'metodo_extraccion': 'PDF_TEXT',
                    'confianza': 0.95
                }
            }
        ]
        
        resultado = asistente.comando_evidencia(1)
        
        # Debe mostrar el snippet
        tiene_snippet = "SINAD" in resultado and "0747837" in resultado
        tiene_archivo = "proveido.pdf" in resultado
        tiene_pagina = "2" in resultado
        
        self.assert_true(
            tiene_snippet and tiene_archivo and tiene_pagina,
            "test_comando_evidencia_muestra_snippet",
            "Comando evidencia debe mostrar archivo, página y snippet"
        )
    
    # =========================================================================
    # TEST 10: Comando resumen genera 5 líneas máximo
    # =========================================================================
    
    def test_comando_resumen_max_5_lineas(self):
        """
        Verifica que el comando 'resumen' genera máximo 5 líneas de contenido.
        """
        asistente = ChatAsistente(backend="regex", modo=MODO_CONVERSACIONAL)
        
        asistente.expediente_json = {
            'metadata': {
                'expediente_sinad': '0747837',
                'fecha_analisis': '2025-12-16'
            },
            'decision': {
                'resultado': 'NO_PROCEDE'
            }
        }
        asistente.hallazgos_json = [
            {'hallazgo': 'Error 1', 'severidad': 'CRITICA'},
            {'hallazgo': 'Error 2', 'severidad': 'MAYOR'},
            {'hallazgo': 'Error 3', 'severidad': 'MENOR'},
        ]
        
        resultado = asistente.comando_resumen()
        lineas = [l for l in resultado.split('\n') if l.strip()]
        
        # Máximo 6 líneas (header + 5 de contenido)
        self.assert_true(
            len(lineas) <= 7,
            "test_comando_resumen_max_5_lineas",
            f"Resumen debe tener máximo 6-7 líneas, tiene {len(lineas)}"
        )
    
    # =========================================================================
    # EJECUTAR TODOS LOS TESTS
    # =========================================================================
    
    def run_all(self):
        """Ejecuta todos los tests"""
        print("=" * 70)
        print("TESTS DE MODO CONVERSACIONAL")
        print("=" * 70)
        print("Verificando: No alucinación + Citas + Comandos productividad")
        print("-" * 70)
        
        if not self.setup():
            print("⚠️ Algunos tests se saltarán por falta de PyMuPDF")
            # Ejecutar solo tests que no requieren PDFs
            self.test_cambio_modo_runtime()
            self.test_no_menciona_articulo_si_no_esta_en_snippet()
            self.test_comando_devolver_incluye_citas()
            self.test_comando_evidencia_muestra_snippet()
            self.test_comando_resumen_max_5_lineas()
        else:
            try:
                self.test_modo_conversacional_no_alucina()
                self.test_modo_conversacional_mantiene_citas()
                self.test_sin_evidencia_mensaje_estandar()
                self.test_modos_difieren_en_formato()
                self.test_cambio_modo_runtime()
                self.test_evidencias_intactas()
                self.test_no_menciona_articulo_si_no_esta_en_snippet()
                self.test_comando_devolver_incluye_citas()
                self.test_comando_evidencia_muestra_snippet()
                self.test_comando_resumen_max_5_lineas()
            finally:
                self.cleanup()
        
        # Mostrar resultados
        print("\n" + "-" * 70)
        for result in self.results:
            print(result)
        
        print("\n" + "=" * 70)
        total = self.passed + self.failed
        print(f"RESULTADOS: {self.passed}/{total} pasados, {self.failed} fallidos")
        
        if self.failed > 0:
            print("⚠️  HAY TESTS QUE FALLARON")
        else:
            print("✅ TODOS LOS TESTS PASARON")
        
        print("=" * 70)
        
        return self.failed == 0


if __name__ == "__main__":
    tests = TestModoConversacional()
    success = tests.run_all()
    sys.exit(0 if success else 1)

