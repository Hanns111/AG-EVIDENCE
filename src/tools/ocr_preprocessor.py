# -*- coding: utf-8 -*-
"""
Adaptador OCRmyPDF para AG-EVIDENCE
===================================
Preprocesa PDFs escaneados para que lleguen con texto extraíble al MCP pdf-handler.

Versión: 1.0.0
Fecha: 2026-02-07
"""

import subprocess
import time
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from config.settings import OCR_CONFIG


@dataclass
class ResultadoPreprocesamientoOCR:
    """Resultado del preprocesamiento OCR de un PDF"""
    
    # Identificación
    archivo_original: str          # Nombre del PDF original
    archivo_procesado: str         # Ruta completa al PDF resultante
    
    # Clasificación
    tipo_detectado: str            # "NATIVO_DIGITAL" | "ESCANEADO_PROCESADO" | "FALLO_OCR"
    requirio_ocr: bool             # True si se aplicó OCRmyPDF
    
    # Métricas
    paginas_total: int             # Número total de páginas
    tiempo_proceso_ms: int         # Tiempo de procesamiento en milisegundos
    tamanio_original_bytes: int    # Tamaño del archivo original
    tamanio_procesado_bytes: int   # Tamaño del archivo resultante
    
    # Estado
    exito: bool                    # True si el procesamiento fue exitoso
    error: str | None              # Mensaje de error si falló
    
    # Trazabilidad (requerida por AGENT_GOVERNANCE_RULES Art. 4)
    comando_ejecutado: str         # Comando WSL exacto que se ejecutó
    version_ocrmypdf: str          # Versión de ocrmypdf usada
    timestamp_iso: str             # Fecha/hora ISO del procesamiento


def _ruta_windows_a_wsl(ruta_windows: str) -> str:
    """Convierte ruta Windows a ruta accesible desde WSL2.
    
    Ejemplo:
      "C:\\Users\\Hans\\Proyectos\\AG-EVIDENCE\\data\\archivo.pdf"
      → "/mnt/c/Users/Hans/Proyectos/AG-EVIDENCE/data/archivo.pdf"
    """
    ruta = ruta_windows.replace("\\", "/")
    if len(ruta) > 1 and ruta[1] == ":":
        letra = ruta[0].lower()
        ruta = f"/mnt/{letra}{ruta[2:]}"
    return ruta


def _obtener_version_ocrmypdf() -> str:
    """Obtiene la versión de ocrmypdf desde WSL2."""
    try:
        resultado = subprocess.run(
            ["wsl", "ocrmypdf", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if resultado.returncode == 0:
            return resultado.stdout.strip() or resultado.stderr.strip() or "desconocida"
        return "desconocida"
    except Exception:
        return "desconocida"


def preprocesar_pdf(
    ruta_pdf: str,           # Ruta Windows al PDF (ej: "C:\...\archivo.pdf")
    directorio_salida: str,  # Carpeta donde guardar el PDF procesado
    idioma: str = "spa",     # Idioma OCR (default: español)
) -> ResultadoPreprocesamientoOCR:
    """
    Preprocesa un PDF escaneado usando OCRmyPDF en WSL2.
    
    Args:
        ruta_pdf: Ruta Windows al PDF original
        directorio_salida: Carpeta destino para el PDF procesado
        idioma: Idioma para OCR (default: "spa")
    
    Returns:
        ResultadoPreprocesamientoOCR con toda la información de trazabilidad
    """
    inicio = time.time()
    timestamp_iso = datetime.now(timezone.utc).isoformat()
    
    # Validar archivo
    pdf_path = Path(ruta_pdf)
    if not pdf_path.exists():
        return ResultadoPreprocesamientoOCR(
            archivo_original=pdf_path.name,
            archivo_procesado=ruta_pdf,
            tipo_detectado="FALLO_OCR",
            requirio_ocr=False,
            paginas_total=0,
            tiempo_proceso_ms=0,
            tamanio_original_bytes=0,
            tamanio_procesado_bytes=0,
            exito=False,
            error=f"Archivo no encontrado: {ruta_pdf}",
            comando_ejecutado="",
            version_ocrmypdf=_obtener_version_ocrmypdf(),
            timestamp_iso=timestamp_iso
        )
    
    if not pdf_path.suffix.lower() == ".pdf":
        return ResultadoPreprocesamientoOCR(
            archivo_original=pdf_path.name,
            archivo_procesado=ruta_pdf,
            tipo_detectado="FALLO_OCR",
            requirio_ocr=False,
            paginas_total=0,
            tiempo_proceso_ms=0,
            tamanio_original_bytes=0,
            tamanio_procesado_bytes=0,
            exito=False,
            error=f"No es un archivo PDF: {ruta_pdf}",
            comando_ejecutado="",
            version_ocrmypdf=_obtener_version_ocrmypdf(),
            timestamp_iso=timestamp_iso
        )
    
    # Preparar rutas
    tamanio_original = pdf_path.stat().st_size
    directorio_salida_path = Path(directorio_salida)
    directorio_salida_path.mkdir(parents=True, exist_ok=True)
    
    archivo_salida = directorio_salida_path / pdf_path.name
    ruta_wsl_entrada = _ruta_windows_a_wsl(str(pdf_path.absolute()))
    ruta_wsl_salida = _ruta_windows_a_wsl(str(archivo_salida.absolute()))
    
    # Construir comando OCRmyPDF
    flags = OCR_CONFIG.get("ocrmypdf_flags", []).copy()  # No modificar la lista original
    if "--skip-text" not in flags:
        flags.insert(0, "--skip-text")
    
    comando = ["wsl", "ocrmypdf"] + flags + ["-l", idioma, ruta_wsl_entrada, ruta_wsl_salida]
    comando_str = " ".join(comando)
    
    # Ejecutar OCRmyPDF
    try:
        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=OCR_CONFIG.get("timeout_segundos", 120)
        )
        
        tiempo_proceso_ms = int((time.time() - inicio) * 1000)
        
        # Interpretar código de salida
        if resultado.returncode == 0:
            # OCR aplicado exitosamente
            tipo = "ESCANEADO_PROCESADO"
            exito = True
            error = None
            requirio_ocr = True
            tamanio_procesado = archivo_salida.stat().st_size if archivo_salida.exists() else tamanio_original
            
            # Contar páginas (aproximado, usando PyMuPDF si está disponible)
            try:
                import fitz
                doc = fitz.open(str(archivo_salida))
                paginas = len(doc)
                doc.close()
            except Exception:
                paginas = 0
            
        elif resultado.returncode == 6:
            # PDF ya tiene texto (--skip-text)
            tipo = "NATIVO_DIGITAL"
            exito = True
            error = None
            requirio_ocr = False
            # Copiar archivo original a salida
            import shutil
            shutil.copy2(pdf_path, archivo_salida)
            tamanio_procesado = tamanio_original
            
            # Contar páginas
            try:
                import fitz
                doc = fitz.open(str(pdf_path))
                paginas = len(doc)
                doc.close()
            except Exception:
                paginas = 0
                
        else:
            # Error
            tipo = "FALLO_OCR"
            exito = False
            error = f"ocrmypdf exit code {resultado.returncode}: {resultado.stderr}"
            requirio_ocr = False
            # Retornar archivo original sin modificar
            archivo_salida = pdf_path
            tamanio_procesado = tamanio_original
            paginas = 0
        
        return ResultadoPreprocesamientoOCR(
            archivo_original=pdf_path.name,
            archivo_procesado=str(archivo_salida.absolute()),
            tipo_detectado=tipo,
            requirio_ocr=requirio_ocr,
            paginas_total=paginas,
            tiempo_proceso_ms=tiempo_proceso_ms,
            tamanio_original_bytes=tamanio_original,
            tamanio_procesado_bytes=tamanio_procesado,
            exito=exito,
            error=error,
            comando_ejecutado=comando_str,
            version_ocrmypdf=_obtener_version_ocrmypdf(),
            timestamp_iso=timestamp_iso
        )
        
    except subprocess.TimeoutExpired:
        tiempo_proceso_ms = int((time.time() - inicio) * 1000)
        return ResultadoPreprocesamientoOCR(
            archivo_original=pdf_path.name,
            archivo_procesado=ruta_pdf,
            tipo_detectado="FALLO_OCR",
            requirio_ocr=False,
            paginas_total=0,
            tiempo_proceso_ms=tiempo_proceso_ms,
            tamanio_original_bytes=tamanio_original,
            tamanio_procesado_bytes=tamanio_original,
            exito=False,
            error=f"Timeout después de {OCR_CONFIG.get('timeout_segundos', 120)} segundos",
            comando_ejecutado=comando_str,
            version_ocrmypdf=_obtener_version_ocrmypdf(),
            timestamp_iso=timestamp_iso
        )
    except Exception as e:
        tiempo_proceso_ms = int((time.time() - inicio) * 1000)
        return ResultadoPreprocesamientoOCR(
            archivo_original=pdf_path.name,
            archivo_procesado=ruta_pdf,
            tipo_detectado="FALLO_OCR",
            requirio_ocr=False,
            paginas_total=0,
            tiempo_proceso_ms=tiempo_proceso_ms,
            tamanio_original_bytes=tamanio_original,
            tamanio_procesado_bytes=tamanio_original,
            exito=False,
            error=f"Excepción: {str(e)}",
            comando_ejecutado=comando_str,
            version_ocrmypdf=_obtener_version_ocrmypdf(),
            timestamp_iso=timestamp_iso
        )


def preprocesar_expediente(
    carpeta_expediente: str,     # Ruta Windows a carpeta con PDFs
    directorio_salida: str,      # Carpeta destino para PDFs procesados
    idioma: str = "spa"
) -> List[ResultadoPreprocesamientoOCR]:
    """
    Preprocesa TODOS los PDFs de un expediente.
    
    Ejemplo:
      resultados = preprocesar_expediente(
          "C:\\...\\DIGC2026-INT-0072851",
          "C:\\...\\output\\procesados"
      )
      
      for r in resultados:
          print(f"{r.archivo_original}: {r.tipo_detectado} ({r.tiempo_proceso_ms}ms)")
    
    Salida esperada con el expediente de prueba:
      SolicituddeviaticosRony.pdf: ESCANEADO_PROCESADO (3200ms)
      RendiciondeCuentasRonnyDurand.pdf: NATIVO_DIGITAL (50ms)
      NUEVA DIRECTIVA DE VIÁTICOS.pdf: NATIVO_DIGITAL (40ms)
    """
    carpeta = Path(carpeta_expediente)
    if not carpeta.exists() or not carpeta.is_dir():
        return []
    
    resultados = []
    pdfs = list(carpeta.glob("*.pdf"))
    
    for pdf in sorted(pdfs):
        resultado = preprocesar_pdf(
            str(pdf),
            directorio_salida,
            idioma=idioma
        )
        resultados.append(resultado)
    
    return resultados
