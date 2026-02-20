# SESSION_PROTOCOL.md — Protocolo de Apertura y Cierre de Sesion

> **Regla:** Claude Code DEBE ejecutar estos checklists automaticamente.
> Si Hans olvida pedirlo, Claude Code lo ejecuta igual.

---

## APERTURA DE SESION

### Prompt recomendado de Hans:
```
Proyecto AG-EVIDENCE. Lee CLAUDE.md. Verifica estado del repo.
Consulta Notion si es necesario. Resume donde estamos y propon siguiente paso.
```

### Checklist que Claude Code ejecuta SIEMPRE al iniciar:

1. **Leer CLAUDE.md** como fuente principal de contexto
2. **git log --oneline -5** para verificar ultimo commit real
3. **git status** para detectar cambios no commiteados
4. **Comparar** estado documentado vs estado real del repo
5. **Consultar Notion** (Tablero de Tareas) si hay discrepancia
6. **Resumir** a Hans:
   - Ultima tarea completada
   - Tarea en progreso (si hay)
   - Siguiente tarea pendiente
   - Cualquier anomalia detectada
7. **Proponer siguiente paso** sin ejecutar cambios hasta confirmacion

### Si Hans NO dice nada especifico:
Claude Code ejecuta pasos 1-7 de todas formas y pregunta:
"He verificado el estado. Estamos en [X]. Quieres continuar con [Y]?"

---

## CIERRE DE SESION

### Prompt recomendado de Hans:
```
Cierre de sesion.
```

### Checklist que Claude Code ejecuta SIEMPRE al cerrar:

1. **Verificar cambios pendientes:**
   - `git status` — hay archivos modificados sin commit?
   - `git diff --stat` — que cambio exactamente?

2. **Commit si hay cambios:**
   - Conventional Commits obligatorio
   - Mensaje claro y descriptivo
   - NO commitear archivos sensibles (.env, credentials, PDFs de expedientes)

3. **Push a GitHub:**
   - `git push origin main`
   - Verificar que el push fue exitoso

4. **Actualizar CLAUDE.md** si cambio:
   - Estado actual del proyecto
   - Ultima tarea completada
   - Siguiente tarea pendiente
   - Cualquier decision arquitectonica nueva

5. **Registrar en Bitacora Notion:**
   - Fecha, hora, ejecutor, accion, resultado
   - Codigo de tarea si aplica

6. **Actualizar Tablero Notion:**
   - Marcar tareas completadas
   - Actualizar fechas reales
   - Actualizar campo "Ejecutado Por"

7. **Generar resumen de sesion** para Hans:
   - Que se hizo
   - Que quedo pendiente
   - Proximo paso recomendado

### Si Hans cierra sin decir nada:
**PROBLEMA:** Claude Code no puede ejecutar automaticamente si la sesion se cierra.

### Solucion implementada — Proteccion contra cierre sin guardar:

**Estrategia 1: Commits frecuentes (PRINCIPAL)**
- Claude Code hace commit + push despues de CADA tarea completada
- No acumula cambios para "el final"
- Si Hans cierra la ventana, maximo se pierde el trabajo en progreso actual

**Estrategia 2: CLAUDE.md como checkpoint**
- Claude Code actualiza CLAUDE.md despues de cada tarea importante
- El archivo siempre refleja el ultimo estado estable
- La siguiente sesion puede reconstruir desde ahi

**Estrategia 3: Notion como respaldo externo**
- Cada tarea completada se documenta en Notion inmediatamente
- No se espera al "cierre" para documentar
- Si se pierde una sesion, Notion tiene el registro

**Regla de oro:** Si una tarea se completo, ya debe estar:
- Commiteada en git
- Pusheada a GitHub
- Documentada en Notion
ANTES de empezar la siguiente tarea.

---

## PROTOCOLO DE COMMIT INCREMENTAL

Para evitar perdida de trabajo, Claude Code sigue este flujo:

```
TAREA COMPLETADA
    |
    v
1. git add [archivos especificos]
2. git commit -m "tipo(scope): descripcion"
3. git push origin main
4. Actualizar Notion (tarea + bitacora)
5. Actualizar CLAUDE.md si es necesario
    |
    v
SIGUIENTE TAREA
```

**NUNCA** se acumulan multiples tareas sin commit.
**NUNCA** se deja un push para "despues".

---

## PROTOCOLO OPERATIVO POR HITO (OBLIGATORIO)

> **Adoptado:** 2026-02-19 por instrucción directa de Hans.
> **Regla:** Este protocolo se ejecuta SIN que Hans lo recuerde.
> Sin bloque de evidencia completo, NO se autoriza PR/push ni avance al siguiente hito.

### 1. Pre-check al iniciar hito

Claude Code ejecuta ANTES de escribir cualquier línea de código:

```bash
git status --short --branch
git rev-parse --short HEAD
```

- Confirmar rama objetivo (main u otra)
- Confirmar sincronización con origin/main
- Reportar resultado a Hans

### 2. Cierre de hito con bloque de evidencia completo

Al terminar CADA hito, Claude Code genera este bloque COMPLETO:

```
=== EVIDENCIA DE CIERRE — [Tarea #XX Hito Y] ===

1. Estado git:
   $ git status --short --branch
   [salida real]

2. Commit:
   $ git rev-parse --short HEAD
   [hash]
   $ git show --stat --name-only [hash]
   [salida real]

3. Tests:
   $ pytest [ruta] -v
   [salida real con números exactos: passed, skipped, failed]

4. Archivos tocados (ruta exacta):
   - src/...
   - tests/...

5. Riesgos abiertos:
   - [lista o "Ninguno"]

6. Decisión: GO / NO-GO
   [justificación]

=== FIN EVIDENCIA ===
```

### 3. Regla de control

- **Sin bloque de evidencia completo → NO se autoriza push ni avance.**
- Si un hito falla tests o tiene riesgos CRITICAL → NO-GO obligatorio.
- Hans puede overridear un NO-GO con instrucción explícita.

### 4. Documentación obligatoria por hito

Después de cada hito completado, actualizar:

| Documento | Siempre | Condicional |
|-----------|---------|-------------|
| ROADMAP.md | ✅ | — |
| CLAUDE.md | ✅ | — |
| docs/CURRENT_STATE.md | — | Si cambia flujo, módulo nuevo, o cambio de fase |
| Notion Tarea (tablero) | ✅ | — |
| Notion Bitácora | ✅ | — |
| Notion Dashboard | — | Si cambia progreso de fase |

### 5. Reconciliación semanal

Una vez por semana (o al inicio de sesión si pasó >3 días):

- Listar ramas/worktrees activas: `git worktree list`
- Reportar divergencias entre main y origin/main
- Verificar que Notion refleja estado real del tablero
- Reportar anomalías a Hans

---

## FUENTES DE VERDAD

| Fuente | Contenido | Prioridad |
|--------|-----------|-----------|
| **Codigo en main** | Estado real del sistema | 1 (maxima) |
| **CLAUDE.md** | Contexto y estado documentado | 2 |
| **Notion Tablero** | Tracking de tareas y progreso | 3 |
| **Notion Bitacora** | Registro cronologico de acciones | 4 |

Si hay discrepancia, el codigo en main siempre tiene razon.

---

*Creado: 2026-02-13 por Claude Code*
*Protocolo por hito agregado: 2026-02-19 por instrucción de Hans*
*Archivo protegido: requiere aprobacion de Hans para modificar*
