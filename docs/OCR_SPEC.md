# OCR_SPEC.md
## Especificación Técnica de OCR — Fases 1 y 2

**Versión:** 2.1.0  
**Estado:** Fase 2 CERRADA — Gating PDF nativo vs OCR implementado  
**Fecha de Cierre:** 2026-01-07  
**Commits Clave:** `3be5172`, `300df6f`, `c490972`  
**Prioridad:** 🔴 CRÍTICA

---

## 1. OBJETIVO

Transformar el Agente AG02 (actualmente "evaluador de calidad") en un módulo de **OCR real** capaz de extraer texto de documentos escaneados, manteniendo las reglas de gobernanza del sistema.

---

## 2. DEFINICIONES OPERATIVAS

### 2.1 Categorías de Documento

| Categoría | Código | Definición Operativa | Acción del Sistema |
|-----------|--------|----------------------|-------------------|
| **Nativo Digital** | `NATIVO_DIGITAL` | PDF generado digitalmente. Texto seleccionable. PyMuPDF extrae texto directamente con ratio de caracteres válidos > 95%. | Extracción directa con `fitz.get_text()` |
| **Escaneado Legible** | `ESCANEADO_LEGIBLE` | Imagen escaneada con resolución ≥ 150 DPI, contraste suficiente, sin rotación significativa. Un humano puede leerlo sin dificultad. | Aplicar OCR. Si falla → Marcar para revisión manual, NO bloquear. |
| **Escaneado Deficiente** | `ESCANEADO_DEFICIENTE` | Imagen con resolución < 100 DPI, contraste < 30%, rotación > 15°, manchas en > 40% del área, o texto cortado. Ilegible incluso para humanos. | Observación INFORMATIVA. NO bloquear expediente. |

### 2.2 Criterios de Clasificación

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        ÁRBOL DE DECISIÓN DE LEGIBILIDAD                      │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ¿PyMuPDF extrae texto con ratio válido > 80%?                              │
│       │                                                                      │
│       ├── SÍ ────► NATIVO_DIGITAL                                           │
│       │                                                                      │
│       └── NO ────► ¿Es imagen embebida?                                     │
│                        │                                                     │
│                        ├── NO ────► NATIVO_DIGITAL (texto oculto/protegido) │
│                        │                                                     │
│                        └── SÍ ────► Evaluar métricas de imagen              │
│                                         │                                    │
│                                         ├── DPI ≥ 150 AND                   │
│                                         │   Contraste ≥ 40% AND             │
│                                         │   Rotación < 10° AND              │
│                                         │   Área legible > 70%              │
│                                         │       │                            │
│                                         │       └── SÍ ► ESCANEADO_LEGIBLE  │
│                                         │                                    │
│                                         └── NO ────► ESCANEADO_DEFICIENTE   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. MÉTRICAS Y UMBRALES

### 3.1 Métricas de Calidad de Imagen

| Métrica | Descripción | Umbral Mínimo (Legible) | Método de Cálculo |
|---------|-------------|-------------------------|-------------------|
| **DPI** | Resolución de escaneo | ≥ 150 DPI | `width_px / width_inch` del render |
| **Contraste** | Diferencia entre texto y fondo | ≥ 40% | `(max_gray - min_gray) / 255 * 100` |
| **Rotación** | Ángulo de desviación | < 10° | Detección de líneas con Hough Transform |
| **Blur Score** | Nitidez de la imagen | < 100 (Laplacian variance) | `cv2.Laplacian().var()` |
| **Área Legible** | Porcentaje sin manchas/sombras | ≥ 70% | Análisis de histograma |

### 3.2 Métricas de Calidad de OCR

| Métrica | Descripción | Umbral Aceptable | Acción si No Cumple |
|---------|-------------|------------------|---------------------|
| **Confianza OCR** | Score promedio de Tesseract | ≥ 60% | Marcar como `LOW_CONFIDENCE` |
| **Ratio Caracteres Válidos** | `len(valid_chars) / len(all_chars)` | ≥ 70% | Reintentar con preprocesamiento |
| **Palabras Reconocidas** | % de palabras en diccionario ES | ≥ 50% | Advertencia, no bloquea |

### 3.3 Umbrales Propuestos (Ajustables)

```python
OCR_THRESHOLDS = {
    "min_dpi": 150,
    "min_contrast": 0.40,
    "max_rotation_degrees": 10,
    "max_blur_variance": 100,
    "min_legible_area": 0.70,
    "min_ocr_confidence": 0.60,
    "min_valid_char_ratio": 0.70,
    "min_dictionary_match": 0.50,
}
```

---

## 4. REGLA OBLIGATORIA: LEGIBILIDAD HUMANA

### 4.1 Regla Cardinal

> **PROHIBIDO** devolver un expediente únicamente porque el OCR/IA no pueda extraer texto, si el documento es legible para un ojo humano.

### 4.2 Protocolo de Aplicación

```
SI (OCR_falla AND documento_clasificado_como_ESCANEADO_LEGIBLE):
    → NO generar observación CRÍTICA
    → Marcar página: "requiere_revision_manual = True"
    → Mensaje: "Página [N] legible visualmente. Extracción automática fallida. Requiere lectura manual."
    → Continuar con el análisis del expediente

SI (documento_clasificado_como_ESCANEADO_DEFICIENTE):
    → Observación INFORMATIVA (no CRÍTICA)
    → Mensaje: "Página [N] presenta calidad deficiente de escaneo. Se recomienda re-escanear."
    → NO bloquear el expediente
```

### 4.3 Justificación Normativa

Referencia: `docs/AGENT_GOVERNANCE_RULES.md`, Artículos 9-10.

---

## 5. CONTRATO DE SALIDA POR PÁGINA

### 5.1 Estructura de Datos

```python
@dataclass
class ResultadoOCRPagina:
    """Resultado de OCR para una página individual"""
    
    # Identificación
    archivo: str                          # Nombre del PDF
    pagina: int                           # Número de página (1-indexed)
    
    # Clasificación
    categoria: str                        # NATIVO_DIGITAL | ESCANEADO_LEGIBLE | ESCANEADO_DEFICIENTE
    
    # Texto extraído
    texto: str                            # Texto completo extraído
    snippet: str                          # Primeros 200 caracteres (para evidencia)
    
    # Métricas de calidad
    dpi_estimado: int                     # DPI calculado
    contraste: float                      # 0.0 a 1.0
    rotacion_grados: float                # Grados de rotación detectada
    blur_score: float                     # Varianza del Laplacian
    confianza_ocr: float                  # 0.0 a 1.0 (promedio Tesseract)
    
    # Metadatos de extracción
    metodo_extraccion: str                # PDF_TEXT | OCR_TESSERACT | OCR_EASYOCR | MANUAL
    tiempo_extraccion_ms: int             # Tiempo de procesamiento
    
    # Flags
    requiere_revision_manual: bool        # True si OCR falló pero es legible
    tiene_imagenes: bool                  # True si la página contiene imágenes
    es_formulario: bool                   # True si detecta campos de formulario
    
    # Coordenadas (futuro)
    # bboxes: List[BoundingBox]           # Coordenadas de texto detectado
```

### 5.2 Ejemplo de Salida JSON

```json
{
  "archivo": "conformidad_2025.pdf",
  "pagina": 3,
  "categoria": "ESCANEADO_LEGIBLE",
  "texto": "CONFORMIDAD DE SERVICIO N° 00723-2025-MINEDU...",
  "snippet": "CONFORMIDAD DE SERVICIO N° 00723-2025-MINEDU-SPE-OTIC-USAU. El suscrito, en calidad de...",
  "dpi_estimado": 200,
  "contraste": 0.72,
  "rotacion_grados": 0.5,
  "blur_score": 45.2,
  "confianza_ocr": 0.85,
  "metodo_extraccion": "OCR_TESSERACT",
  "tiempo_extraccion_ms": 1250,
  "requiere_revision_manual": false,
  "tiene_imagenes": true,
  "es_formulario": false
}
```

---

## 6. CASOS DE PRUEBA

### 6.1 Casos de Aceptación

| ID | Caso | Entrada | Salida Esperada | Criterio de Éxito |
|----|------|---------|-----------------|-------------------|
| TC-01 | PDF nativo digital | PDF generado desde Word | `categoria = NATIVO_DIGITAL`, texto completo | Extracción sin OCR |
| TC-02 | Escaneo 300 DPI claro | Imagen escaneada a 300 DPI | `categoria = ESCANEADO_LEGIBLE`, OCR exitoso | `confianza_ocr ≥ 0.80` |
| TC-03 | Escaneo 150 DPI aceptable | Imagen escaneada a 150 DPI | `categoria = ESCANEADO_LEGIBLE` | OCR funciona |
| TC-04 | Escaneo 72 DPI borroso | Imagen baja resolución | `categoria = ESCANEADO_DEFICIENTE` | Observación INFORMATIVA |
| TC-05 | Documento rotado 5° | Escaneo ligeramente rotado | Auto-corregir rotación, OCR exitoso | Rotación corregida |
| TC-06 | Documento rotado 45° | Escaneo muy rotado | `categoria = ESCANEADO_DEFICIENTE` | Requiere re-escaneo |
| TC-07 | OCR falla pero legible | Fuente inusual pero legible | `requiere_revision_manual = True` | NO bloquea expediente |
| TC-08 | Página en blanco | Página sin contenido | Detectar y reportar | `texto = ""` válido |
| TC-09 | Formulario con campos | PDF con form fields | Detectar campos | `es_formulario = True` |
| TC-10 | Documento protegido | PDF con restricciones | Reportar limitación | Mensaje informativo |

### 6.2 Criterios de Aceptación Globales

- [ ] OCR extrae texto de ≥ 90% de documentos escaneados legibles
- [ ] Tiempo de procesamiento ≤ 3 segundos por página promedio
- [ ] Cero falsos positivos de "documento ilegible" en documentos legibles a ojo humano
- [ ] Integración transparente con el flujo existente de AG02

---

## 7. PLAN DE IMPLEMENTACIÓN

### 7.1 Stack Técnico Propuesto

| Componente | Librería | Propósito | Instalación |
|------------|----------|-----------|-------------|
| **OCR Principal** | Tesseract OCR | Reconocimiento de texto | `pip install pytesseract` + binario Tesseract |
| **OCR Alternativo** | EasyOCR | Fallback para fuentes complejas | `pip install easyocr` |
| **Preprocesamiento** | OpenCV | Corrección de rotación, contraste | `pip install opencv-python` |
| **Render PDF→Imagen** | PyMuPDF (fitz) | Ya instalado | Uso de `page.get_pixmap()` |
| **PDF con OCR embebido** | ocrmypdf | Crear PDF searchable | `pip install ocrmypdf` (opcional) |

### 7.2 Flujo de Procesamiento

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FLUJO DE OCR PROPUESTO                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PDF Input                                                                  │
│      │                                                                      │
│      ▼                                                                      │
│  ┌─────────────────┐                                                        │
│  │ 1. Intentar     │──► Texto extraído ────► NATIVO_DIGITAL ──► Fin       │
│  │    fitz.get_text│                                                        │
│  └────────┬────────┘                                                        │
│           │ (texto vacío o basura)                                          │
│           ▼                                                                 │
│  ┌─────────────────┐                                                        │
│  │ 2. Render a     │──► Imagen PNG/JPEG                                    │
│  │    imagen (DPI) │                                                        │
│  └────────┬────────┘                                                        │
│           │                                                                 │
│           ▼                                                                 │
│  ┌─────────────────┐                                                        │
│  │ 3. Evaluar      │──► DPI, contraste, rotación, blur                     │
│  │    calidad      │                                                        │
│  └────────┬────────┘                                                        │
│           │                                                                 │
│           ├── (calidad < umbral) ────► ESCANEADO_DEFICIENTE ──► Obs. INFO  │
│           │                                                                 │
│           ▼                                                                 │
│  ┌─────────────────┐                                                        │
│  │ 4. Preprocesar  │──► Corregir rotación, mejorar contraste               │
│  │    imagen       │                                                        │
│  └────────┬────────┘                                                        │
│           │                                                                 │
│           ▼                                                                 │
│  ┌─────────────────┐                                                        │
│  │ 5. Tesseract    │──► Texto + confianza                                  │
│  │    OCR          │                                                        │
│  └────────┬────────┘                                                        │
│           │                                                                 │
│           ├── (confianza ≥ umbral) ────► ESCANEADO_LEGIBLE ──► Texto OK    │
│           │                                                                 │
│           ▼                                                                 │
│  ┌─────────────────┐                                                        │
│  │ 6. EasyOCR      │──► Fallback para fuentes difíciles                    │
│  │    (fallback)   │                                                        │
│  └────────┬────────┘                                                        │
│           │                                                                 │
│           ├── (confianza ≥ umbral) ────► ESCANEADO_LEGIBLE ──► Texto OK    │
│           │                                                                 │
│           ▼                                                                 │
│  ┌─────────────────┐                                                        │
│  │ 7. Marcar para  │──► requiere_revision_manual = True                    │
│  │    revisión     │    (NO bloquear expediente)                           │
│  └─────────────────┘                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.3 Archivos a Modificar

| Archivo | Cambio Propuesto | Impacto |
|---------|------------------|---------|
| `agentes/agente_02_ocr.py` | Agregar lógica de OCR real | PRINCIPAL |
| `utils/pdf_extractor.py` | Agregar método `extraer_con_ocr()` | Bajo |
| `utils/ocr_processor.py` | **NUEVO**: Procesador OCR encapsulado | Nuevo módulo |
| `config/settings.py` | Agregar `OCR_THRESHOLDS` | Configuración |
| `requirements.txt` | Agregar dependencias OCR | Instalación |

### 7.4 Dependencias Nuevas

```txt
# requirements.txt (agregar)
pytesseract>=0.3.10
easyocr>=1.7.0
opencv-python>=4.8.0
# ocrmypdf>=15.0.0  # Opcional, para PDF searchable
```

### 7.5 Instalación de Tesseract (Windows)

```powershell
# Opción 1: Chocolatey
choco install tesseract

# Opción 2: Instalador manual
# Descargar de: https://github.com/UB-Mannheim/tesseract/wiki
# Agregar al PATH: C:\Program Files\Tesseract-OCR
```

---

## 8. RESTRICCIONES DE IMPLEMENTACIÓN

### 8.1 Compatibilidad con Gobernanza

- NO modificar la lógica de decisión de AG09 (Decisor)
- NO cambiar el contrato de `ResultadoAgente`
- NO introducir nuevas observaciones CRÍTICAS por OCR
- Mantener compatibilidad con JSON de salida v2.0

### 8.2 Performance

- Tiempo máximo por página: 5 segundos
- Memoria máxima por documento: 500 MB
- Procesamiento secuencial (no paralelo en v1)

### 8.3 Fallbacks

Si Tesseract no está instalado:
1. Log de advertencia
2. Continuar con extracción PyMuPDF
3. Marcar páginas problemáticas como `requiere_revision_manual`

---

## 9. MÉTRICAS DE ÉXITO (POST-IMPLEMENTACIÓN)

| Métrica | Baseline (actual) | Objetivo | Medición |
|---------|-------------------|----------|----------|
| Expedientes procesables | ~60% | ≥ 95% | % con texto extraíble |
| Tiempo promedio/página | N/A | ≤ 2s | Promedio en 100 docs |
| Falsos negativos OCR | Alto | < 5% | Páginas marcadas incorrectamente |
| Uso de memoria | N/A | < 500 MB | Monitor en ejecución |

---

## 10. CRONOGRAMA PROPUESTO

| Fase | Duración | Entregable |
|------|----------|------------|
| **Fase 1a**: Instalación y prueba de stack | 1 día | Tesseract + PyMuPDF funcionando |
| **Fase 1b**: Implementación básica en AG02 | 2 días | OCR integrado, sin preprocesamiento |
| **Fase 1c**: Preprocesamiento de imagen | 1 día | Corrección de rotación y contraste |
| **Fase 1d**: Tests con expedientes reales | 1 día | Validación en `data/expedientes/pruebas/` |
| **Fase 1e**: Fallback EasyOCR | 1 día | OCR alternativo funcionando |
| **Total estimado** | **6 días** | OCR real operativo |

---

## 11. REGISTRO DE FASES IMPLEMENTADAS

### 11.1 Fase 1a — Smoke Test OCR — ✅ CERRADA

**Fecha de cierre:** 2025-12-31  
**Commit:** `50c725f`

**Entregables:**
- Script aislado: `tools/ocr_smoke_test.py`
- Dependencias agregadas: `pytesseract`, `opencv-python`
- Renderizado PDF→imagen con PyMuPDF (`fitz.Matrix`)
- Métricas implementadas: DPI, contraste (percentiles), blur_score (Laplacian)
- OCR con Tesseract + confianza promedio + snippet 200 chars

**Comando de ejecución:**
```bash
python tools/ocr_smoke_test.py --pdf "<RUTA_PDF>" --page 1 --dpi 200 --lang eng
```

**Evidencia (PDF de prueba con `--lang eng`):**
- `confianza_promedio`: 0.77
- `num_palabras`: 47
- `tiempo_ms`: 329
- `error`: null

---

### 11.2 Fase 1b — OCR Español (spa) — ✅ CERRADA

**Fecha de cierre:** 2025-12-31

**Prerrequisito:**
- Archivo `spa.traineddata` instalado en `tessdata/`
- Verificar con: `tesseract --list-langs` (debe incluir `spa`)

**Comando de ejecución:**
```bash
python tools/ocr_smoke_test.py --pdf "<RUTA_PDF>" --page 1 --dpi 200 --lang spa
```

**Evidencia (PDF de prueba con `--lang spa`):**
```json
{
  "confianza_promedio": 0.847,
  "num_palabras": 46,
  "tiempo_ms": 491,
  "error": null,
  "langs_disponibles": ["eng", "osd", "spa"]
}
```

~~**Nota Windows — TESSDATA_PREFIX:**~~ ⚠️ **OBSOLETA**
```powershell
# NOTA: Esta configuración es OBSOLETA. El OCR se ejecuta exclusivamente en WSL.
$env:TESSDATA_PREFIX = "C:\Program Files\Tesseract-OCR\tessdata"
```

> **⚠️ IMPORTANTE — Arquitectura WSL-Only:**
> 
> El OCR de este proyecto está diseñado para ejecutarse **exclusivamente en WSL (Ubuntu)**.
> Windows actúa únicamente como **host/editor** y no requiere instalación de Tesseract ni Ghostscript.
> Todo el runtime OCR (Tesseract, Ghostscript, ocrmypdf) debe estar instalado y configurado en WSL.
> 
> **No es necesario** configurar variables de entorno en Windows ni instalar binarios OCR en Windows.

**Criterio de aceptación:**
> OCR con `--lang spa` ejecuta sin error y `confianza_promedio >= 0.75` en PDF de prueba.

✅ **Criterio cumplido:** 0.847 ≥ 0.75

---

### 11.3 Fase 1c — Rotación/Deskew — ✅ CERRADA

**Fecha de cierre:** 2026-01-07  
**Commit:** `b314c20`

**Entregables:**
- Detección de rotación con Tesseract OSD (0°/90°/180°/270°)
- Fallback bruteforce si OSD falla (4 pruebas, early exit)
- Detección de deskew leve (≤15°) con `cv2.minAreaRect()`
- Corrección de rotación con `cv2.warpAffine()`
- Campos JSON: `rotacion_grados` (numérico), `rotacion_metodo`, `deskew_grados`

**Evidencia:**
```json
{
  "rotacion_grados": 0,
  "rotacion_metodo": "osd",
  "deskew_grados": 0.0
}
```

✅ **Criterio cumplido:** `rotacion_grados` es numérico, no "pendiente".

---

## 12. FASE 2 — GATING (INTEGRACIÓN CONTROLADA) — ✅ CERRADA

**Fecha de cierre:** 2026-01-07  
**Versión del módulo:** 2.0.0

### 12.1 Objetivo

Implementar decisión automática entre:
- `direct_text`: PDF nativo con texto embebido → extracción directa PyMuPDF
- `ocr`: PDF escaneado → Tesseract OCR con preprocesamiento
- `fallback_manual`: Ambos fallan → requiere revisión humana (NUNCA inventa texto)

### 12.2 Archivos Creados

| Archivo | Propósito |
|---------|-----------|
| `src/ocr/__init__.py` | Módulo OCR core reutilizable |
| `src/ocr/core.py` | Funciones: render, rotación, OCR, métricas |
| `src/ingestion/__init__.py` | Módulo de ingestión |
| `src/ingestion/config.py` | Umbrales de gating (`GatingThresholds`) |
| `src/ingestion/pdf_text_extractor.py` | Función principal `extract_text_with_gating()` |
| `tests/test_pdf_text_extractor.py` | 9 tests PyTest |

### 12.3 Umbrales por Defecto

```python
GatingThresholds(
    direct_text_min_chars=200,    # Mínimo caracteres para direct_text
    direct_text_min_words=30,     # Mínimo palabras para direct_text
    ocr_min_confidence=0.60,      # Mínima confianza OCR
    ocr_min_words=20,             # Mínimo palabras OCR
    sample_pages=1,               # Páginas de muestra
    ocr_dpi=200,                  # DPI para render
    ocr_lang="spa"                # Idioma OCR
)
```

### 12.4 Uso del Módulo

```python
from src.ingestion import extract_text_with_gating

resultado = extract_text_with_gating("documento.pdf", lang="spa")

print(resultado["decision"]["metodo"])  # "direct_text" | "ocr" | "fallback_manual"
print(resultado["decision"]["razon"])   # Explicación basada en métricas
```

### 12.5 Ejemplo de Salida JSON

```json
{
  "archivo": "PAUTAS.pdf",
  "decision": {
    "metodo": "direct_text",
    "razon": "direct_text: 15234 chars >= 200, 2847 words >= 30"
  },
  "direct_text": {
    "texto": "...",
    "num_chars": 15234,
    "num_words": 2847,
    "num_paginas": 19,
    "tiempo_ms": 45,
    "error": null
  },
  "ocr": {
    "texto": "...",
    "confianza_promedio": 0.847,
    "num_words": 46,
    "tiempo_ms": 485
  },
  "evidencia": {
    "thresholds_usados": { ... },
    "version_modulo": "2.0.0",
    "timestamp_iso": "2026-01-07T...",
    "tesseract_disponible": true,
    "pymupdf_disponible": true
  }
}
```

### 12.6 Tests Implementados

| Test | Descripción | Estado |
|------|-------------|--------|
| `test_direct_text_detection` | PDF nativo → decide direct_text | ✅ PASS |
| `test_direct_text_metrics` | Métricas completas | ✅ PASS |
| `test_ocr_fallback_with_low_threshold` | Umbral alto → OCR o fallback | ✅ PASS |
| `test_ocr_result_structure` | Estructura OCR completa | ✅ PASS |
| `test_archivo_inexistente` | Archivo no existe → fallback_manual | ✅ PASS |
| `test_pdf_corrupto_simulado` | Archivo corrupto → manejo seguro | ✅ PASS |
| `test_estructura_completa_siempre` | JSON completo incluso con error | ✅ PASS |
| `test_custom_thresholds` | Umbrales personalizados | ✅ PASS |
| `test_default_thresholds` | Valores por defecto | ✅ PASS |

**Comando de ejecución:**
```bash
python -m pytest tests/test_pdf_text_extractor.py -v
```

### 12.7 Principios de Gobernanza Respetados

- ✅ NUNCA inventa texto si falla la extracción
- ✅ Retorna `fallback_manual` con evidencia del fallo
- ✅ No bloquea el flujo completo
- ✅ Decisión basada en métricas medibles (no heurística opaca)
- ✅ Trazabilidad completa (thresholds, timestamp, versión)

### 12.8 Estabilidad y Optimizaciones

- **Lazy Import EasyOCR**: Se implementó carga perezosa para `easyocr` y `torch` en `agente_02_ocr.py` (Commit `300df6f`). Esto resuelve problemas de crash en sistemas sin GPU o con memoria limitada al no cargar librerías pesadas a menos que sean estrictamente necesarias.
- **PyTest Green**: Cobertura completa de la lógica de decisión en `tests/test_pdf_text_extractor.py` (Commit `c490972`).
- **Gating Robusto**: El sistema prioriza `direct_text` (rápido y exacto) y solo recurre a `ocr` si el texto extraído es insuficiente o inexistente.

---

**Documento creado:** 2025-12-18  
**Última actualización:** 2026-01-07  
**Autor:** Sistema AG-EVIDENCE  
**Estado:** Fase 1c cerrada, Fase 2 cerrada

