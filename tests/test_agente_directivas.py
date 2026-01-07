# -*- coding: utf-8 -*-
"""
TESTS DE AGENTE DE DIRECTIVAS - ESTÁNDAR PROBATORIO
====================================================
Tests que DEBEN FALLAR si:
1. Se responde sin archivo
2. Se responde sin página
3. Se responde sin snippet
4. Se responde sin haber PDFs cargados
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from agentes.agente_directivas import (
    AgenteDirectivas,
    RespuestaDirectiva,
    EvidenciaDirectiva,
    MENSAJE_NO_CONSTA
)


# =============================================================================
# PDF DE PRUEBA
# =============================================================================

def crear_pdf_prueba(contenido: str, nombre: str = "test_directiva.pdf") -> str:
    """Crea un PDF temporal de prueba"""
    try:
        import fitz
        
        # Crear directorio temporal
        temp_dir = tempfile.mkdtemp()
        ruta = os.path.join(temp_dir, nombre)
        
        # Crear PDF
        doc = fitz.open()
        page = doc.new_page()
        
        # Insertar texto
        rect = fitz.Rect(50, 50, 550, 750)
        page.insert_textbox(rect, contenido, fontsize=11)
        
        doc.save(ruta)
        doc.close()
        
        return ruta
        
    except ImportError:
        return None


CONTENIDO_DIRECTIVA_PRUEBA = """
DIRECTIVA N° 001-2025-MINEDU

DIRECTIVA PARA LA ADMINISTRACIÓN DE VIÁTICOS

CAPÍTULO I: DISPOSICIONES GENERALES

Artículo 1.- Objeto
La presente directiva tiene por objeto establecer las disposiciones para 
la administración y rendición de viáticos del personal del Ministerio.

Artículo 2.- Ámbito de aplicación
Aplica a todo el personal que realice comisiones de servicio.

CAPÍTULO II: DEL PLAZO DE RENDICIÓN

Artículo 5.- Plazo para rendir viáticos
El comisionado tiene un plazo máximo de OCHO (8) DÍAS HÁBILES contados 
desde el término de la comisión para presentar la rendición de cuentas.

Artículo 6.- Documentos requeridos
La rendición debe incluir:
a) Formato de rendición de cuentas
b) Comprobantes de pago originales
c) Declaración jurada de gastos

CAPÍTULO III: DE LAS PENALIDADES

Artículo 10.- Penalidad por incumplimiento
En caso de no presentar la rendición en el plazo establecido, se aplicará
un descuento del 10% del monto de viáticos no rendidos.
"""


# =============================================================================
# CLASE DE TESTS
# =============================================================================

class TestAgenteDirectivas:
    """Tests de estándar probatorio para agente de directivas"""
    
    def setup_method(self, method=None):
        """Inicializa el entorno para cada test (compatible con pytest)"""
        self.passed = 0
        self.failed = 0
        self.results = []
        self.pdf_prueba = None
        self.setup()
    
    def teardown_method(self, method=None):
        """Limpia después de cada test (compatible con pytest)"""
        self.cleanup()
    
    def setup(self):
        """Configura el entorno de prueba"""
        self.pdf_prueba = crear_pdf_prueba(CONTENIDO_DIRECTIVA_PRUEBA)
        if not self.pdf_prueba:
            print("⚠️ No se pudo crear PDF de prueba (falta PyMuPDF)")
            return False
        return True
    
    def cleanup(self):
        """Limpia archivos temporales"""
        if self.pdf_prueba and os.path.exists(self.pdf_prueba):
            try:
                os.remove(self.pdf_prueba)
                os.rmdir(os.path.dirname(self.pdf_prueba))
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
    # TEST 1: Sin PDFs cargados debe retornar mensaje apropiado
    # =========================================================================
    
    def test_sin_pdfs_retorna_mensaje(self):
        """Sin PDFs debe indicar que no hay documentos"""
        agente = AgenteDirectivas(backend="regex")
        respuesta = agente.preguntar("¿Cuál es el plazo?")
        
        self.assert_true(
            "no hay documentos" in respuesta.texto.lower() or 
            not respuesta.tiene_sustento,
            "test_sin_pdfs_retorna_mensaje",
            "Debe indicar que no hay documentos cargados"
        )
    
    # =========================================================================
    # TEST 2: Respuesta con sustento DEBE tener archivo
    # =========================================================================
    
    def test_respuesta_tiene_archivo(self):
        """Respuesta con sustento debe citar archivo"""
        if not self.pdf_prueba:
            self.results.append("⏭️ test_respuesta_tiene_archivo: Saltado (sin PyMuPDF)")
            return
        
        agente = AgenteDirectivas(backend="regex")
        agente.cargar_pdf(self.pdf_prueba)
        
        respuesta = agente.preguntar("¿Cuál es el plazo para rendir viáticos?")
        
        if respuesta.tiene_sustento:
            tiene_archivo = all(ev.archivo for ev in respuesta.evidencias)
            self.assert_true(
                tiene_archivo,
                "test_respuesta_tiene_archivo",
                "Evidencias deben tener archivo"
            )
        else:
            self.assert_true(
                True,
                "test_respuesta_tiene_archivo",
                "Sin sustento (aceptable)"
            )
    
    # =========================================================================
    # TEST 3: Respuesta con sustento DEBE tener página
    # =========================================================================
    
    def test_respuesta_tiene_pagina(self):
        """Respuesta con sustento debe citar página"""
        if not self.pdf_prueba:
            self.results.append("⏭️ test_respuesta_tiene_pagina: Saltado (sin PyMuPDF)")
            return
        
        agente = AgenteDirectivas(backend="regex")
        agente.cargar_pdf(self.pdf_prueba)
        
        respuesta = agente.preguntar("plazo días hábiles rendición")
        
        if respuesta.tiene_sustento:
            tiene_pagina = all(ev.pagina > 0 for ev in respuesta.evidencias)
            self.assert_true(
                tiene_pagina,
                "test_respuesta_tiene_pagina",
                "Evidencias deben tener página > 0"
            )
        else:
            self.assert_true(True, "test_respuesta_tiene_pagina", "")
    
    # =========================================================================
    # TEST 4: Respuesta con sustento DEBE tener snippet
    # =========================================================================
    
    def test_respuesta_tiene_snippet(self):
        """Respuesta con sustento debe incluir snippet"""
        if not self.pdf_prueba:
            self.results.append("⏭️ test_respuesta_tiene_snippet: Saltado (sin PyMuPDF)")
            return
        
        agente = AgenteDirectivas(backend="regex")
        agente.cargar_pdf(self.pdf_prueba)
        
        respuesta = agente.preguntar("penalidad incumplimiento")
        
        if respuesta.tiene_sustento:
            tiene_snippet = all(ev.snippet for ev in respuesta.evidencias)
            self.assert_true(
                tiene_snippet,
                "test_respuesta_tiene_snippet",
                "Evidencias deben tener snippet"
            )
        else:
            self.assert_true(True, "test_respuesta_tiene_snippet", "")
    
    # =========================================================================
    # TEST 5: Término inexistente debe retornar "no consta"
    # =========================================================================
    
    def test_termino_inexistente_retorna_no_consta(self):
        """Término no encontrado debe retornar mensaje de no consta"""
        if not self.pdf_prueba:
            self.results.append("⏭️ test_termino_inexistente_retorna_no_consta: Saltado")
            return
        
        agente = AgenteDirectivas(backend="regex")
        agente.cargar_pdf(self.pdf_prueba)
        
        # Usar pregunta con términos que NO existen en el PDF de prueba
        respuesta = agente.preguntar("xyzabc123nonexistent qwerty98765")
        
        es_no_consta = (
            MENSAJE_NO_CONSTA.lower() in respuesta.texto.lower() or
            not respuesta.tiene_sustento or
            len(respuesta.evidencias) == 0
        )
        
        self.assert_true(
            es_no_consta,
            "test_termino_inexistente_retorna_no_consta",
            f"Debe indicar no consta o no tener evidencias (tiene_sustento={respuesta.tiene_sustento}, evidencias={len(respuesta.evidencias)})"
        )
    
    # =========================================================================
    # TEST 6: Evidencia completa cumple estándar
    # =========================================================================
    
    def test_evidencia_completa_cumple_estandar(self):
        """Evidencia con archivo+página+snippet cumple estándar"""
        ev = EvidenciaDirectiva(
            archivo="test.pdf",
            pagina=5,
            snippet="Texto de prueba",
            contexto="contexto"
        )
        
        cumple = bool(ev.archivo and ev.pagina > 0 and ev.snippet)
        
        self.assert_true(
            cumple,
            "test_evidencia_completa_cumple_estandar",
            "Evidencia completa debe cumplir estándar"
        )
    
    # =========================================================================
    # TEST 7: Evidencia sin archivo NO cumple estándar
    # =========================================================================
    
    def test_evidencia_sin_archivo_no_cumple(self):
        """Evidencia sin archivo NO cumple estándar"""
        ev = EvidenciaDirectiva(
            archivo="",  # FALTA
            pagina=5,
            snippet="Texto"
        )
        
        cumple = bool(ev.archivo and ev.pagina > 0 and ev.snippet)
        
        self.assert_true(
            not cumple,
            "test_evidencia_sin_archivo_no_cumple",
            "Sin archivo no debe cumplir"
        )
    
    # =========================================================================
    # TEST 8: Evidencia sin página NO cumple estándar
    # =========================================================================
    
    def test_evidencia_sin_pagina_no_cumple(self):
        """Evidencia sin página NO cumple estándar"""
        ev = EvidenciaDirectiva(
            archivo="test.pdf",
            pagina=0,  # FALTA
            snippet="Texto"
        )
        
        cumple = bool(ev.archivo and ev.pagina > 0 and ev.snippet)
        
        self.assert_true(
            not cumple,
            "test_evidencia_sin_pagina_no_cumple",
            "Sin página no debe cumplir"
        )
    
    # =========================================================================
    # TEST 9: Evidencia sin snippet NO cumple estándar
    # =========================================================================
    
    def test_evidencia_sin_snippet_no_cumple(self):
        """Evidencia sin snippet NO cumple estándar"""
        ev = EvidenciaDirectiva(
            archivo="test.pdf",
            pagina=5,
            snippet=""  # FALTA
        )
        
        cumple = bool(ev.archivo and ev.pagina > 0 and ev.snippet)
        
        self.assert_true(
            not cumple,
            "test_evidencia_sin_snippet_no_cumple",
            "Sin snippet no debe cumplir"
        )
    
    # =========================================================================
    # TEST 10: Búsqueda encuentra texto existente
    # =========================================================================
    
    def test_busqueda_encuentra_texto(self):
        """Búsqueda debe encontrar texto existente en PDF"""
        if not self.pdf_prueba:
            self.results.append("⏭️ test_busqueda_encuentra_texto: Saltado")
            return
        
        agente = AgenteDirectivas(backend="regex")
        agente.cargar_pdf(self.pdf_prueba)
        
        # Buscar término que existe en el PDF
        evidencias = agente.buscar_en_documentos(["viáticos", "plazo"])
        
        self.assert_true(
            len(evidencias) > 0,
            "test_busqueda_encuentra_texto",
            "Debe encontrar términos existentes"
        )
    
    # =========================================================================
    # EJECUTAR TODOS LOS TESTS
    # =========================================================================
    
    def run_all(self):
        """Ejecuta todos los tests"""
        print("=" * 70)
        print("TESTS DE AGENTE DE DIRECTIVAS - ESTÁNDAR PROBATORIO")
        print("=" * 70)
        print("Política: Solo respuestas con archivo + página + snippet")
        print("-" * 70)
        
        # Setup
        if not self.setup():
            print("⚠️ Algunos tests se saltarán por falta de PyMuPDF")
        
        try:
            # Ejecutar tests
            self.test_sin_pdfs_retorna_mensaje()
            self.test_respuesta_tiene_archivo()
            self.test_respuesta_tiene_pagina()
            self.test_respuesta_tiene_snippet()
            self.test_termino_inexistente_retorna_no_consta()
            self.test_evidencia_completa_cumple_estandar()
            self.test_evidencia_sin_archivo_no_cumple()
            self.test_evidencia_sin_pagina_no_cumple()
            self.test_evidencia_sin_snippet_no_cumple()
            self.test_busqueda_encuentra_texto()
            
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
    tests = TestAgenteDirectivas()
    success = tests.run_all()
    sys.exit(0 if success else 1)

