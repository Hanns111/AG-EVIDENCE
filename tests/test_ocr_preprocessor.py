# -*- coding: utf-8 -*-
"""
Tests para ocr_preprocessor.py
===============================
Tests mínimos requeridos según OCR_PREPROCESSOR_SPEC.md
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.tools.ocr_preprocessor import (
    preprocesar_pdf,
    preprocesar_expediente,
    _ruta_windows_a_wsl,
    ResultadoPreprocesamientoOCR
)


def test_conversion_ruta_windows_a_wsl():
    """Verifica conversión de rutas Windows a WSL."""
    ruta_windows = r"C:\Users\Hans\Proyectos\AG-EVIDENCE\data\archivo.pdf"
    ruta_wsl = _ruta_windows_a_wsl(ruta_windows)
    
    assert ruta_wsl.startswith("/mnt/c/")
    assert "Users/Hans/Proyectos/AG-EVIDENCE/data/archivo.pdf" in ruta_wsl
    assert "\\" not in ruta_wsl


def test_pdf_nativo_no_modifica():
    """PDF con texto → no aplica OCR, tipo = NATIVO_DIGITAL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Crear un PDF de prueba (simulado)
        pdf_path = Path(tmpdir) / "test_nativo.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nfake pdf content")
        
        salida_dir = Path(tmpdir) / "salida"
        salida_dir.mkdir()
        
        # Mock de subprocess para simular exit code 6 (PDF nativo)
        with patch('src.tools.ocr_preprocessor.subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 6  # PDF ya tiene texto
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            
            resultado = preprocesar_pdf(
                str(pdf_path),
                str(salida_dir),
                idioma="spa"
            )
            
            assert resultado.tipo_detectado == "NATIVO_DIGITAL"
            assert not resultado.requirio_ocr
            assert resultado.exito is True
            assert resultado.error is None


def test_pdf_escaneado_aplica_ocr():
    """PDF imagen → aplica OCR, tipo = ESCANEADO_PROCESADO."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "test_escaneado.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nfake scanned pdf")
        
        salida_dir = Path(tmpdir) / "salida"
        salida_dir.mkdir()
        archivo_salida = salida_dir / "test_escaneado.pdf"
        archivo_salida.write_bytes(b"%PDF-1.4\nprocessed pdf")
        
        # Mock de subprocess para simular exit code 0 (OCR exitoso)
        with patch('src.tools.ocr_preprocessor.subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0  # OCR aplicado exitosamente
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            
            # Mock de fitz para contar páginas (se importa dentro de la función)
            # Usar patch.object en sys.modules para mockear fitz cuando se importe
            import sys
            mock_fitz_module = MagicMock()
            mock_doc = MagicMock()
            mock_doc.__len__ = lambda self: 5
            mock_fitz_module.open.return_value = mock_doc
            sys.modules['fitz'] = mock_fitz_module
            
            try:
                resultado = preprocesar_pdf(
                    str(pdf_path),
                    str(salida_dir),
                    idioma="spa"
                )
                
                assert resultado.tipo_detectado == "ESCANEADO_PROCESADO"
                assert resultado.requirio_ocr is True
                assert resultado.exito is True
                assert resultado.error is None
            finally:
                # Limpiar el mock
                if 'fitz' in sys.modules:
                    del sys.modules['fitz']


def test_error_no_bloquea():
    """Si OCR falla → retorna original, exito = False, archivo original devuelto."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "test_error.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nfake pdf")
        tamanio_original = pdf_path.stat().st_size
        
        salida_dir = Path(tmpdir) / "salida"
        salida_dir.mkdir()
        
        # Mock de subprocess para simular error (exit code 1)
        with patch('src.tools.ocr_preprocessor.subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1  # Error
            mock_result.stdout = ""
            mock_result.stderr = "Error: Tesseract not found"
            mock_run.return_value = mock_result
            
            resultado = preprocesar_pdf(
                str(pdf_path),
                str(salida_dir),
                idioma="spa"
            )
            
            assert resultado.tipo_detectado == "FALLO_OCR"
            assert resultado.exito is False
            assert resultado.error is not None
            assert "exit code 1" in resultado.error
            # Debe retornar el archivo original
            assert Path(resultado.archivo_procesado).name == pdf_path.name


def test_expediente_completo():
    """Carpeta con 3 PDFs mixtos → 3 resultados, tipos correctos."""
    with tempfile.TemporaryDirectory() as tmpdir:
        carpeta_expediente = Path(tmpdir) / "expediente"
        carpeta_expediente.mkdir()
        
        # Crear 3 PDFs de prueba
        (carpeta_expediente / "nativo1.pdf").write_bytes(b"%PDF-1.4\nnative")
        (carpeta_expediente / "escaneado1.pdf").write_bytes(b"%PDF-1.4\nscanned")
        (carpeta_expediente / "nativo2.pdf").write_bytes(b"%PDF-1.4\nnative2")
        
        salida_dir = Path(tmpdir) / "salida"
        salida_dir.mkdir()
        
        # Mock de subprocess para simular diferentes resultados
        call_count = [0]  # Usar lista para mutabilidad en closure
        
        def mock_run_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            # El primer y tercer PDF son nativos (índices 0 y 2)
            if call_count[0] in [0, 2]:
                mock_result.returncode = 6  # PDF nativo
            else:
                mock_result.returncode = 0  # PDF escaneado procesado
            mock_result.stdout = ""
            mock_result.stderr = ""
            call_count[0] += 1
            return mock_result
        
        with patch('src.tools.ocr_preprocessor.subprocess.run') as mock_run:
            mock_run.side_effect = mock_run_side_effect
            
            # Mock de fitz para contar páginas (se importa dentro de la función)
            # Usar patch.object en sys.modules para mockear fitz cuando se importe
            import sys
            mock_fitz_module = MagicMock()
            mock_doc = MagicMock()
            mock_doc.__len__ = lambda self: 1
            mock_fitz_module.open.return_value = mock_doc
            sys.modules['fitz'] = mock_fitz_module
            
            try:
                resultados = preprocesar_expediente(
                    str(carpeta_expediente),
                    str(salida_dir),
                    idioma="spa"
                )
                
                assert len(resultados) == 3
                tipos = [r.tipo_detectado for r in resultados]
                assert "NATIVO_DIGITAL" in tipos
                assert "ESCANEADO_PROCESADO" in tipos
            finally:
                # Limpiar el mock
                if 'fitz' in sys.modules:
                    del sys.modules['fitz']


def test_trazabilidad_completa():
    """Verifica campos de auditoría: comando, versión, timestamp presentes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "test_trazabilidad.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\ntest")
        
        salida_dir = Path(tmpdir) / "salida"
        salida_dir.mkdir()
        
        # Mock de subprocess
        with patch('src.tools.ocr_preprocessor.subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 6  # PDF nativo
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            
            # Mock de obtener versión
            with patch('src.tools.ocr_preprocessor._obtener_version_ocrmypdf', return_value="17.1.0"):
                resultado = preprocesar_pdf(
                    str(pdf_path),
                    str(salida_dir),
                    idioma="spa"
                )
                
                # Verificar campos de trazabilidad
                assert resultado.comando_ejecutado != ""
                assert "wsl" in resultado.comando_ejecutado.lower()
                assert "ocrmypdf" in resultado.comando_ejecutado.lower()
                assert resultado.version_ocrmypdf == "17.1.0"
                assert resultado.timestamp_iso != ""
                # Verificar formato ISO
                assert "T" in resultado.timestamp_iso or "Z" in resultado.timestamp_iso
