# CLAUDE.md — Contexto de Continuidad para Claude Code

> Este archivo es la memoria persistente del proyecto.
> Claude Code DEBE leerlo al inicio de cada sesión.

---

## Estado del Sistema (referencia rápida)

| Indicador | Valor |
|---|---|
| **Pipeline** | 7 pasos: custodia → OCR → parseo → OCR-first + VLM → evaluación → validación → Excel |
| **Fases completadas** | 0-4 (28/42 tareas = 66.7%) + ADR-011 Niveles 1-3 + ADR-012 parcial |
| **Fase siguiente** | Fase 5: Evaluación + Legal prep + ADR-012 benchmark VLM |
| **Tests** | 1403 collected (verificado 2026-04-04) |
| **GPU** | RTX 5090 24GB VRAM (Laptop) |
| **Orquestador** | src/extraction/escribano_fiel.py |
| **ADR-012** | PaddleOCR-VL-1.5 benchmark EN PROGRESO — nativo BROKEN, pendiente vLLM |
| **ADR-013** | Source map Claude Code → solo referencia conceptual externa (no operativa) |
| **Investigación** | `docs/research/CLAUDE_CODE_SOURCEMAP_NOTES.md` — benchmark arquitectónico; no toca `src/` |
| **Principio rector** | VISIBILIDAD PROBATORIA: sin inferencia, sin cruce, NULL si no visible |
| **Última actualización** | 2026-04-04 |

---

## Estado Actual

- **Proyecto:** AG-EVIDENCE v2.0 — Sistema multi-agente de control previo
- **Repositorio:** Hanns111/AG-EVIDENCE
- **Rama de trabajo:** main (directa, sin worktrees)
- **Último commit en main:** (ver git log, se actualiza frecuentemente)
- **Tag:** v2.2.0 (publicado en GitHub)
- **Limpieza legacy:** Completada 2026-02-11 — todo v1.0 eliminado, auditoría certificada
- **OCR Engine:** PaddleOCR 3.4.0 PP-OCRv5 server GPU (ADR-008) + Tesseract fallback
- **VLM Engine:** Ollama 0.16.2 + Qwen3-VL-8B (Q4_K_M, 6.1GB, 8.7GB VRAM) — ADR-009 actualizado
- **DuckDB:** 1.4.4 instalado (base analitica)
- **Seguridad:** Blindaje 4 capas completado 2026-02-25 (ACTA aprobada por Hans)

---

## Última Tarea Completada

- **Sesiones post 2026-03-24** — Commits en main hasta 2026-04-04:
  - `c95533f` feat(extraccion): recuperación post-extracción con visibilidad probatoria y trazabilidad
  - `42dd78a` feat: fallback OCR-first para generación de comprobantes sin VLM
  - `18b9c82` feat(escribano): fallback OCR-first cuando Ollama no está disponible
  - `51ba029` docs: handoff maestro de continuidad (AG_EVIDENCE_MASTER_HANDOFF.txt)
  - `1a0225a` docs(research): sourcemap Claude Code como referencia conceptual

- **Sesión 2026-03-24** — ADR-012 benchmark + herramientas de descarga
  - `src/tools/descargador_expedientes.py`: Playwright CDP para descargar PDFs del MINEDU
  - `src/tools/watchdog_expedientes.py`: Monitor carpeta incoming + notif Telegram
  - `src/extraction/excel_writer.py`: Hojas ANEXO_3 + COMPROBANTES (anti-alucinación)
  - `docs/ADR-012.md`: Benchmark PaddleOCR-VL-1.5 (resultado: nativo BROKEN en RTX 5090)
  - `scripts/benchmark_paddleocr_vl.py`: Script de benchmark formal
  - `.env.example`: Variables Telegram + CDP
  - vLLM 0.18.0 instalado en WSL2 (pendiente ejecutar benchmark con backend vLLM)
  - Commits: `c34bf1e` (tools + excel), pendiente commit ADR-012

- **Pipeline v4.1.0** — Performance optimizado: 2.7 min/expediente (sesión 2026-03-13/14)
- escribano_fiel.py v4.1.0: overlap + keep_alive + JSON estricto + telemetría
- qwen2.5vl:7b primario (sin fallback), format="json", keep_alive="10m"
- num_predict=800, num_ctx=4096, timeout=60s, vlm_workers=2
- OCR-first (8/21 sin VLM), ROI crop (17.6% área), ThreadPoolExecutor paralelo
- E2E DIRI2026: **2.7 min** (16x speedup vs 45 min), 19 comprobantes, 0 fallos JSON
  - ⚠️ Performance condicional: benchmark bajo DIRI2026-INT-0196314 (19 comprobantes). No es garantía universal — expedientes con más páginas imagen o peor calidad de escaneo serán más lentos.
- MonkeyOCR-pro-1.2B descartado (sm_120 incompatible PyTorch cu124)
- Tests: 1403 collected (actualizado 2026-04-04)
- **Fase 4 COMPLETADA** (3/3 tareas: #27 ✅ #28 ✅ #29 ✅)
- **Fase 3 COMPLETADA** (5/5 tareas: #22 ✅ #23 ✅ #24 ✅ #25 ✅ #26 ✅)

## Tareas Anteriores Completadas

- **Tarea #41** — Blindaje de Seguridad (Transversal)
- 4 capas defense-in-depth: GitHub platform → CI → pre-commit hooks → session protocol
- **Tarea #21** — Integrar router en escribano_fiel.py (Fase 2, ÚLTIMA)
- Pipeline 5→7 pasos, EscribanoFiel con inyección de dependencias
- **Fase 2 COMPLETADA** (5/5 tareas: #17-#21)

## Tareas Anteriores Completadas

- **Tarea #20** — Hoja DIAGNOSTICO en Excel (Fase 2)
- src/extraction/excel_writer.py: ~850 líneas, VERSION_EXCEL_WRITER = "1.0.0"
- Commit 81a3cb8: EscritorDiagnostico + escribir_diagnostico() convenience
- Consume DecisionCheckpoint → genera hoja DIAGNOSTICO en workbook openpyxl
- Banner: SINAD, status semáforo, confianza global, acción recomendada
- 6 secciones diagnósticas con colores semáforo (verde/amarillo/rojo)
- Detalle por campo: nombre, valor, confianza%, status, motor, archivo:página
- Pie: alertas + métricas globales (total campos, % extracción, confianza promedio)
- Colores: Verde (#C6EFCE), Amarillo (#FFEB9C), Rojo (#FFC7CE)
- Tests: 59 tests propios, 835 totales, 0 failures

## Tareas Anteriores Relevantes

- **Tarea #19** — Calibrar umbrales con distribución real (Fase 2)
- src/extraction/calibracion.py: ~500 líneas, VERSION_CALIBRACION = "1.0.0"
- Commit d52f75b: CalibradorUmbrales + 3 perfiles + JSON export
- Tests: 84 tests propios
- **Tarea #18** — Confidence Router + Integrity Checkpoint (Fase 2)
- src/extraction/confidence_router.py: 1424 líneas, 86 tests
- IntegrityCheckpoint evalúa integrity_status → CONTINUAR/ALERTAS/DETENER
- DiagnosticoExpediente + DecisionCheckpoint serializables
- Commits: e34e196 (Hito 1), 33d5466 (Hito 2)
- **Tarea #17** — Contrato de datos tipado: ExpedienteJSON (Fase 2)
- src/extraction/expediente_contract.py: 1161 líneas, 7 enums, 18+ dataclasses
- 11 Grupos (A-K) de PARSING_COMPROBANTES_SPEC.md, DocumentosConvenio (Pautas 5.1.11)
- Tests: 84 tests nuevos, commit a276ec4
- **Tarea #14** — Extender ResultadoPagina con bbox + confianza por linea (+ TraceLogger)
- LineaOCR dataclass: bbox (Optional), confianza (Optional), motor
- +815 lineas, 44 tests nuevos, commit e6a3229
- **Tarea #13** — Rewrite OCR Engine (Tesseract → PaddleOCR PP-OCRv5)
- src/ocr/core.py reescrito de 383 a 733 lineas, 47 tests, commit 8b5efe6
- **Tarea #12** — Política formal de abstención operativa (src/extraction/abstencion.py)
- 550 líneas, 66 tests pasando, commit bb6849c
- **Tarea #11** — Logger estructurado JSONL con trace_id (src/ingestion/trace_logger.py)
- 638 líneas, 55 tests pasando, commit ccc5022
- **Limpieza legacy v1.0** — 46+ archivos eliminados, commits: ab74c2f, 2bae185
- **Gobernanza** — ROADMAP.md creado, Sección 10 añadida a GOVERNANCE_RULES.md, commit e8244ac

## Prueba Real Completada (2026-02-12)

- **Expediente:** ODI2026-INT-0139051 (viáticos, Piura)
- Procesado completo: Anexo 3, DJ, 6 facturas, 2 boarding pass, tiquete aéreo
- Excel generado: `RENDICION_ODI2026-INT-0139051.xlsx` (4 hojas, 20 columnas SUNAT)
- Script: `scripts/generar_excel_expediente.py`
- **Hallazgo normativo:** IGV 10% para MYPES restaurantes/hoteles (Ley 31556 + 32219)
- Documentado: `data/directivas/.../RESUMEN_TASAS_IGV_MYPES.md`

### Conocimiento Normativo Adquirido — IGV MYPES

Para Fase 4 (Validaciones), el sistema debe verificar:
- IGV 18% = régimen general
- IGV 10% = MYPE restaurante/hotel/alojamiento (Ley 31556+32219, vigente 2025-2026)
- IGV 0% = zona Amazonía (Ley 27037)
- Verificación vía consulta RUC SUNAT: actividad económica + condición MYPE + RUC activo
- Escala temporal: 10% (2025-2026) → 15% (2027) → 18% (2028+)

## Benchmark OCR Completado (2026-02-17)

Prueba empirica con Caja Chica N.3 (112 paginas, 16 comprobantes):

| Metrica | Tesseract | PaddleOCR 2.9.1 CPU | PP-OCRv5 GPU |
|---------|-----------|---------------------|--------------|
| Precision total | 20.3% | 36.2% | **42.0%** |
| Match exacto | 14/69 | 25/69 | **29/69** |
| No extraido | 31 | 17 | **15** |
| Serie/Numero | — | 10/16 | 10/16 |
| IGV | — | 7/10 | 7/10 |
| Total (monto) | — | — | 7/16 |
| Fecha | — | 6/16 | 5/16 |
| RUC | — | 0/11 | 0/11 |

**RTX 5090 GPU:** Operativo con PaddlePaddle 3.3.0 cu129 (CUDA 12.9, sm_120).
Requiere `export LD_LIBRARY_PATH=/usr/lib/wsl/lib:$LD_LIBRARY_PATH` en WSL2.

## Qwen2.5-VL Operativo (2026-02-18)

- **Motor:** Ollama 0.16.2 + qwen2.5vl:7b (Q4_K_M, 6.0 GB) — ADR-009
- **Instalacion:** Sin sudo en ~/ollama/ (WSL2 user-space)
- **GPU:** RTX 5090 Laptop 24GB, CUDA 12.0, 29/29 layers offloaded
- **VRAM:** ~14.3 GB total (5.3 weights + 8.3 compute + 0.4 KV cache)
- **Nombre correcto del modelo:** `qwen2.5vl:7b` (SIN guion entre qwen2.5 y vl)

### Fase A Completada — Resultados 3 facturas de referencia

| Factura | Tiempo | Tokens | Confianza | Grupo J |
|---------|--------|--------|-----------|---------|
| El Chalan F011-8846 (imagen) | 46.1s | 891 | alta | 1 OK, 2 ERR |
| Win & Win F700-141 (texto) | 14.2s | 947 | alta | 3 OK, 1 ERR |
| Virgen del Carmen E001-1771 (texto) | 13.4s | 871 | baja | 2 OK, 1 ERR |

- **Estrategia aprobada:** Mixta PyMuPDF + Qwen-VL (ADR-009)
  - 12 comprobantes con texto digital → parseo PyMuPDF (regex Python)
  - 3 paginas imagen → Qwen-VL via Ollama
  - Validacion aritmetica Grupo J siempre con Python

### Arranque Ollama (patron confiable)
```bash
wsl bash -c 'export LD_LIBRARY_PATH=/home/hans/ollama/lib/ollama:/usr/lib/wsl/lib:$LD_LIBRARY_PATH && export OLLAMA_MODELS=/home/hans/.ollama/models && /home/hans/ollama/bin/ollama serve & sleep 3 && /home/hans/ollama/bin/ollama list'
```
IMPORTANTE: serve + comandos en el MISMO bash -c, porque el server muere cuando el proceso padre termina.

## Expediente DEBEDSAR2026-INT-0146130 Completado (2026-02-18)

- **Comisionado:** MARTIARENA CARHUARUPAY, Víctor (DNI 25185850)
- **Destino:** Lima → Tarapoto → Chachapoyas → Tarapoto → Lima (07-10/Feb/2026)
- **Excel generado:** `output/RENDICION_DEBEDSAR2026-INT-0146130_v2.xlsx` (4 hojas, 18 columnas)
- **Script:** `scripts/generar_excel_DEBEDSAR2026.py`
- **Estrategia:** PyMuPDF (6 comprobantes texto digital) + Qwen2.5-VL-7B 500 DPI (11 comprobantes imagen)
- **Resultado:** 0 NULL en datos principales. 500 DPI eliminó casi todos los vacíos vs 200 DPI.

### Reglas de Extracción Validadas por Hans

1. **SIN inferencia** — si el texto dice "NUEVA", se pone "NUEVA", NO se completa a "NUEVA CAJAMARCA"
2. **SIN cruce** — NO comparar Anexo 3 con documento fuente en observaciones
3. **SIN corrección manual** — si VLM lee algo mal, se reporta tal cual
4. **NULL** = el campo EXISTE en el comprobante pero el motor no lo leyó
5. **Blanco (vacío)** = el campo NO APLICA para ese tipo de comprobante
6. **Observaciones** = solo texto relevante del propio comprobante (pie de página), nunca comparativas

### Errores de Lectura VLM Detectados (Qwen2.5-VL-7B 500 DPI)

| Comprobante | VLM leyó | Real (humano) | Tipo error |
|-------------|----------|---------------|------------|
| F205-00012200 (p41) | F205-00012200 | F205-00012299 | Confusión 0/9 en serie |
| F205 (p41) | SANGUICHE BUTITARRA | SANGUCHE BUTIFARRA | Lectura imprecisa texto |
| Boleta 001-005367 (p56) | Caldo Calli 25.00 | Caldo de gallina | Error lectura nombre plato |
| F002-12174 (p63) | Jr. Pedro Canaa 398 | Jr. Pedro Canga 398 | Error lectura apellido |
| F001-00000664 (p20) | PROGRAMA EDUCACION BASICA PAR. TODOS | PARA TODOS | Truncamiento |
| FP01-233 (p60) | PAIACONES RELLENOS | PATACONES RELLENOS | Confusión I/T |

**Conclusión Hans:** Estos errores de "lectura fina" requieren herramienta con mejor resolución
o zoom. Qwen2.5-VL-7B a 500 DPI no los detecta. Se prosigue, queda pendiente para mejora.

### Reglas de Negocio Aprendidas (feedback de Hans)

1. **IGV en servicios de taxi:** Correcto que sea 0, pero si hay IGV igual se acepta
   siempre que el comprobante sea válido (RUC con actividad económica correcta)
2. **Boleta de Venta (persona natural):** El RUC comprador debe ser el de la institución
   (ej: 20380795907 PROGRAMA EDUCACION BASICA PARA TODOS), NO el DNI del comisionado.
   Si la boleta pone DNI del comisionado como comprador → NO es válido (inscripción a
   título personal no permitida). Si pone el nombre/RUC de la institución → OK.
3. **Hotel con múltiples noches en 1 factura:** Es válido. No es duplicado.
4. **Columna pendiente para futuro:** Datos de referencia (correo, web, teléfono) del emisor.
   NO implementar en esta rendición, guardar para futuras fases.

## Convenios Interinstitucionales (Pautas 5.1.11) — Documentado 2026-02-19

- **Documento:** `docs/CONVENIOS_INTERINSTITUCIONALES.md`
- **Identificador:** GOV_RULE_CONVENIOS_INTERINSTITUCIONALES_v1
- **Categoría:** OTROS_EXPEDIENTES → CONVENIO_INTERINSTITUCIONAL
- **Naturaleza:** Relación Estado-Estado, NO aplica Ley de Contrataciones
- **Documentos mínimos:** Convenio + Cobranza + Detalle + Informe Técnico + CCP + SINAD
- **Conformidad funcional:** Informe técnico + memo = OK (no requiere doc separado)
- **Validación obligatoria:** Coherencia económica (montos y periodos)
- **No requiere:** Factura SUNAT, SEACE, Orden Servicio SIGA, proveído Logística
- **Impacto en Tarea #17:** `ExpedienteJSON.documentos_convenio` (Optional[DocumentosConvenio])
- **Impacto en settings.py:** Agregar CONVENIO_INTERINSTITUCIONAL a NaturalezaExpediente
- **Ejemplo práctico:** Expedientes con RENIEC u otra entidad pública

## Siguiente Sesión — Pendientes (actualizado 2026-03-24)

### BLOQUE INMEDIATO (próxima sesión)

**1. ADR-012: Completar benchmark PaddleOCR-VL-1.5**
- PaddlePaddle nativo BROKEN en RTX 5090 sm_120 (output vacío, 766s/page en PDF)
- vLLM 0.18.0 ya instalado — ejecutar: `paddleocr genai_server --model_name PaddleOCR-VL-1.5-0.9B --backend vllm --port 8118`
- GGUF disponible en [PaddlePaddle/PaddleOCR-VL-1.5-GGUF](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5-GGUF) como alternativa
- Si vLLM funciona → benchmark contra DIRI2026-INT-0196314, campos y tiempo
- Si ni vLLM ni GGUF funcionan → probar MonkeyOCR-pro-1.2B o descartar y seguir con qwen2.5vl:7b
- **ATENCIÓN:** vLLM instaló nvidia-cublas diferentes, verificar que PaddleOCR GPU sigue funcionando

**2. Telegram bot setup (manual por Hans)**
- Crear bot con @BotFather
- Agregar TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID a .env
- Probar: `python -m src.tools.watchdog_expedientes`

**3. Fase 5 inicio**
- Tarea #30: Golden dataset (expected.json)
- Tarea #16: Re-generar Excel con pipeline formal
- Tarea #31: test_flywheel.py

### BLOQUE SEMANA 2
- Tech Sentinel (scripts/tech_sentinel.py)
- Procesamiento de expedientes reales con pipeline v4.1.0
- Inicio diseño legal (Tareas #33-34)

### BLOQUE SEMANA 3-5 (Deadline Premio BPG: 4 mayo 2026)
- Frontend MVP con v0.dev
- Video demo (3-5 min)
- Documento de postulación

### Completado sesión 2026-03-13:
- Tarea #29 (reporte_hallazgos.py) — 49 tests, commit 490dacd
- ADR-011 Performance Pipeline — estrategia 5 niveles, reordenada tras auditoría multi-AI
- Pipeline improvements: gating tipo comprobante, downscale VLM 1200px, métricas dispatcher
- CLAUDE.md sincronizado (estaba 2 fases atrasado)
- Auditoría multi-AI: ChatGPT + Gemini + Opus → consolidado, ADR-011 ajustado
- Commits: 490dacd, a2bb4c1, fa456c5 — 1284 tests, 0 failures

### Completado sesión 2026-03-13 (tarde/noche):
- **ADR-011 Nivel 2 IMPLEMENTADO:** OCR-first + score suficiencia (commit 380dc71)
  - _extraer_campos_ocr_por_tipo(): RUC, fecha, serie/numero, total, IGV, subtotal
  - Score: campos_encontrados/campos_esperados, umbrales 0.75/0.50
  - 37 tests nuevos, 1322 total, escribano_fiel.py v3.0.0
- **E2E DIRI2026-INT-0196314:** 8/21 páginas sin VLM (38% reducción), 19 comprobantes (commit 40a9637)
- **ADR-011 Nivel 3 SALTADO:** Hans decidió saltar ROI crop, ir directo a Nivel 4
- **ADR-011 Nivel 4 EVALUADO:** MonkeyOCR-pro-1.2B **DESCARTADO**
  - RTX 5090 sm_120 incompatible con PyTorch 2.5.1 cu124
  - Stack pesado: PyTorch + PaddlePaddle + lmdeploy + paddlex
  - qwen3-vl:8b benchmarked: 28.4s/pág promedio, 4/5 páginas extrajeron campos

### Próxima sesión — Plan actualizado:

**BLOQUE 1 — Procesamiento expedientes con pipeline v3.0.0**
- Procesar DIRI2026-INT-0068815 con pipeline OCR-first
- Reprocesar Caja Chica N.3 con pipeline formal
- Medir impacto real OCR-first en expedientes variados

**BLOQUE 2 — Fase 5 inicio**
- Tarea #30: Golden dataset (expected.json por expediente)
- Tarea #16: Re-generar Excel con pipeline formal

**BLOQUE 3 — Optimización VLM (cuello de botella confirmado)**
- **ACCIÓN URGENTE:** Cambiar qwen2.5vl:7b como modelo primario (qwen3-vl:8b produce JSON corrupto con num_predict=4096)
- qwen2.5vl:7b: ~25-30s/pág, ~730 tokens, 0 fallos en 13 páginas
- qwen3-vl:8b: JSON corrupto en ~80% de páginas, forzando 2x120s retry antes de fallback
- Impacto esperado: de 49 min → ~10-15 min (elimina retry overhead)
- Evaluar vLLM como alternativa a Ollama para continuous batching

**BLOQUE 4 — Pendientes menores**
- Branch protection — Hans configura en GitHub UI
- Convertir las 15 preguntas de ChatGPT en checklist de métricas automáticas por expediente

### Mejoras de pipeline aprobadas (implementar progresivamente):
- **Cache OCR** — Si SHA-256 del PDF ya existe, saltar OCR y cargar resultado previo (→ ADR-010 ERL)
- **Pipeline overlap CPU/GPU** — OCR página N+1 en CPU mientras VLM procesa página N (ADR-011 Nivel 5)
- **Ampliar benchmark dataset** — Agregar 2 facturas adicionales: 1 compleja + 1 escaneo malo (total: 5 facturas de referencia)

### Vigilancia tecnológica:
10. **AI Stack Sentinel** — Ejecutar `python3 scripts/tech_monitor.py` semanalmente (lunes)
11. **DESCARTADO:** MonkeyOCR-pro-1.2B — incompatible RTX 5090 sm_120 (PyTorch cu124 no soporta Blackwell). Reevaluar cuando PyTorch nightly soporte sm_120.
12. **WATCH:** Qwen3.5 multimodal — esperar fix GGUF en Ollama

### Investigacion Pendiente — TensorRT (pedido por Hans 2026-02-17)

**Estado actual:**
- PaddlePaddle 3.3.0 cu129 tiene **TensorRT compilado** como version `1.0.500`
  (valor interno de PaddlePaddle, NO es la version publica de NVIDIA TensorRT)
- `paddle.version.with_pip_tensorrt = OFF` — NO incluye TensorRT via pip
- `paddle.inference.Config.enable_tensorrt_engine()` existe como metodo pero **falla en runtime**
  porque **libnvinfer NO esta instalado** (ni en `/usr/lib/`, ni en `/usr/local/cuda/`)
- `paddle.is_compiled_with_tensorrt()` NO existe como atributo

**Por que falla:**
- PaddlePaddle GPU cu129 fue compilado con soporte TensorRT opcional, pero el
  paquete pip NO incluye las librerias runtime de TensorRT (`libnvinfer.so`)
- Para activar TensorRT hay que instalar NVIDIA TensorRT separadamente
  (dpkg/apt desde NVIDIA repos, o pip `tensorrt-cu12`)
- Sin `libnvinfer.so`, `enable_tensorrt_engine()` lanza error en runtime

**Accion sugerida para Hans:**
1. Verificar si TensorRT aceleraria significativamente PaddleOCR
   (actualmente ~1.5s/pagina GPU vs ~3-5s CPU; TensorRT podria bajar a ~0.5s)
2. Si vale la pena: `pip install tensorrt-cu12 tensorrt-dispatch-cu12 tensorrt-lean-cu12`
3. Riesgo: compatibilidad cu129 + sm_120 (Blackwell) no garantizada con TensorRT
4. Prioridad: BAJA — el cuello de botella actual es precision, no velocidad

### Analisis Pendiente — RUC 0% y Fecha 31% (pedido por Hans 2026-02-17)

**RUC — 0/11 (0.0%): OCR lee RUCs pero selecciona el EQUIVOCADO**

El problema NO es que el OCR no lee numeros de RUC. Los lee correctamente.
El problema es que cada pagina tiene MULTIPLES RUCs (proveedor, pagador, intermediario)
y la funcion `buscar_ruc()` simplemente toma el primero que no sea del MINEDU:

| Gasto | Esperado | Extraido | Problema |
|-------|----------|----------|----------|
| #2 | 20610827171 | 20613530577 | Lee RUC de otro ente en la pagina |
| #5 | 20604955498 | 20602200761 | Lee RUC de pagador/intermediario |
| #7 | 20609780451 | 20613032101 | Lee otro RUC visible en la pagina |
| #8 | 20606697091 | 20563313952 | Lee otro RUC |
| #9 | 10701855406 | 10707855466 | Casi correcto — error OCR de digitos |
| #10 | 20440493781 | 20132272418 | Lee RUC del pagador |
| #14 | 20508565934 | 20131370998 | Lee RUC del MINEDU (no filtrado) |
| #16 | 10073775006 | 20131370998 | Lee RUC del MINEDU |

**Soluciones propuestas (en orden de viabilidad):**
1. **Heuristica posicional (Fase 1):** buscar RUC CERCA de la etiqueta "RUC" o
   "R.U.C." usando bbox de LineaOCR — el RUC del proveedor esta al inicio del
   comprobante, junto a razon social. Requiere las lineas+bbox de Tarea #14.
2. **Padron RUC SUNAT via DuckDB (Fase 2):** validar que el RUC extraido existe
   y corresponde a una razon social coherente con el contexto del comprobante.
3. **Qwen-VL vision (Fase 3):** modelo VLM entiende estructura visual de facturas
   y puede distinguir "RUC del emisor" vs "RUC del comprador".
4. **Filtro ampliado:** Expandir `rucs_pagador` con mas RUCs conocidos del Estado
   (20131370998, 20304634781, etc.) — solucion parcial.

**Fecha — 5/16 (31.2%): OCR lee fechas pero selecciona la EQUIVOCADA**

Mismo patron: cada comprobante tiene multiples fechas (emision, vencimiento,
recepcion, impresion) y `buscar_fecha()` toma la primera que encuentra.

| Gasto | Esperado | Extraido | Problema |
|-------|----------|----------|----------|
| #1 | 06/02/2026 | 04/02/2026 | Lee fecha de recepcion, no emision |
| #2 | 03/02/2026 | 30/01/2026 | Lee fecha de otra factura en la pagina |
| #5 | 30/01/2026 | 06/02/2026 | Lee fecha de recepcion |
| #6 | 07/02/2026 | 06/02/2020 | Error OCR: 2026→2020 + fecha equivocada |
| #7 | 07/02/2026 | 06/02/2026 | Lee otra fecha |

**Soluciones propuestas:**
1. **Heuristica contextual:** buscar fecha DESPUES de "FECHA DE EMISION",
   "F. EMISION", "FECHA:" usando contexto de lineas adyacentes.
2. **Filtro por rango temporal:** descartar fechas fuera del rango del expediente
   (ej: 2020 en un expediente 2026 = error evidente).

### Decisión Arquitectónica Implementada — Integrity Checkpoint (Tarea #18 ✅)

- Nodo formal IntegrityCheckpoint en confidence_router.py (NO módulo monolítico, ADR-005)
- Evalúa `integrity_status = OK | WARNING | CRITICAL` → acción CONTINUAR/ALERTAS/DETENER
- EvidenceEnforcer valida snippet + página + regla en cada observación CRITICA/MAYOR
- DiagnosticoExpediente genera 6 secciones para hoja Excel DIAGNOSTICO
- DecisionCheckpoint.to_dict() serializable a JSON para trazabilidad
- Commits: e34e196 (Hito 1), 33d5466 (Hito 2)

---

## Tracking en Notion (limpieza 2026-03-05)

Páginas activas (7 páginas + 2 databases + tareas del tablero):

- **Plan de Desarrollo (ROOT):** 303b188d-be2e-8193-85f5-f6861c924539
- **Tablero de Tareas:** DB 6003e907-28f5-4757-ba93-88aa3efe03e1 (data source: collection://16c577cf-e572-45a0-8cad-5e64ebd56d9f)
- **Dashboard de Progreso:** 311b188d-be2e-81d5-a98f-d6959bacc8f8
- **Bitácora:** 303b188d-be2e-8135-899b-d209caf42dc9
- **Árbol de Ramas:** 303b188d-be2e-81a7-b38a-d42b811a9832
- **Seguridad:** 30cb188d-be2e-8103-8d68-e6dbb968394f (sub: ACTA DE CIERRE)
- **Plan Estratégico:** 312b188d-be2e-8106-92c3-e206f873457a
- **Glosario Técnico:** DB collection://bffe2c97-e824-459b-af01-febd94f54dec

Eliminadas 2026-03-05: Dashboard v1 (archivado), Protocolo Cursor vs Claude Code (obsoleto)

### Protocolo Notion + Obsidian obligatorio (ALINEACION ABSOLUTA):
1. Antes de empezar una tarea → marcar 🔵 En Progreso en Notion + actualizar Tablero de Tareas.md en Obsidian
2. Al terminar → marcar ✅ Completado + Fecha Real + Ejecutado Por + Bitácora en Notion + actualizar Obsidian
3. Actualizar Bitácora en AMBAS plataformas con cada acción relevante
4. Si cambia algo del plan → avisar a Hans + actualizar AMBAS plataformas
5. Notion y Obsidian son ayudas visuales para Hans — NO fuentes para codificar
6. Si una tiene información que la otra no → es un DEFECTO a corregir inmediatamente

### Momentos de sincronización automática (Claude Code lo hace SIN que Hans lo pida):
1. Al cerrar o cambiar estado de una tarea
2. Al cerrar o abrir una fase
3. Al cerrar sesión (SESSION_PROTOCOL)
4. Después de decisiones de gobernanza
5. Después de push a GitHub

---

## Protocolo Multi-Agente (v3 — Actualizado 2026-03-05)

### Principio fundamental (v4 — actualizado 2026-03-10):
**Cursor es el implementador principal.** Claude Code audita TODO. Codex CLI apoya como consulta inteligente.

### Cursor (IMPLEMENTADOR PRINCIPAL) hace:
- Código nuevo, módulos, pipelines multi-archivo
- Tests (pytest)
- Ejecución de OCR/pipeline en WSL2
- Commits + push (Conventional Commits)
- Instalación de dependencias
- Debug y refactors

### Claude Code (AUDITOR) hace:
- Auditoría de calidad sobre trabajo de Cursor
- Revisión de diffs, tests, coherencia arquitectónica
- Cambios en docs/ de gobernanza y archivos protegidos
- Actualización de Notion y Obsidian (sincronización absoluta)
- Ejecución de `audit_repo_integrity.py` (8 checks)
- Veredicto formal: CONFORME / NO CONFORME / INCIERTO

### Codex CLI (CONSULTA INTELIGENTE) hace:
- Apoyo técnico a Cursor: investigación, análisis, alternativas
- Lectura y consultas sobre el codebase
- Nunca modifica código ni hace commits

### Gemini CLI (CONSULTA) hace:
- Solo lectura y consultas
- Nunca modifica código, archivos ni configuración

### Cursor NO debe:
- Modificar archivos PROTEGIDOS (docs/ de gobernanza, CLAUDE.md, etc.)
- Crear worktrees ni ramas (trabaja directo en main)
- Hacer merge de ramas

### Archivos protegidos (ambos necesitan aprobación):
- docs/AGENT_GOVERNANCE_RULES.md
- docs/GOVERNANCE_RULES.md
- docs/PROJECT_SPEC.md
- AGENTS.md
- .cursorrules
- .cursor/mcp.json
- CLAUDE.md (este archivo)
- governance/SESSION_PROTOCOL.md
- docs/security/SECURITY_GOVERNANCE_POLICY.md

### Gobernanza Cursor — Cuándo y cómo usarlo:
Hans o Claude Code deciden cuándo Cursor debe actuar (ediciones puntuales).
Los guardrails de Cursor están en .cursorrules (sección GUARDRAILS, reglas G1-G12).

### Flujo de trabajo principal:
```
Hans asigna tarea + dice quién actúa (Codex CLI o Cursor)
    → Implementador asignado ejecuta → commit + push
    → Claude Code audita → veredicto → Hans decide GO/NO-GO
```

---

## Permisos de Proyecto

Claude Code tiene **permisos completos** sobre todo el directorio del proyecto AG-EVIDENCE y sus subcarpetas, incluyendo:
- `data/` (expedientes, directivas, normativa, evaluacion)
- `docs/` (gobernanza, ADRs, specs)
- `src/` (codigo fuente)
- `tests/` (tests)
- `output/` (resultados generados)
- `scripts/` (scripts de procesamiento)
- `config/` (configuracion)

**No preguntar permisos** para leer, escribir o ejecutar dentro del proyecto. Solo los archivos listados en "Archivos protegidos" requieren aprobacion de Hans para modificar.

### Regla de Autonomia Total (establecida por Hans 2026-03-02)

**Claude Code NUNCA debe pedir autorizacion para ejecutar herramientas.** Hans trabaja en paralelo y las interrupciones por permisos rompen su flujo de trabajo. Esto aplica a TODAS las herramientas: Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch, MCP Notion, y cualquier otra.

**Protocolo obligatorio al inicio de cada sesion/worktree:**
1. Verificar que `.claude/settings.local.json` tenga permisos amplios (`Bash(*)`, `Read(*)`, `Write(*)`, etc.)
2. Si no los tiene, escribirlos automaticamente SIN preguntar
3. Ver configuracion completa en memoria persistente: `~/.claude/projects/.../memory/permisos.md`

---

## Herramientas por Fase (decisión 2026-03-05)

| Herramienta | Cuándo | Fase | Uso |
|-------------|--------|------|-----|
| **Cursor** | **Ya activo** | Desde Fase 3 | Ediciones puntuales, parseo regex, debug campo por campo |
| **Obsidian** | Opcional | Fases 4-6 | Knowledge base normativa (graph view reglas) |
| **v0.dev** | Cierre Fase 4 | Cuando haya datos reales | Frontend/UI del sistema AG-EVIDENCE |
| **AntiGravity** | Condicional | Según necesidad | Herramienta complementaria UI |

**Regla frontend:** NO construir UI hasta que Fase 3 (parseo profundo) y Fase 4 (validaciones) produzcan datos limpios. Un frontend sin datos reales es cáscara vacía.

### Bóveda Obsidian — Mapa Visual del Proyecto (aprobada 2026-03-05)

- **Ruta:** `C:\Users\Hans\ObsidianVaults\AG-EVIDENCE-MAPA\` (aislada del repo)
- **Propósito:** Mapa visual para que Hans entienda el proyecto: arquitectura, pipeline, estado, fases, normativa
- **Contenido (24 notas):** MOC, Pipeline, 7 fases, 7 módulos, 4 conceptos, 3 normativa, Tablero de Tareas, Bitácora, Gobernanza, Seguridad, Glosario, Plan Estratégico, Árbol de Ramas
- **Alineación:** ABSOLUTAMENTE ALINEADA con Notion (mismos datos, mismos estados)
- **Actualización:** Claude Code sincroniza automáticamente en los 5 momentos definidos (ver protocolo)
- **Aislamiento:** Sin git, sin relación con el repo, solo lectura conceptual

---

## Reglas de Proyecto

- **VISIBILIDAD PROBATORIA (principio rector):** el dato existe SOLO si es visible en el documento fuente. Sin inferencia, sin cruce con Anexo 3 durante extracción, NULL si el campo existe pero no se leyó, vacío si no aplica al tipo de comprobante. Validación cruzada (Anexo 3 vs factura) es etapa POSTERIOR (Fase 5+).
- **Anti-alucinación:** toda observación CRÍTICA/MAYOR requiere archivo + página + snippet
- **Abstención:** prefiere vacío honesto a dato inventado
- **Completitud:** Completado = módulo en src/ + tests + integración pipeline. Scripts exploratorios NO cuentan.
- **Gate de arranque:** Ver governance/SESSION_PROTOCOL.md — verificar 5 fuentes antes de declarar "listo"
- **Local-first:** ningún dato sale a cloud (GDPR ready)
- **Commits:** Conventional Commits obligatorio
- **Hardware:** RTX 5090 24GB VRAM (Laptop), WSL2 Ubuntu 22.04
- **LLM texto:** Ollama + qwen3:32b
- **VLM vision:** Ollama + qwen2.5vl:7b (extraccion de comprobantes)
- **Session Protocol:** Ver governance/SESSION_PROTOCOL.md (commit incremental obligatorio)
- **Sync Protocol:** Ver docs/PROTOCOL_SYNC.md v2 — Claude Code = Auditor, Codex CLI = Implementador (desde 2026-03-02)
- **OCR/Pipeline SIEMPRE en WSL2:** PaddleOCR, Tesseract, ocrmypdf, pdftotext, y todo el pipeline de extraccion OCR se ejecuta EXCLUSIVAMENTE desde WSL2. Nunca desde Windows nativo (los motores no están instalados ahí). La GPU (RTX 5090) solo es accesible desde WSL2. Para ejecutar scripts Python que usen OCR: `wsl bash -c "cd /mnt/c/Users/Hans/Proyectos/AG-EVIDENCE && python script.py"`

### Directiva Vigente de Viáticos (FUENTE PRINCIPAL)

| Documento | Ruta Local | Estado |
|-----------|-----------|--------|
| **NUEVA Directiva de Viáticos RGS 023-2026-MINEDU** | `data/directivas/vigentes_2025_11_26/VIÁTICO/NUEVA DIRECTIVA DE VIÁTICOS_{Res_de_Secretaría_General Nro. 023-2026-MINEDU.pdf` | **FUENTE PRINCIPAL** |
| Directiva de Viáticos 011-2020 (DEROGADA) | misma carpeta | Solo contexto, NO usar para validación |

**Regla:** Toda validación de viáticos se hace contra la NUEVA directiva (RGS 023-2026).
La directiva anterior (011-2020) queda como referencia histórica únicamente.

### Gestión de Archivos y Backups

- **PDFs de directivas NO se versionan en git** (ver data/directivas/INVENTARIO_DIRECTIVAS.md)
- **PDFs de expedientes NO se versionan en git** (datos sensibles del Estado)
- **Backup completo:** `python scripts/backup_local.py` (ZIP con timestamp)
- **GitHub contiene:** solo código, docs .md, configs, tests, scripts
- **Inventario de directivas:** data/directivas/INVENTARIO_DIRECTIVAS.md

### Extracción de texto de PDFs (WSL2)

Cuando Claude Code necesite leer PDFs y el reader nativo falle, usar estas herramientas en WSL2:

```bash
# Instalar (una vez)
sudo apt install poppler-utils

# PDF con texto embebido → extraer directo
pdftotext "ruta/del/archivo.pdf" "ruta/del/archivo.txt"

# PDF escaneado (imagen) → OCR primero, luego extraer
ocrmypdf "archivo.pdf" "archivo_ocr.pdf" --force-ocr
pdftotext "archivo_ocr.pdf" "archivo.txt"
```

**Flujo recomendado:**
1. Intentar `pdftotext` directo (más rápido)
2. Si el .txt sale vacío → el PDF es imagen → usar `ocrmypdf` primero
3. Luego `pdftotext` sobre el PDF con OCR

---

## Progreso por Fases

| Fase | Estado | Tareas |
|------|--------|--------|
| 0: Setup | ✅ Completada | #1-9 |
| 1: Trazabilidad + OCR | 🔵 En progreso | #10-15 ✅, #16 🔵 en progreso |
| 2: Contrato + Router | ✅ Completada | #17 ✅, #18 ✅, #19 ✅, #20 ✅, #21 ✅ |
| 3: Qwen Fallback | ✅ Completada | #22 ✅, #23 ✅, #24 ✅, #25 ✅, #26 ✅ |
| 4: Validaciones | ✅ Completada | #27 ✅, #28 ✅, #29 ✅ |
| 5: Evaluación + Legal prep | ⬜ Pendiente | #30-34 |
| 6: Motor Legal | ⬜ Pendiente | #35-40 |
| Transversal: Seguridad | ✅ Completada | #41 (Blindaje 4 capas) |

---

## Estructura del Codebase

```
.github/
  workflows/ci-lint.yml     ← CI pipeline: 4 jobs (lint, commit-lint, governance, author)
  CODEOWNERS                ← Propiedad de archivos criticos (@Hanns111)
  pull_request_template.md  ← Template PRs con checklist gobernanza
.gitattributes              ← Merge protection (ours) para archivos protegidos
.pre-commit-config.yaml     ← 8 hooks: ruff, governance guard, seguridad
config/
  __init__.py, settings.py
governance/
  SESSION_PROTOCOL.md       ← protocolo de apertura/cierre de sesion
  integrity_manifest.json   ← 13 hashes SHA-256 (9 gobernanza + 4 CI)
src/
  __init__.py
  agents/.gitkeep           ← placeholder Fase 2
  extraction/
    __init__.py, abstencion.py, calibracion.py, confidence_router.py, excel_writer.py, expediente_contract.py, local_analyst.py
  ingestion/
    __init__.py, config.py, custody_chain.py,
    pdf_text_extractor.py, trace_logger.py
  ocr/
    __init__.py, core.py
  validation/
    __init__.py, reporte_hallazgos.py
  rules/
    __init__.py, detraccion_spot.py, integrador.py, tdr_requirements.py
  tools/
    __init__.py, ocr_preprocessor.py
scripts/
  audit_repo_integrity.py   ← Auditoria integridad: 7 checks SHA-256 + branches + CI
  governance_guard.py       ← Pre-commit hook: bloquea cambios a 9 archivos protegidos
  backup_local.py           ← backup ZIP del proyecto completo
  extraer_con_qwen_vl.py    ← Fase A: extraccion con Qwen2.5-VL via Ollama
  explorar_expediente.py    ← PyMuPDF + PaddleOCR para explorar PDFs
  extraer_expediente_diri.py ← Extraccion texto completa del expediente
  generar_excel_expediente.py
  generar_excel_DIRI2026.py ← Excel con datos hardcoded (referencia)
  generar_excel_OTIC2026.py
  calibrar_umbrales.py      ← Calibracion de umbrales (Tarea #19)
  setup_ollama.sh           ← Setup Ollama server en WSL2
tests/
  conftest.py,
  test_abstencion.py, test_calibracion.py, test_confidence_router.py, test_custody_chain.py, test_excel_writer.py,
  test_detraccion_spot.py, test_expediente_contract.py, test_ocr_core.py,
  test_ocr_preprocessor.py, test_pdf_text_extractor.py,
  test_tdr_requirements.py, test_trace_logger.py
data/
  directivas/               ← PDFs locales (NO en git, ver INVENTARIO_DIRECTIVAS.md)
  expedientes/              ← PDFs sensibles (NO en git)
  normativa/                ← JSON de reglas (SI en git)
```

---

*Actualizado: 2026-02-26 por Claude Code*

## Reglas de Sesión Obligatorias

### Fuente de verdad
- origin/main es LA ÚNICA fuente de verdad del proyecto
- Notion y Obsidian son herramientas de CONSULTA y APRENDIZAJE del usuario, NO bases del proyecto
- NUNCA tomar decisiones basándose en lo que dice Notion u Obsidian
- SIEMPRE verificar contra origin/main antes de cualquier diagnóstico

### Al INICIAR cada sesión:
1. git fetch && git pull origin main (SIEMPRE primero)
2. git log --oneline -5 (verificar estado real)
3. pytest --co -q 2>/dev/null | tail -3 (conteo de tests)

### Al COMPLETAR cada tarea:
1. git add -A && git commit -m "feat: descripción"
2. git push origin main (INMEDIATAMENTE)
3. Mostrar output completo del push
4. git log origin/main --oneline -1 (VERIFICAR que llegó al remoto)

### Después de push exitoso, PROPAGAR a:
1. Notion Checkpoint (321b188d-be2e-81fe-a4fd-eff56dc82cdb) — actualizar estado
2. Notion Dashboard — actualizar conteo tareas y tests
3. Notion Bitácora — agregar entrada de la tarea completada
4. Obsidian Tablero, Bitácora y archivo de Fase correspondiente

### Sincronización automática Cursor (Windows)
- Después de cada push a origin/main, ejecutar automáticamente:
  `git -C /mnt/c/Users/Hans/Proyectos/AG-EVIDENCE pull origin main`
- Esto mantiene la copia de Windows (Cursor) sincronizada sin que Hans haga nada manual

### PROHIBIDO:
- Usar worktrees o ramas temporales — todo va directo a main
- Decir "pusheado" sin mostrar el output real del push
- Diagnosticar estado del repo sin hacer git fetch primero
- Tomar Notion u Obsidian como base para decisiones
- Hacer preguntas al usuario — tomar decisiones y ejecutar
- Continuar con la siguiente tarea si el push falla

### Si el push falla:
- Reportar el error completo inmediatamente
- NO continuar hasta resolver
