# Log de sesión — 2026-03-24

## Qué se hizo

- **page_classifier (Fase 5):** motor de scoring auditable (`TipoPagina`, scores SUNAT/comprobante, `senales_activadas`); integración en `escribano_fiel._identificar_paginas_comprobante` para excluir SUNAT del parseo profundo; tests contra golden DIRI2026.
- **page_segmenter (Fase 5):** segmentación multi-comprobante por huecos en X e Y sobre bboxes OCR; filtro `score_comprobante >= 2`; integración en parseo profundo (bloques por página, recortes VLM por región); tests p21/p34/p37, SUNAT vacío, N≥3 columnas sintéticas.
- **Documentación de cierre:** `CURRENT_STATE.md`, `docs/NEXT_STEP.md`, este log.

## Qué se corrigió

- Falsos positivos en páginas de validez SUNAT (Problema 1).
- Suposición 1 página = 1 comprobante en presencia de layout multi-columna / multi-bloque (Problema 2).

## Qué sigue

- **Problema 3:** extractor determinístico de montos (etiquetas + aritmética, sin depender del VLM para decidir total; NULL si duda).

## Implementación fallback OCR-first

- Se eliminó early return en `parseo_profundo` cuando Ollama no está disponible
- Se implementó `_parseo_profundo_fallback_sin_vlm`
- Se creó `construir_comprobante_minimo` (regex + abstención)
- Se reutilizó segmentación existente (sin duplicar lógica)
- Se mantuvo deduplicación y contratos sin cambios

### Resultado

El sistema ahora genera comprobantes sin depender del VLM.

### Cambio arquitectónico

**De:** VLM-gated pipeline

**A:** OCR-first robusto con VLM opcional
