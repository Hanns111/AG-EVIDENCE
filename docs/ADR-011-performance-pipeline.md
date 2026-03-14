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
Adoptar estrategia incremental en 5 niveles. Principio rector: evitar costo → reducir costo → cambiar herramienta → paralelizar.

**Nivel 1 — Gating + clasificación (YA IMPLEMENTADO):**
1. Clasificar tipo de página: FACTURA, BOLETA, BOARDING_PASS, DJ, RECIBO_HONORARIOS, ADMINISTRATIVO
2. Gating digital/imagen: PyMuPDF get_text() umbral 100 chars
3. Downscale general: MAX_VLM_IMAGE_PX=1200 antes de VLM
4. Métricas dispatcher: tiempo VLM, páginas por carril, tipos detectados
5. Prompts diferenciados por tipo en qwen_fallback.py

**Nivel 2 — OCR-first + score de suficiencia (IMPLEMENTADO 2026-03-13):**
6. Extracción regex por tipo: campos robustos primero (RUC, fecha, total). Proveedor/razón social NO como condición dura al inicio (campo inestable con OCR sucio)
7. Score de suficiencia: `campos_encontrados / campos_esperados`
   - score >= 0.75 → resolver sin VLM
   - 0.50 <= score < 0.75 → resolver con observación de confianza baja
   - score < 0.50 → escalar a VLM
8. Métricas nuevas: paginas_resueltas_sin_vlm, paginas_escaladas_vlm, score_promedio_ocr_por_tipo

**Nivel 3 — ROI crop + downscale + timeout audit (IMPLEMENTADO 2026-03-13):**
9. Unión de bboxes PaddleOCR → región dominante → crop con 5% margen
10. Downscale post-crop: reducir imagen cropeada a max 1200px
11. Fallback: si <3 bboxes válidos o crop <5% área, página completa con downscale
12. Orden: OCR → score → si falla: crop → downscale → VLM
13. Timeout audit: num_predict 16384→4096, num_ctx 16384→8192 (caps thinking tokens)
14. Métricas: pages_with_crop, pages_full_page, crop_area_ratios, VLM input dimensions

**Nivel 4 — Benchmark modelo especializado (EVALUADO 2026-03-13):**
13. MonkeyOCR-pro-1.2B: **DESCARTADO** para RTX 5090 (Blackwell sm_120)
    - PyTorch 2.5.1 cu124 no soporta sm_120 (necesita nightly builds)
    - Depende de PaddleX + PaddlePaddle + lmdeploy (stack pesado)
    - Conflictos de dependencias: numpy<2, PyMuPDF<=1.24.14, transformers==4.51.0
    - Reevaluar cuando PyTorch soporte sm_120 estable
14. PaddleOCR-VL: pendiente de evaluar (alternativa)
15. Benchmark qwen3-vl:8b solo (5 páginas imagen DIRI2026):
    - Promedio: 28.4s/pág | 4/5 páginas extrajeron RUC+fecha
    - Page 21: timeout (49.8s, 0 campos) — página sin estructura clara
    - Conclusión: qwen3-vl:8b sigue siendo viable, cuello de botella son timeouts

**Nivel 5 — Paralelismo (solo si Niveles 1-4 insuficientes):**
15. Pipeline overlap CPU/GPU: OCR página N+1 en CPU mientras VLM procesa página N en GPU
16. Migrar etapa VLM a vLLM con continuous batching (alternativa al overlap)
17. Workers concurrentes (max 2) con scheduling de VRAM

### Resultados reales E2E (DIRI2026-INT-0196314, 2026-03-13)

| Métrica | Baseline v2.0.0 | v3.0.0 OCR-first |
|---|---|---|
| Páginas al VLM | 21 | **13** (-38%) |
| Páginas resueltas sin VLM | 0 | **8** |
| Comprobantes extraídos | 19 | **19** (mismo) |
| Score promedio OCR | N/A | **0.41** |
| Tiempo total | ~45 min | **43.6 min** |
| Status | CRITICAL | **WARNING** (mejoró) |

Nota: el tiempo no bajó significativamente porque el cuello de botella son los timeouts de qwen3-vl:8b (120s) con fallback a qwen2.5vl:7b. Las 8 páginas resueltas por OCR-first son instantáneas (<1ms).

### Estimación de impacto (proyección original)

| Optimización | Antes | Después |
|---|---|---|
| Páginas al VLM | 16 | 8-12 (OCR-first filtra) |
| Resolución imagen | 3500×2500 px | ~1200×900 px (crop+downscale) |
| Latencia estimada/pág | 45s | 12-20s |
| Tiempo total 16 págs | 720s | 150-300s |
| Expediente completo | 12-27 min | 4-7 min |

### Consecuencias
- No cambia stack actual (Ollama + qwen3-vl:8b se mantiene)
- No requiere instalación de modelos nuevos en Niveles 1-3
- Crop usa bboxes de PaddleOCR ya disponibles (LineaOCR, Tarea #14)
- Fallback: si no hay bboxes, enviar página completa con downscale
- OCR-first puede eliminar 50-70% de llamadas VLM en expedientes de viáticos
- Métricas habilitan decisiones informadas para Niveles 4-5
- Paralelismo y cambio de modelo son decisiones diferidas hasta tener datos
- Pipeline overlap (Nivel 5) no requiere cambio de stack, solo scheduling

### Relación con otros ADRs
- ADR-001: se mantiene local-first
- ADR-008: PaddleOCR sigue como motor OCR
- ADR-009: qwen3-vl:8b sigue como VLM, pero potencialmente como fallback en Nivel 3
- ADR-010: ERL cache complementa esta estrategia (evitar re-inferencia)
