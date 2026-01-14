# CONTEXT_CHAIN – CADENA DE CONTINUIDAD ENTRE SESIONES E IAs

## Propósito

Este archivo define **cómo continuar el proyecto sin perder coherencia**
cuando se termina la ventana de contexto o se cambia de herramienta
(ChatGPT, Cursor, Claude, Gemini).

---

## 1. Regla de Inicio Universal (Obligatoria)

En CADA nuevo chat o IA, el prompt inicial debe ser exactamente:

```
Actúa como Ingeniero Senior y Tech Lead del proyecto AG-EVIDENCE.
Lee PROJECT_SPEC.md, ARCHITECTURE.md, HARDWARE_CONTEXT.md,
GOVERNANCE_RULES.md, ADR.md y CURRENT_STATE.md antes de responder.
Respeta estrictamente su contenido.
No propongas cambios de stack ni arquitectura sin justificar en ADR.
Confirma con "Contexto cargado" antes de continuar.
```

Si la IA no confirma, se detiene la interacción.

---

## 2. Archivos Estables vs Archivos Vivos

### Archivos ESTABLES (no cambian salvo decisión estructural):

- PROJECT_SPEC.md
- ARCHITECTURE.md
- HARDWARE_CONTEXT.md
- GOVERNANCE_RULES.md
- ADR.md

### Archivos VIVOS (cambian con frecuencia):

- CURRENT_STATE.md
- CONTEXT_CHAIN.md

---

## 3. Quién Decide los Cambios

La IA NO cambia archivos por iniciativa propia.

La IA DEBE:
- Detectar cuando un cambio es necesario
- Proponer explícitamente:
  - Qué archivo cambiar
  - Por qué
  - Impacto

El usuario decide si se aplica.

---

## 4. Regla de Fin de Sesión

Si ocurre cualquiera de estos eventos:
- Conversación larga
- Cambio de IA
- Cambio de herramienta
- Dudas de coherencia

La IA debe proponer:

1. Generar resumen
2. Actualizar CURRENT_STATE.md
3. Commit de documentación
4. Reiniciar chat limpio

---

## 5. Regla de Enlace Manual

Antes de cambiar de chat o IA:

- Copiar CURRENT_STATE.md actualizado
- Abrir nuevo chat
- Usar la Regla de Inicio Universal
- Continuar desde allí

Este archivo es el "cable" que une todas las sesiones.

---

## 6. Autoridad

Si una IA ignora este archivo:
- Sus respuestas se consideran inválidas
- Se debe reiniciar la sesión

Este archivo garantiza continuidad, no memoria implícita.
