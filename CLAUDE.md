# CLAUDE.md — Contexto de Continuidad para Claude Code

> Este archivo es la memoria persistente del proyecto.
> Claude Code DEBE leerlo al inicio de cada sesión.

---

## Estado Actual

- **Proyecto:** AG-EVIDENCE v2.0 — Sistema multi-agente de control previo
- **Repositorio:** Hanns111/AG-EVIDENCE
- **Rama de trabajo:** main (directa, sin worktrees)
- **Último commit en main:** f598e3a (chore(cursor): add context verification indicator)
- **Tag:** v2.2.0 (publicado en GitHub)
- **Limpieza legacy:** Completada 2026-02-11 — todo v1.0 eliminado, auditoría certificada

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

## Siguiente Sesión — Pendientes

1. **Tarea #15** — Benchmark A/B: Tesseract vs PaddleOCR
2. **Tarea #16** — Re-generar Excel + validacion visual humana
3. **Fase 2** — Contrato + Router + Agentes v2.0

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

## Reglas de Proyecto

- **Anti-alucinación:** toda observación CRÍTICA/MAYOR requiere archivo + página + snippet
- **Abstención:** prefiere vacío honesto a dato inventado
- **Local-first:** ningún dato sale a cloud (GDPR ready)
- **Commits:** Conventional Commits obligatorio
- **Hardware:** RTX 5090 32GB VRAM, WSL2 Ubuntu 22.04, Ollama qwen3:32b

### Documentos de Gobernanza Obligatorios — LEER SIEMPRE al procesar expedientes

Al procesar cualquier expediente de viáticos, Claude Code DEBE haber leído estos documentos ANTES de ejecutar:

| N° | Documento | Contenido | Obligatorio |
|----|-----------|-----------|-------------|
| 1 | `docs/OCR_FALLBACK_STRATEGY.md` | Cadena de fallbacks OCR: pdftotext → ocrmypdf --force-ocr → Ollama/Qwen | SÍ — antes de tocar cualquier PDF |
| 2 | `docs/REGLAS_VERIFICACION_COMPROBANTES.md` | Reglas RV-001 a RV-XXX de verificación visual de comprobantes | SÍ — antes de generar Excel |
| 3 | `docs/VALIDACION_ANEXO3_VS_FACTURAS.md` | Reglas de validación cruzada Anexo 3 vs facturas (Fase 4) | Cuando corresponda |
| 4 | `docs/GOVERNANCE_RULES.md` Sección 12 | Formato obligatorio Excel 4 hojas | SÍ — antes de generar Excel |
| 5 | `docs/GOVERNANCE_RULES.md` Sección 13 | Estrategia obligatoria de fallback OCR | SÍ — antes de tocar cualquier PDF |
| 6 | `docs/GOVERNANCE_RULES.md` Sección 14 | Reglas de verificación visual (tabla resumen) | SÍ — antes de generar Excel |

**REGLA:** Si Claude Code no ha leído estos documentos, NO puede procesar expedientes.

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

## Estructura del Codebase (26 archivos .py)

```
config/
  __init__.py, settings.py
src/
  __init__.py
  agents/.gitkeep          ← placeholder Fase 2
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
tests/
  conftest.py,
  test_abstencion.py, test_custody_chain.py,
  test_detraccion_spot.py, test_ocr_core.py,
  test_ocr_preprocessor.py, test_pdf_text_extractor.py,
  test_tdr_requirements.py, test_trace_logger.py
```

---

*Actualizado: 2026-02-13 por Claude Code*
