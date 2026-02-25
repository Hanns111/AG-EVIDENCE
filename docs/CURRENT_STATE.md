# ESTADO ACTUAL DEL PROYECTO — AG-EVIDENCE

## Fecha de Corte
2026-02-25

---

## 1. Estado General

**v2.0 — Fase 2 en progreso (Contrato + Router) + Gobernanza Transversal**

El proyecto completo su reestructuracion de v1.0 (prototipo con 9 agentes monoliticos)
a v2.0 (arquitectura modular por dominios). Todo el codigo legacy fue eliminado.
Se implemento el patron de 3 capas (Extraccion/Validacion/Analisis) como diseno
estructural transversal.

**OCR Engine:** PaddleOCR 3.4.0 PP-OCRv5 server (GPU RTX 5090 via CUDA 12.9)
**VLM Engine:** Ollama 0.16.2 + qwen2.5vl:7b (Q4_K_M, 6GB) — ADR-009
**Expedientes procesados:** ODI2026-INT-0139051, DEBEDSAR2026-INT-0146130 (2 completados)

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
| Contrato de expediente (JSON tipado) | Fase 2 (#17) | ✅ Completado (1161 líneas, 84 tests) |
| Router multi-agente + Integrity Checkpoint | Fase 2 (#18) | ✅ Completado (1424 líneas, 86 tests) |
| Calibrar umbrales con distribucion real | Fase 2 (#19) | ✅ Completado (500 lineas, 84 tests, 3 perfiles) |
| Hoja DIAGNOSTICO en Excel | Fase 2 (#20) | ✅ Completado (850 lineas, 59 tests) |
| Blindaje de Seguridad (4 capas) | Transversal (#41) | ✅ Completado (8 archivos, ACTA aprobada 2026-02-25) |
| Integrar router en escribano_fiel.py | Fase 2 (#21) | ⬜ Pendiente — **SIGUIENTE** |
| Qwen fallback LLM (motor para Capa C) | Fase 3 (#22-26) | Pendiente |
| Validaciones cruzadas | Fase 4 (#27-29) | Pendiente |
| Motor legal | Fase 6 (#35-40) | Pendiente |

---

## 5. Tests

- **Total:** 835 passed, 8 skipped, 0 failures (2026-02-23)
- 13 test suites cubriendo todos los modulos activos
- Tests de seguridad: bloqueo de campos probatorios en Capa C
- Tests de backward compatibility: CampoExtraido sin nuevos campos
- Tests de calibracion: 84 tests (3 perfiles, benchmark cc003)
- Tests de excel_writer: 59 tests (colores, secciones, detalle campos, edge cases)

---

## 6. Directiva Vigente

- **FUENTE PRINCIPAL:** Nueva Directiva de Viaticos RGS 023-2026-MINEDU
- **DEROGADA (solo contexto):** Directiva de Viaticos 011-2020
- Toda validacion se hace contra la nueva directiva

---

## 7. Decisiones Recientes

- **ADR-009:** Qwen2.5-VL-7B via Ollama como motor VLM (estrategia mixta PyMuPDF + Qwen-VL)
- **ADR-008:** PaddleOCR PP-OCRv5 GPU restaurado (RTX 5090 via CUDA 12.9 cu129)
- **Benchmark OCR:** PP-OCRv5 GPU 42.0% vs PaddleOCR 2.9.1 CPU 36.2% vs Tesseract 20.3%
- **Expediente DEBEDSAR2026 procesado:** 17 comprobantes, 500 DPI, estrategia mixta
- **Regla de Literalidad Forense:** IA extrae literalmente, Python valida aritmeticamente
- **NULL vs Blank:** NULL = motor no leyo campo existente; Blank = campo no aplicable
- **DuckDB 1.4.4** instalado como base analitica (padron RUC futuro)
- Patron de 3 capas formalizado (Regla 8 en Gobernanza Transversal)
- PDFs de directivas removidos del tracking git (~35 MB liberados)
- Commit incremental obligatorio (ver governance/SESSION_PROTOCOL.md)
- **Blindaje de Seguridad (#41):** 4 capas defense-in-depth implementadas, ACTA aprobada 2026-02-25

---

## 8. Scripts que violan Regla 1 (hardcode)

| Script | Violacion |
|--------|-----------|
| `scripts/generar_excel_caja_chica_003.py` | 16 gastos hardcodeados (~28 valores) |
| `scripts/generar_excel_OTIC2026.py` | Comprobantes hardcodeados (~50 valores) |
| `scripts/generar_excel_expediente.py` | Comprobantes hardcodeados (~22 valores) |
| `scripts/generar_excel_DEBEDSAR2026.py` | Comprobantes hardcodeados (~120 valores) — validado por Hans |
| `scripts/generar_excel_otic0072834.py` | Comprobantes hardcodeados (~50 valores) |

**Pendiente:** Refactorizar para consumir JSON del pipeline (post-Regla 4).

---

## 9. Stack de Herramientas (instalado en WSL2)

| Herramienta | Version | Estado | Uso |
|-------------|---------|--------|-----|
| PaddleOCR | 3.4.0 (GPU) | Operativo | Motor OCR primario PP-OCRv5 server |
| PaddlePaddle | 3.3.0 GPU cu129 | Operativo | Backend PaddleOCR (CUDA 12.9, sm_120) |
| Tesseract | 5.x | Operativo | Motor OCR fallback |
| DuckDB | 1.4.4 | Instalado | Base analitica (padron RUC) |
| Qwen2.5-VL-7B | Q4_K_M, 6GB | Operativo (Ollama 0.16.2) | Motor VLM primario (ADR-009) |
| PyMuPDF | 1.x | Operativo | Renderizado PDF + extraccion texto digital |

**RTX 5090 GPU:** Operativo con PaddlePaddle cu129. Requiere
`export LD_LIBRARY_PATH=/usr/lib/wsl/lib:$LD_LIBRARY_PATH` en WSL2.

---

## 10. Proximos Pasos

1. **Tarea #21** — Integrar router en `src/extraction/escribano_fiel.py` (pipeline formal completo, ultima de Fase 2)
2. **Tarea #16** — Re-generar Excel con pipeline formal (4 expedientes, solo tras #21)
4. Investigar herramienta de lectura fina para errores VLM (crop+zoom, modelo mayor)
5. Reprocesar Caja Chica N.3 con pipeline formal exclusivamente

---

**Ultima actualizacion:** 2026-02-25 por Claude Code
