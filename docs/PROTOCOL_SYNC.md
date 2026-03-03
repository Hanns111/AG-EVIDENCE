# Protocolo de Sincronizacion entre IAs — AG-EVIDENCE

> **Identificador:** GOV_PROTOCOL_SYNC_v2
> **Fecha:** 2026-03-02
> **Aprobado por:** Hans
> **Estado:** VIGENTE
> **Cambio v2:** Swap de roles — Codex = Implementador, Claude Code = Auditor

---

## 1. Problema que resuelve

Multiples IAs participan en el desarrollo de AG-EVIDENCE:
- **Codex CLI:** Implementador (codigo, tests, docs, pipelines)
- **Claude Code:** Auditor (verificacion de calidad y completitud)
- **ChatGPT:** Coordinacion y arquitectura de alto nivel (puntual)

**Razon del swap (v2):** Codex CLI es mas rapido ejecutando codigo. Claude Code
es mas reflexivo y analitico, ideal para auditoria.

**Regla fundamental:** La auditoria NUNCA se basa en estado percibido del repo.
Se basa EXCLUSIVAMENTE en artefactos inmutables (commits, diffs, tests).

---

## 2. Artefactos validos para auditoria

Claude Code (auditor) puede verificar trabajo usando:

| Artefacto | Descripcion | Cuando usarlo |
|-----------|-------------|---------------|
| **Commit SHA** | Hash completo de un commit especifico | Verificar un cambio puntual |
| **Pull Request** | PR en GitHub con diff visible | Verificar un bloque de trabajo |
| **Diff directo** | `git diff` sobre el repo local | Auditoria en tiempo real |
| **Paquete de Auditoria** | Bloque estructurado de 8 secciones | Verificacion formal de fase/tarea |

**Ventaja v2:** Claude Code tiene acceso directo al repo, puede inspeccionar
archivos, ejecutar tests y revisar diffs sin necesidad de paquetes intermedios.

---

## 3. Paquete de Auditoria — Formato obligatorio

Para entregas formales (cierre de tarea/fase), se genera este bloque:

```
=== PAQUETE DE AUDITORIA — [Tarea #XX / Fase Y] ===

1. BRANCH
   Nombre: <branch>
   Base: origin/main @ <hash>

2. COMMIT
   SHA: <hash completo>
   Mensaje: <mensaje del commit>

3. DIFFSTAT
   <salida de: git diff --stat origin/main...HEAD>

4. TESTS
   Comando: pytest <tests> -v
   Resultado: <N passed, M failed, K skipped>
   Salida completa: <pegada o referenciada>

5. ARCHIVOS TOCADOS
   Nuevos: <lista>
   Modificados: <lista>
   Eliminados: <lista>

6. ARTEFACTOS GENERADOS
   <Excel, JSON, logs, etc. con rutas>

7. RIESGOS ABIERTOS
   <lista o "Ninguno">

8. DECISION
   GO / NO-GO — <justificacion basada en evidencia>

=== FIN PAQUETE ===
```

### 3.1 Generacion del paquete

```bash
python scripts/generar_paquete_auditoria.py --tarea 22 --fase 3
```

---

## 4. Responsabilidades

### Codex CLI (Implementador)
- Escribe codigo, tests y documentacion
- Ejecuta pipeline, OCR, procesamiento
- Hace commit + push al terminar
- Pasa ruff check + pytest antes de cada commit
- Genera Paquete de Auditoria al cerrar tarea/fase (opcional: Claude Code puede generarlo)

### Claude Code (Auditor)
- Revisa diffs, tests, coherencia del trabajo de Codex
- Puede inspeccionar el repo directamente (tiene acceso completo)
- Ejecuta `python scripts/audit_repo_integrity.py` (8 checks)
- Verifica alineacion con ROADMAP.md, CLAUDE.md, CURRENT_STATE.md
- Emite veredicto: CONFORME / NO CONFORME / INCIERTO
- Actualiza Notion (Bitacora, Dashboard)

### Hans (Aprobador)
- Valida decision GO/NO-GO
- Puede solicitar auditoria adicional via PR o patch
- Arbitra desacuerdos entre implementador y auditor

---

## 5. Flujo operativo

```
Hans asigna tarea (Notion o chat)
    |
    v
Codex CLI implementa: codigo + tests + docs
    |
    v
Codex CLI: ruff check + pytest + commit + push
    |
    v
Hans pide a Claude Code: "audita el trabajo de Codex"
    |
    v
Claude Code audita: revisa diff, tests, coherencia, integrity
    |
    v
Claude Code emite veredicto (CONFORME / NO CONFORME / INCIERTO)
    |
    v
Hans decide: GO / NO-GO / corregir
```

---

## 6. Formato de Auditoria de Claude Code

```
=== AUDITORIA CLAUDE CODE — [Tarea #XX] ===
SHA auditado: <hash>
Fecha: <fecha>

VEREDICTO: CONFORME / NO CONFORME / INCIERTO

HALLAZGOS:
1. [TIPO] Descripcion — SHA: <hash>, evidencia: <cita>
2. ...

RECOMENDACION:
<accion sugerida si aplica>

=== FIN AUDITORIA ===
```

---

## 7. Integracion con protocolos existentes

- **SESSION_PROTOCOL.md:** El Paquete de Auditoria es una extension del
  bloque `=== EVIDENCIA DE CIERRE ===` ya existente. Ambos son obligatorios.
- **CLAUDE.md:** Referencia a este protocolo en seccion de reglas.
- **CODEX.md:** Instrucciones de implementador para Codex CLI.
- **ROADMAP.md:** Referencia a este protocolo en notas de gobernanza.

---

## 8. Vigencia

Este protocolo es **obligatorio desde 2026-03-02** para toda entrega
de codigo, documentacion o cambio en el proyecto AG-EVIDENCE.

No requiere herramientas nuevas. Requiere disciplina de entrega.

---

*Documento creado por Claude Code, aprobado por Hans — 2026-03-02*
*v2: Swap de roles (Codex = Implementador, Claude Code = Auditor) — 2026-03-02*
