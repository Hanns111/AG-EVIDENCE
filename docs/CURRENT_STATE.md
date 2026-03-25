# ESTADO ACTUAL DEL PROYECTO — AG-EVIDENCE

## Fecha de Corte
2026-03-24

---

## 1. Estado General

**v2.0 — Fase 4 completada + Pipeline v4.1.0 + Golden Dataset**

Pipeline v4.1.0 operativo: OCR-first + qwen2.5vl:7b (sin fallback) + keep_alive + JSON estricto.
Benchmark formal contra golden dataset completado (DIRI2026-INT-0196314).
ADR-012: PaddleOCR-VL-1.5 evaluado y descartado — proyecto sigue con qwen2.5vl:7b.

**OCR Engine:** PaddleOCR 3.4.0 PP-OCRv5 server (GPU RTX 5090 via CUDA 12.9)
**VLM Engine:** Ollama 0.16.2 + qwen2.5vl:7b (Q4_K_M, 6.0GB) — modelo primario sin fallback
**Pipeline:** v4.1.0 — 2.7 min/expediente, 0 fallos JSON, OCR-first (38% paginas sin VLM)
**Tests:** 1355 passed, 0 failures
**Expedientes procesados E2E:** 6 (ODI-0139051, DEBEDSAR-0146130, DIGC-072851, OTIC-086866, DIGC-073285, DIRI2026-INT-0196314)

---

## 2. Lo que existe y funciona

| Modulo | Estado | Descripcion |
|--------|--------|-------------|
| `src/ingestion/custody_chain.py` | Operativo | Cadena de custodia SHA-256 |
| `src/ingestion/trace_logger.py` | Operativo | Logger JSONL con trace_id |
| `src/ingestion/pdf_text_extractor.py` | Operativo | Extraccion texto PDF con gating + validacion post-rotacion (Regla 2) |
| `src/extraction/abstencion.py` | Operativo | Politica formal de abstencion + EvidenceStatus + clasificar_status() |
| `src/extraction/confidence_router.py` | Operativo | Router de confianza + IntegrityCheckpoint + DiagnosticoExpediente (v2.0.0) |
| `src/extraction/excel_writer.py` | Operativo | Hoja DIAGNOSTICO en Excel (semaforo, 6 secciones, detalle campos) |
| `src/extraction/expediente_contract.py` | Operativo | Contrato tipado ExpedienteJSON (11 Grupos A-K, 18+ dataclasses) |
| `src/extraction/escribano_fiel.py` | Operativo | Pipeline orquestador: custodia→OCR→parseo→router→Excel (v1.0.0) |
| `src/extraction/local_analyst.py` | Nuevo | Capa C: IA local confinada con bloqueo de campos probatorios |
| `src/ocr/core.py` | Operativo | Motor OCR PP-OCRv5 server GPU + Tesseract fallback + bbox/confianza + Regla 2 (v4.0.0) |
| `src/tools/vision.py` | Nuevo | Preprocesamiento de imagen (337 lineas) |
| `src/rules/detraccion_spot.py` | Operativo | Validacion SPOT/detracciones |
| `src/rules/tdr_requirements.py` | Operativo | Requisitos TDR |
| `src/rules/integrador.py` | Operativo | Consolidacion SPOT+TDR |
| `src/rules/field_validators.py` | Nuevo | Capa B: Validadores deterministas (RUC, serie/numero, monto, fecha, aritmetica) |
| `src/tools/ocr_preprocessor.py` | Operativo | OCRmyPDF via WSL2 |
| `config/settings.py` | Actualizado | +VISION_CONFIG, +LOCAL_ANALYST_CONFIG |
| `docs/GOBERNANZA_TECNICA_TRANSVERSAL.md` | Nuevo | 8 reglas estructurales transversales |
| `governance/SESSION_PROTOCOL.md` | Vigente | Protocolo apertura/cierre sesion |
| `scripts/backup_local.py` | Vigente | Backup ZIP completo del proyecto |
| `scripts/generar_excel_DEBEDSAR2026.py` | Operativo | Excel rendicion DEBEDSAR2026 (estrategia mixta PyMuPDF+VLM 500 DPI) |
| `scripts/extraer_con_qwen_vl.py` | Operativo | Extraccion VLM Qwen2.5-VL via Ollama (11 grupos A-K) |
| `scripts/audit_repo_integrity.py` | Operativo | Auditoria integridad: 7 checks SHA-256 + branches + CI + CRLF normalization |
| `scripts/governance_guard.py` | Operativo | Pre-commit hook: bloquea cambios a 9 archivos protegidos (override: AG_GOVERNANCE_OVERRIDE) |
| `governance/integrity_manifest.json` | Operativo | 13 hashes SHA-256 (9 gobernanza + 4 CI) |
| `.pre-commit-config.yaml` | Operativo | 8 hooks: ruff, ruff-format, large files, merge conflicts, private key, eof-fixer, trailing whitespace, governance guard |
| `.github/workflows/ci-lint.yml` | Operativo | CI pipeline: 4 jobs (lint, commit-lint, governance-check, author-check) |
| `.github/CODEOWNERS` | Operativo | Propiedad archivos criticos → @Hanns111 |
| `.github/pull_request_template.md` | Operativo | Template PRs con checklist gobernanza |
| `.gitattributes` | Operativo | Merge protection (ours) para archivos protegidos |

---

## 3. Patron de 3 Capas (Regla 8)

| Capa | Modulo | Estado |
|------|--------|--------|
| **A — Extraccion determinista** | `abstencion.py` + `core.py` | Operativo. CampoExtraido extendido con EvidenceStatus, bbox, motor_ocr |
| **B — Validacion determinista** | `src/rules/field_validators.py` | Nuevo. Validadores de RUC, serie/numero, monto, fecha, aritmetica |
| **C — IA local analista** | `src/extraction/local_analyst.py` | Nuevo. Interfaz con bloqueo de campos probatorios. Motor no conectado (Fase 3) |

**Feature flag:** `LOCAL_ANALYST_CONFIG["enabled"] = False` (default).

---

## 4. Lo que NO existe (y esta planificado)

| Componente | Fase | Estado |
|------------|------|--------|
| Benchmark A/B Tesseract vs PaddleOCR | Fase 1 (#15) | Completado (ADR-008) |
| Re-generar Excel + validacion visual | Fase 1 (#16) | En progreso (4 expedientes procesados) |
| Reprocesar Caja Chica N.3 con pipeline formal | Pre-Fase 2 | Pendiente (proxima sesion) |
| Contrato de expediente (JSON tipado) | Fase 2 (#17) | ✅ Completado |
| Router + Integrity Checkpoint | Fase 2 (#18) | ✅ Completado |
| Calibrar umbrales | Fase 2 (#19) | ✅ Completado |
| Hoja DIAGNOSTICO en Excel | Fase 2 (#20) | ✅ Completado |
| Integrar router en escribano_fiel.py | Fase 2 (#21) | ✅ Completado |
| Parseo profundo Qwen-VL | Fase 3 (#22-26) | ✅ Completado |
| Validaciones + Hallazgos | Fase 4 (#27-29) | ✅ Completado |
| Golden dataset DIRI2026 | Fase 5 (#30) | ✅ Completado |
| ADR-012 PaddleOCR-VL-1.5 | Transversal | ✅ Evaluado y descartado |
| Blindaje de Seguridad (4 capas) | Transversal (#41) | ✅ Completado |
| test_flywheel.py | Fase 5 (#31) | Pendiente |
| Motor legal | Fase 6 (#35-40) | Pendiente |

---

## 5. Benchmark Pipeline v4.1.0 vs Golden Dataset (2026-03-24)

**Expediente:** DIRI2026-INT-0196314 (Ucayali, 44 paginas, 12 comprobantes reales)

### Precision por campo (9 comprobantes detectados de 12)

| Campo | Correcto | Porcentaje |
|-------|----------|------------|
| Serie/Numero | 9/9 | **100%** |
| RUC emisor | 9/9 | **100%** |
| Fecha emision | 8/9 | **89%** |
| Monto total | 2/9 | **22%** (cuello de botella critico) |

### Metricas de deteccion

| Metrica | Valor |
|---------|-------|
| Recall comprobantes | 75% (9/12) |
| Precision comprobantes | 47% (9/19, 10 falsos positivos SUNAT) |
| Tiempo total | 162s (2.7 min) |
| VLM promedio/pag | 13.2s |
| JSON fallos | 0 |

### 3 Problemas criticos identificados

1. **Falsos positivos SUNAT:** 10 paginas de validacion SUNAT detectadas como comprobantes
2. **Paginas dobles:** p21 y p34 tienen 2 comprobantes cada una, pipeline solo detecta 1 (3 comprobantes perdidos)
3. **Monto 22%:** Mayoria de totales salen como 0.00 o "?". p37 alucino 236.00 vs real 25.00

---

## 6. Tests

- **Total:** 1355 passed, 0 failures (2026-03-24)
- 14 test suites cubriendo todos los modulos activos
- Tests de seguridad: bloqueo de campos probatorios en Capa C
- Tests de backward compatibility: CampoExtraido sin nuevos campos
- Tests de calibracion: 84 tests (3 perfiles, benchmark cc003)
- Tests de excel_writer: 59 tests (colores, secciones, detalle campos, edge cases)

---

## 7. Directiva Vigente

- **FUENTE PRINCIPAL:** Nueva Directiva de Viaticos RGS 023-2026-MINEDU
- **DEROGADA (solo contexto):** Directiva de Viaticos 011-2020
- Toda validacion se hace contra la nueva directiva

---

## 8. Decisiones Recientes

- **ADR-012 (2026-03-24):** PaddleOCR-VL-1.5 evaluado — nativo BROKEN en RTX 5090 sm_120, Docker vLLM funciona (5.8x mas rapido, 3x menos VRAM) pero campo extraction inferior a qwen2.5vl:7b. Descartado.
- **Golden Dataset (#30, 2026-03-24):** `data/evaluacion/expected_DIRI2026-INT-0196314.json` — 12 comprobantes ground truth verificados manualmente
- **Pipeline v4.1.0 (2026-03-14):** OCR-first + qwen2.5vl:7b sin fallback + keep_alive=10m + format=json. 2.7 min/expediente (16x speedup vs v1)
- **ADR-009:** qwen2.5vl:7b como modelo primario (qwen3-vl:8b descartado por JSON corrupto)
- **ADR-008:** PaddleOCR PP-OCRv5 GPU restaurado (RTX 5090 via CUDA 12.9 cu129)
- **Benchmark OCR:** PP-OCRv5 GPU 42.0% vs PaddleOCR 2.9.1 CPU 36.2% vs Tesseract 20.3%
- **Blindaje de Seguridad (#41):** 4 capas defense-in-depth, ACTA aprobada 2026-02-25

---

## 9. Scripts que violan Regla 1 (hardcode)

| Script | Violacion |
|--------|-----------|
| `scripts/generar_excel_caja_chica_003.py` | 16 gastos hardcodeados (~28 valores) |
| `scripts/generar_excel_OTIC2026.py` | Comprobantes hardcodeados (~50 valores) |
| `scripts/generar_excel_expediente.py` | Comprobantes hardcodeados (~22 valores) |
| `scripts/generar_excel_DEBEDSAR2026.py` | Comprobantes hardcodeados (~120 valores) — validado por Hans |
| `scripts/generar_excel_otic0072834.py` | Comprobantes hardcodeados (~50 valores) |

**Pendiente:** Refactorizar para consumir JSON del pipeline (post-Regla 4).

---

## 10. Stack de Herramientas (instalado en WSL2)

| Herramienta | Version | Estado | Uso |
|-------------|---------|--------|-----|
| PaddleOCR | 3.4.0 (GPU) | Operativo | Motor OCR primario PP-OCRv5 server |
| PaddlePaddle | 3.3.0 GPU cu129 | Operativo | Backend PaddleOCR (CUDA 12.9, sm_120) |
| Tesseract | 5.x | Operativo | Motor OCR fallback |
| DuckDB | 1.4.4 | Instalado | Base analitica (padron RUC) |
| Qwen2.5-VL-7B | Q4_K_M, 6.0GB | Operativo (Ollama 0.16.2) | Motor VLM primario (sin fallback) |
| Qwen3-VL-8B | Q4_K_M, 6.1GB | Disponible | Descartado como primario (JSON corrupto) |
| PyMuPDF | 1.x | Operativo | Renderizado PDF + extraccion texto digital |

**RTX 5090 GPU:** Operativo con PaddlePaddle cu129. Requiere
`export LD_LIBRARY_PATH=/usr/lib/wsl/lib:$LD_LIBRARY_PATH` en WSL2.

---

## 11. Proximos Pasos

### Problemas criticos a resolver (siguiente sesion)
1. **Falsos positivos SUNAT** — Filtrar paginas de validacion SUNAT (detectadas como comprobantes)
2. **Paginas dobles** — Detectar paginas con 2 comprobantes (p21, p34 en DIRI2026)
3. **Monto 22%** — Mejorar extraccion de montos (mayoria sale 0.00 o "?", p37 alucino 236.00)

### Fase 5 en progreso
- Tarea #30: Golden dataset ✅ (expected.json DIRI2026-INT-0196314)
- Tarea #16: Re-generar Excel con pipeline formal
- Tarea #31: test_flywheel.py

### Pendiente
- apiperu.dev: Validacion CPE automatizada (100 queries gratis/mes, Hans debe registrarse)
- Tech Sentinel (scripts/tech_sentinel.py)
- Frontend MVP con v0.dev (post Fase 5)
- Deadline Premio BPG: 4 mayo 2026

---

**Ultima actualizacion:** 2026-03-24 por Claude Code
