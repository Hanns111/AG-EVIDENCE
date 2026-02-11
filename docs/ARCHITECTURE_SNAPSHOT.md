# ARCHITECTURE_SNAPSHOT.md
## AG-EVIDENCE v2.0 — Estado Real del Sistema

**Fecha de snapshot:** 2026-02-11
**Version:** 2.2.0

---

## 1. Objetivo del Sistema

Sistema modular para revision automatizada de expedientes administrativos del sector publico peruano (MINEDU). Analiza documentos PDF de expedientes de pago y genera hallazgos con estandar probatorio (archivo + pagina + snippet). Implementa politica anti-alucinacion estricta y abstencion formal ante datos inciertos.

---

## 2. Arquitectura v2.0

```
PDFs Expediente
      |
      v
+-------------------+
| ingestion/        |  custody_chain (SHA-256) + trace_logger (JSONL)
| pdf_text_extractor|  Extraccion texto + gating de calidad
+--------+----------+
         |
         v
+-------------------+
| extraction/       |  abstencion.py: CampoExtraido + AbstencionPolicy
|                   |  Umbral por tipo de campo, hallazgo automatico
+--------+----------+
         |
         v
+-------------------+
| ocr/              |  core.py: Motor OCR (Fase 1.3 pendiente: PaddleOCR)
| tools/            |  ocr_preprocessor.py: Preprocesamiento WSL2
+--------+----------+
         |
         v
+-------------------+
| rules/            |  detraccion_spot.py: Validacion SPOT
|                   |  tdr_requirements.py: Requisitos TDR
|                   |  integrador.py: Consolidacion SPOT+TDR
+-------------------+
```

---

## 3. Modulos Implementados

| Modulo | Archivo | Proposito | Estado |
|--------|---------|-----------|--------|
| Cadena de custodia | `src/ingestion/custody_chain.py` | SHA-256, vault copy, verificacion integridad | Operativo |
| Logger estructurado | `src/ingestion/trace_logger.py` | JSONL con trace_id UUID, rotacion diaria | Operativo |
| Extractor PDF | `src/ingestion/pdf_text_extractor.py` | Texto directo PyMuPDF + fallback OCR | Operativo |
| Gating config | `src/ingestion/config.py` | Umbrales de calidad OCR | Operativo |
| Abstencion | `src/extraction/abstencion.py` | Politica formal: campo incierto = None + hallazgo | Operativo |
| Motor OCR | `src/ocr/core.py` | Procesamiento OCR basico | Pendiente rewrite |
| Preprocesador OCR | `src/tools/ocr_preprocessor.py` | OCRmyPDF via WSL2 | Operativo |
| Validador SPOT | `src/rules/detraccion_spot.py` | Detracciones, Anexo 3, constancias deposito | Operativo |
| Requisitos TDR | `src/rules/tdr_requirements.py` | Extraccion CV, experiencia, titulos | Operativo |
| Integrador | `src/rules/integrador.py` | Consolidacion SPOT+TDR | Operativo |
| Configuracion | `config/settings.py` | Enums, dataclasses, limites normativos | Operativo |

---

## 4. Lo que NO existe todavia

- Agentes v2.0 (src/agents/ es placeholder, Fase 2)
- Orquestador multi-agente (Fase 2)
- Chat conversacional (Fase futura)
- UI web (Fase futura)
- Consulta SUNAT automatizada (Fase futura)
- CLI de ejecucion batch (Fase futura)

---

## 5. Tests

| Suite | Archivo | Tests |
|-------|---------|-------|
| Abstencion | `tests/test_abstencion.py` | 66 |
| Cadena custodia | `tests/test_custody_chain.py` | 21 |
| SPOT | `tests/test_detraccion_spot.py` | 14 |
| OCR preprocessor | `tests/test_ocr_preprocessor.py` | 6 |
| PDF extractor | `tests/test_pdf_text_extractor.py` | 7 |
| TDR | `tests/test_tdr_requirements.py` | 22 |
| Trace logger | `tests/test_trace_logger.py` | 55 |

**Total:** 199/201 passed (2 fallos = PyMuPDF no instalado en Windows, se ejecuta en WSL2)

---

## 6. Hardware y Entorno

| Componente | Valor |
|------------|-------|
| GPU | RTX 5090 32GB VRAM |
| LLM | Ollama + qwen3:32b (texto) + qwen3-vl:32b (vision) |
| Entorno | WSL2 Ubuntu 22.04 |
| OCR | ocrmypdf + tesseract-ocr (WSL2 only) |

---

**Ultima actualizacion:** 2026-02-11
