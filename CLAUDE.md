# CLAUDE.md — Contexto de Continuidad para Claude Code

> Este archivo es la memoria persistente del proyecto.
> Claude Code DEBE leerlo al inicio de cada sesión.

---

## Estado Actual

- **Proyecto:** AG-EVIDENCE v2.0 — Sistema multi-agente de control previo
- **Repositorio:** Hanns111/AG-EVIDENCE
- **Rama de trabajo:** main (directa, sin worktrees)
- **Último commit en main:** (ver git log, se actualiza frecuentemente)
- **Tag:** v2.2.0 (publicado en GitHub)
- **Limpieza legacy:** Completada 2026-02-11 — todo v1.0 eliminado, auditoría certificada
- **OCR Engine:** PaddleOCR 3.4.0 PP-OCRv5 server GPU (ADR-008) + Tesseract fallback
- **VLM Engine:** Ollama 0.16.2 + Qwen2.5-VL-7B (Q4_K_M, 6GB) — ADR-009
- **DuckDB:** 1.4.4 instalado (base analitica)

---

## Última Tarea Completada

- **Tarea #14** — Extender ResultadoPagina con bbox + confianza por linea (+ TraceLogger)
- LineaOCR dataclass: bbox (Optional), confianza (Optional), motor
- PaddleOCR: extrae dt_polys → _polygon_to_bbox()
- Tesseract: agrupa palabras por (block_num, line_num) → lineas con bbox
- TraceLogger integrado en ejecutar_ocr() via duck typing
- +815 lineas, 44 tests nuevos (274 totales, 0 failures), commit e6a3229
- Version: 3.0.0 → 3.1.0

## Tareas Anteriores Relevantes

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

## Siguiente Sesión — Pendientes

1. **Procesar expediente DIRI2026-INT-0068815 completo** — Script con estrategia mixta + Excel 4 hojas
2. **Tarea #16** — Re-generar Excel con pipeline formal
3. Reprocesar Caja Chica N.3 con pipeline formal
4. **Fase 2** — Contrato + Router + Agentes v2.0

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

### Decisión Arquitectónica Pendiente de Implementación

**Integrity Checkpoint** (se implementa en Tarea #18):
- Nodo formal en el Router LangGraph, NO módulo monolítico separado (ADR-005)
- Evalúa `integrity_status = OK | WARNING | CRITICAL`. Si CRITICAL → pipeline se detiene
- Incluye EvidenceEnforcer (snippet + página + regla) post-contrato tipado
- Decisión consensuada en sesión multi-IA (2026-02-11)

---

## Tracking en Notion

- **Tablero:** "Tablero de Tareas AG-EVIDENCE" (DB: 6003e907-28f5-4757-ba93-88aa3efe03e1)
- **Data source:** collection://16c577cf-e572-45a0-8cad-5e64ebd56d9f
- **Bitácora:** 303b188d-be2e-8135-899b-d209caf42dc9
- **Plan de Desarrollo:** 303b188d-be2e-8193-85f5-f6861c924539
- **Glosario Técnico:** collection://bffe2c97-e824-459b-af01-febd94f54dec
- **Árbol de Ramas:** 303b188d-be2e-81a7-b38a-d42b811a9832

### Protocolo Notion obligatorio:
1. Antes de empezar una tarea → marcar 🔵 En Progreso
2. Al terminar → marcar ✅ Completado + Fecha Real + Ejecutado Por + Bitácora
3. Actualizar página Bitácora de Actividades con cada acción relevante
4. Si cambia algo del plan → avisar a Hans

---

## Protocolo Cursor + Claude Code

### Claude Code hace:
- Arquitectura, módulos nuevos, pipelines multi-archivo
- Cambios en docs/ de gobernanza
- Merges y gestión de ramas
- Actualización de Notion
- Creación de tests complejos

### Cursor hace:
- Ediciones puntuales dentro de archivos existentes
- Refactors locales (renombrar variable, extraer función)
- Revisión visual de código
- Completado de funciones individuales
- Debug rápido con contexto de un solo archivo

### Cursor NO debe:
- Crear carpetas ni mover archivos entre módulos
- Modificar docs/ de gobernanza
- Crear worktrees, ramas ni hacer merge
- Tocar archivos protegidos sin aprobación

### Archivos protegidos (ambos necesitan aprobación):
- docs/AGENT_GOVERNANCE_RULES.md
- docs/GOVERNANCE_RULES.md
- docs/PROJECT_SPEC.md
- AGENTS.md
- .cursorrules
- .cursor/mcp.json
- CLAUDE.md (este archivo)

### Gobernanza Cursor — Cuándo y cómo usarlo:
Claude Code es quien decide cuándo Cursor debe actuar.
Cuando sea necesario, Claude Code le dará a Hans:
1. El prompt EXACTO para pegar en Cursor
2. Qué archivo(s) debe editar Cursor
3. Qué resultado se espera
4. Hans pega el prompt en Cursor, obtiene resultado, y se lo muestra a Claude Code
5. Claude Code valida el resultado y lo registra en Notion (Ejecutado Por: Cursor)
Si Cursor hace algo fuera de protocolo, Hans avisa a Claude Code para corregir.
Los guardrails de Cursor están en .cursorrules (sección GUARDRAILS, reglas G1-G12).

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

---

## Reglas de Proyecto

- **Anti-alucinación:** toda observación CRÍTICA/MAYOR requiere archivo + página + snippet
- **Abstención:** prefiere vacío honesto a dato inventado
- **Local-first:** ningún dato sale a cloud (GDPR ready)
- **Commits:** Conventional Commits obligatorio
- **Hardware:** RTX 5090 24GB VRAM (Laptop), WSL2 Ubuntu 22.04
- **LLM texto:** Ollama + qwen3:32b
- **VLM vision:** Ollama + qwen2.5vl:7b (extraccion de comprobantes)
- **Session Protocol:** Ver governance/SESSION_PROTOCOL.md (commit incremental obligatorio)
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
| 1: Trazabilidad + OCR | 🔵 En progreso | #10 ✅, #11 ✅, #12 ✅, #13 ✅, #14 ✅, #15-16 pendientes |
| 2: Contrato + Router | ⬜ Pendiente | #17-21 |
| 3: Qwen Fallback | ⬜ Pendiente | #22-26 |
| 4: Validaciones | ⬜ Pendiente | #27-29 |
| 5: Evaluación + Legal prep | ⬜ Pendiente | #30-34 |
| 6: Motor Legal | ⬜ Pendiente | #35-40 |

---

## Estructura del Codebase

```
config/
  __init__.py, settings.py
governance/
  SESSION_PROTOCOL.md       ← protocolo de apertura/cierre de sesión
src/
  __init__.py
  agents/.gitkeep           ← placeholder Fase 2
  extraction/
    __init__.py, abstencion.py
  ingestion/
    __init__.py, config.py, custody_chain.py,
    pdf_text_extractor.py, trace_logger.py
  ocr/
    __init__.py, core.py
  rules/
    __init__.py, detraccion_spot.py, integrador.py, tdr_requirements.py
  tools/
    __init__.py, ocr_preprocessor.py
scripts/
  backup_local.py           ← backup ZIP del proyecto completo
  extraer_con_qwen_vl.py    ← Fase A: extraccion con Qwen2.5-VL via Ollama
  explorar_expediente.py    ← PyMuPDF + PaddleOCR para explorar PDFs
  extraer_expediente_diri.py ← Extraccion texto completa del expediente
  generar_excel_expediente.py
  generar_excel_DIRI2026.py ← Excel con datos hardcoded (referencia)
  generar_excel_OTIC2026.py
  setup_ollama.sh           ← Setup Ollama server en WSL2
tests/
  conftest.py,
  test_abstencion.py, test_custody_chain.py,
  test_detraccion_spot.py, test_ocr_core.py,
  test_ocr_preprocessor.py, test_pdf_text_extractor.py,
  test_tdr_requirements.py, test_trace_logger.py
data/
  directivas/               ← PDFs locales (NO en git, ver INVENTARIO_DIRECTIVAS.md)
  expedientes/              ← PDFs sensibles (NO en git)
  normativa/                ← JSON de reglas (SÍ en git)
```

---

*Actualizado: 2026-02-18 por Claude Code*
