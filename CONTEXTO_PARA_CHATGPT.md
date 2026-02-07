# CONTEXTO DEL PROYECTO AG-EVIDENCE — Estado Actual

**Fecha:** 2026-02-07  
**Propósito:** Documento de contexto para continuar el desarrollo

---

## 1. DESCRIPCIÓN DEL PROYECTO

**AG-EVIDENCE** es un sistema multi-agente de Control Previo para revisión de expedientes administrativos del MINEDU (Perú). El sistema analiza expedientes de gasto público con estándar probatorio estricto.

**Hardware:**
- GPU: RTX 5090 MSI Titan 32GB VRAM
- Modelo LLM local: qwen3:32b via Ollama (localhost:11434)
- OCR: Tesseract 5.4 + OCRmyPDF (español + inglés)

---

## 2. ARQUITECTURA ACTUAL

### 2.1 Stack Técnico

- **Host:** Windows 11 (solo UI, IDE, gestión de archivos)
- **Runtime obligatorio:** WSL2 (Ubuntu 22.04)
- **Framework IA:** PyTorch NIGHTLY (build Linux) — requerido para sm_120 (RTX 5090)
- **Motor inferencia:** vLLM (aprobado, pendiente despliegue)
- **OCR:** Exclusivamente en WSL2

### 2.2 Regla Crítica

> **TODO el procesamiento OCR se ejecuta en WSL2. Windows solo actúa como host/editor.**

---

## 3. ESTADO ACTUAL DEL OCR

### 3.1 Decisiones Técnicas Recientes

✅ **MCPs (Model Context Protocol):**
- Se descartó definitivamente `readpdfx`
- El proyecto usa **UN solo MCP**: `pdf-handler`

✅ **Arquitectura OCR WSL2-Only:**
- El OCR se ejecuta exclusivamente en WSL2 (Ubuntu)
- Windows actúa solo como host/editor y orquestador
- Los chequeos o warnings de OCR en Windows son **irrelevantes** y no forman parte del runtime soportado

### 3.2 Dependencias OCR Instaladas en WSL2

- `ocrmypdf` v17.1.0
- `tesseract-ocr` con idioma `spa`
- `ghostscript`

### 3.3 Módulos OCR Implementados

| Módulo | Ubicación | Estado | Propósito |
|--------|-----------|--------|-----------|
| `src/ocr/core.py` | Core OCR | ✅ Implementado | Funciones base: render, rotación, OCR, métricas |
| `src/ingestion/pdf_text_extractor.py` | Gating | ✅ Implementado | Decisión automática: direct_text vs ocr vs fallback |
| `agentes/agente_02_ocr.py` | Agente OCR | ✅ Implementado | Análisis de calidad y mejora OCR |
| `tools/ocr_smoke_test.py` | Testing | ✅ Implementado | Smoke test aislado para OCR |

### 3.4 Pipeline de Extracción de Texto

El sistema usa `extract_text_with_gating()` que:
1. Intenta extracción directa con PyMuPDF (`direct_text`)
2. Si falla, intenta OCR con Tesseract (`ocr`)
3. Si ambos fallan, marca como `fallback_manual` (requiere revisión humana)

**Umbrales por defecto:**
```python
GatingThresholds(
    direct_text_min_chars=200,
    direct_text_min_words=30,
    ocr_min_confidence=0.60,
    ocr_min_words=20,
    sample_pages=1,
    ocr_dpi=200,
    ocr_lang="spa"
)
```

---

## 4. EXPEDIENTE DE PRUEBA ANALIZADO

### 4.1 Carpeta
`C:\Users\Hans\Proyectos\AG-EVIDENCE\data\expedientes\pruebas\viaticos_2026\DIGC2026-INT-0072851`

### 4.2 PDFs Encontrados (3 archivos)

#### PDF 1: `2026011711336SolicituddeviaticosRony.pdf`
- **Páginas:** 8
- **Tamaño:** 1,832,137 bytes (1.79 MB)
- **Tipo:** 🖼️ **IMAGEN ESCANEADA** (requiere OCR)
- **Observación:** No tiene texto extraíble nativo

#### PDF 2: `2026020616500RendiciondeCuentasRonnyDurand.pdf`
- **Páginas:** 45
- **Tamaño:** 5,733,467 bytes (5.60 MB)
- **Tipo:** ✅ **NATIVO DIGITAL** (texto extraíble)
- **Muestra:** "Sistema Integrado de Gestión Administrativa / Módulo de Tesorería..."

#### PDF 3: `NUEVA DIRECTIVA DE VIÁTICOS_{Res_de_Secretaría_General Nro. 023-2026-MINEDU.pdf`
- **Páginas:** 36
- **Tamaño:** 1,924,576 bytes (1.88 MB)
- **Tipo:** ✅ **NATIVO DIGITAL** (texto extraíble)
- **Muestra:** "Resolución de Aprobación / Resolución de Secretaría General N° 023-2026-MINEDU..."

### 4.3 Estadísticas

- **Total PDFs:** 3
- **PDFs nativos:** 2 (66.7%)
- **PDFs escaneados:** 1 (33.3%) ← **Requiere OCR**
- **Total páginas:** 89
- **Tamaño total:** 9.05 MB

---

## 5. PRÓXIMO PASO TÉCNICO

### 5.1 Tarea Pendiente

**Implementar el adaptador:** `src/tools/ocr_preprocessor.py`

### 5.2 Requisitos del Adaptador

El adaptador debe:

1. **Detectar automáticamente** si un PDF requiere OCR
   - Usar el pipeline de gating existente (`extract_text_with_gating`)
   - Si `decision["metodo"] == "ocr"` → requiere OCR

2. **Procesar solo PDFs escaneados** con OCRmyPDF
   - Ejecutar: `ocrmypdf input.pdf output.pdf --language spa`
   - Solo procesar si el PDF es escaneado (no modificar nativos)

3. **Integrarse con el pipeline existente**
   - Usar `src/ingestion/pdf_text_extractor.py` para detección
   - Mantener compatibilidad con `agentes/agente_02_ocr.py`

4. **Ejecutarse en WSL2**
   - El adaptador debe ejecutar `ocrmypdf` dentro de WSL2
   - No debe intentar ejecutar en Windows

### 5.3 Caso de Uso Real

Del expediente analizado:
- **1 de 3 PDFs requiere OCR** (33% del expediente)
- **Documento objetivo:** `2026011711336SolicituddeviaticosRony.pdf` (8 páginas, 1.79 MB)
- **Mezcla de tipos:** El adaptador debe manejar ambos tipos (nativo y escaneado)

---

## 6. ESTRUCTURA DEL PROYECTO

```
AG-EVIDENCE/
├── src/
│   ├── ocr/
│   │   └── core.py                    # Funciones base OCR
│   ├── ingestion/
│   │   └── pdf_text_extractor.py      # Gating automático
│   └── tools/                         # ← AQUÍ va ocr_preprocessor.py
├── agentes/
│   └── agente_02_ocr.py               # Agente OCR
├── tools/
│   └── ocr_smoke_test.py              # Testing
├── data/
│   └── expedientes/
│       └── pruebas/
│           └── viaticos_2026/
│               └── DIGC2026-INT-0072851/  # Expediente analizado
└── docs/
    ├── CURRENT_STATE.md               # Estado del proyecto
    ├── OCR_SPEC.md                    # Especificación OCR
    └── HARDWARE_CONTEXT.md            # Contexto hardware
```

---

## 7. REGLAS DE GOBIERNAZA

### 7.1 Principio Anti-Alucinación

- **PROHIBIDO** inventar datos que no estén visibles en el documento
- **PROHIBIDO** inferir montos o números parcialmente legibles
- Si hay duda sobre la clasificación, marcar como "CLASIFICACIÓN INCIERTA"
- Toda observación CRÍTICA o MAYOR debe citar: archivo, página y snippet

### 7.2 Regla de Legibilidad Humana

> **PROHIBIDO** devolver un expediente únicamente porque el OCR/IA no pueda extraer texto, si el documento es legible para un ojo humano.

---

## 8. COMANDOS ÚTILES

### 8.1 Verificar OCR en WSL2
```bash
wsl tesseract --version
wsl tesseract --list-langs  # Debe incluir 'spa'
wsl ocrmypdf --version
wsl gs --version
```

### 8.2 Ejecutar Smoke Test OCR
```bash
python tools/ocr_smoke_test.py --pdf "ruta/archivo.pdf" --page 1 --lang spa
```

### 8.3 Usar Pipeline de Gating
```python
from src.ingestion import extract_text_with_gating

resultado = extract_text_with_gating("documento.pdf", lang="spa")
print(resultado["decision"]["metodo"])  # "direct_text" | "ocr" | "fallback_manual"
```

---

## 9. ESTADO DE VALIDACIÓN

✅ **Código coherente** con arquitectura WSL-only  
✅ **Estado estable** y listo para pruebas reales  
✅ **Sin necesidad** de cambios inmediatos en código existente  
✅ **Dependencias OCR** instaladas y operativas en WSL2  
✅ **Pipeline de gating** implementado y funcional  

---

## 10. CONTEXTO PARA EL DESARROLLO

### 10.1 Lo que Funciona

- ✅ Extracción directa de PDFs nativos (PyMuPDF)
- ✅ OCR con Tesseract (vía WSL2)
- ✅ Gating automático (decisión direct_text vs ocr)
- ✅ Fallback manual (cuando ambos fallan)
- ✅ Métricas de calidad (DPI, contraste, rotación)

### 10.2 Lo que Falta

- ⏳ **Adaptador OCRmyPDF** (`src/tools/ocr_preprocessor.py`)
  - Integrar OCRmyPDF al pipeline
  - Procesar PDFs escaneados antes de extracción
  - Mantener PDFs nativos sin modificar

### 10.3 Restricciones Técnicas

- ❌ **NO ejecutar OCR en Windows** (solo WSL2)
- ❌ **NO modificar PDFs nativos** (solo procesar escaneados)
- ❌ **NO inventar texto** si OCR falla (marcar como fallback_manual)
- ✅ **SÍ usar** el pipeline de gating existente para detección
- ✅ **SÍ mantener** compatibilidad con agentes existentes

---

## 11. INFORMACIÓN ADICIONAL

### 11.1 Documentación Relevante

- `docs/OCR_SPEC.md` - Especificación técnica completa del OCR
- `docs/CURRENT_STATE.md` - Estado actual del proyecto
- `docs/HARDWARE_CONTEXT.md` - Contexto de hardware y WSL2
- `VALIDACION_OCR_WSL.md` - Validación técnica de arquitectura OCR

### 11.2 Archivos Clave para Revisar

- `src/ingestion/pdf_text_extractor.py` - Pipeline de gating (línea 251)
- `src/ocr/core.py` - Funciones base OCR (línea 47)
- `agentes/agente_02_ocr.py` - Agente OCR (línea 65)

---

## 12. RESUMEN EJECUTIVO

**Estado actual:**
- Sistema OCR funcional en WSL2
- Pipeline de gating implementado
- 1 de 3 PDFs del expediente de prueba requiere OCR
- Falta adaptador OCRmyPDF para procesar PDFs escaneados

**Próximo paso:**
- Implementar `src/tools/ocr_preprocessor.py`
- Integrar OCRmyPDF al pipeline existente
- Procesar solo PDFs escaneados (no modificar nativos)
- Ejecutar en WSL2 (no Windows)

**Restricciones:**
- OCR exclusivamente en WSL2
- No modificar PDFs nativos
- Mantener compatibilidad con pipeline existente

---

**FIN DEL CONTEXTO**
