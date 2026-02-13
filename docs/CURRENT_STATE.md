# ESTADO ACTUAL DEL PROYECTO — AG-EVIDENCE

## Fecha de Corte
2026-02-13

---

## 1. Estado General

**v2.0 — Fase 1 en progreso (Trazabilidad + OCR)**

El proyecto completo su reestructuracion de v1.0 (prototipo con 9 agentes monoliticos)
a v2.0 (arquitectura modular por dominios). Todo el codigo legacy fue eliminado.

**Ultimo commit:** b598cf5 (feat(governance): add session protocol, backup script, and untrack PDFs)

---

## 2. Lo que existe y funciona

| Modulo | Estado | Descripcion |
|--------|--------|-------------|
| `src/ingestion/custody_chain.py` | Operativo | Cadena de custodia SHA-256 |
| `src/ingestion/trace_logger.py` | Operativo | Logger JSONL con trace_id |
| `src/ingestion/pdf_text_extractor.py` | Operativo | Extraccion texto PDF con gating |
| `src/extraction/abstencion.py` | Operativo | Politica formal de abstencion |
| `src/ocr/core.py` | Operativo | Motor OCR PaddleOCR PP-OCRv5 + Tesseract fallback + bbox/confianza por linea |
| `src/rules/detraccion_spot.py` | Operativo | Validacion SPOT/detracciones |
| `src/rules/tdr_requirements.py` | Operativo | Requisitos TDR |
| `src/rules/integrador.py` | Operativo | Consolidacion SPOT+TDR |
| `src/tools/ocr_preprocessor.py` | Operativo | OCRmyPDF via WSL2 |
| `governance/SESSION_PROTOCOL.md` | Nuevo | Protocolo apertura/cierre sesion |
| `scripts/backup_local.py` | Nuevo | Backup ZIP completo del proyecto |

---

## 3. Lo que NO existe (y esta planificado)

| Componente | Fase | Estado |
|------------|------|--------|
| Benchmark A/B Tesseract vs PaddleOCR | Fase 1 (#15) | Pendiente |
| Re-generar Excel + validacion visual | Fase 1 (#16) | En progreso (3 expedientes procesados) |
| Contrato de expediente | Fase 2 (#17) | Pendiente |
| Router multi-agente + Integrity Checkpoint | Fase 2 (#18) | Pendiente |
| Agentes v2.0 | Fase 2 (#19-21) | Pendiente |
| Qwen fallback LLM | Fase 3 (#22-26) | Pendiente |
| Validaciones cruzadas | Fase 4 (#27-29) | Pendiente |
| Motor legal | Fase 6 (#35-40) | Pendiente |

---

## 4. Tests

- **274 passed, 18 skipped** (0.73s)
- 16 skips: PIL no disponible en Windows (tests OCR que requieren imagen real, runtime WSL2)
- 2 skips pre-existentes: PyMuPDF no instalado en Windows
- 8 test suites cubriendo todos los modulos activos

---

## 5. Directiva Vigente

- **FUENTE PRINCIPAL:** Nueva Directiva de Viaticos RGS 023-2026-MINEDU
- **DEROGADA (solo contexto):** Directiva de Viaticos 011-2020
- Toda validacion se hace contra la nueva directiva

---

## 6. Decisiones Recientes

- PDFs de directivas removidos del tracking git (~35 MB liberados)
- Inventario de directivas en data/directivas/INVENTARIO_DIRECTIVAS.md
- Commit incremental obligatorio (ver governance/SESSION_PROTOCOL.md)
- Backup local via scripts/backup_local.py

---

## 7. Proximos Pasos

1. Tarea #15: Benchmark A/B Tesseract vs PaddleOCR
2. Tarea #16: Cerrar validacion visual de expedientes
3. Fase 2: Contrato + Router + Agentes v2.0

---

**Ultima actualizacion:** 2026-02-13 por Claude Code
