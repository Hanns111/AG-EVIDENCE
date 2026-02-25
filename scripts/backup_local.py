#!/usr/bin/env python3
"""
backup_local.py — Backup completo del proyecto AG-EVIDENCE

Genera un ZIP con timestamp de todo el proyecto, excluyendo:
- .git/ (historial pesado, ya esta en GitHub)
- .venv/ / venv/ (entorno virtual, se recrea con pip install)
- __pycache__/ (cache Python, se regenera)

INCLUYE todo lo demas:
- src/, config/, tests/, scripts/, docs/, governance/
- data/directivas/ (PDFs de normativa)
- data/expedientes/ (PDFs de expedientes reales)
- data/normativa/ (JSON de reglas)
- Archivos raiz (CLAUDE.md, .gitignore, requirements.txt, etc.)

Uso:
    python scripts/backup_local.py
    python scripts/backup_local.py --destino "D:\\Backups"
    python scripts/backup_local.py --destino "C:\\Users\\Hans\\OneDrive\\Backups"

El ZIP se guarda en exports/backups/ por defecto.
"""

import argparse
import os
import zipfile
from datetime import datetime
from pathlib import Path

# Raiz del proyecto (un nivel arriba de scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Carpetas y patrones a EXCLUIR del backup
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    ".claude",
    "exports",  # No incluir backups anteriores
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
}


def should_exclude(path: Path) -> bool:
    """Determina si un archivo o carpeta debe excluirse del backup."""
    parts = path.relative_to(PROJECT_ROOT).parts

    # Excluir carpetas prohibidas
    for part in parts:
        if part in EXCLUDE_DIRS:
            return True

    # Excluir extensiones prohibidas
    if path.suffix.lower() in EXCLUDE_EXTENSIONS:
        return True

    return False


def create_backup(destino: Path | None = None) -> Path:
    """
    Crea un ZIP del proyecto completo.

    Args:
        destino: Carpeta donde guardar el ZIP.
                 Si None, usa exports/backups/ dentro del proyecto.

    Returns:
        Path al archivo ZIP creado.
    """
    # Determinar carpeta destino
    if destino is None:
        destino = PROJECT_ROOT / "exports" / "backups"
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)

    # Nombre del ZIP con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"AG-EVIDENCE_backup_{timestamp}.zip"
    zip_path = destino / zip_name

    # Contar archivos para progreso
    all_files = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        root_path = Path(root)
        # Filtrar directorios in-place (evita entrar en ellos)
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            file_path = root_path / f
            if not should_exclude(file_path):
                all_files.append(file_path)

    total_files = len(all_files)
    total_size = sum(f.stat().st_size for f in all_files)

    print("AG-EVIDENCE Backup")
    print("=" * 50)
    print(f"Archivos a respaldar: {total_files}")
    print(f"Tamano total:         {total_size / (1024 * 1024):.1f} MB")
    print(f"Destino:              {zip_path}")
    print("=" * 50)

    # Crear ZIP
    archived = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in all_files:
            arcname = file_path.relative_to(PROJECT_ROOT)
            zf.write(file_path, arcname)
            archived += 1
            if archived % 50 == 0 or archived == total_files:
                pct = (archived / total_files) * 100
                print(f"  [{pct:5.1f}%] {archived}/{total_files} archivos...")

    zip_size = zip_path.stat().st_size
    compression = (1 - zip_size / total_size) * 100 if total_size > 0 else 0

    print("=" * 50)
    print("Backup completado!")
    print(f"Archivo:     {zip_path.name}")
    print(f"Tamano ZIP:  {zip_size / (1024 * 1024):.1f} MB")
    print(f"Compresion:  {compression:.1f}%")
    print(f"Ubicacion:   {zip_path}")
    print()
    print("RECOMENDACION: Copiar este ZIP a una ubicacion externa:")
    print("  - OneDrive/Google Drive")
    print("  - USB/Disco externo")
    print("  - Otra maquina")

    return zip_path


def main():
    parser = argparse.ArgumentParser(description="Backup completo del proyecto AG-EVIDENCE")
    parser.add_argument(
        "--destino",
        type=str,
        default=None,
        help="Carpeta destino para el ZIP (default: exports/backups/)",
    )
    args = parser.parse_args()

    destino = Path(args.destino) if args.destino else None
    create_backup(destino)


if __name__ == "__main__":
    main()
