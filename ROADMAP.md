# ROADMAP — AG-EVIDENCE v2.0

> Fuente unica de verdad del panorama completo del proyecto.
> Sincronizado con el tablero Notion (DB: 6003e907-28f5-4757-ba93-88aa3efe03e1).

**Ultima actualizacion:** 2026-02-11
**Progreso global:** 12/40 completadas (30%), 1 en progreso

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

## Fase 1: Trazabilidad + OCR — EN PROGRESO (3/7 + 1 activa)

| # | Tarea | Estado | Modulo |
|---|-------|--------|--------|
| 10 | Cadena de custodia SHA-256 + registro JSONL | ✅ | src/ingestion/custody_chain.py |
| 11 | Logger estructurado JSONL con trace_id | ✅ | src/ingestion/trace_logger.py |
| 12 | Politica formal de abstencion operativa | ✅ | src/extraction/abstencion.py |
| **13** | **Rewrite OCR: Tesseract → PaddleOCR PP-OCRv5** | **🔵** | **src/ocr/core.py** |
| 14 | Extender ResultadoPagina con bbox + confianza por linea | ⬜ | src/ocr/core.py |
| 15 | Benchmark A/B: Tesseract vs PaddleOCR | ⬜ | scripts/benchmark_ocr.py |
| 16 | Re-generar Excel + validacion visual humana | ⬜ | Validacion manual |

---

## Fase 2: Contrato + Router — PENDIENTE (0/5)

| # | Tarea | Estado | Modulo |
|---|-------|--------|--------|
| 17 | Contrato de datos: CampoExtraido + ExpedienteJSON | ⬜ | src/extraction/expediente_contract.py |
| 18 | Confidence Router con umbrales por tipo de campo | ⬜ | src/extraction/confidence_router.py |
| 19 | Calibrar umbrales con distribucion real | ⬜ | Calibracion |
| 20 | Hoja DIAGNOSTICO en Excel | ⬜ | src/extraction/excel_writer.py |
| 21 | Integrar router en escribano_fiel.py | ⬜ | src/extraction/escribano_fiel.py |

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

## Modulos Operativos (codigo real en src/)

| Modulo | Archivo | Lineas | Tests |
|--------|---------|--------|-------|
| Cadena de custodia | src/ingestion/custody_chain.py | ~529 | 27 |
| Logger estructurado | src/ingestion/trace_logger.py | ~638 | 55 |
| Extractor PDF | src/ingestion/pdf_text_extractor.py | ~365 | 10 |
| Config gating | src/ingestion/config.py | ~38 | — |
| Abstencion | src/extraction/abstencion.py | ~550 | 66 |
| OCR Core (Tesseract) | src/ocr/core.py | ~383 | — |
| OCR Preprocessor | src/tools/ocr_preprocessor.py | ~301 | 6 |
| Detraccion SPOT | src/rules/detraccion_spot.py | — | 25 |
| Requisitos TDR | src/rules/tdr_requirements.py | — | 10 |
| Integrador SPOT+TDR | src/rules/integrador.py | — | — |
| Config global | config/settings.py | ~360 | — |

**Total tests:** 201 passed, 2 skipped (PyMuPDF en Windows)

---

## Resumen de Progreso por Fase

```
Fase 0: Setup          [██████████] 9/9  — COMPLETADA
Fase 1: Trazabilidad   [██████░░░░] 3/7  — EN PROGRESO (Tarea #13)
Fase 2: Contrato       [░░░░░░░░░░] 0/5  — PENDIENTE
Fase 3: Qwen           [░░░░░░░░░░] 0/5  — PENDIENTE
Fase 4: Validaciones   [░░░░░░░░░░] 0/3  — PENDIENTE
Fase 5: Evaluacion     [░░░░░░░░░░] 0/5  — PENDIENTE
Fase 6: Motor Legal    [░░░░░░░░░░] 0/6  — PENDIENTE
```
