# ARQUITECTURA DEL SISTEMA – AG-EVIDENCE

## 1. Propósito de este Documento

Este archivo define **cómo está organizado el sistema** y **dónde va cada cosa**.  
Cualquier IA que genere código debe **ajustarse estrictamente** a esta estructura.

Si una propuesta rompe esta arquitectura, debe ser cuestionada antes de implementarse.

---

## 2. Principios Arquitectónicos

- **Arquitectura modular y desacoplada**: Separación clara de responsabilidades
- **Separación estricta entre capas**:
  - Dominio (lógica de negocio)
  - Orquestación (flujo de trabajo)
  - Infraestructura (herramientas técnicas)
- **Privacy by Design (GDPR-ready)**: Cumplimiento con estándares europeos
- **Local-first**: Sin dependencias cloud pagadas
- **Auditabilidad total**: Todo flujo es trazable y verificable

---

## 3. Diseño Actual del Sistema

### 3.1 Arquitectura Multi-Agente

El sistema utiliza **9 agentes especializados** que operan de forma secuencial:

1. **AG01 - Clasificador**: Determina la naturaleza del expediente (viáticos, caja chica, encargo, pago proveedor)
2. **AG02 - OCR**: Evalúa calidad de extracción de texto y detecta páginas escaneadas
3. **AG03 - Coherencia**: Verifica consistencia de datos (SINAD, SIAF, RUC, montos)
4. **AG04 - Legal**: Verifica cumplimiento de directiva aplicable según naturaleza
5. **AG05 - Firmas**: Detecta y valida firmas digitales/manuscritas
6. **AG06 - Integridad**: Verifica documentos requeridos según naturaleza
7. **AG07 - Penalidades**: Evalúa aplicación de penalidades contractuales
8. **AG08 - SUNAT**: Consulta estado tributario (informativo)
9. **AG09 - Decisor**: Consolida hallazgos y emite decisión final

### 3.2 Flujo de Ejecución

```
Expediente PDF → Extracción → Orquestador → 9 Agentes → Validación → Reporte
```

El **Orquestador** (`orquestador.py`) coordina la ejecución secuencial de los agentes, pasando el estado entre ellos mediante estructuras de datos tipadas (`ResultadoAgente`).

### 3.3 Estándar Probatorio

Toda observación crítica o mayor debe incluir:
- **Archivo fuente**: Nombre exacto del PDF
- **Página**: Número de página
- **Snippet**: Extracto literal del texto

Si no hay evidencia suficiente, la observación se degrada a **INCIERTO**.

---

## 4. Capas del Sistema

### Capa 1 – Dominio

Contiene la lógica propia del problema.

**Ubicación actual**: `agentes/`, `config/settings.py`

**Ejemplos**:
- Reglas de viáticos
- Validaciones normativas
- Criterios de observación
- Interpretación de directivas

**Principio**: Esta capa NO conoce IA, GPU ni bases vectoriales.

---

### Capa 2 – Orquestación

Responsable del flujo de trabajo.

**Ubicación actual**: `orquestador.py`

**Framework futuro**: LangGraph (planificado)

**Controla**:
- Secuencia de agentes
- Reintentos
- Validaciones cruzadas
- Bucles de auditoría

**Principio**: Esta capa coordina, no decide contenido.

---

### Capa 3 – Herramientas

Servicios técnicos intercambiables.

**Ubicación actual**: `utils/`, `tools/`

**Ejemplos actuales**:
- PyMuPDF (extracción PDF)
- Ollama/Qwen (inferencia local)
- EasyOCR (OCR avanzado)

**Ejemplos planificados**:
- vLLM (inferencia local)
- Qdrant (vector store)
- OSRM (ruteo geográfico)
- DuckDB (padrones SUNAT)

**Principio**: Debe implementarse mediante **adaptadores**.

---

## 5. Estructura de Directorios Actual

```text
AG-EVIDENCE/
├─ agentes/              # 9 agentes especializados (implementación actual)
├─ config/               # Configuración global, enums, settings
├─ data/                 # Directivas y expedientes de prueba
│  ├─ directivas/        # PDFs de normativas (NO versionados)
│  └─ expedientes/      # Expedientes de prueba (NO versionados)
├─ docs/                 # Documentación de gobernanza y arquitectura
├─ scripts/              # Scripts de utilidad (categorización, etc.)
├─ src/                  # Código fuente estructurado (en desarrollo)
├─ tests/                # Tests unitarios e integración
├─ tools/                # Herramientas de desarrollo
├─ utils/                # Utilidades (PDF, LLM, validación)
├─ output/               # Informes generados (NO versionado)
├─ orquestador.py        # Orquestador principal
├─ chat_asistente.py     # Chat conversacional
└─ ejecutar_control_previo.py  # Entrypoint principal
```

---

## 6. Flujo General del Sistema

1. **Ingesta de expediente**: Extracción de PDFs desde carpeta
2. **OCR / visión**: Detección de texto nativo vs escaneado
3. **Extracción estructurada**: Normalización de datos
4. **Validación externa**: Consultas SUNAT, verificación de fechas
5. **Auditoría normativa**: Verificación contra directivas
6. **Síntesis de observaciones**: Consolidación de hallazgos
7. **Generación de reporte**: JSON + TXT con estándar probatorio

**Nota**: Actualmente implementado como flujo secuencial. Planificado migración a LangGraph para permitir ciclos y validaciones cruzadas.

---

## 7. Reglas de Modificación

- **Cambios en dominio**: Requieren actualizar ADR.md si afectan criterios
- **Cambios en flujo**: Requieren actualizar este archivo
- **Cambios técnicos**: NO deben afectar dominio

---

## 8. Prioridad del Documento

Este archivo tiene prioridad sobre:
- Estilo personal de una IA
- Sugerencias genéricas
- Frameworks alternativos no aprobados

Si hay contradicción, se sigue ARCHITECTURE.md.

---

## 9. Referencias

- `docs/ARCHITECTURE_SNAPSHOT.md`: Estado técnico detallado del sistema
- `docs/PROJECT_SPEC.md`: Objetivos y principios del proyecto
- `docs/ADR.md`: Decisiones arquitectónicas registradas
