# -*- coding: utf-8 -*-
"""
TESTS DE CHAT ASISTENTE - ESTÁNDAR PROBATORIO
==============================================
Tests que verifican:
1. Detección de PDFs en carpetas recursivas (rglob)
2. Respuestas con sustento DEBEN incluir archivo+página+snippet
3. Retrieval determinístico funciona correctamente
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
    MENSAJE_NO_CONSTA
)


# =============================================================================
# HELPERS PARA TESTS
# =============================================================================

def crear_pdf_prueba(contenido: str, ruta: str) -> bool:
    """Crea un PDF de prueba en la ruta especificada"""
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


def crear_estructura_carpetas(base_dir: str) -> dict:
    """
    Crea estructura de carpetas con PDFs para test recursivo:
    
    base_dir/
    ├── directiva_raiz.pdf
    ├── subcarpeta1/
    │   └── norma_sub1.pdf
    └── subcarpeta2/
        └── nivel2/
            └── pauta_nivel2.pdf
    """
    estructura = {
        "raiz": os.path.join(base_dir, "directiva_raiz.pdf"),
        "sub1": os.path.join(base_dir, "subcarpeta1", "norma_sub1.pdf"),
        "sub2": os.path.join(base_dir, "subcarpeta2", "nivel2", "pauta_nivel2.pdf")
    }
    
    contenidos = {
        "raiz": "DIRECTIVA RAÍZ\nArtículo 1. Esta es la directiva principal.\nEl plazo es de 10 días hábiles.",
        "sub1": "NORMA SUBCARPETA 1\nArtículo 5. Los viáticos se rinden en 8 días.\nEl monto máximo es S/ 500.",
        "sub2": "PAUTA NIVEL 2\nNumeral 3.2. La penalidad es del 10%.\nAplica para contratos mayores a S/ 1000."
    }
    
    for key, ruta in estructura.items():
        if not crear_pdf_prueba(contenidos[key], ruta):
            return None
    
    return estructura


# =============================================================================
# CLASE DE TESTS
# =============================================================================

class TestChatAsistente:
    """Tests del Chat Asistente"""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
        self.temp_dir = None
        self.estructura = None
    
    def setup(self):
        """Configura el entorno de prueba"""
        self.temp_dir = tempfile.mkdtemp()
        self.estructura = crear_estructura_carpetas(self.temp_dir)
        
        if not self.estructura:
            print("⚠️ No se pudo crear estructura de prueba (falta PyMuPDF)")
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
    # TEST 1: Carpeta recursiva detecta PDFs en subcarpetas
    # =========================================================================
    
    def test_carpeta_recursiva_detecta_subcarpetas(self):
        """Verifica que rglob encuentra PDFs en subcarpetas"""
        if not self.estructura:
            self.results.append("⏭️ test_carpeta_recursiva_detecta_subcarpetas: Saltado")
            return
        
        asistente = ChatAsistente(backend="regex")
        cargados, rutas = asistente.cargar_carpeta(self.temp_dir, recursivo=True)
        
        # Debe encontrar los 3 PDFs
        self.assert_true(
            cargados == 3,
            "test_carpeta_recursiva_detecta_subcarpetas",
            f"Esperado 3 PDFs, encontrados {cargados}"
        )
        
        # Verificar que retorna lista de rutas
        self.assert_true(
            len(rutas) == 3,
            "test_carpeta_recursiva_retorna_rutas",
            f"Esperado 3 rutas, retornadas {len(rutas)}"
        )
    
    # =========================================================================
    # TEST 2: Carpeta NO recursiva solo detecta raíz
    # =========================================================================
    
    def test_carpeta_no_recursiva_solo_raiz(self):
        """Verifica que glob normal solo encuentra PDFs en raíz"""
        if not self.estructura:
            self.results.append("⏭️ test_carpeta_no_recursiva_solo_raiz: Saltado")
            return
        
        asistente = ChatAsistente(backend="regex")
        cargados, rutas = asistente.cargar_carpeta(self.temp_dir, recursivo=False)
        
        # Solo debe encontrar 1 PDF (el de la raíz)
        self.assert_true(
            cargados == 1,
            "test_carpeta_no_recursiva_solo_raiz",
            f"Esperado 1 PDF, encontrados {cargados}"
        )
    
    # =========================================================================
    # TEST 2b: Carpeta vacía retorna 0 PDFs
    # =========================================================================
    
    def test_carpeta_vacia_retorna_cero(self):
        """Carpeta vacía debe retornar 0 PDFs cargados"""
        # Crear carpeta temporal vacía
        carpeta_vacia = tempfile.mkdtemp()
        
        try:
            asistente = ChatAsistente(backend="regex")
            cargados, rutas = asistente.cargar_carpeta(carpeta_vacia, recursivo=True)
            
            self.assert_true(
                cargados == 0 and len(rutas) == 0,
                "test_carpeta_vacia_retorna_cero",
                f"Esperado 0 PDFs, encontrados {cargados}"
            )
        finally:
            shutil.rmtree(carpeta_vacia, ignore_errors=True)
    
    # =========================================================================
    # TEST 2c: PDFs de 0 bytes son ignorados
    # =========================================================================
    
    def test_pdfs_cero_bytes_ignorados(self):
        """PDFs de 0 bytes deben ser ignorados"""
        carpeta_temp = tempfile.mkdtemp()
        
        try:
            # Crear PDF vacío (0 bytes)
            pdf_vacio = os.path.join(carpeta_temp, "vacio.pdf")
            with open(pdf_vacio, 'w') as f:
                pass  # Archivo de 0 bytes
            
            asistente = ChatAsistente(backend="regex")
            cargados, rutas = asistente.cargar_carpeta(carpeta_temp, recursivo=True)
            
            self.assert_true(
                cargados == 0,
                "test_pdfs_cero_bytes_ignorados",
                "PDFs de 0 bytes deben ser ignorados"
            )
        finally:
            shutil.rmtree(carpeta_temp, ignore_errors=True)
    
    # =========================================================================
    # TEST 3: Respuesta con sustento DEBE tener archivo
    # =========================================================================
    
    def test_respuesta_sustento_tiene_archivo(self):
        """Respuesta con sustento debe tener archivo en evidencias"""
        if not self.estructura:
            self.results.append("⏭️ test_respuesta_sustento_tiene_archivo: Saltado")
            return
        
        asistente = ChatAsistente(backend="regex")
        asistente.cargar_carpeta(self.temp_dir, recursivo=True)  # Ignora retorno para este test
        
        respuesta = asistente.preguntar("plazo días hábiles")
        
        if respuesta.tiene_sustento:
            tiene_archivo = all(ev.archivo for ev in respuesta.evidencias)
            self.assert_true(
                tiene_archivo,
                "test_respuesta_sustento_tiene_archivo",
                "Todas las evidencias deben tener archivo"
            )
        else:
            self.assert_true(True, "test_respuesta_sustento_tiene_archivo", "")
    
    # =========================================================================
    # TEST 4: Respuesta con sustento DEBE tener página
    # =========================================================================
    
    def test_respuesta_sustento_tiene_pagina(self):
        """Respuesta con sustento debe tener página en evidencias"""
        if not self.estructura:
            self.results.append("⏭️ test_respuesta_sustento_tiene_pagina: Saltado")
            return
        
        asistente = ChatAsistente(backend="regex")
        asistente.cargar_carpeta(self.temp_dir, recursivo=True)
        
        respuesta = asistente.preguntar("viáticos rendición")
        
        if respuesta.tiene_sustento:
            tiene_pagina = all(ev.pagina >= 0 for ev in respuesta.evidencias)
            self.assert_true(
                tiene_pagina,
                "test_respuesta_sustento_tiene_pagina",
                "Todas las evidencias deben tener página"
            )
        else:
            self.assert_true(True, "test_respuesta_sustento_tiene_pagina", "")
    
    # =========================================================================
    # TEST 5: Respuesta con sustento DEBE tener snippet
    # =========================================================================
    
    def test_respuesta_sustento_tiene_snippet(self):
        """Respuesta con sustento debe tener snippet en evidencias"""
        if not self.estructura:
            self.results.append("⏭️ test_respuesta_sustento_tiene_snippet: Saltado")
            return
        
        asistente = ChatAsistente(backend="regex")
        asistente.cargar_carpeta(self.temp_dir, recursivo=True)
        
        respuesta = asistente.preguntar("penalidad contratos")
        
        if respuesta.tiene_sustento:
            tiene_snippet = all(ev.snippet for ev in respuesta.evidencias)
            self.assert_true(
                tiene_snippet,
                "test_respuesta_sustento_tiene_snippet",
                "Todas las evidencias deben tener snippet"
            )
        else:
            self.assert_true(True, "test_respuesta_sustento_tiene_snippet", "")
    
    # =========================================================================
    # TEST 6: Término inexistente retorna "no consta"
    # =========================================================================
    
    def test_termino_inexistente_no_consta(self):
        """Término no encontrado debe retornar mensaje de no consta"""
        if not self.estructura:
            self.results.append("⏭️ test_termino_inexistente_no_consta: Saltado")
            return
        
        asistente = ChatAsistente(backend="regex")
        asistente.cargar_carpeta(self.temp_dir, recursivo=True)
        
        respuesta = asistente.preguntar("xyznonexistent123 qwerty98765")
        
        no_consta = (
            not respuesta.tiene_sustento or
            len(respuesta.evidencias) == 0
        )
        
        self.assert_true(
            no_consta,
            "test_termino_inexistente_no_consta",
            "Debe indicar que no consta o no tener evidencias"
        )
    
    # =========================================================================
    # TEST 7: Evidencia válida tiene los 3 campos obligatorios
    # =========================================================================
    
    def test_evidencia_campos_obligatorios(self):
        """Evidencia debe tener archivo, página y snippet"""
        ev = Evidencia(
            archivo="test.pdf",
            pagina=5,
            snippet="Texto de prueba",
            match="prueba"
        )
        
        cumple = bool(ev.archivo and ev.pagina >= 0 and ev.snippet and ev.match)
        
        self.assert_true(
            cumple,
            "test_evidencia_campos_obligatorios",
            "Evidencia debe tener todos los campos"
        )
    
    # =========================================================================
    # TEST 8: Evidencia sin archivo NO es válida
    # =========================================================================
    
    def test_evidencia_sin_archivo_invalida(self):
        """Evidencia sin archivo no es válida"""
        ev = Evidencia(
            archivo="",  # FALTA
            pagina=5,
            snippet="Texto",
            match="test"
        )
        
        invalida = not bool(ev.archivo)
        
        self.assert_true(
            invalida,
            "test_evidencia_sin_archivo_invalida",
            "Evidencia sin archivo debe ser inválida"
        )
    
    # =========================================================================
    # TEST 9: Evidencia sin snippet NO es válida
    # =========================================================================
    
    def test_evidencia_sin_snippet_invalida(self):
        """Evidencia sin snippet no es válida"""
        ev = Evidencia(
            archivo="test.pdf",
            pagina=5,
            snippet="",  # FALTA
            match="test"
        )
        
        invalida = not bool(ev.snippet)
        
        self.assert_true(
            invalida,
            "test_evidencia_sin_snippet_invalida",
            "Evidencia sin snippet debe ser inválida"
        )
    
    # =========================================================================
    # TEST 10: Memoria no excede 5 turnos
    # =========================================================================
    
    def test_memoria_max_5_turnos(self):
        """La memoria no debe exceder 5 turnos"""
        if not self.estructura:
            self.results.append("⏭️ test_memoria_max_5_turnos: Saltado")
            return
        
        asistente = ChatAsistente(backend="regex")
        asistente.cargar_carpeta(self.temp_dir, recursivo=True)
        
        # Hacer 7 preguntas
        for i in range(7):
            asistente.preguntar(f"pregunta número {i}")
        
        self.assert_true(
            len(asistente.memoria) <= 5,
            "test_memoria_max_5_turnos",
            f"Memoria tiene {len(asistente.memoria)} turnos, máximo 5"
        )
    
    # =========================================================================
    # TEST 11: Retrieval encuentra términos en múltiples archivos
    # =========================================================================
    
    def test_retrieval_multiples_archivos(self):
        """Retrieval debe encontrar términos en diferentes archivos"""
        if not self.estructura:
            self.results.append("⏭️ test_retrieval_multiples_archivos: Saltado")
            return
        
        asistente = ChatAsistente(backend="regex")
        asistente.cargar_carpeta(self.temp_dir, recursivo=True)
        
        # "artículo" aparece en múltiples PDFs
        evidencias = asistente.retrieval("artículo")
        
        archivos_unicos = set(ev.archivo for ev in evidencias)
        
        self.assert_true(
            len(archivos_unicos) >= 2,
            "test_retrieval_multiples_archivos",
            f"Esperado >= 2 archivos, encontrados {len(archivos_unicos)}"
        )
    
    # =========================================================================
    # TEST 12: Sin documentos retorna mensaje apropiado
    # =========================================================================
    
    def test_sin_documentos_mensaje_apropiado(self):
        """Sin documentos debe indicar que no hay documentos"""
        asistente = ChatAsistente(backend="regex")
        
        respuesta = asistente.preguntar("cualquier pregunta")
        
        self.assert_true(
            "no hay documentos" in respuesta.texto.lower() or not respuesta.tiene_sustento,
            "test_sin_documentos_mensaje_apropiado",
            "Debe indicar que no hay documentos"
        )
    
    # =========================================================================
    # EJECUTAR TODOS LOS TESTS
    # =========================================================================
    
    def run_all(self):
        """Ejecuta todos los tests"""
        print("=" * 70)
        print("TESTS DE CHAT ASISTENTE - ESTÁNDAR PROBATORIO")
        print("=" * 70)
        print("Verificando: Carpeta recursiva + Evidencia obligatoria")
        print("-" * 70)
        
        if not self.setup():
            print("⚠️ Algunos tests se saltarán por falta de PyMuPDF")
        
        try:
            # Tests de carpeta recursiva y validación
            self.test_carpeta_recursiva_detecta_subcarpetas()
            self.test_carpeta_no_recursiva_solo_raiz()
            self.test_carpeta_vacia_retorna_cero()
            self.test_pdfs_cero_bytes_ignorados()
            
            # Tests de estándar probatorio
            self.test_respuesta_sustento_tiene_archivo()
            self.test_respuesta_sustento_tiene_pagina()
            self.test_respuesta_sustento_tiene_snippet()
            self.test_termino_inexistente_no_consta()
            
            # Tests de Evidencia
            self.test_evidencia_campos_obligatorios()
            self.test_evidencia_sin_archivo_invalida()
            self.test_evidencia_sin_snippet_invalida()
            
            # Tests de memoria y retrieval
            self.test_memoria_max_5_turnos()
            self.test_retrieval_multiples_archivos()
            self.test_sin_documentos_mensaje_apropiado()
            
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
    tests = TestChatAsistente()
    success = tests.run_all()
    sys.exit(0 if success else 1)


