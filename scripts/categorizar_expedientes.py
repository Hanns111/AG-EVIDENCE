# -*- coding: utf-8 -*-
"""
Script para categorizar y organizar expedientes automáticamente
según su naturaleza (viáticos, encargo, caja chica, órdenes de servicio, etc.)
"""
import os
import sys
import shutil
import re
from pathlib import Path
from typing import Optional, Tuple

# Configurar encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import NaturalezaExpediente, KEYWORDS_NATURALEZA
from utils.pdf_extractor import extraer_todos_pdfs, DocumentoPDF

# Mapeo de naturaleza a carpeta
MAPEO_CARPETAS = {
    NaturalezaExpediente.VIATICOS: "viaticos",
    NaturalezaExpediente.CAJA_CHICA: "caja_chica",
    NaturalezaExpediente.ENCARGO: "encargo",
    NaturalezaExpediente.ORDEN_SERVICIO: "ordenes_servicio",
    NaturalezaExpediente.ORDEN_COMPRA: "ordenes_compra",
    NaturalezaExpediente.CONTRATO: "contratos",
    NaturalezaExpediente.PAGO_PROVEEDOR: "pago_proveedor",
    NaturalezaExpediente.OTRO: "otros",
    NaturalezaExpediente.NO_DETERMINADO: "no_determinado"
}

# Agregar SUBVENCIONES (si no está en el enum, usar OTRO)
CARPETA_SUBVENCIONES = "subvenciones"


def detectar_naturaleza(carpeta_expediente: Path) -> Tuple[NaturalezaExpediente, float]:
    """
    Detecta la naturaleza de un expediente analizando sus documentos.
    
    Returns:
        (NaturalezaExpediente, score): Naturaleza detectada y confianza (0-1)
    """
    try:
        documentos = extraer_todos_pdfs(str(carpeta_expediente))
    except Exception as e:
        print(f"  ⚠️  Error al leer PDFs: {e}")
        return NaturalezaExpediente.NO_DETERMINADO, 0.0
    
    if not documentos:
        return NaturalezaExpediente.NO_DETERMINADO, 0.0
    
    # Analizar nombres de archivos
    texto_nombres = " ".join([doc.nombre.lower() for doc in documentos])
    
    # Analizar contenido (primeros 5000 caracteres de cada documento)
    texto_contenido = " ".join([doc.texto_completo[:5000].lower() for doc in documentos])
    
    texto_completo = f"{texto_nombres} {texto_contenido}"
    
    # Contar coincidencias por naturaleza
    scores = {}
    
    for naturaleza, keywords in KEYWORDS_NATURALEZA.items():
        score = 0
        for keyword in keywords:
            # Buscar en nombres (peso 2) y contenido (peso 1)
            count_nombres = len(re.findall(rf"\b{re.escape(keyword.lower())}\b", texto_nombres))
            count_contenido = len(re.findall(rf"\b{re.escape(keyword.lower())}\b", texto_contenido))
            score += (count_nombres * 2) + count_contenido
        
        if score > 0:
            scores[naturaleza] = score
    
    # Detección especial para SUBVENCIONES
    if re.search(r"subvenci[oó]n|transferencia|donaci[oó]n", texto_completo, re.IGNORECASE):
        # Si hay indicios de subvención, marcar como especial
        scores["SUBVENCIONES"] = 10
    
    if not scores:
        return NaturalezaExpediente.NO_DETERMINADO, 0.0
    
    # Obtener naturaleza con mayor score
    naturaleza_ganadora = max(scores.items(), key=lambda x: x[1])
    
    if naturaleza_ganadora[0] == "SUBVENCIONES":
        # Retornar OTRO pero con flag especial
        return NaturalezaExpediente.OTRO, 0.8
    
    max_score = naturaleza_ganadora[1]
    total_score = sum(scores.values())
    confianza = min(max_score / max(total_score, 1), 1.0)
    
    return naturaleza_ganadora[0], confianza


def categorizar_expediente(carpeta_expediente: Path, destino_base: Path, mover: bool = False) -> Tuple[bool, str]:
    """
    Categoriza un expediente y lo mueve/copia a la carpeta correspondiente.
    
    Args:
        carpeta_expediente: Carpeta con el expediente
        destino_base: Carpeta base donde organizar (data/expedientes/pruebas/)
        mover: Si True, mueve; si False, copia
    
    Returns:
        (exito, mensaje)
    """
    if not carpeta_expediente.is_dir():
        return False, f"No es una carpeta: {carpeta_expediente}"
    
    # Detectar naturaleza
    naturaleza, confianza = detectar_naturaleza(carpeta_expediente)
    
    # Determinar carpeta destino
    if naturaleza == NaturalezaExpediente.OTRO and confianza > 0.7:
        # Verificar si es subvención
        try:
            documentos = extraer_todos_pdfs(str(carpeta_expediente))
            texto = " ".join([doc.texto_completo[:5000].lower() for doc in documentos])
            if re.search(r"subvenci[oó]n|transferencia", texto, re.IGNORECASE):
                carpeta_destino = destino_base / CARPETA_SUBVENCIONES
            else:
                carpeta_destino = destino_base / MAPEO_CARPETAS[naturaleza]
        except:
            carpeta_destino = destino_base / MAPEO_CARPETAS[naturaleza]
    else:
        carpeta_destino = destino_base / MAPEO_CARPETAS[naturaleza]
    
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    
    # Mover o copiar
    destino_final = carpeta_destino / carpeta_expediente.name
    
    if destino_final.exists():
        return False, f"Ya existe: {destino_final.name}"
    
    try:
        if mover:
            shutil.move(str(carpeta_expediente), str(destino_final))
            accion = "Movido"
        else:
            shutil.copytree(str(carpeta_expediente), str(destino_final))
            accion = "Copiado"
        
        return True, f"{accion} a {carpeta_destino.name}/ ({naturaleza.value}, confianza: {confianza:.2f})"
    except Exception as e:
        return False, f"Error: {e}"


def procesar_carpeta_origen(carpeta_origen: Path, destino_base: Path, mover: bool = False):
    """
    Procesa todos los expedientes en una carpeta origen.
    """
    print(f"\n{'='*60}")
    print(f"CATEGORIZANDO EXPEDIENTES")
    print(f"{'='*60}")
    print(f"\nOrigen: {carpeta_origen}")
    print(f"Destino: {destino_base}")
    print(f"Acción: {'MOVER' if mover else 'COPIAR'}")
    print(f"\n{'='*60}\n")
    
    expedientes = [item for item in carpeta_origen.iterdir() if item.is_dir()]
    
    if not expedientes:
        print("⚠️  No se encontraron carpetas de expedientes")
        return
    
    resultados = {
        "exitosos": [],
        "fallidos": [],
        "ya_existen": []
    }
    
    for i, expediente in enumerate(expedientes, 1):
        print(f"[{i}/{len(expedientes)}] Procesando: {expediente.name}...", end=" ")
        
        exito, mensaje = categorizar_expediente(expediente, destino_base, mover)
        
        if exito:
            print(f"✅ {mensaje}")
            resultados["exitosos"].append((expediente.name, mensaje))
        elif "Ya existe" in mensaje:
            print(f"⏭️  {mensaje}")
            resultados["ya_existen"].append(expediente.name)
        else:
            print(f"❌ {mensaje}")
            resultados["fallidos"].append((expediente.name, mensaje))
    
    # Resumen
    print(f"\n{'='*60}")
    print("RESUMEN")
    print(f"{'='*60}")
    print(f"✅ Exitosos: {len(resultados['exitosos'])}")
    print(f"⏭️  Ya existían: {len(resultados['ya_existen'])}")
    print(f"❌ Fallidos: {len(resultados['fallidos'])}")
    
    if resultados["exitosos"]:
        print(f"\n✅ Expedientes procesados:")
        for nombre, mensaje in resultados["exitosos"]:
            print(f"   - {nombre}")
    
    if resultados["fallidos"]:
        print(f"\n❌ Errores:")
        for nombre, mensaje in resultados["fallidos"]:
            print(f"   - {nombre}: {mensaje}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Categoriza y organiza expedientes según su naturaleza"
    )
    parser.add_argument(
        "origen",
        help="Carpeta origen con expedientes a categorizar"
    )
    parser.add_argument(
        "--destino",
        default="data/expedientes/pruebas",
        help="Carpeta destino base (default: data/expedientes/pruebas)"
    )
    parser.add_argument(
        "--mover",
        action="store_true",
        help="Mover expedientes en lugar de copiar"
    )
    
    args = parser.parse_args()
    
    origen = Path(args.origen)
    destino = Path(args.destino)
    
    if not origen.exists():
        print(f"❌ Error: La carpeta origen no existe: {origen}")
        sys.exit(1)
    
    procesar_carpeta_origen(origen, destino, mover=args.mover)
