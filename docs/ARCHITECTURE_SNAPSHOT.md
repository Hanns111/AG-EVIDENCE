# ARCHITECTURE_SNAPSHOT.md
## AG-EVIDENCE v3.2 — Estado Real del Sistema

**Fecha de snapshot:** 2026-02-18
**Version:** 3.2.0

---

## 1. Objetivo del Sistema

Sistema modular para revision automatizada de expedientes administrativos del sector publico peruano (MINEDU). Analiza documentos PDF de expedientes de pago y genera hallazgos con estandar probatorio (archivo + pagina + snippet). Implementa politica anti-alucinacion estricta y abstencion formal ante datos inciertos.

---

## 2. Arquitectura v3.2

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
    +----+----+
    |         |
    v         v
+--------+ +------------------+
| ocr/   | | VLM (Ollama)     |  Estrategia mixta:
| core.py| | qwen2.5vl:7b     |  - PyMuPDF texto digital → regex Python
+--------+ +------------------+  - Imagenes → Qwen2.5-VL via Ollama
    |         |                  - PaddleOCR PP-OCRv5 GPU = fallback OCR
    +----+----+
         |
         v
+-------------------+
| Grupo J           |  Validacion aritmetica Python (ZERO INFERENCE)
| (Python valida)   |  J1: Σitems=subtotal, J2: IGV, J3: total, J4: noches
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
| Motor OCR | `src/ocr/core.py` | PaddleOCR PP-OCRv5 GPU + Tesseract fallback | Operativo (ADR-008) |
| Motor VLM | `scripts/extraer_con_qwen_vl.py` | Qwen2.5-VL-7B via Ollama, 11 grupos A-K | Operativo (ADR-009) |
| Preprocesador OCR | `src/tools/ocr_preprocessor.py` | OCRmyPDF via WSL2 | Operativo |
| Validador SPOT | `src/rules/detraccion_spot.py` | Detracciones, Anexo 3, constancias deposito | Operativo |
| Requisitos TDR | `src/rules/tdr_requirements.py` | Extraccion CV, experiencia, titulos | Operativo |
| Integrador | `src/rules/integrador.py` | Consolidacion SPOT+TDR | Operativo |
| Configuracion | `config/settings.py` | Enums, dataclasses, limites normativos | Operativo |

---

## 4. Stack de Extraccion (Estrategia Mixta — ADR-009)

| Motor | Caso de uso | Precision |
|-------|-------------|-----------|
| PyMuPDF (fitz) | PDFs electronicos con texto embebido | ~100% texto perfecto |
| Qwen2.5-VL-7B | Paginas imagen (comprobantes escaneados) | >90% campos |
| PaddleOCR PP-OCRv5 GPU | Fallback OCR para paginas no-comprobante | 42% total |
| Tesseract | Fallback ultimo recurso | 20.3% total |

**Regla de Oro:** "La IA extrae LITERALMENTE lo que ve. Python valida aritmeticamente."

---

## 5. Lo que NO existe todavia

- Agentes v2.0 (src/agents/ es placeholder, Fase 2)
- Orquestador multi-agente LangGraph (Fase 2)
- Contrato JSON tipado (Fase 2)
- Router de confianza (Fase 2)
- Consulta SUNAT automatizada (Fase futura)
- UI web (Fase futura)

---

## 6. Tests

| Suite | Archivo | Tests |
|-------|---------|-------|
| Abstencion | `tests/test_abstencion.py` | 66 |
| Cadena custodia | `tests/test_custody_chain.py` | 21 |
| SPOT | `tests/test_detraccion_spot.py` | 14 |
| OCR core | `tests/test_ocr_core.py` | 44 |
| OCR preprocessor | `tests/test_ocr_preprocessor.py` | 6 |
| PDF extractor | `tests/test_pdf_text_extractor.py` | 7 |
| TDR | `tests/test_tdr_requirements.py` | 22 |
| Trace logger | `tests/test_trace_logger.py` | 55 |

**Total:** 274 tests (0 failures en WSL2)

---

## 7. Hardware y Entorno

| Componente | Valor |
|------------|-------|
| GPU | RTX 5090 Laptop 24GB VRAM (Blackwell sm_120) |
| LLM texto | Ollama + qwen3:32b |
| VLM vision | Ollama 0.16.2 + qwen2.5vl:7b (Q4_K_M, 6GB, ADR-009) |
| OCR primario | PaddleOCR 3.4.0 PP-OCRv5 server GPU (ADR-008) |
| OCR fallback | Tesseract 5.x (WSL2) |
| Texto PDF | PyMuPDF (fitz) |
| Entorno | WSL2 Ubuntu 22.04, CUDA 12.9, PaddlePaddle 3.3.0 cu129 |

---

**Ultima actualizacion:** 2026-02-18
