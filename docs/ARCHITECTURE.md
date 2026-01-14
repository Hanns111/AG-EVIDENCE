# ARQUITECTURA DEL SISTEMA – AG-EVIDENCE

## 1. Propósito de este Documento

Este archivo define **cómo está organizado el sistema** y **dónde va cada cosa**.  
Cualquier IA que genere código debe **ajustarse estrictamente** a esta estructura.

Si una propuesta rompe esta arquitectura, debe ser cuestionada antes de implementarse.

---

## 2. Principios Arquitectónicos

- Arquitectura modular y desacoplada
- Separación estricta entre:
  - Dominio
  - Orquestación
  - Infraestructura
- Privacy by Design (GDPR-ready)
- Local-first, sin dependencias cloud pagadas
- Todo flujo es auditable y trazable

---

## 3. Capas del Sistema

### Capa 1 – Dominio

Contiene la lógica propia del problema.

Ejemplos:
- Reglas de viáticos
- Validaciones normativas
- Criterios de observación
- Interpretación de directivas

Esta capa:
- NO conoce IA
- NO conoce GPU
- NO conoce bases vectoriales

---

### Capa 2 – Orquestación

Responsable del flujo de trabajo.

- Framework: LangGraph
- Controla:
  - Secuencia de agentes
  - Reintentos
  - Validaciones cruzadas
  - Bucles de auditoría

Esta capa coordina, no decide contenido.

---

### Capa 3 – Herramientas

Servicios técnicos intercambiables.

Ejemplos:
- vLLM (inferencia local)
- Qdrant (vector store)
- OSRM (ruteo geográfico)
- DuckDB (padrones SUNAT)
- OCR / Visión

Debe implementarse mediante **adaptadores**.

---

## 4. Estructura de Directorios Base

```text
AG-EVIDENCE/
├─ docs/
│  ├─ PROJECT_SPEC.md
│  ├─ ARCHITECTURE.md
│  ├─ HARDWARE_CONTEXT.md
│  ├─ CURRENT_STATE.md
│  ├─ GOVERNANCE_RULES.md
│  ├─ ADR.md
│  └─ CONTEXT_CHAIN.md
│
├─ src/
│  ├─ domain/
│  ├─ orchestration/
│  ├─ agents/
│  ├─ tools/
│  ├─ rag/
│  ├─ vision/
│  └─ reporting/
│
├─ tests/
├─ scripts/
└─ configs/
```

---

## 5. Flujo General del Sistema

1. Ingesta de expediente
2. OCR / visión
3. Extracción estructurada
4. Validación externa
5. Auditoría normativa
6. Síntesis de observaciones
7. Generación de reporte

Este flujo se expresa como un grafo LangGraph, no como un script lineal.

---

## 6. Reglas de Modificación

Cambios en dominio:
- Requieren actualizar ADR.md si afectan criterios

Cambios en flujo:
- Requieren actualizar este archivo

Cambios técnicos:
- NO deben afectar dominio

---

## 7. Prioridad del Documento

Este archivo tiene prioridad sobre:
- Estilo personal de una IA
- Sugerencias genéricas
- Frameworks alternativos no aprobados

Si hay contradicción, se sigue ARCHITECTURE.md.
