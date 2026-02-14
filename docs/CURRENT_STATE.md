# ESTADO ACTUAL DEL PROYECTO — AG-EVIDENCE

## Fecha de Corte
2026-02-14

---

## 1. Estado General

**v2.0 — Fase 1 en progreso (Trazabilidad + OCR) + Gobernanza Transversal**

El proyecto completo su reestructuracion de v1.0 (prototipo con 9 agentes monoliticos)
a v2.0 (arquitectura modular por dominios). Todo el codigo legacy fue eliminado.
Se implemento el patron de 3 capas (Extraccion/Validacion/Analisis) como diseno
estructural transversal.

**Ultimo commit:** 9cdf65c (chore: structural governance baseline + enforced image validation pipeline)

---

## 2. Lo que existe y funciona

| Modulo | Estado | Descripcion |
|--------|--------|-------------|
| `src/ingestion/custody_chain.py` | Operativo | Cadena de custodia SHA-256 |
| `src/ingestion/trace_logger.py` | Operativo | Logger JSONL con trace_id |
| `src/ingestion/pdf_text_extractor.py` | Operativo | Extraccion texto PDF con gating + validacion post-rotacion (Regla 2) |
| `src/extraction/abstencion.py` | Operativo | Politica formal de abstencion + EvidenceStatus + clasificar_status() |
| `src/extraction/local_analyst.py` | Nuevo | Capa C: IA local confinada con bloqueo de campos probatorios |
| `src/ocr/core.py` | Operativo | Motor OCR PaddleOCR PP-OCRv5 + Tesseract fallback + bbox/confianza + Regla 2 |
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
| Benchmark A/B Tesseract vs PaddleOCR | Fase 1 (#15) | Pendiente |
| Re-generar Excel + validacion visual | Fase 1 (#16) | En progreso (3 expedientes procesados) |
| Reprocesar Caja Chica N.3 con pipeline formal | Pre-Fase 2 | Pendiente (proxima sesion) |
| Contrato de expediente (JSON tipado) | Fase 2 (#17) | Pendiente |
| Router multi-agente + Integrity Checkpoint | Fase 2 (#18) | Pendiente |
| Agentes v2.0 | Fase 2 (#19-21) | Pendiente |
| Qwen fallback LLM (motor para Capa C) | Fase 3 (#22-26) | Pendiente |
| Validaciones cruzadas | Fase 4 (#27-29) | Pendiente |
| Motor legal | Fase 6 (#35-40) | Pendiente |

---

## 5. Tests

- **Total esperado:** ~400+ tests (se actualiza post-pytest)
- 11 test suites cubriendo todos los modulos activos
- Tests de seguridad: bloqueo de campos probatorios en Capa C
- Tests de backward compatibility: CampoExtraido sin nuevos campos

---

## 6. Directiva Vigente

- **FUENTE PRINCIPAL:** Nueva Directiva de Viaticos RGS 023-2026-MINEDU
- **DEROGADA (solo contexto):** Directiva de Viaticos 011-2020
- Toda validacion se hace contra la nueva directiva

---

## 7. Decisiones Recientes

- Patron de 3 capas formalizado (Regla 8 en Gobernanza Transversal)
- LOCAL_ANALYST_ENABLED=False por defecto (Capa C no conectada a motor)
- Bloqueo de campos probatorios en salida de IA: NO_AUTORIZADO
- PDFs de directivas removidos del tracking git (~35 MB liberados)
- Inventario de directivas en data/directivas/INVENTARIO_DIRECTIVAS.md
- Commit incremental obligatorio (ver governance/SESSION_PROTOCOL.md)
- Backup local via scripts/backup_local.py

---

## 8. Scripts que violan Regla 1 (hardcode)

| Script | Violacion |
|--------|-----------|
| `scripts/generar_excel_caja_chica_003.py` | 16 gastos hardcodeados (~28 valores) |
| `scripts/generar_excel_OTIC2026.py` | Comprobantes hardcodeados (~50 valores) |
| `scripts/generar_excel_expediente.py` | Comprobantes hardcodeados (~22 valores) |
| `scripts/generar_excel_otic0072834.py` | Comprobantes hardcodeados (~50 valores) |

**Pendiente:** Refactorizar para consumir JSON del pipeline (post-Regla 4).

---

## 9. Proximos Pasos

1. Reprocesar Caja Chica N.3 con pipeline formal exclusivamente
2. Tarea #15: Benchmark A/B Tesseract vs PaddleOCR
3. Tarea #16: Cerrar validacion visual de expedientes
4. Fase 2: Contrato JSON tipado + Router + Agentes v2.0

---

**Ultima actualizacion:** 2026-02-14 por Claude Code
