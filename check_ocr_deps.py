# -*- coding: utf-8 -*-
"""
Detector de Dependencias OCR
============================
Verifica versiones de tesseract, ghostscript y ocrmypdf
"""

import subprocess
import sys
from typing import Dict, Any, Tuple

def run_cmd(cmd: list) -> Tuple[int, str, str]:
    """Ejecuta un comando y retorna (returncode, stdout, stderr)"""
    try:
        p = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        out, err = p.communicate(timeout=30)
        return p.returncode, out.strip(), err.strip()
    except Exception as e:
        return -1, "", str(e)

def check_tesseract() -> Dict[str, Any]:
    """Verifica Tesseract"""
    result = {
        "instalado": False,
        "version": None,
        "comando": "tesseract",
        "idiomas": [],
        "error": None
    }
    
    # Verificar versión
    rc, out, err = run_cmd(["tesseract", "--version"])
    if rc == 0:
        result["instalado"] = True
        # Extraer versión de la primera línea
        lines = out.split('\n')
        if lines:
            result["version"] = lines[0].strip()
    else:
        result["error"] = err or "Comando no encontrado"
        return result
    
    # Listar idiomas
    rc, out, err = run_cmd(["tesseract", "--list-langs"])
    if rc == 0:
        langs = []
        for line in out.splitlines():
            line = line.strip()
            if line and not line.startswith("List of available languages"):
                langs.append(line)
        result["idiomas"] = langs
    
    return result

def check_ghostscript() -> Dict[str, Any]:
    """Verifica Ghostscript"""
    result = {
        "instalado": False,
        "version": None,
        "comando": "gs",
        "error": None
    }
    
    rc, out, err = run_cmd(["gs", "--version"])
    if rc == 0:
        result["instalado"] = True
        # Ghostscript imprime versión en stderr
        if err:
            lines = err.split('\n')
            for line in lines:
                if "version" in line.lower() or "Ghostscript" in line:
                    result["version"] = line.strip()
                    break
        if not result["version"] and out:
            result["version"] = out.strip()
    else:
        result["error"] = err or "Comando no encontrado"
    
    return result

def check_ocrmypdf() -> Dict[str, Any]:
    """Verifica ocrmypdf"""
    result = {
        "instalado": False,
        "version": None,
        "comando": "ocrmypdf",
        "error": None
    }
    
    rc, out, err = run_cmd(["ocrmypdf", "--version"])
    if rc == 0:
        result["instalado"] = True
        result["version"] = out.strip() or err.strip()
    else:
        # Intentar como módulo Python
        rc2, out2, err2 = run_cmd([sys.executable, "-m", "ocrmypdf", "--version"])
        if rc2 == 0:
            result["instalado"] = True
            result["version"] = out2.strip() or err2.strip()
        else:
            result["error"] = err or err2 or "Comando no encontrado"
    
    return result

def main():
    """Función principal"""
    # Configurar encoding UTF-8 para Windows
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    
    print("=" * 70)
    print("DETECTOR DE DEPENDENCIAS OCR")
    print("=" * 70)
    print()
    
    # Tesseract
    print("📋 Verificando Tesseract...")
    tesseract = check_tesseract()
    if tesseract["instalado"]:
        print(f"   ✅ Instalado: {tesseract['version']}")
        if tesseract["idiomas"]:
            print(f"   📦 Idiomas disponibles: {', '.join(tesseract['idiomas'][:10])}")
            if len(tesseract["idiomas"]) > 10:
                print(f"   ... y {len(tesseract['idiomas']) - 10} más")
    else:
        print(f"   ❌ No instalado: {tesseract.get('error', 'Comando no encontrado')}")
    print()
    
    # Ghostscript
    print("📋 Verificando Ghostscript...")
    gs = check_ghostscript()
    if gs["instalado"]:
        print(f"   ✅ Instalado: {gs['version']}")
    else:
        print(f"   ❌ No instalado: {gs.get('error', 'Comando no encontrado')}")
    print()
    
    # ocrmypdf
    print("📋 Verificando ocrmypdf...")
    ocrmypdf = check_ocrmypdf()
    if ocrmypdf["instalado"]:
        print(f"   ✅ Instalado: {ocrmypdf['version']}")
    else:
        print(f"   ❌ No instalado: {ocrmypdf.get('error', 'Comando no encontrado')}")
    print()
    
    # Resumen
    print("=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print(f"Tesseract:  {'✅' if tesseract['instalado'] else '❌'} {tesseract.get('version', 'N/A')}")
    print(f"Ghostscript: {'✅' if gs['instalado'] else '❌'} {gs.get('version', 'N/A')}")
    print(f"ocrmypdf:   {'✅' if ocrmypdf['instalado'] else '❌'} {ocrmypdf.get('version', 'N/A')}")
    print()
    
    # JSON output
    import json
    report = {
        "tesseract": tesseract,
        "ghostscript": gs,
        "ocrmypdf": ocrmypdf
    }
    print("JSON:")
    print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
