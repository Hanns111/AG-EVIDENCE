## ADR-011 — Estrategia de Performance para Páginas Escaneadas

**Estado:** Aceptada
**Fecha:** 2026-03-13

### Contexto
Un expediente típico tiene 40-50 páginas. Las ~35 digitales se procesan rápido (PyMuPDF + regex, ~2-5s/pág). Las ~16 escaneadas van al VLM qwen3-vl:8b (~30-90s/pág), totalizando 12-27 minutos por expediente. Objetivo: <5 minutos.

Restricciones:
- Local-first obligatorio (ADR-001)
- GPU única: RTX 5090 24GB VRAM
- qwen3-vl:8b usa ~9GB VRAM
- /no_think causa respuesta vacía (thinking tokens obligatorios)

### Evaluación de alternativas

| Estrategia | Impacto estimado | Complejidad | Riesgo |
|------------|-----------------|-------------|--------|
| ROI crop (enviar solo región comprobante) | -30-60% latencia | Baja | Bajo |
| Downscale adaptativo (1200px max) | -30-50% latencia | Baja | Bajo |
| OCR-first (skip VLM si campos suficientes) | -50-70% llamadas VLM | Media | Medio |
| Modelo documental especializado (MonkeyOCR/PaddleOCR-VL) | -80-90% latencia | Media | Medio (requiere benchmark) |
| Paralelismo vLLM (continuous batching) | 2-3x throughput | Alta | Medio |
| Paralelismo Ollama (mismo modelo) | Inestable | Media | Alto (issues documentados) |

### Decisión
Adoptar estrategia incremental en 4 niveles, en orden de impacto/riesgo:

**Nivel 1 (implementar ahora):**
1. Gating mejorado: clasificar tipo de página (FACTURA, BOLETA, BOARDING_PASS, DJ, ADMINISTRATIVO)
2. ROI crop: usar bounding boxes de PaddleOCR para recortar región útil (~20-40% de la página)
3. Downscale: reducir imagen a max 1200px lado mayor antes de VLM
4. Métricas del dispatcher: instrumentar tiempo VLM, páginas por carril, resolución efectiva

**Nivel 2 (implementar después de métricas):**
5. OCR-first: si PaddleOCR detecta campos clave (RUC, TOTAL, FECHA) con alta confianza, parsear con regex sin VLM
6. Prompts mínimos por tipo: JSON reducido, sin explicaciones

**Nivel 3 (requiere benchmark):**
7. Evaluar MonkeyOCR-pro-1.2B y PaddleOCR-VL contra corpus peruano real (30 facturas, 30 boletas, 30 boarding, 30 DJ)
8. Si modelo especializado resuelve con <5s/pág → migrar

**Nivel 4 (solo si Nivel 3 insuficiente):**
9. Migrar etapa VLM a vLLM con continuous batching
10. Workers concurrentes (max 2) con scheduling de VRAM

### Estimación de impacto combinado (Niveles 1-2)

| Optimización | Antes | Después |
|---|---|---|
| Páginas al VLM | 16 | 8-12 (OCR-first filtra) |
| Resolución imagen | 3500×2500 px | ~1200×900 px (crop+downscale) |
| Latencia estimada/pág | 45s | 12-20s |
| Tiempo total 16 págs | 720s | 150-300s |
| Expediente completo | 12-27 min | 4-7 min |

### Consecuencias
- No cambia stack actual (Ollama + qwen3-vl:8b se mantiene)
- No requiere instalación de modelos nuevos en Nivel 1-2
- Crop usa bboxes de PaddleOCR ya disponibles (LineaOCR, Tarea #14)
- Fallback: si no hay bboxes, enviar página completa
- Métricas habilitan decisiones informadas para Niveles 3-4
- Paralelismo y cambio de modelo son decisiones diferidas hasta tener datos

### Relación con otros ADRs
- ADR-001: se mantiene local-first
- ADR-008: PaddleOCR sigue como motor OCR
- ADR-009: qwen3-vl:8b sigue como VLM, pero potencialmente como fallback en Nivel 3
- ADR-010: ERL cache complementa esta estrategia (evitar re-inferencia)
