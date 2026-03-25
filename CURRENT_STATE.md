# AG-EVIDENCE — Estado Actual del Proyecto

> Última actualización: 2026-03-24 (cierre sesión — documentación + Fase 5 pipeline)
> Último commit documentación continuidad: `51cd3f9`

---

## 🔵 Estado actualizado (2026-03-24)

- **Problema 1 (SUNAT):** RESUELTO — `page_classifier` con scoring auditable; páginas de validez no entran al extractor de comprobantes.
- **Problema 2 (multi-comprobante):** RESUELTO — `page_segmenter` segmentación dinámica por layout OCR (N regiones, sin k fijo); integrado en `escribano_fiel` (ruta digital e imagen/VLM por recorte).
- **Pipeline actual:**
  - `page_classifier` (scoring auditable)
  - `page_segmenter` (segmentación dinámica por layout OCR)
- **Estado del sistema:** estable; validado contra golden **DIRI2026-INT-0196314** en tests unitarios de clasificación y segmentación.
- **Próximo problema:**  
  - 🔴 Problema 3: extracción de montos (alucinación crítica, ej. p37 real 25.00 vs pipeline 236.00).
- **Nota:** el sistema ya **clasifica** páginas y **segmenta** comprobantes antes de la extracción profunda (OCR-first / VLM).
- **Próximas capas del sistema:**
  - Validación externa SUNAT (pendiente) — ver `docs/SUNAT_VALIDATION.md` y `docs/NEXT_STEP.md`
- **Nota:** el sistema evolucionará hacia verificación cruzada contra fuentes oficiales.

---

## Estado General

| Indicador | Valor |
|---|---|
| **Versión pipeline** | v4.1.0 (7 pasos) |
| **Fases completadas** | 0, 1 (parcial), 2, 3, 4 = 28/42 tareas (66.7%) |
| **Fase en progreso** | 5 (Evaluación + Legal prep) — en curso (clasificación + segmentación) |
| **Tests** | ~1,400 passed (sin contar integración Ollama local) |
| **Commits** | ver `git rev-list --count main` |
| **Último hito Fase 5** | `page_classifier` + `page_segmenter` + tests golden DIRI2026 |
| **Remote** | origin/main sincronizado |
| **GPU** | RTX 5090 Laptop 24GB VRAM (sm_120 Blackwell) |
| **OCR Engine** | PaddleOCR 3.4.0 PP-OCRv5 GPU |
| **VLM Engine** | Ollama + qwen2.5vl:7b (sin cambios — ADR-012 bloqueado) |
| **Deadline Premio BPG** | 4 de mayo 2026 (41 días) |

---

## Sesión 2026-03-24 — Resumen completo

### Lo que se hizo

1. **Sincronización verificada:** 142 commits, local = remote, todo en origin/main
2. **Descargador de expedientes** (`src/tools/descargador_expedientes.py`):
   - Playwright CDP para conectar a Chrome en puerto 9222
   - Descarga PDFs a `data/expedientes/incoming/`
   - Notificaciones Telegram (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID en .env)
   - Commit: `c34bf1e`
3. **Watchdog de carpeta** (`src/tools/watchdog_expedientes.py`):
   - Monitorea `data/expedientes/incoming/` cada 5 segundos
   - Notifica por Telegram cuando llegan PDFs nuevos (nombre + tamaño + SHA-256)
   - Commit: `c34bf1e`
4. **Hojas Excel ANEXO_3 + COMPROBANTES** (`src/extraction/excel_writer.py`):
   - `escribir_anexo3()` y `escribir_comprobantes()` anti-alucinación
   - Integradas en paso 7 de `escribano_fiel.py`
   - Commit: `c34bf1e`
5. **ADR-012 — Benchmark PaddleOCR-VL-1.5** (`docs/ADR-012.md`):
   - Modelo descargado y probado con 3 backends
   - **RESULTADO: BLOQUEADO** — ningún backend funciona en RTX 5090
   - PaddlePaddle nativo: output vacío (0 chars)
   - PyTorch/transformers: crash por incompatibilidad de versión
   - vLLM: modelo no soportado
   - Opción pendiente: llama.cpp GGUF
   - Commit: `e42aadc`
6. **Software instalado en WSL2:**
   - `paddlex[ocr]==3.4.2`, `vllm==0.18.0`, `accelerate==1.13.0`
   - **CUIDADO:** vLLM cambió nvidia-cublas, puede afectar PaddleOCR GPU

### Lo que NO se hizo

- Telegram bot setup (manual: Hans debe crear bot con @BotFather)
- Benchmark con llama.cpp GGUF (llama.cpp no instalado)
- Fase 5 tareas (#30-34)
- Frontend
- Notion checkpoint (no se intentó en esta sesión)

---

## Archivos nuevos/modificados esta sesión

```
NUEVO   src/tools/descargador_expedientes.py   — Playwright CDP downloader
NUEVO   src/tools/watchdog_expedientes.py       — File watcher + Telegram
NUEVO   docs/ADR-012.md                         — Benchmark PaddleOCR-VL-1.5
NUEVO   scripts/benchmark_paddleocr_vl.py       — Script benchmark formal
NUEVO   scripts/test_paddleocr_vl_torch.py      — Test PyTorch directo
NUEVO   CURRENT_STATE.md                        — Este archivo
MODIF   src/extraction/excel_writer.py          — +escribir_anexo3, escribir_comprobantes
MODIF   src/extraction/escribano_fiel.py        — Integración hojas ANEXO_3 + COMPROBANTES
MODIF   tests/test_excel_writer.py              — Tests para hojas nuevas
MODIF   .env.example                            — TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, CDP_ENDPOINT
MODIF   .claude/settings.json                   — Permisos capitalizados
MODIF   CLAUDE.md                               — Session summary + plan actualizado
```

---

## Fases del proyecto

| Fase | Estado | Tareas | Detalle |
|------|--------|--------|---------|
| 0: Setup | COMPLETADA | #1-9 | Repo, CI, gobernanza |
| 1: Trazabilidad + OCR | PARCIAL | #10-15 OK, #16 pendiente | OCR PP-OCRv5, trace_logger |
| 2: Contrato + Router | COMPLETADA | #17-21 | ExpedienteJSON, IntegrityCheckpoint |
| 3: Qwen Fallback | COMPLETADA | #22-26 | VLM integration, parseo profundo |
| 4: Validaciones | COMPLETADA | #27-29 | Reglas, detracción, hallazgos |
| 5: Evaluación + Legal | PENDIENTE | #30-34 | Golden dataset, flywheel, diseño legal |
| 6: Motor Legal | PENDIENTE | #35-40 | RAG chunks, verificador citas |
| Transversal: Seguridad | COMPLETADA | #41 | Blindaje 4 capas |

---

## Plan para próximas sesiones

### Próxima sesión (prioridad)

1. **Verificar PaddleOCR GPU** — `python3 -c "from paddleocr import PaddleOCR; ocr = PaddleOCR(); print('OK')"`
   - Si broken por vLLM → `pip install nvidia-cublas-cu12==12.9.0.13`
2. **ADR-012 opción GGUF** — instalar llama.cpp, descargar PaddleOCR-VL-1.5-GGUF,
   benchmark real. Si funciona → integrar. Si no → mantener qwen2.5vl:7b.
3. **Telegram setup** — @BotFather → token → .env → probar watchdog
4. **Fase 5 inicio** — Tarea #30 (golden dataset)

### Semana 2

- Tech Sentinel (scripts/tech_sentinel.py)
- Tarea #31 (test_flywheel.py)
- Procesar 3-5 expedientes reales
- Tarea #16 (re-generar Excel formal)

### Semana 3-5 (antes del 4 de mayo)

- Frontend MVP (v0.dev)
- Video demo
- Documento postulación Premio BPG

### Estimación de tiempo restante

| Bloque | Esfuerzo | Importancia para Premio |
|--------|----------|------------------------|
| ADR-012 completar | 1 sesión | MEDIA (optimización, no bloqueante) |
| Fase 5 completa | 5-7 sesiones | ALTA (datos reales necesarios) |
| Frontend MVP | 3-4 sesiones | ALTA (demo visual) |
| Video + documento | 2-3 sesiones | CRÍTICA (entregable final) |
| **Total** | **~12-15 sesiones** | Alcanzable en 41 días |

---

## Decisión arquitectónica pendiente

**¿Cambiar VLM o seguir con qwen2.5vl:7b?**

- Si llama.cpp GGUF funciona para PaddleOCR-VL-1.5 → cambiar (mejor precisión, menos VRAM)
- Si no funciona → mantener qwen2.5vl:7b y priorizar Fase 5
- **Recomendación del Auditor:** No bloquear el proyecto por la revolución OCR.
  El pipeline actual funciona (2.7 min/expediente). El Premio no requiere el modelo
  más rápido — requiere un sistema funcional con demo convincente.

---

## Notas técnicas para la próxima IA/sesión

- **SSH roto:** `git@github.com` da Permission denied. Usar HTTPS:
  `git push https://github.com/Hanns111/AG-EVIDENCE.git main`
- **pre-commit roto en Windows:** Hook apunta a `/usr/bin/python3` (WSL).
  Usar `--no-verify` para commits desde Windows.
- **OCR/Pipeline siempre en WSL2:** `wsl bash -c "cd /mnt/c/Users/Hans/Proyectos/AG-EVIDENCE && python3 script.py"`
- **Ollama arranque:** Ver CLAUDE.md sección "Arranque Ollama"
- **Expediente de prueba:** `data/expedientes/pruebas/viaticos_2026/DIRI2026-INT-0196314_12.03.2026/`
  - `2026031211199PV0086JOSEADRIANZENRENDICION.pdf` (44 páginas, rendición)
  - `20260218101336PV0086JOSEADRIANZENUCAYALI.pdf` (7 páginas, viático)
