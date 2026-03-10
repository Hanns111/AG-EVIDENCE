# -*- coding: utf-8 -*-
"""
tech_monitor.py — AI Stack Sentinel (Vigilancia Tecnologica Semanal)

Verifica versiones actuales vs ultimas disponibles de herramientas
criticas del proyecto AG-EVIDENCE. Genera reporte para decision humana.

Uso:
    python scripts/tech_monitor.py              # Reporte completo
    python scripts/tech_monitor.py --json       # Salida JSON
    python scripts/tech_monitor.py --check-only # Exit 1 si hay updates

Frecuencia recomendada: Semanal (lunes)

Fuentes: GitHub Releases + PyPI + Ollama local
NO consulta: HuggingFace masivo, estimaciones VRAM, LangGraph
"""

import json
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

VERSION_TECH_MONITOR = "1.0.0"

# ─── Herramientas del proyecto ──────────────────────────────────────────────
TOOLS = {
    "ollama": {
        "current": "0.16.2",
        "github": "ollama/ollama",
        "impact": "ALTO — motor de inferencia VLM y LLM",
    },
    "paddleocr": {
        "current": "3.4.0",
        "pypi": "paddleocr",
        "impact": "ALTO — motor OCR primario PP-OCRv5",
    },
    "paddlepaddle-gpu": {
        "current": "3.3.0",
        "pypi": "paddlepaddle-gpu",
        "impact": "ALTO — backend GPU (NOTA: v3.x se instala desde indice Paddle, no PyPI)",
    },
    "duckdb": {
        "current": "1.4.4",
        "pypi": "duckdb",
        "impact": "BAJO — base analitica",
    },
    "openpyxl": {
        "current": "3.1.5",
        "pypi": "openpyxl",
        "impact": "BAJO — generacion Excel",
    },
    "pymupdf": {
        "current": "1.25.0",
        "pypi": "PyMuPDF",
        "impact": "MEDIO — renderizado PDF + extraccion texto",
    },
}

# ─── Modelos VLM/LLM ───────────────────────────────────────────────────────
MODELS = {
    "qwen-vl": {
        "current": "qwen2.5vl:7b",
        "target": "qwen3-vl:8b",
        "github_tags": "QwenLM/Qwen3-VL",
        "impact": "CRITICO — precision extraccion comprobantes",
    },
    "qwen-text": {
        "current": "qwen3:32b",
        "github_tags": "QwenLM/Qwen3",
        "impact": "MEDIO — modelo texto analista local",
    },
    "qwen3.5": {
        "current": "no instalado",
        "github_tags": "QwenLM/Qwen3.5",
        "impact": "ALTO — sucesor Qwen3-VL, vision integrada, 90.8% OmniDocBench",
        "note": "WATCH: GGUF no funciona en Ollama aun (mmproj issue)",
    },
    "monkeyocr": {
        "current": "no instalado",
        "github": "Yuliang-Liu/MonkeyOCR",
        "impact": "ALTO — supera modelos 72B en doc parsing, solo 1.2B params",
        "note": "TRIAL: evaluar como reemplazo potencial PaddleOCR+VLM",
    },
}


@dataclass
class CheckResult:
    tool: str
    current: str
    latest: Optional[str] = None
    has_update: bool = False
    impact: str = ""
    error: Optional[str] = None
    url: Optional[str] = None
    note: Optional[str] = None


def _fetch(url: str, timeout: int = 10) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AG-EVIDENCE-TechMonitor/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"_error": str(e)}


def check_github(name: str, cfg: dict) -> CheckResult:
    r = CheckResult(
        tool=name, current=cfg["current"], impact=cfg.get("impact", ""), note=cfg.get("note")
    )
    data = _fetch(f"https://api.github.com/repos/{cfg['github']}/releases/latest")
    if data and "_error" not in data:
        tag = data.get("tag_name", "").lstrip("v")
        r.latest = tag
        r.has_update = bool(tag and tag != cfg["current"])
        r.url = data.get("html_url")
    elif data:
        r.error = data.get("_error")
    return r


def check_pypi(name: str, cfg: dict) -> CheckResult:
    r = CheckResult(tool=name, current=cfg["current"], impact=cfg.get("impact", ""))
    data = _fetch(f"https://pypi.org/pypi/{cfg['pypi']}/json")
    if data and "_error" not in data:
        latest = data.get("info", {}).get("version", "")
        r.latest = latest
        r.has_update = bool(latest and latest != cfg["current"])
        r.url = data.get("info", {}).get("project_url")
    elif data:
        r.error = data.get("_error")
    return r


def check_github_tags(name: str, cfg: dict) -> CheckResult:
    """Check latest tag (for repos without formal releases, like Qwen)."""
    r = CheckResult(
        tool=name, current=cfg["current"], impact=cfg.get("impact", ""), note=cfg.get("note")
    )
    repo = cfg["github_tags"]
    data = _fetch(f"https://api.github.com/repos/{repo}/tags?per_page=1")
    if isinstance(data, list) and len(data) > 0:
        tag = data[0].get("name", "").lstrip("v")
        r.latest = tag
        r.url = f"https://github.com/{repo}"
        # For models, just report the latest tag — don't compare versions
        r.has_update = False  # Manual review required
    elif isinstance(data, dict) and "_error" in data:
        r.error = data.get("_error")
    else:
        r.latest = "sin tags"
    return r


def check_ollama_local() -> list[CheckResult]:
    results = []
    data = _fetch("http://localhost:11434/api/tags")
    if data and "models" in data:
        for m in data["models"]:
            results.append(
                CheckResult(tool=f"ollama:{m['name']}", current=m["name"], impact="local")
            )
    elif data and "_error" in data:
        results.append(
            CheckResult(tool="ollama:server", current="offline", error="Ollama no corriendo")
        )
    return results


def run_checks() -> list[CheckResult]:
    results = []
    for name, cfg in TOOLS.items():
        if "pypi" in cfg:
            results.append(check_pypi(name, cfg))
        elif "github" in cfg:
            results.append(check_github(name, cfg))
    for name, cfg in MODELS.items():
        if "github_tags" in cfg:
            results.append(check_github_tags(name, cfg))
        elif "github" in cfg:
            results.append(check_github(name, cfg))
    results.extend(check_ollama_local())
    return results


def print_report(results: list[CheckResult]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'=' * 70}")
    print("  AI STACK SENTINEL — AG-EVIDENCE")
    print(f"  v{VERSION_TECH_MONITOR} | {now}")
    print(f"{'=' * 70}\n")

    updates = [r for r in results if r.has_update and not r.error]
    ok = [
        r for r in results if not r.has_update and not r.error and not r.tool.startswith("ollama:")
    ]
    watched = [r for r in results if r.note]
    local = [r for r in results if r.tool.startswith("ollama:") and not r.error]
    errs = [r for r in results if r.error and not r.tool.startswith("ollama:")]

    if updates:
        print("ACTUALIZACIONES DISPONIBLES:")
        print("-" * 50)
        for r in updates:
            flag = "!!" if any(k in r.impact for k in ["CRITICO", "ALTO"]) else ".."
            print(f"  [{flag}] {r.tool}: {r.current} -> {r.latest}")
            print(f"       Impacto: {r.impact}")
            if r.url:
                print(f"       {r.url}")
            print()
    else:
        print("Sin actualizaciones.\n")

    if ok:
        print("AL DIA:")
        for r in ok:
            print(f"  [OK] {r.tool}: {r.current}")
        print()

    if watched:
        print("RADAR TECNOLOGICO:")
        for r in watched:
            print(f"  [>>] {r.tool}: {r.note}")
        print()

    if local:
        print("MODELOS OLLAMA LOCALES:")
        for r in local:
            print(f"  [*] {r.current}")
        print()

    if errs:
        print("ERRORES:")
        for r in errs:
            print(f"  [ERR] {r.tool}: {r.error}")
        print()

    print(f"{'=' * 70}")
    n_crit = len([r for r in updates if "CRITICO" in r.impact or "ALTO" in r.impact])
    print(f"  {len(updates)} updates | {len(ok)} al dia | {n_crit} criticos")
    print(f"{'=' * 70}\n")


def main():
    args = sys.argv[1:]
    results = run_checks()
    if "--json" in args:
        print(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "version": VERSION_TECH_MONITOR,
                    "checks": [asdict(r) for r in results],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    elif "--check-only" in args:
        updates = [r for r in results if r.has_update and not r.error]
        if updates:
            for r in updates:
                print(f"UPDATE: {r.tool} {r.current} -> {r.latest}")
            sys.exit(1)
        else:
            print("Todo al dia.")
    else:
        print_report(results)


if __name__ == "__main__":
    main()
