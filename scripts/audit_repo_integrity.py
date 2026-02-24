# -*- coding: utf-8 -*-
"""
audit_repo_integrity.py — Auditoria de integridad del repositorio AG-EVIDENCE.

Disenado para ejecutarse por Claude Code al inicio de cada sesion
(Gate de Arranque, SESSION_PROTOCOL.md seccion 3.5).

Realiza 7 checks independientes:
  1. Integridad SHA-256 de archivos de gobernanza vs manifiesto
  2. Ramas remotas no esperadas
  3. Autores desconocidos en commits recientes de main
  4. Deteccion de push directo (sin merge commit)
  5. Worktrees activos (exceso = riesgo)
  6. Existencia de archivos CI/proteccion
  7. Cambios no commiteados en archivos protegidos

Uso:
    python scripts/audit_repo_integrity.py
    python scripts/audit_repo_integrity.py --json
    python scripts/audit_repo_integrity.py --update-manifest

Exit codes:
    0 = PASS (con o sin warnings)
    1 = FAIL (al menos un check critico fallo)
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

VERSION_AUDIT = "1.0.0"

# Raiz del proyecto (2 niveles arriba de scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

MANIFEST_PATH = PROJECT_ROOT / "governance" / "integrity_manifest.json"

# Archivos protegidos — misma lista que GOVERNANCE_RULES.md Sec. 10.5
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

# Archivos CI/proteccion que deben existir
CI_FILES = [
    ".github/workflows/ci-lint.yml",
    ".github/CODEOWNERS",
    ".gitattributes",
    ".pre-commit-config.yaml",
]

AUTHORIZED_AUTHORS = [
    "Hanns111",
    "Hans",
    "Claude Code",
    "github-actions[bot]",
]

EXPECTED_REMOTE_BRANCHES = [
    "origin/main",
    "origin/HEAD",
]


def _run_git(args, cwd=None):
    """Ejecuta un comando git y retorna stdout. Retorna None si falla."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd or str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _sha256_file(filepath):
    """Calcula SHA-256 de un archivo. Retorna None si no existe."""
    full_path = PROJECT_ROOT / filepath
    if not full_path.exists():
        return None
    h = hashlib.sha256()
    with open(full_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest():
    """Carga el manifiesto de integridad. Retorna None si no existe."""
    if not MANIFEST_PATH.exists():
        return None
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════
# CHECK 1: Integridad SHA-256 de archivos de gobernanza
# ═══════════════════════════════════════════════════════════════════
def check_governance_integrity(manifest):
    """Compara hashes actuales vs manifiesto."""
    results = []
    status = "PASS"

    if manifest is None:
        return "WARN", [("manifest", "NO EXISTE — ejecutar --update-manifest")]

    stored_hashes = manifest.get("files", {})

    for filepath in PROTECTED_FILES:
        current_hash = _sha256_file(filepath)
        stored_hash = stored_hashes.get(filepath)

        if current_hash is None:
            results.append((filepath, "ARCHIVO NO ENCONTRADO"))
            status = "WARN"
        elif stored_hash is None:
            results.append((filepath, "NO EN MANIFIESTO"))
            status = "WARN"
        elif current_hash == stored_hash:
            results.append((filepath, "SHA-256 OK"))
        else:
            results.append((filepath, "HASH MISMATCH — posible modificacion no autorizada"))
            status = "FAIL"

    return status, results


# ═══════════════════════════════════════════════════════════════════
# CHECK 2: Ramas remotas no esperadas
# ═══════════════════════════════════════════════════════════════════
def check_remote_branches():
    """Detecta ramas remotas fuera de la lista esperada."""
    results = []
    status = "PASS"

    # Fetch para tener info actualizada
    _run_git(["fetch", "--prune"])

    output = _run_git(["branch", "-r", "--format=%(refname:short)"])
    if output is None:
        return "WARN", [("git branch -r", "No se pudo ejecutar (sin remoto?)")]

    remote_branches = [b.strip() for b in output.splitlines() if b.strip()]
    unexpected = []

    for branch in remote_branches:
        # Normalizar: origin/HEAD -> origin/main no es inesperado
        if branch in EXPECTED_REMOTE_BRANCHES or branch == "origin/HEAD -> origin/main":
            continue
        unexpected.append(branch)

    if unexpected:
        status = "WARN"
        for b in unexpected:
            results.append((b, "RAMA REMOTA NO ESPERADA"))
    else:
        results.append(("remote branches", "Solo origin/main. OK."))

    return status, results


# ═══════════════════════════════════════════════════════════════════
# CHECK 3: Autores desconocidos en commits recientes
# ═══════════════════════════════════════════════════════════════════
def check_commit_authors():
    """Verifica que los ultimos 20 commits de main sean de autores autorizados."""
    results = []
    status = "PASS"

    output = _run_git(["log", "--format=%an", "-20", "main"])
    if output is None:
        # Intentar sin especificar rama (por si estamos en main)
        output = _run_git(["log", "--format=%an", "-20"])
    if output is None:
        return "WARN", [("git log", "No se pudo ejecutar")]

    authors = set(a.strip() for a in output.splitlines() if a.strip())
    unknown = []

    for author in authors:
        if author not in AUTHORIZED_AUTHORS:
            unknown.append(author)

    if unknown:
        status = "FAIL"
        for a in unknown:
            results.append((a, "AUTOR NO AUTORIZADO"))
    else:
        results.append(("authors", "{} autores verificados. OK.".format(len(authors))))

    return status, results


# ═══════════════════════════════════════════════════════════════════
# CHECK 4: Push directo (sin merge commit)
# ═══════════════════════════════════════════════════════════════════
def check_direct_pushes():
    """Detecta commits que no vinieron de un merge (PR)."""
    results = []
    status = "PASS"

    output = _run_git(["log", "--format=%H %P", "-20", "main"])
    if output is None:
        output = _run_git(["log", "--format=%H %P", "-20"])
    if output is None:
        return "WARN", [("git log", "No se pudo ejecutar")]

    direct_count = 0
    merge_count = 0

    for line in output.splitlines():
        parts = line.strip().split()
        if len(parts) <= 2:
            direct_count += 1
        else:
            merge_count += 1

    # Informativo por ahora — se vuelve FAIL cuando branch protection este activo
    if direct_count > 0:
        status = "WARN"
        results.append((
            "direct pushes",
            "{} directos, {} merges en ultimos 20 commits".format(
                direct_count, merge_count
            ),
        ))
        results.append((
            "nota",
            "Esto es WARN hasta que branch protection este activo en GitHub",
        ))
    else:
        results.append(("pushes", "Todos via merge/PR. OK."))

    return status, results


# ═══════════════════════════════════════════════════════════════════
# CHECK 5: Worktrees activos
# ═══════════════════════════════════════════════════════════════════
def check_worktrees():
    """Reporta cantidad de worktrees activos."""
    results = []
    status = "PASS"

    output = _run_git(["worktree", "list", "--porcelain"])
    if output is None:
        return "WARN", [("git worktree", "No se pudo ejecutar")]

    worktree_count = output.count("worktree ")

    if worktree_count > 5:
        status = "WARN"
        results.append((
            "worktrees",
            "{} activos (recomendado: <= 5). Considerar limpieza.".format(
                worktree_count
            ),
        ))
    else:
        results.append(("worktrees", "{} activos. OK.".format(worktree_count)))

    return status, results


# ═══════════════════════════════════════════════════════════════════
# CHECK 6: Archivos CI/proteccion existen
# ═══════════════════════════════════════════════════════════════════
def check_ci_files():
    """Verifica que los archivos de CI y proteccion existan."""
    results = []
    status = "PASS"

    for filepath in CI_FILES:
        full_path = PROJECT_ROOT / filepath
        if full_path.exists():
            results.append((filepath, "EXISTE"))
        else:
            status = "WARN"
            results.append((filepath, "NO ENCONTRADO"))

    return status, results


# ═══════════════════════════════════════════════════════════════════
# CHECK 7: Cambios no commiteados en archivos protegidos
# ═══════════════════════════════════════════════════════════════════
def check_uncommitted_protected():
    """Detecta cambios unstaged/staged en archivos protegidos."""
    results = []
    status = "PASS"

    # Unstaged changes
    unstaged = _run_git(["diff", "--name-only"])
    # Staged changes
    staged = _run_git(["diff", "--staged", "--name-only"])

    changed = set()
    if unstaged:
        changed.update(unstaged.splitlines())
    if staged:
        changed.update(staged.splitlines())

    protected_changed = [f for f in changed if f in PROTECTED_FILES]

    if protected_changed:
        status = "FAIL"
        for f in protected_changed:
            results.append((f, "CAMBIO NO COMMITEADO — posible tampering"))
    else:
        results.append(("protected files", "Sin cambios pendientes. OK."))

    return status, results


# ═══════════════════════════════════════════════════════════════════
# UPDATE MANIFEST
# ═══════════════════════════════════════════════════════════════════
def update_manifest():
    """Genera/actualiza el manifiesto de integridad con hashes actuales."""
    files_hashes = {}
    for filepath in PROTECTED_FILES:
        h = _sha256_file(filepath)
        if h:
            files_hashes[filepath] = h
        else:
            print("  WARN: {} no encontrado, omitido del manifiesto".format(filepath))

    # Agregar CI files al manifiesto tambien
    for filepath in CI_FILES:
        h = _sha256_file(filepath)
        if h:
            files_hashes[filepath] = h

    manifest = {
        "version": VERSION_AUDIT,
        "generated_by": "audit_repo_integrity.py --update-manifest",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hash_algorithm": "sha256",
        "files": files_hashes,
        "authorized_authors": AUTHORIZED_AUTHORS,
        "expected_remote_branches": EXPECTED_REMOTE_BRANCHES,
    }

    os.makedirs(MANIFEST_PATH.parent, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("Manifiesto actualizado: {}".format(MANIFEST_PATH))
    print("Archivos registrados: {}".format(len(files_hashes)))
    return manifest


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
def run_audit(as_json=False):
    """Ejecuta los 7 checks y retorna resultado global."""
    manifest = _load_manifest()

    checks = [
        ("Governance File Integrity (SHA-256)", check_governance_integrity, (manifest,)),
        ("Remote Branch Scan", check_remote_branches, ()),
        ("Commit Author Verification", check_commit_authors, ()),
        ("Direct Push Detection", check_direct_pushes, ()),
        ("Worktree Status", check_worktrees, ()),
        ("CI/Protection Files", check_ci_files, ()),
        ("Uncommitted Protected Files", check_uncommitted_protected, ()),
    ]

    all_results = []
    global_status = "PASS"

    for i, (name, func, args) in enumerate(checks, 1):
        try:
            status, results = func(*args)
        except Exception as e:
            status = "WARN"
            results = [("error", str(e))]

        all_results.append({
            "check": i,
            "name": name,
            "status": status,
            "details": results,
        })

        if status == "FAIL":
            global_status = "FAIL"
        elif status == "WARN" and global_status != "FAIL":
            global_status = "WARN"

    if as_json:
        output = {
            "audit_version": VERSION_AUDIT,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "global_status": global_status,
            "checks": all_results,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print()
        print("=" * 60)
        print("AG-EVIDENCE REPOSITORY INTEGRITY AUDIT v{}".format(VERSION_AUDIT))
        print("=" * 60)
        print("Date: {}".format(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")))
        print()

        for check_result in all_results:
            tag = check_result["status"]
            marker = {"PASS": "OK", "WARN": "!!", "FAIL": "XX"}[tag]
            print("CHECK {}: {} [{}]".format(
                check_result["check"],
                check_result["name"],
                tag,
            ))
            for item, detail in check_result["details"]:
                print("  [{}] {} — {}".format(marker, item, detail))
            print()

        print("=" * 60)
        print("RESULTADO GLOBAL: {}".format(global_status))
        if global_status == "FAIL":
            print("ACCION: DETENER. Reportar a Hans antes de continuar.")
        elif global_status == "WARN":
            print("ACCION: Continuar con precaucion. Revisar warnings.")
        else:
            print("ACCION: Todo limpio. Continuar.")
        print("=" * 60)

    return 0 if global_status != "FAIL" else 1


def main():
    parser = argparse.ArgumentParser(
        description="AG-EVIDENCE Repository Integrity Audit"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output en formato JSON (parseable por Claude Code)",
    )
    parser.add_argument(
        "--update-manifest",
        action="store_true",
        help="Actualizar manifiesto con hashes actuales",
    )
    args = parser.parse_args()

    if args.update_manifest:
        update_manifest()
        sys.exit(0)

    sys.exit(run_audit(as_json=args.json))


if __name__ == "__main__":
    main()
