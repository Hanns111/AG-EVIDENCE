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

**Nivel 2 — OCR-first + score de suficiencia (SIGUIENTE PRIORIDAD):**
6. Extracción regex por tipo: campos robustos primero (RUC, fecha, total). Proveedor/razón social NO como condición dura al inicio (campo inestable con OCR sucio)
7. Score de suficiencia: `campos_encontrados / campos_esperados`
   - score >= 0.75 → resolver sin VLM
   - 0.50 <= score < 0.75 → resolver con observación de confianza baja
   - score < 0.50 → escalar a VLM
8. Métricas nuevas: paginas_resueltas_sin_vlm, paginas_escaladas_vlm, score_promedio_ocr_por_tipo

**Nivel 3 — ROI crop + downscale (solo para páginas que escalan a VLM):**
9. Clustering de bboxes PaddleOCR → región dominante → crop con margen de seguridad
10. Downscale post-crop: reducir imagen cropeada a max 1200px
11. Fallback: si no hay bboxes útiles, página completa con downscale directo
12. Orden obligatorio: OCR → score → si falla: crop → downscale → VLM

**Nivel 4 — Benchmark modelo especializado (requiere corpus):**
13. Evaluar MonkeyOCR-pro-1.2B y PaddleOCR-VL contra corpus peruano real (30 facturas, 30 boletas, 30 boarding, 30 DJ)
14. Si modelo especializado resuelve con <5s/pág → migrar

**Nivel 5 — Paralelismo (solo si Niveles 1-4 insuficientes):**
15. Pipeline overlap CPU/GPU: OCR página N+1 en CPU mientras VLM procesa página N en GPU
16. Migrar etapa VLM a vLLM con continuous batching (alternativa al overlap)
17. Workers concurrentes (max 2) con scheduling de VRAM

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
