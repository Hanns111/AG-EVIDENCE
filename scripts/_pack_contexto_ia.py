"""Genera un TXT único en Descargas con contexto para IAs. Uso puntual; no CI."""

from __future__ import annotations

from pathlib import Path


def section(title: str, body: str) -> str:
    return f"\n{'=' * 80}\n{title}\n{'=' * 80}\n\n{body}\n"


def load_utf8(p: Path) -> str:
    if not p.is_file():
        return f"[ARCHIVO NO ENCONTRADO: {p}]\n"
    return p.read_text(encoding="utf-8", errors="replace")


def load_lines(p: Path, start_1: int, end_1: int) -> str:
    if not p.is_file():
        return f"[ARCHIVO NO ENCONTRADO: {p}]\n"
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    chunk = "\n".join(lines[start_1 - 1 : end_1])
    return chunk + f"\n\n[... el archivo continúa en repo; aquí líneas {start_1}-{end_1} ...]\n"


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out = Path.home() / "Downloads" / "AG_EVIDENCE_IA_CONTEXTO_COMPLETO.txt"

    intro = section(
        "AG-EVIDENCE — CONTEXTO CONSOLIDADO PARA IA",
        f"""GENERADO por scripts/_pack_contexto_ia.py
Ruta repo: {root}
USO: Pegar al inicio de un chat o adjuntar en Cursor. Si el repo diverge, prima origin/main.

PDFs/binarios: NO incrustados.
Source map investigación (NO en repo; ruta local típica): C:\\Users\\Hans\\Proyectos\\CLAUDE_SOURCE_FINAL_60MB.map — ver docs/research/CLAUDE_CODE_SOURCEMAP_NOTES.md y ADR-013.
PDF citado por el usuario (puede estar en Descargas o en expediente): 2026032418553310RendicionparaCPSimeon.pdf

SECCIONES EN ESTE ARCHIVO:
  1. CHATGPT_BRIEF_AG_EVIDENCE.txt (completo)
  2. CURRENT_STATE.md raíz (completo)
  3. AG_EVIDENCE_CONTEXT_UPDATED.txt (completo)
  4. docs/NEXT_STEP.md (completo)
  5. docs/SUNAT_VALIDATION.md (completo)
  6. docs/SESSION_LOG_2026-03-24.md (completo)
  7. tools/run_local_expediente.py (completo)
  8. scripts/extract_comprobantes_minedu.py (primeras 150 líneas)
  9. AGENTS.md (líneas 1-120)
  10. docs/PROJECT_SPEC.md (líneas 1-100)
  11. CLAUDE.md (COMPLETO)
  12. AG_EVIDENCE_MASTER_HANDOFF.txt (COMPLETO)
  13. docs/AGENT_GOVERNANCE_RULES.md (COMPLETO)
  14. governance/SESSION_PROTOCOL.md (líneas 1-120)
  15. docs/research/CLAUDE_CODE_SOURCEMAP_NOTES.md (completo)
  16. docs/ADR-013-claude-code-sourcemap-reference.md (completo)
  17. Archivos adicionales recomendados

Los archivos COMPLETOS de secciones 11-13 cubren memoria de sesión, handoff y gobernanza de agentes.
Las secciones 15-16 documentan el source map externo solo como referencia conceptual (ADR-013).
""",
    )

    parts: list[str] = [intro]
    parts.append(
        section(
            "1. CHATGPT_BRIEF_AG_EVIDENCE.txt", load_utf8(root / "CHATGPT_BRIEF_AG_EVIDENCE.txt")
        )
    )
    parts.append(section("2. CURRENT_STATE.md (raíz)", load_utf8(root / "CURRENT_STATE.md")))
    parts.append(
        section(
            "3. AG_EVIDENCE_CONTEXT_UPDATED.txt (completo)",
            load_utf8(root / "AG_EVIDENCE_CONTEXT_UPDATED.txt"),
        )
    )
    parts.append(section("4. docs/NEXT_STEP.md", load_utf8(root / "docs" / "NEXT_STEP.md")))
    parts.append(
        section("5. docs/SUNAT_VALIDATION.md", load_utf8(root / "docs" / "SUNAT_VALIDATION.md"))
    )
    parts.append(
        section(
            "6. docs/SESSION_LOG_2026-03-24.md",
            load_utf8(root / "docs" / "SESSION_LOG_2026-03-24.md"),
        )
    )
    parts.append(
        section(
            "7. tools/run_local_expediente.py",
            load_utf8(root / "tools" / "run_local_expediente.py"),
        )
    )

    ext = root / "scripts" / "extract_comprobantes_minedu.py"
    if ext.is_file():
        lines = ext.read_text(encoding="utf-8", errors="replace").splitlines()[:150]
        parts.append(
            section(
                "8. scripts/extract_comprobantes_minedu.py (primeras 150 líneas)",
                "\n".join(lines),
            )
        )
    else:
        parts.append(section("8. extract_comprobantes_minedu.py", "[no encontrado]\n"))

    parts.append(section("9. AGENTS.md (extracto)", load_lines(root / "AGENTS.md", 1, 120)))
    parts.append(
        section(
            "10. docs/PROJECT_SPEC.md (extracto)",
            load_lines(root / "docs" / "PROJECT_SPEC.md", 1, 100),
        )
    )
    parts.append(section("11. CLAUDE.md (COMPLETO)", load_utf8(root / "CLAUDE.md")))
    parts.append(
        section(
            "12. AG_EVIDENCE_MASTER_HANDOFF.txt (COMPLETO)",
            load_utf8(root / "AG_EVIDENCE_MASTER_HANDOFF.txt"),
        )
    )
    parts.append(
        section(
            "13. docs/AGENT_GOVERNANCE_RULES.md (COMPLETO)",
            load_utf8(root / "docs" / "AGENT_GOVERNANCE_RULES.md"),
        )
    )
    parts.append(
        section(
            "14. governance/SESSION_PROTOCOL.md (extracto)",
            load_lines(root / "governance" / "SESSION_PROTOCOL.md", 1, 120),
        )
    )
    research_dir = root / "docs" / "research" / "CLAUDE_CODE_SOURCEMAP_NOTES.md"
    parts.append(
        section(
            "15. docs/research/CLAUDE_CODE_SOURCEMAP_NOTES.md (completo)",
            load_utf8(research_dir),
        )
    )
    parts.append(
        section(
            "16. docs/ADR-013-claude-code-sourcemap-reference.md (completo)",
            load_utf8(root / "docs" / "ADR-013-claude-code-sourcemap-reference.md"),
        )
    )
    parts.append(
        section(
            "17. ARCHIVOS ADICIONALES RECOMENDADOS (abrir en repo)",
            """- docs/AGENT_GOVERNANCE_RULES.md
- docs/ARCHITECTURE.md
- docs/PARSING_COMPROBANTES_SPEC.md
- docs/ADR.md (índice ADRs)
- ROADMAP.md
- CONTRIBUTING.md
- src/extraction/escribano_fiel.py
- src/extraction/expediente_contract.py
- src/extraction/confidence_router.py
- src/extraction/excel_writer.py
- src/ocr/core.py
- docs/ADR-011-performance-pipeline.md, docs/ADR-012.md, docs/ADR-013-claude-code-sourcemap-reference.md
- scripts/benchmark_paddleocr_vl.py
- config/settings.py
""",
        )
    )

    out.write_text("".join(parts), encoding="utf-8", newline="\n")
    print(f"Escrito: {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
