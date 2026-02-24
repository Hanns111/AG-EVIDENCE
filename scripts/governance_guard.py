# -*- coding: utf-8 -*-
"""
governance_guard.py — Pre-commit hook: bloquea commits en archivos protegidos.

Llamado por .pre-commit-config.yaml cuando un archivo de gobernanza
esta staged para commit. Solo permite el commit si la variable de entorno
AG_GOVERNANCE_OVERRIDE=HANS_APPROVED esta presente.

Exit 0 = permitir commit
Exit 1 = bloquear commit (archivo protegido sin override)
"""

import os
import sys

VERSION_GOVERNANCE_GUARD = "1.0.0"

PROTECTED_FILES = [
    "docs/AGENT_GOVERNANCE_RULES.md",
    "docs/GOVERNANCE_RULES.md",
    "docs/PROJECT_SPEC.md",
    "AGENTS.md",
    "CLAUDE.md",
    ".cursorrules",
    ".cursor/mcp.json",
    "governance/SESSION_PROTOCOL.md",
    "docs/security/SECURITY_GOVERNANCE_POLICY.md",
]


def main():
    staged_protected = [f for f in sys.argv[1:] if f in PROTECTED_FILES]

    if not staged_protected:
        sys.exit(0)

    print("=" * 60)
    print("GOVERNANCE GUARD v{}: Archivos protegidos detectados".format(
        VERSION_GOVERNANCE_GUARD
    ))
    print("=" * 60)
    for f in staged_protected:
        print("  BLOQUEADO: {}".format(f))
    print()
    print("Per GOVERNANCE_RULES.md Seccion 10.5, estos archivos")
    print("requieren aprobacion explicita de Hans antes de modificar.")
    print()

    override = os.environ.get("AG_GOVERNANCE_OVERRIDE", "")
    if override == "HANS_APPROVED":
        print("Override detectado (AG_GOVERNANCE_OVERRIDE=HANS_APPROVED).")
        print("Commit permitido.")
        sys.exit(0)
    else:
        print("Para overridear, ejecutar:")
        print('  AG_GOVERNANCE_OVERRIDE=HANS_APPROVED git commit ...')
        print()
        print("O en PowerShell:")
        print('  $env:AG_GOVERNANCE_OVERRIDE="HANS_APPROVED"; git commit ...')
        sys.exit(1)


if __name__ == "__main__":
    main()
