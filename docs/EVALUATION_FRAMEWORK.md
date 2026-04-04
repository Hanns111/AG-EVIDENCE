# Marco de evaluación del sistema — AG-EVIDENCE

**Versión:** 1.1  
**Tipo:** documentación de gobernanza técnica (no implementación)  
**Alcance:** validación del comportamiento del sistema frente a expedientes reales del MINEDU.

---

## 1. Propósito

AG-EVIDENCE integra extracción documental, razonamiento asistido y mecanismos de recuperación de contexto para apoyar el análisis probatorio de expedientes administrativos. La calidad del sistema no puede afirmarse solo con pruebas ad hoc: debe **medirse frente a una referencia estable derivada del propio expediente**.

Este marco define **cómo** se establece esa referencia, **qué** se compara contra la salida del sistema y **con qué criterios** se interpretan las diferencias.

**El expediente es la verdad. El sistema debe ajustarse a esa verdad.**

El documento no prescribe cambios al código ni al diseño del producto; formaliza un procedimiento de evaluación reproducible y auditable.

---

## 2. Principio de No Alucinación

**Principio obligatorio:** *«Si un dato no es claramente visible para un humano en el documento, el sistema NO debe inferirlo ni generarlo.»*

La evaluación y cualquier extracción automatizada asociada al marco de referencia deben alinearse con un criterio de **fidelidad documental**:

- El sistema **no debe generar información** que no esté **explícitamente presente** en el documento fuente (PDF u otro soporte del expediente).
- Ante **duda razonable** sobre el contenido o la lectura, el valor registrado debe ser **ausencia de dato** (p. ej. `NULL` o equivalente acordado en el esquema), no una completación plausible.
- La prioridad es la **fidelidad al documento**, no la completitud del formulario ni la fluidez del informe.

**Es preferible ausencia de dato que la introducción de información incorrecta.**

Este principio tiene **prioridad** sobre heurísticas de conveniencia, plantillas de salida “siempre llenas” o inferencias contextuales no sustentadas en evidencia literal reproducible.

---

## 3. Definición de *ground truth*

### 3.1 Fuente de verdad

La **fuente de verdad** para la evaluación es un **Excel estructurado** que consolida, por expediente, los comprobantes de pago y sus atributos fiscales relevantes.

### 3.2 Origen del Excel

El archivo se construye por medios **externos al flujo RAG** del proyecto, entre otros:

- **Extracción manual** revisada por un operador (transcripción controlada desde PDF).
- **Herramientas externas** (p. ej. scripts de procesamiento de PDF con reglas explícitas y trazabilidad de página y archivo).

La procedencia de cada fila (manual, script, revisión cruzada) debe poder documentarse cuando la evaluación sea formal; el marco no sustituye a una política de custodia de datos ya definida en el proyecto.

### 3.3 Nombre del artefacto

El artefacto de referencia se denomina, por convención de este marco:

**`comprobantes.xlsx`**

En evaluaciones multi-expediente, cada carpeta de expediente puede contener su propio `comprobantes.xlsx`; la comparación siempre es **por expediente** (un Excel de verdad frente a una o más salidas del sistema asociadas a ese mismo conjunto documental).

---

## 4. Definición del sistema evaluado

En el contexto de AG-EVIDENCE, el subsistema sometido a evaluación bajo este marco es el que combina:

1. **Recuperación de información** desde el corpus documental del expediente (fragmentos, metadatos o representaciones derivadas de los PDF u otros soportes indexados).
2. **Generación de respuestas** mediante modelos de lenguaje (LLM), utilizando el contexto recuperado para producir afirmaciones sobre comprobantes, montos, identificadores tributarios y fechas.

Salidas típicas incluyen enumeración de comprobantes, síntesis de totales o respuestas a preguntas puntuales sobre una rendición. Lo evaluable son los **hechos verificables** extraíbles del expediente (conteos, identificadores, importes, fechas), no la redacción meramente estilística.

---

## 5. Comparación (Excel versus salida RAG)

### 5.1 Roles

| Rol | Significado |
|-----|-------------|
| **Excel** | Verdad operativa para la evaluación: filas = comprobantes consolidados según §3. |
| **RAG** | Salida del sistema bajo prueba: texto o estructura derivada del pipeline de recuperación + LLM. |

### 5.2 Dimensiones de comparación

Deben contrastarse, al menos, las siguientes dimensiones cuando estén presentes en el Excel de referencia y sean reclamables en la consulta al sistema:

| Dimensión | Descripción |
|-----------|-------------|
| **Conteo** | Número de comprobantes distintos (según clave acordada: p. ej. serie-número normalizado + RUC). |
| **Montos totales** | Coherencia de importes totales por comprobante y, cuando aplique, agregados sobre el conjunto. |
| **Serie y número** | Coincidencia respecto a la referencia (incluyendo reglas de normalización explícitas en el Excel o en el procedimiento de extracción). |
| **RUC** | Coincidencia del identificador del emisor u otro RUC definido en el contrato de columnas del Excel. |
| **Fechas** | Coincidencia de fecha de emisión u otra fecha de referencia acordada en el esquema del Excel. |

La comparación puede ser **automática** (parseo de salida + reglas) o **asistida** (plantilla de revisión). El marco exige que la operación sea **repetible** y que los criterios de coincidencia (tolerancias de formato, redondeo) queden fijados antes de la corrida.

---

## 6. Tipos de error a detectar

| Tipo | Definición |
|------|------------|
| **Falsos positivos** | El sistema inventa o confirma comprobantes que no existen en el Excel de verdad para ese expediente. |
| **Falsos negativos** | El sistema omite comprobantes que sí figuran en el Excel de verdad. |
| **Errores de monto** | Diferencia en importe total (o subtotal acordado) respecto al Excel. |
| **Errores de RUC** | Diferencia en el RUC atribuido al comprobante o confusión entre RUC de emisor y otros RUC del documento. |
| **Errores de fecha** | Fecha distinta de la de referencia o asignación a un campo equivocado (emisión vs. otros). |
| **Errores de interpretación** | Respuesta coherente superficialmente pero incorrecta en el sentido probatorio (p. ej. mezcla de conceptos, lectura de la línea equivocada en un comprobante complejo). |

La clasificación del error debe apoyarse en **evidencia documental** (archivo y página del PDF cuando la evaluación sea formal), alineada al estándar probatorio del proyecto.

---

## 7. Métricas

Las métricas siguientes se definen a nivel de **expediente** o de **conjunto de prueba** según se documente en cada campaña de evaluación.

| Métrica | Definición operativa (orientativa) |
|---------|-------------------------------------|
| **Exactitud de conteo** | Concordancia entre el número de comprobantes en el Excel y el número inferido de la salida RAG (tras reglas de emparejamiento). |
| **Exactitud de montos** | Proporción de comprobantes emparejados cuyo monto coincide con la referencia bajo criterio predefinido (exacto o tolerancia). |
| **Precisión de extracción** | Proporción de campos acordados (RUC, serie-número, fecha, monto) correctos sobre el total de campos evaluables emparejados, o definición alternativa fijada en el plan de evaluación. |
| **Tasa de error** | Proporción de comprobantes o respuestas con al menos un error de los tipos del §6, respecto al total evaluado. |

Los umbrales de aceptación (si existen) son **decisión de producto** y no forman parte de este marco; el marco solo fija que las métricas deben definirse sin ambigüedad antes de medir.

---

## 8. Flujo de evaluación

El flujo de referencia es:

```
Expediente real
    → elaboración del ground truth (extracción manual y/o herramientas externas)
    → comprobantes.xlsx
    → definición de consultas o escenarios de prueba al pipeline RAG
    → ejecución del sistema (recuperación + generación)
    → comparación (Excel vs salida)
    → registro de resultado (métricas, errores tipificados, evidencia)
```

Los artefactos intermedios (logs, trazas de recuperación) pueden incorporarse según la profundidad de la evaluación, sin alterar el orden lógico anterior.

---

## 9. Alcance y límites

- Este framework **no modifica** el sistema AG-EVIDENCE; describe **cómo** validarlo.
- Actúa como **mecanismo de validación externa** respecto al pipeline RAG evaluado: el Excel no se genera dentro de la respuesta del LLM para la misma corrida que se mide.
- Su uso previsto incluye **fases futuras** de evaluación sistemática y comparación entre versiones del sistema ante el mismo `comprobantes.xlsx`.

---

## 10. Futuras extensiones

Sin comprometer implementación concreta, el marco contempla las siguientes extensiones:

- **Automatización de la comparación**: scripts que lean `comprobantes.xlsx` y la salida estructurada o parseada del RAG, produciendo informes reproducibles.
- **Scoring automático**: agregación de métricas del §7 en un índice o informe por expediente y por lote.
- **Integración con testing**: ensayos en `pytest` (u otra herramienta) que invoken flujos acotados del sistema contra fixtures derivados de expedientes anonimizados o golden files compatibles con este marco.

Cualquier extensión debe mantener la separación **verdad (Excel) / sistema (RAG)** y la trazabilidad de errores descrita en este documento.

---

*Documento elaborado para gobernanza técnica del proyecto. Las referencias a componentes concretos del repositorio deben mantenerse alineadas con la arquitectura vigente documentada en `docs/ARCHITECTURE.md`.*
