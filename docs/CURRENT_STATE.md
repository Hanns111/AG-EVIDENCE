# ESTADO ACTUAL DEL PROYECTO — AG-EVIDENCE

## Fecha de Corte
2026-02-11

---

## 1. Estado General

**v2.0 — Fase 1 en progreso (Trazabilidad + OCR)**

El proyecto completo su reestructuracion de v1.0 (prototipo con 9 agentes monoliticos)
a v2.0 (arquitectura modular por dominios). Todo el codigo legacy fue eliminado.

---

## 2. Lo que existe y funciona

| Modulo | Estado | Descripcion |
|--------|--------|-------------|
| `src/ingestion/custody_chain.py` | Operativo | Cadena de custodia SHA-256 |
| `src/ingestion/trace_logger.py` | Operativo | Logger JSONL con trace_id |
| `src/ingestion/pdf_text_extractor.py` | Operativo | Extraccion texto PDF |
| `src/extraction/abstencion.py` | Operativo | Politica formal de abstencion |
| `src/rules/detraccion_spot.py` | Operativo | Validacion SPOT/detracciones |
| `src/rules/tdr_requirements.py` | Operativo | Requisitos TDR |
| `src/rules/integrador.py` | Operativo | Consolidacion SPOT+TDR |
| `src/tools/ocr_preprocessor.py` | Operativo | OCRmyPDF via WSL2 |
| `src/ocr/core.py` | Pendiente rewrite | Tarea #13 |

---

## 3. Lo que NO existe (y esta planificado)

| Componente | Fase | Estado |
|------------|------|--------|
| Motor OCR PaddleOCR | Fase 1 (#13) | Siguiente tarea |
| Contrato de expediente | Fase 2 (#17) | Pendiente |
| Router multi-agente | Fase 2 (#18) | Pendiente |
| Agentes v2.0 | Fase 2 (#19-21) | Pendiente |
| Qwen fallback LLM | Fase 3 (#22-26) | Pendiente |
| Validaciones cruzadas | Fase 4 (#27-29) | Pendiente |
| Motor legal | Fase 6 (#35-40) | Pendiente |

---

## 4. Tests

- **199/201 passed** (0.67s)
- 2 fallos pre-existentes: PyMuPDF no instalado en Windows (runtime es WSL2)
- 7 test suites cubriendo todos los modulos activos

---

## 5. Riesgos Actuales

- OCR de imagenes escaneadas pendiente (Tarea #13)
- integrador.py usa Protocol para DocumentoPDF (se definira la clase real en Fase 2)

---

## 6. Proximos Pasos

1. Tarea #13: Rewrite src/ocr/core.py (Tesseract a PaddleOCR)
2. Tarea #14-16: Completar Fase 1
3. Fase 2: Contrato + Router + Agentes v2.0

---

**Ultima actualizacion:** 2026-02-11
