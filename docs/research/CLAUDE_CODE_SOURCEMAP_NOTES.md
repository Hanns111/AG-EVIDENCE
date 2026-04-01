# Notas de investigación — Source map de Claude Code (referencia externa)

**Estado:** Documento de **investigación / benchmark conceptual**  
**Fecha:** 2026-03-31  
**Alcance:** Este archivo **no** modifica código, **no** incorpora el `.map` al pipeline y **no** relaja reglas probatorias de AG-EVIDENCE.

---

## 1. Qué es el archivo `.map` en este contexto

En inspección local de `CLAUDE_SOURCE_FINAL_60MB.map` (véase §2), el fichero es un **source map de JavaScript** típico del ecosistema bundler: un JSON muy grande que incluye entre otros:

- Un arreglo **`"sources"`** con miles de rutas relativas a módulos empaquetados (p. ej. `../node_modules/lodash-es/...`).
- Fragmentos de **código fuente** embebidos (strings) correspondientes a ese bundle (TypeScript/JavaScript transpilado de herramientas CLI, SDK, integraciones MCP, etc.).

**Qué no es:** no es un manual de AG-EVIDENCE, no es una especificación normativa MINEDU/SUNAT y no es un artefacto que AG-EVIDENCE deba cargar en tiempo de ejecución.

---

## 2. Ubicación (fuente **externa** al repositorio)

| Propiedad | Valor |
|-----------|--------|
| **Ruta local (máquina Hans)** | `C:\Users\Hans\Proyectos\CLAUDE_SOURCE_FINAL_60MB.map` |
| **Tamaño aproximado** | ~60 MB (orden de decenas de millones de caracteres en el JSON) |
| **Versionado en git AG-EVIDENCE** | **No** — permanece fuera del repo (véase ADR-013 y `.gitignore` para patrones que evitan copias accidentales). |

---

## 3. Por qué se considera fuente técnica relevante (para lectura humana / IA)

1. **Evidencia de implementación real** de un producto de asistente con herramientas (read/write/grep/bash, MCP, mensajes estructurados), no un tutorial genérico.
2. **Contraste útil** con AG-EVIDENCE: el asistente comercial prioriza **autonomía operativa del usuario** y **orquestación genérica**; AG-EVIDENCE prioriza **determinismo probatorio**, **abstención** y **trazabilidad sobre expedientes**.
3. **Referencia de patrones de ingeniería** (modularidad de tools, manejo de binarios vs texto, bucles de tool-use) que pueden **inspirar discusiones de diseño** sin copiar código ni comportamiento.

---

## 4. Hallazgos conceptuales útiles (basados en **grep / inspección local** del `.map`)

Los siguientes puntos se obtienen por **búsqueda textual** dentro de `CLAUDE_SOURCE_FINAL_60MB.map`; no se infiere el comportamiento en runtime del producto Anthropic ni se afirma paridad con una versión concreta publicada.

### 4.1 Multimodalidad imagen → modelo

- Aparece la clase/documentación **`ToolError`** con ejemplo de bloques de contenido que incluyen `{ type: 'image', source: { type: 'base64', ... } }`, es decir, el stack contempla **pasar imágenes estructuradas** en resultados de herramienta (observado en el string embebido del `.map`).

### 4.2 Tooling modular

- Referencias explícitas a herramientas nombradas y rutas de implementación, p. ej.:
  - **`BetaToolRunner`** (orquestación de herramientas en flujo con mensajes beta),
  - constantes como **`FILE_READ_TOOL_NAME`** / módulos `FileReadTool`, `FileWriteTool`, `BASH_TOOL_NAME`, integración **MCP** (`CallToolResult`, hosts de docs map URL, etc.).
- Listas de extensiones **binarias** para saltar operaciones “solo texto”, con comentario observado: *«PDF is here; FileReadTool excludes it at the call site»* — separación explícita entre lectura de texto y manejo de PDF/binarios a nivel de herramienta.

### 4.3 Manejo de contexto

- Constantes y prompts que organizan **entrada/salida de terminal** (`BASH_INPUT_TAG`, `BASH_STDOUT_TAG`, …) para que el modelo distinga **salida de shell** de **prompt de usuario**.
- Textos de herramientas tipo **`SendUserMessage` / `Brief`** que enfatizan que **lo que el usuario lee de verdad** va en un canal explícito (adjuntos, markdown) — patrón de **enrutamiento de atención** en conversaciones largas.

### 4.4 Bucles / “agencia” como referencia **solo conceptual**

- `BetaToolRunner` y patrones de **tool loop** (iteraciones, compactación opcional mencionada en strings como `DEFAULT_TOKEN_THRESHOLD` / summaries) muestran cómo un sistema **agentico** encadena pasos hasta una condición de parada.
- **Para AG-EVIDENCE:** esto sirve para **vocabulario y anti-patrones** (“no replicar un REPL autónomo sobre expedientes”), **no** como plantilla operativa.

### 4.5 Separación tool orchestration vs extracción de dominio

- En el `.map`, la capa de **invocación de tools** y la de **SDK de mensajes** (Anthropic) están claramente separadas de la lógica de negocio del usuario final.
- **Paralelo débil en AG-EVIDENCE:** `escribano_fiel.py` / pipeline vs reglas SUNAT/MINEDU en módulos de dominio — ya existe separación; el `.map` **refuerza la idea** de no mezclar “motor de pasos” con “reglas probatorias”.

---

## 5. Límites estrictos (obligatorios)

| Límite | Motivo |
|--------|--------|
| **No usar el `.map` como core del sistema** | Tamaño, licencia/propiedad del código fuente embebido, irrelevancia normativa. |
| **No sustituir OCR/VLM/parsing actuales** | La precisión en RUC/fecha/monto y el bloqueo de venenos (ANEXO/SUNAT) son problemas de **dominio**, no de “más tools”. |
| **No relajar visibilidad probatoria** | AG-EVIDENCE: solo citar lo visible; lo demás **`NULL`** / tags explícitos. |
| **No introducir autonomía decisoria** | Ningún bucle “hasta que el modelo decida conforme” reemplaza checklists humanos y reglas cargadas. |
| **No importar código del bundle** | Riesgo legal/técnico y fuga del modelo local-first disciplinado. |

---

## 6. Aplicabilidad real a AG-EVIDENCE

| Pregunta | Respuesta honesta |
|----------|-------------------|
| ¿Aporta “luces” arquitectónicas? | **Sí**, como **léxico** de tools multimodales, límites de lectura de archivos y organización de contexto. |
| ¿Arregla el “Excel horrible” (fechas malas, RUC en notación científica, NULL masivos)? | **No.** Eso exige **OCR**, **parsing** (series/RUC/fecha/monto), **formato de columnas** en Excel (texto vs número), **bloqueo de contaminación** por páginas tipo anexo/consulta SUNAT y **recalibración de recuperación** — todo ya rastreado en `CURRENT_STATE.md` y código del extractor. |
| ¿Reduce la necesidad de VLM donde el bloque es imagen? | **No automáticamente.** Solo si el **pipeline** sigue mejorando **imagen → texto/campos** con reglas probatorias; el `.map` no es un motor OCR. |
| ¿Debe algún desarrollador leer el `.map` entero? | **No.** Búsquedas puntuales o este resumen bastan para **decidir que no es dependencia**. |

**Conclusión:** el `.map` es **material de investigación** y **contraste epistemológico** (asistente genérico vs sistema probatorio). La mejor inversión marginal sigue siendo **precisión de extracción y gobernanza de fragmentos**, no “importar agencia” del bundle.

---

## 7. Referencias cruzadas en AG-EVIDENCE

- Decisión formal: **`docs/ADR-013-claude-code-sourcemap-reference.md`**
- Continuidad IA (empaquetado): `scripts/_pack_contexto_ia.py` → `AG_EVIDENCE_IA_CONTEXTO_COMPLETO.txt` en Descargas

---

*Fin del documento de investigación.*
