# -*- coding: utf-8 -*-
"""
Configuración de pytest para AG-EVIDENCE
=========================================
Este archivo configura los paths correctamente para que pytest
pueda importar los módulos del proyecto.
"""

import sys
import os

# Agregar el directorio raíz del proyecto al path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Agregar src al path
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)


