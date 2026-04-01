# AG-EVIDENCE — Estado actual del sistema (memoria oficial)

**Fecha de corte:** 2026-03-31  
**Alcance:** Repositorio AG-EVIDENCE y herramienta `scripts/extract_comprobantes_minedu.py` (extracción MINEDU / expedientes en Excel).

Este documento describe el comportamiento **implementado en código** en la fecha indicada. Para el pipeline principal (`src/extraction/escribano_fiel.py`, etc.) no se alteraron reglas en esta milestone; el cambio estructural documentado aquí es la **recuperación post-extracción** en el script autónomo de comprobantes.

---

## 1. Nueva lógica implementada

### Recuperación post-extracción

- Se activa **solo** cuando el clasificador devuelve motivo: **`score_insuficiente_post_extraccion`** (scoring de campos extraídos &lt; 2, tras extracción ciega del bloque).
- Antes de aceptar por recuperación, debe cumplirse **sin veneno** en el bloque, mediante **`_sin_veneno_en_bloque()`**.
- **`_sin_veneno_en_bloque()`** usa las **mismas** comprobaciones que `clasificar_bloque_post_extraccion` antes del scoring:
  - listado múltiples series en bloque;
  - consulta SUNAT / ruido SUNAT;
  - ANEXO + estructura tabular (veneno).

### Criterios de aceptación extendida

Un bloque **sin veneno** y con score insuficiente se acepta además si cumple **al menos uno** de:

1. **Moneda visible** en el texto del bloque (`S/`, `SOLES`, `PEN` vía regex dedicada) **y** patrón de monto (reutiliza `RE_MONTO` y regex de TOTAL / importe ya existentes).
2. **RUC** presente en la fila extraída **o** patrón RUC visible en el bloque **y** **monto parcial** detectable en el bloque.
3. **Estructura tipo ticket:**
   - entre **3 y 45** líneas no vacías;
   - contiene patrón de monto;
   - contiene alguna de las palabras clave **TOTAL**, **IMPORTE**, **PAGO** (mayúsculas normalizadas en texto).

No se cruza información de anexos ni del resto de la página para “salvar” el bloque: solo texto del segmento.

---

## 2. Principio crítico implementado

### Principio de visibilidad probatoria

- El sistema **solo** extrae lo que puede fundamentar en el **bloque** (fragmento segmentado).
- Si un dato no es claramente visible para un lector humano en ese fragmento → **`NULL`** (sin completar desde anexo).
- **Prohibido:** inferencia de valores; completar desde ANEXO; asumir por contexto externo al bloque.
- Documentación en cabecera del script y constante de frase en observaciones (ver sección 5).

---

## 3. Metadatos en filas recuperadas

En la rama de **aceptación extendida**:

- `tier_post_extraccion` = **`"BAJA"`**
- `needs_review` = **`True`**
- `score_post_extraccion` = **valor real** devuelto por `_score_datos_extraidos(fila)` (no inventado)

En comprobantes aceptados por el flujo normal (sin recuperación), `needs_review` se fija en **`False`** y el tier/score provienen de la clasificación estándar.

---

## 4. Trazabilidad (`visible_en_documento`, `parcial_ocr`)

Implementación en **`_calcular_visible_y_parcial(fila, bloque, fuente)`**:

- **`visible_en_documento`**: `True` si hay **al menos un** campo crítico con valor extraído distinto de `NULL`, **o** al menos **un** patrón esperado visible en el bloque para la serie, RUC, monto, fecha o proveedor (etiquetas tipo razón social / emisor / etc.).
- **`parcial_ocr`**: `True` si la fuente de texto es OCR débil (`ocr`, `debil`, `error_ocr`) **o** si para **algún** campo crítico hay patrón en el bloque pero el valor extraído sigue en `NULL` (posible lectura incompleta).

Campos críticos considerados para flags y para el tag de error: serie (normalizada), RUC, monto total, fecha, nombre proveedor.

---

## 5. Observaciones automáticas (recuperación)

En recuperación, a las observaciones existentes del bloque se añade siempre:

- `post_extraccion=aceptacion_extendida_score_insuficiente | tier=BAJA | score_post=... |` + detalle de scoring original;
- Frase literal: **«El sistema solo reporta lo que se puede ver; lo demás se observa como error.»** (constante `FRASE_VISIBILIDAD_PROBATORIA`).

Si **falta alguno** de los campos críticos (serie normalizada, RUC, monto total, fecha, proveedor nombre = `NULL`):

- Se añade el tag **`error_detectado_documento_fuente`** (`TAG_ERROR_DETECTADO_DOCUMENTO_FUENTE`).

---

## 6. Excel

Hoja **`comprobantes`**: columnas adicionales respecto al esquema anterior del script:

- `needs_review`
- `visible_en_documento`
- `parcial_ocr`

Hoja **`bloques_descartados`**: sin cambio de contrato en esta entrega (sigue registrando bloques que no entran ni por aceptación normal ni por recuperación).

---

## 7. Deduplicación

- Clave **`clave_dedup_normalizada`**: tupla de **cuatro** elementos `(archivo_origen, serie_numero_normalizado, ruc, sufijo)`.
- Si **serie normalizada y RUC son ambos `NULL`**, el **sufijo** incorpora página y **`bloque_indice_1based`** para evitar colisiones entre bloques distintos del mismo PDF.
- Campo interno **`bloque_indice_1based`** se asigna en la extracción por bloque (no requiere columna en Excel para funcionar).

---

## 8. Logging

Nuevo mensaje de consola:

- **`[BLOQUE_RECUPERADO_POST_EXTRACCION]`** — incluye archivo, página, índice de bloque, `score_ext`, `needs_review=1`.

Los descartes siguen emitiendo **`[BLOQUE_DESCARTADO_POST_EXTRACCION]`** como antes.

---

## 9. Validación

- **`python -m py_compile scripts/extract_comprobantes_minedu.py`** ejecutado con éxito en el entorno de desarrollo (sin errores de sintaxis).

---

## 10. Impacto funcional (alcance del script autónomo)

- Sobre el **caso de prueba** MINEDU/DIRI asociado a esta iteración se reportó pasar de **~9** filas útiles a **~11–12** en la hoja **`comprobantes`**, según validación manual (el número exacto depende del PDF y de la deduplicación).
- Los registros recuperados llevan **`needs_review=True`** y **`tier_post_extraccion=BAJA`**.

---

## 11. Investigación externa (sin impacto en pipeline)

- **Source map Claude Code** (`CLAUDE_SOURCE_FINAL_60MB.map`): archivo **local** (~60 MB) **fuera** de este repo; **no** se importa ni ejecuta. Su único rol en AG-EVIDENCE es **referencia arquitectónica / contrast e** documentada en:
  - `docs/research/CLAUDE_CODE_SOURCEMAP_NOTES.md`
  - `docs/ADR-013-claude-code-sourcemap-reference.md`
- **No** sustituye OCR, parsing ni reglas de veneno/recuperación; el problema principal del producto sigue siendo **precisión de extracción y calidad de salida** (Excel incl.), no “agregar agencia” tipo asistente genérico.

---

## Regla final

- Este archivo resume el **estado implementado** descrito arriba.
- No sustituye los documentos de gobernanza en `docs/` ni el pipeline en `src/`; indica qué está versionado y cómo se comporta el extractor autónomo en **`scripts/extract_comprobantes_minedu.py`**.
