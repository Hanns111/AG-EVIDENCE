# ARQUITECTURA MAYO — Motor de Control Previo sobre Directiva de Viaticos

> **Aprobado:** 2026-02-26 por Hans
> **Validado:** 2026-02-26 por Claude Code (analisis tecnico)
> **Ultima actualizacion:** 2026-02-26 23:00 UTC por Claude Code
> **Objetivo:** Demo solida para primera quincena de mayo 2026

---

## 1. Que ES y que NO ES

**ES:** Motor de control previo automatizado que analiza expedientes de viaticos,
detecta observaciones con evidencia verificable, y genera reportes auditables.

**NO ES:** Chatbot normativo general, asistente conversacional, ni sistema de IA
que "opine" sobre documentos.

---

## 2. Flujo del Sistema para Mayo

```
FUNCIONARIO                          SISTEMA AG-EVIDENCE
    |                                       |
    |--- Carga expediente (PDF) ----------->|
    |                                       |
    |                                [1. CUSTODIA]
    |                                 SHA-256 + JSONL
    |                                       |
    |                                [2. OCR MULTICAPA]
    |                                 PaddleOCR → Preproceso → Tesseract → Qwen VL
    |                                 Si ilegible → ABSTENCION
    |                                       |
    |                                [3. PARSEO PROFUNDO]
    |                                 Extraer: RUC, montos, fechas, series
    |                                 Grupos A-K del contrato de datos
    |                                 Si no se puede → campo NULL + hallazgo
    |                                       |
    |                                [4. EVALUACION INTEGRIDAD]
    |                                 ConfidenceRouter + IntegrityCheckpoint
    |                                 OK / WARNING / CRITICAL
    |                                       |
    |                                [5. MOTOR DETERMINISTA VIATICOS]
    |                                 Topes por zona (Python puro)
    |                                 Plazos de rendicion (Python puro)
    |                                 Documentos obligatorios (checklist)
    |                                 Calculos aritmeticos (Python puro)
    |                                       |
    |                                [6. RECUPERACION NORMATIVA]
    |                                 Buscar numeral exacto en Directiva
    |                                 Keyword search (sin embeddings)
    |                                 Si no hay cita → no hay conclusion
    |                                       |
    |                                [7. REPORTE]
    |                                 Excel: DIAGNOSTICO + HALLAZGOS
    |                                 Cada observacion:
    |                                   - Numeral de la Directiva
    |                                   - Pagina del expediente
    |                                   - Texto literal extraido
    |                                   - Calculo verificable
    |                                       |
    |<-- Recibe reporte con evidencia ------|
```

---

## 3. Mapeo a Modulos Existentes

### Ya construido (NO modificar logica interna)

| Paso | Modulo existente | Lineas | Tests | Estado |
|------|-----------------|--------|-------|--------|
| 1. Custodia | `src/ingestion/custody_chain.py` | ~529 | 27 | Produccion |
| 2. OCR (parcial) | `src/ocr/core.py` | ~880 | 75 | Produccion |
| 2. Preproceso | `src/tools/ocr_preprocessor.py` | ~301 | 6 | Produccion |
| 3. Contrato datos | `src/extraction/expediente_contract.py` | ~1161 | 84 | Produccion |
| 4. Router | `src/extraction/confidence_router.py` | ~1424 | 86 | Produccion |
| 4. Abstencion | `src/extraction/abstencion.py` | ~550 | 66 | Produccion |
| 4. Calibracion | `src/extraction/calibracion.py` | ~500 | 84 | Produccion |
| 7. Excel DIAGNOSTICO | `src/extraction/excel_writer.py` | ~850 | 59 | Produccion |
| Orquestador | `src/extraction/escribano_fiel.py` | ~1027 | 44 | Produccion |
| Trazabilidad | `src/ingestion/trace_logger.py` | ~638 | 55 | Produccion |

### A construir (nuevos modulos)

| Paso | Modulo nuevo | Descripcion | Dependencias |
|------|-------------|-------------|--------------|
| 2. OCR multicapa | `src/ocr/ocr_multicapa.py` | Encadenar 4 capas OCR como pipeline formal | core.py, ocr_preprocessor.py |
| 3. Parseo profundo | `src/extraction/parser_comprobantes.py` | Regex + heuristicas para Grupos A-K | expediente_contract.py |
| 5. Reglas viaticos | `src/validation/reglas_viaticos.py` | Topes, plazos, docs obligatorios | settings.py (nueva directiva) |
| 5. Validador | `src/validation/validador_expediente.py` | Sumas aritmeticas y cruzadas | parser_comprobantes.py |
| 6. RAG Directiva | `src/legal/indice_directiva.py` | Diccionario numeral→texto, busqueda keyword | data/normativa/ |
| 7. Hoja HALLAZGOS | `src/validation/reporte_hallazgos.py` | Excel con observaciones + evidencia | excel_writer.py |
| UI demo | `demo/app.py` | Streamlit/Gradio: cargar PDF, ver reporte | escribano_fiel.py |

### A ampliar (modulos existentes)

| Modulo | Cambio requerido |
|--------|-----------------|
| `escribano_fiel.py` | Agregar paso 5 (validacion viaticos) entre evaluacion y Excel |
| `confidence_router.py` | Incluir observaciones de reglas de viaticos en evaluacion |
| `excel_writer.py` | Agregar generacion de hoja HALLAZGOS |
| `config/settings.py` | Agregar constantes de Directiva de Viaticos (topes, plazos) |

---

## 4. OCR Multicapa — Detalle

```
Documento PDF
    |
    v
[Capa 1] PaddleOCR PP-OCRv5 GPU
    |
    |--- confianza >= 0.70 ---> Resultado OK
    |
    |--- confianza < 0.70
    v
[Capa 2] Preprocesamiento (binarizacion + deskew + contraste)
    |
    v
[Capa 1 bis] Re-OCR con imagen preprocesada
    |
    |--- confianza >= 0.70 ---> Resultado OK
    |
    |--- confianza < 0.70
    v
[Capa 3] Tesseract (motor alternativo)
    |
    |--- confianza >= 0.60 ---> Resultado OK
    |
    |--- confianza < 0.60
    v
[Capa 4] Qwen2.5-VL-7B via Ollama (500 DPI)
    |
    |--- confianza >= 0.50 ---> Resultado OK (con marca de incertidumbre)
    |
    |--- confianza < 0.50
    v
[ABSTENCION] → campo NULL + hallazgo INFORMATIVA + "evidencia insuficiente"

[Si ilegible para ojo humano] → DEVOLUCION por ilegibilidad
```

---

## 5. RAG Minimo — Solo Directiva de Viaticos

**Enfoque:** Determinista, sin embeddings, sin modelo.

```python
# Estructura conceptual (no codigo final)
DIRECTIVA_VIATICOS = {
    "6.1.1": "El viatico diario para destinos nacionales...",
    "6.1.2": "Los montos asignados segun escala...",
    "6.2.1": "El plazo para presentar la rendicion...",
    # ... todos los numerales indexados
}

def buscar_numeral(keyword: str) -> List[Tuple[str, str]]:
    """Retorna [(numeral, texto)] donde keyword aparece."""
    return [(num, txt) for num, txt in DIRECTIVA_VIATICOS.items()
            if keyword.lower() in txt.lower()]
```

**Por que asi:**
- Un solo documento (la Directiva) = no justifica infraestructura de embeddings
- Busqueda por keyword es 100% determinista y trazable
- Cada observacion incluira: "Ref: Directiva RGS 023-2026, numeral X.Y.Z"
- Si no se encuentra numeral aplicable → no se genera observacion

---

## 6. Principio Anti-Alucinacion — Flujo de Decision

```
¿Se pudo extraer el dato?
    |
    |--- NO ---> ABSTENCION (campo NULL, hallazgo informativo)
    |
    |--- SI
    v
¿El dato tiene confianza suficiente? (AbstencionPolicy)
    |
    |--- NO ---> ABSTENCION (campo NULL, hallazgo informativo)
    |
    |--- SI
    v
¿El dato viola alguna regla determinista?
    |
    |--- NO ---> OK (sin observacion)
    |
    |--- SI
    v
¿Existe numeral de la Directiva que sustente la observacion?
    |
    |--- NO ---> NO generar observacion (falta base legal)
    |
    |--- SI
    v
GENERAR OBSERVACION con:
  - Numeral exacto
  - Pagina del expediente
  - Texto literal extraido
  - Calculo matematico (si aplica)
  - Motor que extrajo el dato
```

**Regla cardinal:** En CADA bifurcacion, si hay duda, se elige la opcion
mas conservadora (abstencion > observacion sin evidencia > inferencia).

---

## 7. Estructura de Carpetas Post-Mayo

```
src/
  extraction/         ← Modulos existentes (NO tocar logica interna)
    abstencion.py
    calibracion.py
    confidence_router.py
    escribano_fiel.py     ← Ampliar con paso de validacion
    excel_writer.py       ← Ampliar con hoja HALLAZGOS
    expediente_contract.py
    parser_comprobantes.py  ← NUEVO: parseo profundo Grupos A-K
  ingestion/          ← Intacto
    custody_chain.py
    trace_logger.py
    pdf_text_extractor.py
  ocr/                ← Ampliar
    core.py
    ocr_multicapa.py      ← NUEVO: pipeline 4 capas encadenado
  validation/         ← NUEVA carpeta
    __init__.py
    validador_expediente.py  ← NUEVO: sumas aritmeticas
    reglas_viaticos.py       ← NUEVO: topes, plazos, docs
    reporte_hallazgos.py     ← NUEVO: hoja HALLAZGOS Excel
  legal/              ← NUEVA carpeta (version minima)
    __init__.py
    indice_directiva.py      ← NUEVO: diccionario numeral→texto
  tools/              ← Intacto
    ocr_preprocessor.py
  rules/              ← Intacto
    detraccion_spot.py
    tdr_requirements.py
demo/                 ← NUEVA carpeta
  app.py              ← UI demo (Streamlit o Gradio)
```

---

## 8. Riesgos Identificados y Mitigaciones

| Riesgo | Impacto | Mitigacion |
|--------|---------|------------|
| Parseo profundo: RUC 0%, Fecha 31% | ALTO | Heuristica posicional (bbox) + Qwen VL para imagenes |
| Tiempo GPU en demo en vivo (~48s) | MEDIO | Preprocesar expedientes demo + indicador progreso |
| Directiva como PDF no indexado | MEDIO | Indexacion manual por numeral (una vez) |
| Timeline ajustado (8 semanas) | MEDIO | No refactorizar, solo extender |
| Expedientes con calidad variable | ALTO | OCR multicapa + abstencion formal |

---

## 9. Restricciones de Implementacion

1. **NO migrar a LangGraph** — escribano_fiel.py funciona E2E
2. **NO migrar a Pydantic** — dataclasses con validacion son suficientes
3. **NO usar Docker para Mayo** — GPU en WSL2 funciona directamente
4. **NO usar Vercel con datos reales** — local-first obligatorio
5. **NO usar embeddings** — keyword search basta para un documento
6. **NO romper pilares existentes** — AbstencionPolicy, EvidenceEnforcer, IntegrityCheckpoint, CustodyChain, TraceLogger
7. **NO introducir herramientas nuevas** fuera de las aprobadas
8. **NO sobre-ingenieria** — minimo viable para Mayo, escala despues

---

*Documento de referencia arquitectonica. Cambios requieren aprobacion de Hans.*
