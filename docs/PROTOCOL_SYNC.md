# Protocolo de Sincronizacion entre IAs — AG-EVIDENCE

> **Identificador:** GOV_PROTOCOL_SYNC_v1
> **Fecha:** 2026-03-02
> **Aprobado por:** Hans
> **Estado:** VIGENTE

---

## 1. Problema que resuelve

Multiples IAs participan en el desarrollo de AG-EVIDENCE:
- **Claude Code:** Implementador (codigo, tests, docs, pipelines)
- **Codex:** Auditor (verificacion de calidad y completitud)
- **ChatGPT:** Coordinacion y arquitectura de alto nivel (puntual)

Codex opera en un **sandbox aislado** que no comparte el mismo arbol de trabajo
ni el mismo commit SHA que Claude Code. Esto genera desalineaciones constantes
cuando Codex audita "estado percibido" en vez de artefactos inmutables.

**Regla fundamental:** La auditoria NUNCA se basa en estado percibido del repo.
Se basa EXCLUSIVAMENTE en artefactos inmutables entregados explicitamente.

---

## 2. Artefactos validos para auditoria

Codex solo puede auditar UNO de los siguientes:

| Artefacto | Descripcion | Cuando usarlo |
|-----------|-------------|---------------|
| **Commit SHA** | Hash completo de un commit especifico | Verificar un cambio puntual |
| **Pull Request** | PR en GitHub con diff visible | Verificar un bloque de trabajo |
| **Paquete de Auditoria** | Archivo estructurado generado por Claude Code | Verificacion formal de fase/tarea |

**Prohibido:** Codex NO debe asumir estado del repo, inferir cambios fuera
del diff entregado, ni reportar HEADs de su sandbox como fuente de verdad.

---

## 3. Paquete de Auditoria — Formato obligatorio

Cada entrega de Claude Code incluye este bloque:

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

### 3.1 Generacion del patch (opcional, para auditoria profunda)

```bash
git diff origin/main...HEAD > audit.patch
```

Este archivo se puede entregar a Codex como insumo unico de auditoria.

---

## 4. Responsabilidades

### Claude Code (Implementador)
- Genera el Paquete de Auditoria al cerrar cada tarea o fase
- Garantiza que el SHA reportado corresponde a un commit pusheado a origin
- No entrega "estados" — entrega artefactos concretos
- Incluye salida real de tests (no narrativa)

### Codex (Auditor)
- Audita UNICAMENTE el contenido del paquete/patch/PR entregado
- No asume estado adicional del repo
- No infiere cambios fuera del diff entregado
- Si detecta inconsistencia en el paquete, la reporta como hallazgo
- Su HEAD local es IRRELEVANTE para la auditoria

### Hans (Aprobador)
- Valida decision GO/NO-GO
- Puede solicitar auditoria adicional via PR o patch
- Arbitra desacuerdos entre implementador y auditor

---

## 5. Flujo operativo

```
Claude Code termina bloque de trabajo
    |
    v
Commit + Push a origin/main (o branch)
    |
    v
Genera Paquete de Auditoria (formato seccion 3)
    |
    v
Hans entrega paquete a Codex
    |
    v
Codex audita SOLO el paquete (no su estado local)
    |
    v
Codex entrega hallazgos (si los hay)
    |
    v
Hans decide: GO / NO-GO / corregir
```

---

## 6. Integracion con protocolos existentes

- **SESSION_PROTOCOL.md:** El Paquete de Auditoria es una extension del
  bloque `=== EVIDENCIA DE CIERRE ===` ya existente. Ambos son obligatorios.
- **CLAUDE.md:** Referencia a este protocolo en seccion de reglas.
- **ROADMAP.md:** Referencia a este protocolo en notas de gobernanza.

---

## 7. Vigencia

Este protocolo es **obligatorio desde 2026-03-02** para toda entrega
de codigo, documentacion o cambio en el proyecto AG-EVIDENCE.

No requiere herramientas nuevas. Requiere disciplina de entrega.

---

*Documento creado por Claude Code, aprobado por Hans — 2026-03-02*
