# Entorno experimental externo — SANTO_GRIAL / agent_sandbox

## 1. Propósito del documento

Este documento registra la existencia y el alcance de un **entorno experimental externo** denominado **SANTO_GRIAL / agent_sandbox**, separado del sistema productivo **AG-EVIDENCE**. Sirve como referencia operativa para equipos humanos y herramientas que trabajan en ambos contextos: define límites, reglas y criterios mínimos antes de considerar cualquier componente experimental como candidato a integración.

---

## 2. Definición

**SANTO_GRIAL / agent_sandbox** es un **entorno de laboratorio** orientado al desarrollo y prueba de componentes de recuperación y razonamiento asistido sobre normativa (**RAG normativo**), flujos auxiliares y prototipos conectados a ese objetivo.

 Características esenciales:

- Opera **fuera** del pipeline productivo de AG-EVIDENCE.
- No sustituye custodia, extracción, validaciones ni reportes oficiales del producto.
- Cualquier resultado obtenido allí tiene, por defecto, **estado experimental** hasta completar el proceso de integración descrito en la sección 6.

---

## 3. Relación con AG-EVIDENCE

| Rol | Sistema |
|-----|---------|
| **Productivo** | **AG-EVIDENCE**: pipeline de control previo probatorio sobre expedientes (ingesta, OCR, extracción, validación, trazabilidad, salidas acordadas). |
| **Previo / laboratorio** | **SANTO_GRIAL / agent_sandbox**: banco de pruebas y prototipos para RAG normativo y afines. |

El sandbox es un **entorno de validación previa**: ideas, pipelines experimentales y componentes se depuran ahí antes de que un responsable decida si procede una integración formal con AG-EVIDENCE.

**AG-EVIDENCE no depende ni requiere el entorno sandbox para su operación actual.**

---

## 4. Regla crítica — Separación e integración

1. **No existe integración directa** entre el sandbox y el despliegue productivo de AG-EVIDENCE. No se asume canal automático de código, datos ni configuración desde el laboratorio hacia producción.
2. **Ningún artefacto originado o probado solo en el sandbox** (código, prompts, índices, reglas, modelos de recuperación, etc.) se considera apto para producción **sin validación completa** según los criterios de la sección 5 y el procedimiento conceptual de la sección 6.
3. La mera compilación o ejecución exitosa en el sandbox **no implica** aceptación en AG-EVIDENCE.

---

## 5. Criterios mínimos para considerar la integración de un componente

Un componente candidato (por ejemplo, un módulo de RAG, un verificador de citas o un flujo de enriquecimiento normativo) solo puede evaluarse para integración si, como mínimo, se demuestra que cumple **simultáneamente**:

Los criterios de integración se alinean con el principio de visibilidad probatoria, donde solo se considera válido lo verificable en fuente documental.

1. **Citas normativas verificables**  
   Referencias a artículo, numeral, inciso (u equivalente en la fuente) **presentes y comprobables** en el documento citado; sin invención de numeración no respaldada por el texto fuente.

2. **Fuente explícita**  
   Cada afirmación vinculada a norma debe asociarse a **archivo (o identificador estable) + número de página** (o ancla equivalente en el formato de archivo), de modo que un auditor pueda reproducir la lectura.

3. **Cero alucinaciones**  
   Comportamiento acorde a las políticas de AG-EVIDENCE: no completar vacíos con suposiciones; degradar o abstenerse cuando falte evidencia.

4. **Trazabilidad completa**  
   Registro suficiente para reconstruir: entrada al componente, fuentes consultadas, decisión o salida, y vínculo con evidencia (archivo + página + extracto cuando aplique).

5. **Validación contra golden dataset**  
   Evidencia de pruebas sistemáticas contra el conjunto de referencia acordado para el proyecto (o validación equivalente aceptada por gobernanza), con resultados revisables.

6. **Comportamiento estable**  
   Repetibilidad controlada: variaciones acotadas y explicadas; ausencia de regresiones no justificadas respecto a casos de referencia obligatorios.

 La no satisfacción de cualquiera de estos puntos **descalifica** la integración hasta subsanación documentada.

---

## 6. Forma de integración (solo conceptual)

La incorporación de piezas probadas en el sandbox al sistema real **no** es un “deploy automático”. A alto nivel, el camino esperable es:

1. **Migración de componentes**  
   Portar o reimplementar el componente en el árbol y convenciones de AG-EVIDENCE (estructura de módulos, pruebas, configuración), sin arrastrar dependencias no aprobadas.

2. **Adaptación al pipeline existente**  
   Encajar el componente en los puntos de extensión definidos por la arquitectura productiva (orquestación, contratos de datos, logging, políticas de abstención), en lugar de paralelizar un segundo pipeline no gobernado.

3. **Validación dentro del sistema real**  
   Ejecutar la suite de pruebas de AG-EVIDENCE, revisiones de gobernanza aplicables y, si corresponde, procesamiento de expedientes de referencia bajo los mismos criterios que el resto del producto.

 Hasta completar estos pasos con evidencia, el componente permanece clasificado como **experimental**.

---

## 7. Alcance y límites de este documento

- **No** define cronograma, hitos ni responsables operativos.
- **No** crea dependencias técnicas ni referencias a código del sandbox dentro de este repositorio.
- **No** sustituye `PROJECT_SPEC.md`, `AGENT_GOVERNANCE_RULES.md`, ADRs ni el código fuente de AG-EVIDENCE.

 Este archivo **únicamente** fija la separación entre sistema productivo y laboratorio externo **SANTO_GRIAL / agent_sandbox**, y los requisitos mínimos y el enfoque conceptual para una integración futura, si se aprueba.
