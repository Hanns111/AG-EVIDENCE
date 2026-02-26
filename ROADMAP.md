# ROADMAP — AG-EVIDENCE v2.0

> Fuente unica de verdad del panorama completo del proyecto.
> Sincronizado con el tablero Notion (DB: 6003e907-28f5-4757-ba93-88aa3efe03e1).

**Ultima actualizacion:** 2026-02-25
**Progreso global:** 20/41 completadas (48.8%), 1 en progreso (#16)

---

## Fase 0: Setup — COMPLETADA (9/9)

| # | Tarea | Estado | Modulo |
|---|-------|--------|--------|
| 1 | Limpiar worktrees huerfanas | ✅ | Git / Worktrees |
| 2 | Arreglar .cursor/mcp.json (ruta rota) | ✅ | .cursor/mcp.json |
| 3 | Actualizar .cursorrules con arquitectura real | ✅ | .cursorrules |
| 4 | Crear protocolo Cursor + Claude Code | ✅ | CONTRIBUTING.md |
| 5 | Renombrar plan Notion: Refactorizacion → Desarrollo | ✅ | Notion |
| 6 | Crear docs/ARCHITECTURE_VISUAL.md | ✅ | docs/ |
| 7 | Crear docs/GLOSSARY.md | ✅ | docs/ |
| 8 | Limpiar referencias a IA de docs presentables | ✅ | docs/ |
| 9 | Configurar tablero Notion | ✅ | Notion |

---

## Fase 1: Trazabilidad + OCR — EN PROGRESO (6/7)

| # | Tarea | Estado | Modulo |
|---|-------|--------|--------|
| 10 | Cadena de custodia SHA-256 + registro JSONL | ✅ | src/ingestion/custody_chain.py |
| 11 | Logger estructurado JSONL con trace_id | ✅ | src/ingestion/trace_logger.py |
| 12 | Politica formal de abstencion operativa | ✅ | src/extraction/abstencion.py |
| 13 | Rewrite OCR: Tesseract → PaddleOCR PP-OCRv5 | ✅ | src/ocr/core.py |
| 14 | Extender ResultadoPagina con bbox + confianza por linea | ✅ | src/ocr/core.py |
| 15 | Benchmark A/B: Tesseract vs PaddleOCR | ✅ | scripts/benchmark_ocr.py |
| 16 | Re-generar Excel + validacion visual humana | 🔵 | Validacion manual (4 expedientes) |

---

## Fase 2: Contrato + Router — COMPLETADA (5/5)

| # | Tarea | Estado | Modulo |
|---|-------|--------|--------|
| 17 | Contrato de datos: CampoExtraido + ExpedienteJSON | ✅ | src/extraction/expediente_contract.py |
| 18 | Confidence Router + Integrity Checkpoint (nodo LangGraph) | ✅ | src/extraction/confidence_router.py |
| 19 | Calibrar umbrales con distribucion real | ✅ | src/extraction/calibracion.py |
| 20 | Hoja DIAGNOSTICO en Excel | ✅ | src/extraction/excel_writer.py |
| 21 | Integrar router en escribano_fiel.py | ✅ | src/extraction/escribano_fiel.py |

> **Nota arquitectonica (Tarea #18):** El Integrity Checkpoint sera un nodo formal
> dentro del Router LangGraph, NO un modulo monolitico separado (respeta ADR-005).
> Evalua `integrity_status = OK | WARNING | CRITICAL`. Si CRITICAL → pipeline se detiene.
> Incluye EvidenceEnforcer (validacion de snippet + pagina + regla) post-contrato tipado.
> Decision consensuada con ChatGPT, validada por Claude Code (2026-02-11).

---

## Fase 3: Qwen Fallback — PENDIENTE (0/5)

| # | Tarea | Estado | Modulo |
|---|-------|--------|--------|
| 22 | Instalar Qwen con Ollama + verificar RTX 5090 | ⬜ | Setup |
| 23 | qwen_fallback.py: cliente con JSON estricto | ⬜ | src/extraction/qwen_fallback.py |
| 24 | Politica de conflicto OCR vs Qwen | ⬜ | src/extraction/qwen_fallback.py |
| 25 | Abstencion automatica cuando Qwen falla | ⬜ | src/extraction/qwen_fallback.py |
| 26 | Documentar punto de quiebre para vLLM | ⬜ | Documentacion |

---

## Fase 4: Validaciones — PENDIENTE (0/3)

| # | Tarea | Estado | Modulo |
|---|-------|--------|--------|
| 27 | Validador de expediente: sumas aritmeticas y cruzadas | ⬜ | src/validation/validador_expediente.py |
| 28 | Reglas de viaticos: topes, plazos, docs obligatorios | ⬜ | src/validation/reglas_viaticos.py |
| 29 | Reporte de hallazgos: hoja HALLAZGOS en Excel | ⬜ | src/validation/reporte_hallazgos.py |

---

## Fase 5: Evaluacion + Legal prep — PENDIENTE (0/5)

| # | Tarea | Estado | Modulo |
|---|-------|--------|--------|
| 30 | Golden dataset: expected.json por expediente | ⬜ | data/evaluacion/ |
| 31 | test_flywheel.py: regresion contra golden dataset | ⬜ | tests/test_flywheel.py |
| 32 | Proceso de crecimiento del dataset | ⬜ | Proceso manual |
| 33 | Disenar esquema de chunks legales (no implementar) | ⬜ | Diseno futuro |
| 34 | Definir verificador de citas (no implementar) | ⬜ | Diseno futuro |

---

## Fase 6: Motor Legal — PENDIENTE (0/6)

| # | Tarea | Estado | Modulo |
|---|-------|--------|--------|
| 35 | chunker_legal.py: chunking por articulo/numeral | ⬜ | src/legal/chunker_legal.py |
| 36 | rag_engine.py: BM25 + embeddings + reranker | ⬜ | src/legal/rag_engine.py |
| 37 | citation_verifier.py: verificar citas vs fuente | ⬜ | src/legal/citation_verifier.py |
| 38 | legal_analyzer.py: orquestador LangGraph | ⬜ | src/legal/legal_analyzer.py |
| 39 | Politica de abstencion legal | ⬜ | src/legal/ |
| 40 | Evaluar serving con batching si volumen crece | ⬜ | Escalabilidad |

---

## Transversal: Seguridad — COMPLETADA (1/1)

| # | Tarea | Estado | Modulo |
|---|-------|--------|--------|
| 41 | Blindaje de Seguridad (4 capas defense-in-depth) | ✅ | scripts/audit_repo_integrity.py, scripts/governance_guard.py, .pre-commit-config.yaml, .github/workflows/ci-lint.yml, .github/CODEOWNERS, .github/pull_request_template.md, .gitattributes, governance/integrity_manifest.json |

> **Nota:** Implementacion transversal fuera de las fases funcionales. 4 capas independientes:
> GitHub platform (CODEOWNERS, PR template, .gitattributes) → CI (4 jobs) → Pre-commit hooks
> (8 hooks: ruff, governance guard, seguridad) → Session protocol (audit_repo_integrity.py).
> ACTA DE CIERRE aprobada por Hans (2026-02-25). Branch protection pendiente configuracion manual.

---

## Modulos Operativos (codigo real en src/)

| Modulo | Archivo | Lineas | Tests |
|--------|---------|--------|-------|
| Cadena de custodia | src/ingestion/custody_chain.py | ~529 | 27 |
| Logger estructurado | src/ingestion/trace_logger.py | ~638 | 55 |
| Extractor PDF | src/ingestion/pdf_text_extractor.py | ~365 | 10 |
| Config gating | src/ingestion/config.py | ~38 | — |
| Abstencion | src/extraction/abstencion.py | ~550 | 66 |
| Contrato de datos | src/extraction/expediente_contract.py | ~1161 | 84 |
| Confidence Router | src/extraction/confidence_router.py | ~1424 | 86 |
| Calibracion Umbrales | src/extraction/calibracion.py | ~500 | 84 |
| Escribano Fiel (Pipeline) | src/extraction/escribano_fiel.py | ~1027 | 44 |
| Excel Writer DIAGNOSTICO | src/extraction/excel_writer.py | ~850 | 59 |
| OCR Core (PaddleOCR PP-OCRv5 + Tesseract fallback) | src/ocr/core.py | ~880 | 75 |
| OCR Preprocessor | src/tools/ocr_preprocessor.py | ~301 | 6 |
| Detraccion SPOT | src/rules/detraccion_spot.py | — | 25 |
| Requisitos TDR | src/rules/tdr_requirements.py | — | 10 |
| Integrador SPOT+TDR | src/rules/integrador.py | — | — |
| Config global | config/settings.py | ~360 | — |
| Audit Repo Integrity | scripts/audit_repo_integrity.py | ~400 | — |
| Governance Guard | scripts/governance_guard.py | ~150 | — |

**Total tests:** 885 passed, 2 skipped

---

## Resumen de Progreso por Fase

```
Fase 0: Setup          [██████████] 9/9  — COMPLETADA
Fase 1: Trazabilidad   [████████░░] 6/7  — EN PROGRESO (#16 en progreso)
Fase 2: Contrato       [██████████] 5/5  — COMPLETADA (#17 ✅, #18 ✅, #19 ✅, #20 ✅, #21 ✅)
Fase 3: Qwen           [░░░░░░░░░░] 0/5  — PENDIENTE
Fase 4: Validaciones   [░░░░░░░░░░] 0/3  — PENDIENTE
Fase 5: Evaluacion     [░░░░░░░░░░] 0/5  — PENDIENTE
Fase 6: Motor Legal    [░░░░░░░░░░] 0/6  — PENDIENTE
Transversal: Seguridad [██████████] 1/1  — COMPLETADA (#41 Blindaje 4 capas)
```
