# Estado actual del proyecto — AG-EVIDENCE

Documento de continuidad: resume el estado funcional del sistema productivo, sus límites y la relación con trabajo experimental externo, sin sustituir la documentación de gobernanza ni el código fuente.

---

## 1. Estado actual del sistema

- **Pipeline existente:** extracción, validación y revisión de expedientes administrativos sobre la base documental aportada.
- **Fuente principal:** archivos PDF (texto nativo cuando existe; imagen cuando corresponde).
- **Modo de operación:** flujo **manual asistido**: el sistema apoya extracción y control; la revisión y decisión final permanecen bajo criterio humano y normativa aplicable.

---

## 2. Capacidades actuales

- **Extracción de texto desde PDF:** lectura directa cuando hay texto embebido; **OCR** cuando el documento es esencialmente imagen.
- **Validación básica de documentos:** comprobaciones y reglas acordadas al alcance implementado en el repositorio (coherencia, formatos, políticas de abstención donde apliquen).
- **Generación de salidas estructuradas:** informes o artefactos tipados o tabulares previstos por el pipeline (por ejemplo, registros trazables y exportaciones acordadas), según módulos vigentes.

---

## 3. Limitaciones actuales

- **Chunking no estructural:** el particionado de texto no reconoce de forma fiable unidades normativas explícitas (por ejemplo, artículo, numeral, inciso) como unidades de recuperación.
- **Ranking semántico limitado:** la priorización de fragmentos relevantes frente a una consulta no alcanza el nivel de un motor centrado en intención y norma.
- **Sin priorización por tipo normativo:** no hay, en el productivo, capa estable que clasifique y ordene fragmentos según familia o jerarquía normativa de consulta.
- **Salida no optimizada para usuario final:** las salidas están orientadas a trazabilidad técnica y revisión; no se asume formato o experiencia de consumo masivo para usuarios no técnicos.
- **Riesgo de alucinación con LLM sin control:** el uso de modelos de lenguaje sin gobierno de evidencia, citas y degradación introduce riesgo de invención o mezcla de fuentes; el sistema productivo debe mantener políticas explícitas de abstención y estándar probatorio donde corresponda.

---

## 4. Avances logrados fuera del sistema (SANTO_GRIAL)

Trabajo en entorno de laboratorio externo (**SANTO_GRIAL / agent_sandbox**), **no productivo** y **no integrado automáticamente** en AG-EVIDENCE:

- **Chunking estructural normativo** sobre documentos de referencia.
- **Detección de unidades tipo** OBJETIVO, ARTÍCULO, NUMERAL (y equivalentes según el prototipo).
- **Ranking orientado a la intención de consulta** (consulta → ordenación de fragmentos).
- **Flujo tipo agente:** decisión, invocación de herramienta y paso de validación encadenados en el prototipo.
- **Respuesta con trazabilidad:** respuesta acompañada de fragmento citado y referencia a fuente en el entorno experimental.

Estos avances **no sustituyen** el pipeline de AG-EVIDENCE hasta completar migración validada (véase `docs/EXPERIMENTAL_SANDBOX.md`).

---

## 5. Problema actual

AG-EVIDENCE **aún no incorpora** de forma productiva las capacidades listadas en la sección 4. Cierta precisión y confiabilidad en consulta y síntesis normativa queda limitada frente a lo demostrable en el laboratorio, **sin perder de vista** que el productivo debe cumplir estándares de evidencia y gobernanza que el sandbox no reemplaza.

---

## 6. Estrategia definida

- **No integrar directamente** código ni configuraciones experimentales sin validación formal.
- **Migración controlada** desde SANTO_GRIAL: solo componentes que pasen criterios de integración y revisión en el árbol de AG-EVIDENCE.
- **Implementación modular:** nuevas piezas como módulos acotados, con pruebas y trazabilidad acordes al sistema real.

---

## 7. Siguiente paso inmediato

- **Crear en AG-EVIDENCE un módulo de chunking normativo** alineado con contratos, pruebas y políticas del repositorio, como primer puente hacia capacidades probadas fuera del productivo.

---

## 8. Regla crítica

**AG-EVIDENCE es entorno productivo.** Todo cambio que afecte extracción, validación o salidas debe ser **validado** (pruebas, evidencia, gobernanza aplicable) **antes** de considerarse integrado. El laboratorio externo no opera esa garantía por sí solo.
