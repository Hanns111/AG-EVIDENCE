# CLAUDE.md — Contexto de Continuidad para Claude Code

> Este archivo es la memoria persistente del proyecto.
> Claude Code DEBE leerlo al inicio de cada sesión.

---

## Estado Actual

- **Proyecto:** AG-EVIDENCE v2.0 — Sistema multi-agente de control previo
- **Repositorio:** Hanns111/AG-EVIDENCE
- **Worktree activo:** claude/serene-faraday
- **Rama de trabajo:** claude/serene-faraday → merge fast-forward a main
- **Último commit en main:** 04ffc7d (feat: custody chain)

---

## Última Tarea Completada

- **Tarea #10** — Cadena de custodia (src/ingestion/custody_chain.py)
- 529 líneas, 27 tests pasando, mergeada a main

## Siguiente Tarea

- **Tarea #11** — Logger estructurado JSONL con trace_id
- Fase 1: Trazabilidad + OCR

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
| 1: Trazabilidad + OCR | 🔵 En progreso | #10 ✅, #11-16 pendientes |
| 2: Contrato + Router | ⬜ Pendiente | #17-21 |
| 3: Qwen Fallback | ⬜ Pendiente | #22-26 |
| 4: Validaciones | ⬜ Pendiente | #27-29 |
| 5: Evaluación + Legal prep | ⬜ Pendiente | #30-34 |
| 6: Motor Legal | ⬜ Pendiente | #35-40 |

---

*Actualizado: 2026-02-11 por Claude Code*
