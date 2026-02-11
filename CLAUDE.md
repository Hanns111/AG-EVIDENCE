# CLAUDE.md — Contexto de Continuidad para Claude Code

> Este archivo es la memoria persistente del proyecto.
> Claude Code DEBE leerlo al inicio de cada sesión.

---

## Estado Actual

- **Proyecto:** AG-EVIDENCE v2.0 — Sistema multi-agente de control previo
- **Repositorio:** Hanns111/AG-EVIDENCE
- **Worktree activo:** claude/serene-faraday
- **Rama de trabajo:** claude/serene-faraday → merge fast-forward a main
- **Último commit en main:** ac8ae15 (docs: enterprise README + CHANGELOG + pyproject.toml)
- **Tag:** v2.2.0 (publicado en GitHub)

---

## Última Tarea Completada

- **Tarea #11** — Logger estructurado JSONL con trace_id (src/ingestion/trace_logger.py)
- 638 líneas, 55 tests pasando, mergeada a main (ccc5022)

## Siguiente Sesión — Pendientes

1. **Limpiar archivos legacy** (necesita aprobación de Hans):
   - Sin trackear: _check_models.py, _check_pdf.py, _generar_imagenes.py, _test_vlm.py, extraer_comprobantes_vlm.py, procesar_comprobantes_skills.py, docs/PLAN_REFACTORIZACION_v2.md, src/tools/calidad_visual.py, src/tools/detector_paginas_comprobantes.py, src/tools/skills/
   - Tracked legacy: CONTEXTO_PARA_CHATGPT.md, PROBLEMA_READPDFX.md, VALIDACION_OCR_WSL.md, __init__.py (raíz), chat_directiva.py
2. **Tarea #12** — Siguiente en Fase 1: Trazabilidad + OCR
   - Consultar tablero Notion para detalles

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

---

## Progreso por Fases

| Fase | Estado | Tareas |
|------|--------|--------|
| 0: Setup | ✅ Completada | #1-9 |
| 1: Trazabilidad + OCR | 🔵 En progreso | #10 ✅, #11 ✅, #12-16 pendientes |
| 2: Contrato + Router | ⬜ Pendiente | #17-21 |
| 3: Qwen Fallback | ⬜ Pendiente | #22-26 |
| 4: Validaciones | ⬜ Pendiente | #27-29 |
| 5: Evaluación + Legal prep | ⬜ Pendiente | #30-34 |
| 6: Motor Legal | ⬜ Pendiente | #35-40 |

---

*Actualizado: 2026-02-10 por Claude Code*
