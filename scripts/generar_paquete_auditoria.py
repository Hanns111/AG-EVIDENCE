#!/usr/bin/env python3
"""
Generador automatico de Paquete de Auditoria.

Uso:
    python scripts/generar_paquete_auditoria.py                     # auto-detect
    python scripts/generar_paquete_auditoria.py --tarea 22           # especificar tarea
    python scripts/generar_paquete_auditoria.py --fase 3             # especificar fase
    python scripts/generar_paquete_auditoria.py --base origin/main   # comparar contra branch
    python scripts/generar_paquete_auditoria.py --no-clipboard       # no copiar al clipboard
    python scripts/generar_paquete_auditoria.py --include-patch      # incluir diff completo
    python scripts/generar_paquete_auditoria.py --output paquete.txt # guardar en archivo

Genera:
    1. Preambulo obligatorio (protocolo PROTOCOL_SYNC.md v2)
    2. Paquete de Auditoria completo (8 secciones)
    3. Copia al clipboard (Windows) automaticamente

Flujo v2: Codex CLI (implementador) genera paquete -> Claude Code (auditor) revisa.
Claude Code tambien puede generar el paquete directamente desde el repo.

Referencia: docs/PROTOCOL_SYNC.md (GOV_PROTOCOL_SYNC_v2)
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── Configuración ──────────────────────────────────────────────
VERSION = "1.0.0"
REPO_ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_REF = "docs/PROTOCOL_SYNC.md (GOV_PROTOCOL_SYNC_v2)"

# Preámbulo que Codex DEBE leer antes de auditar
PREAMBULO_AUDITORIA = """╔═══════════════════════════════════════════════════════════════════════╗
║         PAQUETE DE AUDITORIA — PROTOCOL_SYNC v2                       ║
╠═══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  Protocolo: docs/PROTOCOL_SYNC.md (GOV_PROTOCOL_SYNC_v2)             ║
║  Implementador: Codex CLI                                             ║
║  Auditor: Claude Code                                                 ║
║                                                                       ║
║  REGLAS DE AUDITORIA:                                                 ║
║                                                                       ║
║  1. Auditar UNICAMENTE el contenido de este paquete + repo local.     ║
║  2. Citar SIEMPRE el Commit SHA en hallazgos.                         ║
║  3. Verificar: tests pasan, ruff limpio, coherencia arquitectonica.   ║
║  4. Si falta contexto, solicitar patch o revisar repo directamente.   ║
║  5. Emitir veredicto: CONFORME / NO CONFORME / INCIERTO.             ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
""".strip()


def run_git(args: list[str], check: bool = True) -> str:
    """Ejecuta comando git y retorna stdout."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            check=check,
            timeout=30,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"[ERROR git {' '.join(args)}]: {e.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT git {' '.join(args)}]"


def run_tests() -> str:
    """Ejecuta pytest y retorna resumen."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short", "-q"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=120,
        )
        # Extraer línea de resumen (última línea con "passed")
        lines = result.stdout.strip().split("\n")
        summary_lines = [l for l in lines if "passed" in l or "failed" in l or "error" in l]
        summary = summary_lines[-1] if summary_lines else "No se pudo determinar resultado"
        return f"Comando: pytest tests/ -v --tb=short -q\n   Resultado: {summary}"
    except subprocess.TimeoutExpired:
        return "Comando: pytest tests/ -v\n   Resultado: [TIMEOUT después de 120s]"
    except Exception as e:
        return f"Comando: pytest tests/ -v\n   Resultado: [ERROR: {e}]"


def get_branch() -> str:
    """Retorna branch actual."""
    branch = run_git(["branch", "--show-current"])
    if not branch:
        branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    return branch or "desconocida"


def get_commit_info() -> tuple[str, str]:
    """Retorna (SHA completo, mensaje del último commit)."""
    sha = run_git(["rev-parse", "HEAD"])
    msg = run_git(["log", "-1", "--format=%s"])
    return sha, msg


def get_base_sha(base: str) -> str:
    """Retorna SHA del base branch."""
    return run_git(["rev-parse", base], check=False)


def get_diffstat(base: str) -> str:
    """Retorna diffstat contra base."""
    stat = run_git(["diff", "--stat", f"{base}...HEAD"], check=False)
    return stat if stat else "(sin diferencias contra base)"


def get_diff_full(base: str) -> str:
    """Retorna diff completo contra base."""
    diff = run_git(["diff", f"{base}...HEAD"], check=False)
    return diff if diff else "(sin diferencias contra base)"


def get_files_changed(base: str) -> dict[str, list[str]]:
    """Clasifica archivos en nuevos/modificados/eliminados."""
    raw = run_git(["diff", "--name-status", f"{base}...HEAD"], check=False)
    result: dict[str, list[str]] = {"nuevos": [], "modificados": [], "eliminados": []}

    if not raw or raw.startswith("[ERROR"):
        return result

    for line in raw.split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) < 2:
            continue
        status, filepath = parts[0], parts[1]
        if status.startswith("A"):
            result["nuevos"].append(filepath)
        elif status.startswith("M"):
            result["modificados"].append(filepath)
        elif status.startswith("D"):
            result["eliminados"].append(filepath)
        elif status.startswith("R"):
            # Rename: R100\told\tnew
            rename_parts = line.split("\t")
            if len(rename_parts) >= 3:
                result["eliminados"].append(rename_parts[1])
                result["nuevos"].append(rename_parts[2])

    return result


def format_file_list(files: list[str]) -> str:
    """Formatea lista de archivos."""
    if not files:
        return "Ninguno"
    return "\n      ".join(files)


def detect_tarea_from_commits(base: str) -> str:
    """Intenta detectar # de tarea de los mensajes de commit."""
    log = run_git(["log", "--oneline", f"{base}...HEAD"], check=False)
    if not log:
        return "auto-detectada"

    # Buscar patrones como "#22", "tarea 22", "Tarea #22"
    import re

    for line in log.split("\n"):
        match = re.search(r"#(\d+)", line)
        if match:
            return f"#{match.group(1)}"
        match = re.search(r"[Tt]area\s*(\d+)", line)
        if match:
            return f"#{match.group(1)}"

    return "auto-detectada"


def copy_to_clipboard(text: str) -> bool:
    """Copia texto al clipboard de Windows."""
    try:
        process = subprocess.Popen(
            ["clip"],
            stdin=subprocess.PIPE,
            shell=True,
        )
        process.communicate(text.encode("utf-16-le"))
        return process.returncode == 0
    except Exception:
        # Fallback: intentar con powershell
        try:
            process = subprocess.Popen(
                ["powershell", "-Command", "Set-Clipboard", "-Value", "$input"],
                stdin=subprocess.PIPE,
            )
            process.communicate(text.encode("utf-8"))
            return process.returncode == 0
        except Exception:
            return False


def generar_paquete(
    tarea: str | None = None,
    fase: str | None = None,
    base: str = "origin/main",
    include_patch: bool = False,
    riesgos: str | None = None,
    decision: str | None = None,
) -> str:
    """Genera el paquete completo listo para pegar en Codex."""

    # Recolectar datos
    branch = get_branch()
    sha, commit_msg = get_commit_info()
    base_sha = get_base_sha(base)
    diffstat = get_diffstat(base)
    files = get_files_changed(base)

    # Auto-detectar tarea si no se especificó
    if not tarea:
        tarea = detect_tarea_from_commits(base)

    # Encabezado del paquete
    encabezado = f"Tarea {tarea}"
    if fase:
        encabezado += f" / Fase {fase}"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Tests
    print("⏳ Ejecutando tests...", file=sys.stderr)
    test_result = run_tests()
    print("✅ Tests completados.", file=sys.stderr)

    # Construir paquete
    lines = []

    # ─── Preámbulo obligatorio ───
    lines.append(PREAMBULO_AUDITORIA)
    lines.append("")
    lines.append("")

    # ─── Paquete de Auditoría ───
    lines.append(f"=== PAQUETE DE AUDITORIA — [{encabezado}] ===")
    lines.append(f"Generado: {timestamp}")
    lines.append(f"Protocolo: {PROTOCOL_REF}")
    lines.append("")

    # 1. BRANCH
    lines.append("1. BRANCH")
    lines.append(f"   Nombre: {branch}")
    lines.append(f"   Base: {base} @ {base_sha}")
    lines.append("")

    # 2. COMMIT
    lines.append("2. COMMIT")
    lines.append(f"   SHA: {sha}")
    lines.append(f"   Mensaje: {commit_msg}")
    lines.append("")

    # 3. DIFFSTAT
    lines.append("3. DIFFSTAT")
    for stat_line in diffstat.split("\n"):
        lines.append(f"   {stat_line}")
    lines.append("")

    # 4. TESTS
    lines.append("4. TESTS")
    for test_line in test_result.split("\n"):
        lines.append(f"   {test_line}")
    lines.append("")

    # 5. ARCHIVOS TOCADOS
    lines.append("5. ARCHIVOS TOCADOS")
    lines.append(f"   Nuevos: {format_file_list(files['nuevos'])}")
    lines.append(f"   Modificados: {format_file_list(files['modificados'])}")
    lines.append(f"   Eliminados: {format_file_list(files['eliminados'])}")
    lines.append("")

    # 6. ARTEFACTOS GENERADOS
    lines.append("6. ARTEFACTOS GENERADOS")
    lines.append("   (Listar manualmente si aplica — Excel, JSON, logs)")
    lines.append("")

    # 7. RIESGOS ABIERTOS
    lines.append("7. RIESGOS ABIERTOS")
    lines.append(f"   {riesgos or 'Ninguno identificado'}")
    lines.append("")

    # 8. DECISION
    lines.append("8. DECISION")
    lines.append(f"   {decision or 'GO — Pendiente validación Codex'}")
    lines.append("")

    lines.append("=== FIN PAQUETE ===")

    # ─── Patch opcional ───
    if include_patch:
        lines.append("")
        lines.append("=== PATCH COMPLETO (para auditoría profunda) ===")
        lines.append("")
        diff_full = get_diff_full(base)
        lines.append(diff_full)
        lines.append("")
        lines.append("=== FIN PATCH ===")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Genera Paquete de Auditoría para Codex (listo para pegar)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python scripts/generar_paquete_codex.py
  python scripts/generar_paquete_codex.py --tarea 22 --fase 3
  python scripts/generar_paquete_codex.py --include-patch
  python scripts/generar_paquete_codex.py --output paquete.txt --no-clipboard
        """,
    )

    parser.add_argument(
        "--tarea",
        type=str,
        default=None,
        help="Número de tarea (ej: 22, '#22'). Auto-detecta si no se especifica.",
    )
    parser.add_argument(
        "--fase",
        type=str,
        default=None,
        help="Número de fase (ej: 3). Opcional.",
    )
    parser.add_argument(
        "--base",
        type=str,
        default="origin/main",
        help="Branch base para comparar (default: origin/main)",
    )
    parser.add_argument(
        "--include-patch",
        action="store_true",
        help="Incluir diff completo al final del paquete",
    )
    parser.add_argument(
        "--riesgos",
        type=str,
        default=None,
        help="Riesgos abiertos (texto libre). Default: 'Ninguno identificado'",
    )
    parser.add_argument(
        "--decision",
        type=str,
        default=None,
        help="Decisión GO/NO-GO con justificación",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Guardar paquete en archivo (además del clipboard)",
    )
    parser.add_argument(
        "--no-clipboard",
        action="store_true",
        help="No copiar al clipboard",
    )

    args = parser.parse_args()

    # Normalizar tarea
    tarea = args.tarea
    if tarea and not tarea.startswith("#"):
        tarea = f"#{tarea}"

    print(f"🔧 generar_paquete_codex.py v{VERSION}", file=sys.stderr)
    print(f"📁 Repo: {REPO_ROOT}", file=sys.stderr)
    print(f"🔀 Base: {args.base}", file=sys.stderr)
    print("", file=sys.stderr)

    # Generar
    paquete = generar_paquete(
        tarea=tarea,
        fase=args.fase,
        base=args.base,
        include_patch=args.include_patch,
        riesgos=args.riesgos,
        decision=args.decision,
    )

    # Guardar en archivo si se pidió
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(paquete, encoding="utf-8")
        print(f"💾 Guardado en: {output_path.resolve()}", file=sys.stderr)

    # Copiar al clipboard
    if not args.no_clipboard:
        if copy_to_clipboard(paquete):
            print("📋 ¡Copiado al clipboard! Pégalo directamente en Codex.", file=sys.stderr)
        else:
            print(
                "⚠️  No se pudo copiar al clipboard. Usa --output para guardar en archivo.",
                file=sys.stderr,
            )

    # Imprimir a stdout también
    print(paquete)

    print("", file=sys.stderr)
    print("✅ Paquete generado. Flujo:", file=sys.stderr)
    print("   1. Pega en Claude Code para auditoria (ya esta en clipboard)", file=sys.stderr)
    print("   2. Claude Code revisa diff, tests y coherencia", file=sys.stderr)
    print("   3. Claude Code emite veredicto: CONFORME / NO CONFORME / INCIERTO", file=sys.stderr)


if __name__ == "__main__":
    main()
