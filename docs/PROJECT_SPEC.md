# PROJECT_SPEC – AG_EVIDENCE

## 1. Identidad del Proyecto

Nombre del proyecto: AG_EVIDENCE  
Dominio: Análisis probatorio y control previo de expedientes administrativos  
Contexto inicial de aplicación: Ministerio de Educación del Perú (MINEDU)  
Proyección: Portafolio profesional para instituciones públicas y privadas, con énfasis en estándares de la Unión Europea (Dinamarca).

AG_EVIDENCE es un sistema de apoyo al análisis administrativo cuyo objetivo principal es **detectar observaciones, inconsistencias y riesgos** en expedientes, basándose exclusivamente en **evidencia verificable**, **normativa vigente** y **reglas explícitas**.

No es un chatbot genérico.  
No es un sistema creativo.  
No es un asesor legal automático.

Es un **sistema técnico probatorio**.

---

## 2. Objetivo Principal

Diseñar y desarrollar un sistema asistido por inteligencia artificial que:

- Analice documentos administrativos (PDF, imágenes, texto).
- Extraiga información estructurada de manera controlada.
- Verifique dicha información contra reglas normativas y fuentes auxiliares.
- Produzca observaciones trazables, justificadas y auditables.
- Minimice de forma explícita la alucinación y la inferencia no sustentada.

El sistema debe poder explicar **por qué** realiza una observación y **de dónde** proviene cada dato utilizado.

---

## 3. Principios No Negociables

Estos principios gobiernan todo el proyecto y **no pueden ser ignorados ni reinterpretados**:

1. **Evidencia sobre inferencia**  
   Ninguna conclusión puede emitirse sin respaldo documental o regla explícita.

2. **Cero alucinaciones**  
   Si falta información, el sistema debe declararlo explícitamente.

3. **Privacidad por diseño**  
   Todo el procesamiento se realiza localmente.  
   No se envían documentos ni datos sensibles a servicios externos.

4. **Costo operativo cero**  
   No se utilizan APIs pagadas como OpenAI, Google Maps, etc.

5. **Trazabilidad total**  
   Cada observación debe poder rastrearse a:
   - documento fuente
   - regla aplicada
   - paso del flujo que la generó

6. **Portabilidad institucional**  
   El núcleo del sistema debe poder adaptarse a otros países o entidades cambiando adaptadores, no la lógica central.

---

## 4. Alcance Funcional

AG_EVIDENCE cubre, entre otros:

- Viáticos y rendiciones de cuentas
- Comprobantes de pago escaneados
- Validación de fechas, montos y conceptos
- Análisis de trayectos y distancias
- Revisión normativa basada en documentos oficiales

Queda explícitamente fuera del alcance:

- Interpretación legal subjetiva
- Recomendaciones personales
- Decisiones administrativas finales

El sistema **asiste**, no reemplaza al analista humano.

---

## 5. Entorno de Desarrollo (Restricción Obligatoria)

Debido a restricciones reales de hardware y soporte de software:

- El desarrollo del sistema se realiza **exclusivamente en Linux (Ubuntu 22.04)**.
- El entorno Linux corre sobre **WSL2 en Windows 11**.
- El uso de Windows nativo para tareas de IA está prohibido.

Motivo:
La GPU NVIDIA RTX 5090 utiliza arquitectura sm_120 (Blackwell), la cual:
- No está soportada por PyTorch estable en Windows.
- Requiere PyTorch Nightly en Linux.

Esta decisión **no es opcional** ni discutible sin una nueva decisión arquitectónica documentada.

---

## 6. Stack Tecnológico Aprobado (Nivel Proyecto)

Las siguientes tecnologías están aprobadas a nivel proyecto:

- Lenguaje principal: Python
- Orquestación: LangGraph
- Modelos de lenguaje: Qwen (ej. Qwen2.5-32B cuantizado)
- Modelos de visión: Qwen-VL (7B)
- OCR auxiliar: OCRmyPDF / EasyOCR
- Embeddings: BGE-M3
- Vector store: Qdrant (local)
- Base analítica: DuckDB
- Mapas: OSRM o Valhalla (offline)
- Control de versiones: Git

Cambios en este stack requieren registro explícito en ADR.md.

---

## 7. Prohibiciones Explícitas

Está prohibido dentro de este proyecto:

- Inventar datos, normas, montos o resultados.
- Usar APIs externas sin aprobación documentada.
- Cambiar el stack tecnológico sin ADR.
- Proponer soluciones que ignoren las restricciones de entorno.
- Asumir contexto que no esté documentado.

---

## 8. Criterio de Éxito

El proyecto se considera exitoso si:

- Las observaciones generadas son verificables.
- El sistema es auditable por terceros.
- Puede retomarse el desarrollo en otro chat o IA sin pérdida de coherencia.
- Es defendible como portafolio técnico ante una empresa europea.

Este documento es la referencia suprema del proyecto.
Si existe conflicto entre este archivo y cualquier otra fuente, **PROJECT_SPEC.md prevalece**.
