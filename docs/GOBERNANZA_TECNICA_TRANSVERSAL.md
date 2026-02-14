# Gobernanza Tecnica Transversal — AG-EVIDENCE

> Documento normativo permanente. Define las reglas estructurales
> que aplican a **todo** modulo, script y pipeline del proyecto.
> Ninguna funcionalidad queda exenta.

**Version:** 1.0.0
**Fecha:** 2026-02-13
**Autor:** Hans (definicion) + Claude Code (formalizacion)
**Estado:** VIGENTE

---

## Principio Rector

> *"Prefiero un dato vacio y honesto a un dato inventado."*

AG-EVIDENCE es un sistema de control previo para el sector publico peruano.
Cualquier dato fabricado, inferido o estimado constituye un riesgo
administrativo y legal. Estas reglas existen para garantizar que el sistema
**nunca invente informacion** y que toda salida sea trazable hasta su
fuente documental.

---

## REGLA 1 — Prohibicion absoluta de hardcode funcional

### Enunciado

Ningun script ni modulo del proyecto puede contener datos funcionales
escritos directamente en el codigo fuente. Los datos (RUC, razones
sociales, montos, numeros de comprobante, fechas, descripciones) deben
provenir **exclusivamente** de:

1. Extraccion formal del pipeline OCR, o
2. Un archivo JSON intermedio generado por dicho pipeline.

### Fundamento

Los datos hardcodeados:
- No son verificables contra el documento fuente.
- No registran fuente, pagina ni confianza OCR.
- No permiten auditoria ni trazabilidad.
- Introducen riesgo de alucinacion (el operador o el modelo pueden
  transcribir mal sin evidencia de la discrepancia).

### Criterio de cumplimiento

Un script cumple la Regla 1 si **toda** variable con valor funcional
proviene de `json.load()`, de una funcion del pipeline, o de un parametro
de entrada documentado. Si aparece un literal como `"20100039207"` (RUC)
o `"F001-468"` (serie-numero) directamente asignado, **viola la Regla 1**.

### Scripts que actualmente violan la Regla 1

| Script | Tipo de violacion | Cantidad aprox. de datos hardcodeados |
|--------|-------------------|---------------------------------------|
| `scripts/generar_excel_caja_chica_003.py` | 16 gastos con RUC, razon social, montos, serie-numero, fechas, descripciones escritas en el codigo | ~28 valores hardcodeados + 50 lineas de RUC/razon social |
| `scripts/generar_excel_OTIC2026.py` | Comprobantes con RUC, montos, series, razones sociales hardcodeadas | ~50 valores hardcodeados |
| `scripts/generar_excel_expediente.py` | Comprobantes de viaticos con datos hardcodeados | ~22 valores hardcodeados |

**Accion pendiente:** Refactorizar los 3 scripts para que consuman un
JSON intermedio generado por el pipeline formal. No se refactoriza hoy;
se deja registrado para ejecucion posterior.

---

## REGLA 2 — Validacion obligatoria de dimensiones de imagen en todo el pipeline

### Enunciado

Toda imagen que ingrese al pipeline OCR debe pasar por `_validar_dimensiones()`
antes de ser procesada. Esto aplica en dos puntos obligatorios:

1. **Post-renderizado:** Despues de `renderizar_pagina()` en `src/ocr/core.py`.
2. **Post-rotacion:** Despues de `preprocesar_rotacion()` en
   `src/ingestion/pdf_text_extractor.py`.

### Fundamento

La rotacion con `expand=True` puede generar imagenes mas grandes que las
originales. Sin validacion post-rotacion, imagenes de 4000+ px pueden
llegar al motor OCR, causando:
- Timeouts o crashes por memoria.
- Resultados degradados por dimensiones fuera de rango optimo.

### Implementacion actual

- `src/ocr/core.py` linea ~536: `img = _validar_dimensiones(img)` en
  `renderizar_pagina()`.
- `src/ingestion/pdf_text_extractor.py` lineas 158-161: validacion
  condicional post-rotacion.
- `src/tools/vision.py`: modulo auxiliar con `preparar_imagen()`.
- `config/settings.py`: `VISION_CONFIG.max_dimension_px = 2000`.

### Tests

- 10 tests en `TestValidarDimensiones` (test_ocr_core.py).
- 2 tests en `TestRenderizarPaginaValidaDimensiones` (test_ocr_core.py).
- 3 tests en `TestRegla2PostRotacion` (test_pdf_text_extractor.py).

### Estado: IMPLEMENTADA Y VERIFICADA (342 tests pass, 0 failures).

---

## REGLA 3 — Prohibicion absoluta de inferencia o estimacion de datos no visibles

### Enunciado

Si un dato no es visible en el documento fuente (por baja calidad de
escaneo, oclusion, corte de pagina, o ausencia), el sistema **no debe**:

- Inferirlo de otros campos del mismo documento.
- Estimarlo por patron o similitud con otros documentos.
- Completarlo con valores por defecto.
- Calcularlo a partir de subtotales.

### Fundamento

En control previo, un monto inferido es un monto no verificable.
La auditoria requiere que cada dato sea trazable a un fragmento
visible del documento. La inferencia introduce riesgo de observacion
falsa.

### Criterio de cumplimiento

Toda funcion de extraccion que encuentre un campo no legible debe
retornar el marcador de abstencion correspondiente (ver Regla 5),
**nunca** un valor calculado o estimado.

### Estado: PRINCIPIO DIRECTOR. Se formalizara con definicion tecnica
precisa al implementar el contrato de extraccion (Fase 2).

---

## REGLA 4 — Contrato unico de extraccion con JSON intermedio obligatorio

### Enunciado

La extraccion de datos de un documento debe producir un **unico** archivo
JSON intermedio con estructura tipada. Este JSON es el contrato entre:

- El pipeline de extraccion (OCR + post-procesamiento).
- Los modulos consumidores (Excel, validaciones, reportes).

Ningun modulo consumidor debe extraer datos directamente de PDFs.

### Fundamento

Sin contrato intermedio:
- Cada script reimplementa su propia extraccion (duplicacion de logica).
- No hay punto unico de validacion ni auditoria.
- Los errores de extraccion se propagan sin control.

### Estructura esperada (preliminar)

```json
{
  "expediente": "OT2026-INT-0179550",
  "tipo": "caja_chica",
  "extraido_por": "pipeline_ocr_v3.1.0",
  "timestamp_iso": "2026-02-13T...",
  "gastos": [
    {
      "item": 1,
      "fecha": "2026-01-20",
      "tipo_comprobante": "FACTURA",
      "serie_numero": "F001-468",
      "ruc": "20100039207",
      "razon_social": "...",
      "concepto": "...",
      "monto": 250.00,
      "fuente": {
        "archivo": "sustento.pdf",
        "pagina": 5,
        "confianza_ocr": 0.87
      },
      "estado": "OK"
    }
  ]
}
```

### Estado: PRINCIPIO DIRECTOR. Se implementara como contrato tipado
en Fase 2 (Tarea #17+).

---

## REGLA 5 — Politica de abstencion: si no es legible, marcar ILEGIBLE

### Enunciado

Cuando el pipeline OCR no puede extraer un campo con confianza
suficiente, debe marcar ese campo con el valor `"ILEGIBLE"` (o el
marcador de abstencion formal definido en `src/extraction/abstencion.py`).

### Fundamento

- El modulo `abstencion.py` ya implementa la politica formal de
  abstencion operativa (Tarea #12, 550 lineas, 66 tests).
- Un campo marcado ILEGIBLE permite:
  - Revision humana focalizada (solo los campos dudosos).
  - Evidencia de que el sistema intento y no pudo, en vez de inventar.
  - Auditoria completa del proceso.

### Criterio de cumplimiento

Todo campo extraido cuya confianza OCR sea inferior al umbral
`ocr_min_confidence` (actualmente 0.60) debe retornar el marcador
de abstencion, no un valor parcial ni estimado.

### Estado: PARCIALMENTE IMPLEMENTADA. El modulo `abstencion.py` existe
y esta testeado. Falta integrarlo al contrato de extraccion (Regla 4).

---

## REGLA 6 — Excel y reportes solo consumen datos validados, nunca extraen

### Enunciado

Los scripts de generacion de Excel y reportes:

- **Solo leen** del JSON intermedio (Regla 4).
- **No abren** PDFs.
- **No ejecutan** OCR.
- **No interpretan** imagenes.

Su unica responsabilidad es formatear y presentar datos ya validados.

### Fundamento

Separar extraccion de presentacion garantiza:
- Un unico punto de verdad (el JSON).
- Que el Excel sea reproducible (misma entrada = misma salida).
- Que los errores de extraccion se corrijan en el pipeline, no en el
  script de Excel.

### Estado: PRINCIPIO DIRECTOR. Los 3 scripts actuales violan esta
regla (hardcodean datos en vez de leerlos de JSON). Se corregira al
refactorizar (posterior a Regla 4).

---

## REGLA 7 — Registro obligatorio de fuente, pagina y confianza OCR por campo

### Enunciado

Todo dato extraido debe llevar asociado:

1. **Fuente:** nombre del archivo PDF de origen.
2. **Pagina:** numero de pagina dentro del PDF.
3. **Confianza OCR:** valor numerico (0.0 a 1.0) del motor OCR.
4. **Motor:** identificador del motor usado (paddleocr, tesseract).

### Fundamento

Sin esta metadata:
- No se puede verificar un dato contra el documento fuente.
- No se puede priorizar revision humana (campos de baja confianza).
- No se cumple el principio de trazabilidad probatoria.

### Implementacion parcial

- `src/ocr/core.py`: `ejecutar_ocr()` ya retorna `confianza_promedio`,
  `motor_ocr`, y `lineas` con bbox + confianza por linea (Tarea #14).
- `src/ingestion/pdf_text_extractor.py`: registra paginas procesadas
  con `pagina`, `num_palabras`, `confianza`, `lineas`.
- Falta propagacion al JSON intermedio (Regla 4) y al Excel (Regla 6).

### Estado: PARCIALMENTE IMPLEMENTADA en el pipeline OCR.
Falta propagacion completa al contrato tipado.

---

## Registro de Pendientes

### Manana (proxima sesion):

> **Se reprocesara Caja Chica N.3 (OT2026-INT-0179550) usando
> exclusivamente el pipeline formal de OCR.** Sin datos hardcodeados.
> Con marcadores ILEGIBLE donde corresponda. Con registro de fuente,
> pagina y confianza por cada campo extraido.

### Refactorizacion de scripts (posterior):

1. `scripts/generar_excel_caja_chica_003.py` — eliminar 16 gastos hardcodeados.
2. `scripts/generar_excel_OTIC2026.py` — eliminar comprobantes hardcodeados.
3. `scripts/generar_excel_expediente.py` — eliminar comprobantes hardcodeados.

Los 3 scripts pasaran a consumir JSON intermedio generado por el pipeline.

---

## Historial de Versiones

| Version | Fecha | Cambio |
|---------|-------|--------|
| 1.0.0 | 2026-02-13 | Documento inicial con 7 reglas formalizadas |

---

*Documento generado por Claude Code bajo instruccion directa de Hans.*
*Forma parte del sistema de gobernanza de AG-EVIDENCE.*
