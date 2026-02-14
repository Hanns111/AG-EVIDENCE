# -*- coding: utf-8 -*-
"""
Tests para pdf_text_extractor — Gating PDF nativo vs OCR
=========================================================
Fase 2 del pipeline OCR.
"""

import pytest
from pathlib import Path
import sys

# Agregar path del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.pdf_text_extractor import (
    extract_text_with_gating,
    get_texto_extraido,
)
from src.ingestion.config import GatingThresholds

# Detectar runtime: PyMuPDF solo disponible en WSL2, no en Windows host
try:
    import fitz  # noqa: F401
    FITZ_DISPONIBLE = True
except ImportError:
    FITZ_DISPONIBLE = False

requires_pymupdf = pytest.mark.skipif(
    not FITZ_DISPONIBLE,
    reason="PyMuPDF (fitz) no disponible — estos tests requieren WSL2 runtime"
)


# Rutas de PDFs de prueba
DATA_DIR = Path(__file__).parent.parent / "data"
PAUTAS_DIR = DATA_DIR / "directivas" / "vigentes_2025_11_26" / "PAUTAS"


def _get_pdf_nativo():
    """Obtiene un PDF nativo de prueba si existe."""
    if PAUTAS_DIR.exists():
        pdfs = list(PAUTAS_DIR.glob("*.pdf"))
        if pdfs:
            return pdfs[0]
    return None


class TestDirectTextPath:
    """Tests para PDFs nativos con texto embebido."""
    
    @requires_pymupdf
    def test_direct_text_detection(self):
        """Un PDF nativo debe detectarse como direct_text."""
        pdf_path = _get_pdf_nativo()
        if pdf_path is None:
            pytest.skip("No hay PDF de prueba disponible en PAUTAS")
        
        resultado = extract_text_with_gating(pdf_path, lang="spa")
        
        # Verificar estructura del resultado
        assert "decision" in resultado
        assert "metodo" in resultado["decision"]
        assert "razon" in resultado["decision"]
        assert "direct_text" in resultado
        assert "ocr" in resultado
        assert "evidencia" in resultado
        
        # El PDF de PAUTAS es nativo, debería ser direct_text
        assert resultado["decision"]["metodo"] == "direct_text", (
            f"Esperado direct_text, obtenido {resultado['decision']['metodo']}. "
            f"Razón: {resultado['decision']['razon']}"
        )
        
        # Verificar que tiene texto
        texto = get_texto_extraido(resultado)
        assert len(texto) > 0, "El texto extraído no debe estar vacío"
        
        # Verificar evidencia
        assert resultado["evidencia"]["version_modulo"] is not None
        assert resultado["evidencia"]["timestamp_iso"] is not None
    
    @requires_pymupdf
    def test_direct_text_metrics(self):
        """Las métricas de direct_text deben estar completas."""
        pdf_path = _get_pdf_nativo()
        if pdf_path is None:
            pytest.skip("No hay PDF de prueba disponible")
        
        resultado = extract_text_with_gating(pdf_path)
        
        direct = resultado["direct_text"]
        assert "num_chars" in direct
        assert "num_words" in direct
        assert "num_paginas" in direct
        assert "tiempo_ms" in direct
        assert direct["error"] is None


class TestOCRPath:
    """Tests para OCR cuando direct_text no es suficiente."""
    
    def test_ocr_fallback_with_low_threshold(self):
        """Con umbral muy alto, debería caer en OCR o fallback."""
        pdf_path = _get_pdf_nativo()
        if pdf_path is None:
            pytest.skip("No hay PDF de prueba disponible")
        
        # Umbral imposiblemente alto
        thresholds = GatingThresholds(
            direct_text_min_chars=999999999,
            direct_text_min_words=999999999,
            ocr_min_confidence=0.01,  # Muy bajo para que OCR pase
            ocr_min_words=1
        )
        
        resultado = extract_text_with_gating(pdf_path, thresholds=thresholds)
        
        # No debería ser direct_text
        assert resultado["decision"]["metodo"] in ["ocr", "fallback_manual"], (
            f"Con umbral imposible, no debería ser direct_text. "
            f"Obtenido: {resultado['decision']['metodo']}"
        )
        
        # Si es OCR, verificar estructura
        if resultado["decision"]["metodo"] == "ocr":
            ocr = resultado["ocr"]
            assert "confianza_promedio" in ocr
            assert "num_words" in ocr
    
    def test_ocr_result_structure(self):
        """El resultado OCR debe tener estructura completa."""
        pdf_path = _get_pdf_nativo()
        if pdf_path is None:
            pytest.skip("No hay PDF de prueba disponible")
        
        resultado = extract_text_with_gating(pdf_path)
        
        # OCR siempre se ejecuta para tener métricas
        ocr = resultado["ocr"]
        assert "texto" in ocr or "error" in ocr
        assert "confianza_promedio" in ocr
        assert "tiempo_ms" in ocr


class TestFailureSafe:
    """Tests para manejo seguro de errores."""
    
    def test_archivo_inexistente(self):
        """Un archivo inexistente debe retornar fallback_manual sin excepción."""
        pdf_path = Path("/ruta/que/no/existe/archivo_falso.pdf")
        
        # NO debe lanzar excepción
        resultado = extract_text_with_gating(pdf_path)
        
        # Debe ser fallback_manual
        assert resultado["decision"]["metodo"] == "fallback_manual"
        assert "archivo_no_encontrado" in resultado["decision"]["razon"]
        
        # Evidencia debe estar presente
        assert resultado["evidencia"]["timestamp_iso"] is not None
    
    def test_pdf_corrupto_simulado(self):
        """Un archivo que no es PDF debe manejarse sin excepción."""
        # Crear archivo temporal que no es PDF
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"Este no es un PDF valido, solo texto plano")
            temp_path = Path(f.name)
        
        try:
            resultado = extract_text_with_gating(temp_path)
            
            # No debe lanzar excepción
            # El resultado puede ser fallback_manual o direct_text con poco texto
            assert resultado["decision"]["metodo"] in ["fallback_manual", "direct_text", "ocr"]
            
            # La evidencia siempre debe existir
            assert resultado["evidencia"]["timestamp_iso"] is not None
            assert resultado["metricas_documento"]["existe"] is True
            
        finally:
            temp_path.unlink()
    
    def test_estructura_completa_siempre(self):
        """La estructura de salida debe estar completa incluso con errores."""
        resultado = extract_text_with_gating("/no/existe.pdf")
        
        # Verificar todas las claves obligatorias
        assert "archivo" in resultado
        assert "decision" in resultado
        assert "direct_text" in resultado
        assert "ocr" in resultado
        assert "metricas_documento" in resultado
        assert "evidencia" in resultado
        
        # Subclaves de evidencia
        assert "thresholds_usados" in resultado["evidencia"]
        assert "version_modulo" in resultado["evidencia"]
        assert "timestamp_iso" in resultado["evidencia"]


class TestThresholdsConfig:
    """Tests para configuración de umbrales."""
    
    def test_custom_thresholds(self):
        """Los umbrales personalizados deben aplicarse."""
        custom = GatingThresholds(
            direct_text_min_chars=50,
            direct_text_min_words=5,
            ocr_min_confidence=0.90,
            ocr_min_words=100
        )
        
        pdf_path = _get_pdf_nativo()
        if pdf_path is None:
            pytest.skip("No hay PDF de prueba disponible")
        
        resultado = extract_text_with_gating(pdf_path, thresholds=custom)
        
        # Verificar que los thresholds se registran en evidencia
        th = resultado["evidencia"]["thresholds_usados"]
        assert th["direct_text_min_chars"] == 50
        assert th["direct_text_min_words"] == 5
        assert th["ocr_min_confidence"] == 0.90
        assert th["ocr_min_words"] == 100
    
    def test_default_thresholds(self):
        """Sin pasar thresholds, debe usar valores por defecto."""
        pdf_path = _get_pdf_nativo()
        if pdf_path is None:
            pytest.skip("No hay PDF de prueba disponible")
        
        resultado = extract_text_with_gating(pdf_path)
        
        # Valores por defecto
        th = resultado["evidencia"]["thresholds_usados"]
        assert th["direct_text_min_chars"] == 200
        assert th["ocr_min_confidence"] == 0.60


class TestRegla2PostRotacion:
    """Tests para validación obligatoria de dimensiones post-rotación (Regla 2)."""

    def test_validar_dimensiones_importado(self):
        """_validar_dimensiones debe estar importado en pdf_text_extractor."""
        from src.ingestion import pdf_text_extractor as mod
        # Si OCR está disponible, debe ser callable
        if mod.OCR_DISPONIBLE:
            assert callable(mod._validar_dimensiones)
        else:
            # Si no hay OCR, puede ser None
            assert mod._validar_dimensiones is None or callable(mod._validar_dimensiones)

    def test_post_rotacion_validacion_en_codigo(self):
        """El código fuente debe contener la validación post-rotación."""
        import inspect
        from src.ingestion import pdf_text_extractor as mod
        source = inspect.getsource(mod._extraer_texto_ocr)
        assert "_validar_dimensiones" in source, (
            "La función _extraer_texto_ocr debe llamar a _validar_dimensiones "
            "después de preprocesar_rotacion (Regla 2)"
        )

    def test_post_rotacion_usa_validar_dimensiones(self):
        """_extraer_texto_ocr debe llamar _validar_dimensiones post-rotación."""
        from unittest.mock import patch, MagicMock
        from src.ingestion import pdf_text_extractor as mod

        if not mod.OCR_DISPONIBLE:
            pytest.skip("OCR no disponible")

        mock_img = MagicMock()
        mock_img.size = (3000, 2000)
        mock_img_rotada = MagicMock()
        mock_img_rotada.size = (3000, 2000)
        mock_img_validada = MagicMock()
        mock_img_validada.size = (2000, 1333)

        mock_ocr_result = {
            "texto_completo": "test",
            "snippet_200": "test",
            "confianza_promedio": 0.9,
            "num_palabras": 1,
            "tiempo_ms": 10,
            "error": None,
            "motor_ocr": "paddleocr",
            "lineas": [],
        }

        with patch.object(mod, 'renderizar_pagina', return_value=mock_img), \
             patch.object(mod, 'preprocesar_rotacion', return_value=(mock_img_rotada, {"rotacion_grados": 0})), \
             patch.object(mod, '_validar_dimensiones', return_value=mock_img_validada) as mock_val, \
             patch.object(mod, 'ejecutar_ocr', return_value=mock_ocr_result), \
             patch.object(mod, 'verificar_ocr', return_value=(True, "ok", "paddleocr")), \
             patch.object(mod, 'fitz') as mock_fitz:

            mock_doc = MagicMock()
            mock_doc.__len__ = MagicMock(return_value=1)
            mock_fitz.open.return_value = mock_doc

            result = mod._extraer_texto_ocr(Path("/fake.pdf"), sample_pages=1)

            # _validar_dimensiones DEBE haber sido llamada con la imagen rotada
            mock_val.assert_called_once_with(mock_img_rotada)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
