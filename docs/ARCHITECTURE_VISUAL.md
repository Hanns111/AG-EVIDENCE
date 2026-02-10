# AG-EVIDENCE v2.0 — Arquitectura Visual

> Documento de referencia para entender la estructura completa del sistema.
> Dirigido a stakeholders técnicos y no técnicos.

---

## 1. Vista General del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                     AG-EVIDENCE v2.0                        │
│          Sistema de Control Previo Documental               │
│                                                             │
│  "Cada hallazgo tiene respaldo: archivo, página, texto"     │
└─────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        ┌──────────┐ ┌──────────┐ ┌──────────────┐
        │ ENTRADA  │ │ PROCESO  │ │   SALIDA     │
        │          │ │          │ │              │
        │ PDF del  │ │ 9 Agentes│ │ Excel con    │
        │ expedien-│ │ especia- │ │ hallazgos +  │
        │ te       │ │ lizados  │ │ evidencia    │
        └──────────┘ └──────────┘ └──────────────┘
```

---

## 2. Entorno de Ejecución (Hardware + Software)

```
┌─────────────────────────────────────────────────────────┐
│                   TU PC (Windows 11)                    │
│                                                         │
│  ┌───────────────────────────────────────────────────┐    │
│  │           Entorno de Desarrollo (IDE)              │    │
│  │                                                    │    │
│  │  - Editor de código con asistencia inteligente     │    │
│  │  - Control de versiones (Git)                      │    │
│  │  - Gestión de tareas y documentación               │    │
│  └───────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │              WSL2 (Ubuntu 22.04)                 │    │
│  │                                                  │    │
│  │  ┌──────────────┐  ┌──────────────┐              │    │
│  │  │  Motor OCR    │  │  Motor LLM   │              │    │
│  │  │              │  │              │              │    │
│  │  │  OCRmyPDF    │  │  Actual:     │              │    │
│  │  │  Tesseract   │  │   Ollama +   │              │    │
│  │  │  (español)   │  │   Qwen 32B   │              │    │
│  │  │              │  │              │              │    │
│  │  │  Futuro:     │  │  Futuro:     │              │    │
│  │  │   PaddleOCR  │  │   vLLM       │              │    │
│  │  └──────────────┘  └──────────────┘              │    │
│  │                                                  │    │
│  │  GPU: RTX 5090 (32GB VRAM) ◄── Potencia real     │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Pipeline de Procesamiento (Cómo fluye un expediente)

```
 EXPEDIENTE PDF
      │
      ▼
┌─────────────────┐
│  1. INGESTA      │  Se recibe el PDF y se crea una copia
│     (Cadena de   │  inmutable (intocable) con su huella
│      custodia)   │  digital (hash SHA-256)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  2. OCR          │  Se extrae el texto de cada página
│     (Lectura)    │  Motor: Tesseract/PaddleOCR
│                  │  Cada línea tiene puntuación de
│                  │  confianza (0% a 100%)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  3. ANÁLISIS     │  Los 9 agentes revisan el expediente
│     (9 Agentes)  │  en secuencia, cada uno con su
│                  │  especialidad
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  4. DECISIÓN     │  El Agente 09 consolida todos los
│     (Veredicto)  │  hallazgos y emite un veredicto:
│                  │  CONFORME / OBSERVADO / RECHAZADO
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  5. REPORTE      │  Se genera un Excel con:
│     (Excel)      │  - Datos extraídos
│                  │  - Hallazgos con evidencia
│                  │  - Diagnóstico de confianza
└─────────────────┘
```

---

## 4. Los 9 Agentes Especializados

```
                    ┌──────────────────┐
                    │  AG01 CLASIFICADOR │
                    │                    │
                    │  Determina qué     │
                    │  tipo de expediente │
                    │  es (viáticos,     │
                    │  caja chica, etc.) │
                    └────────┬───────────┘
                             │
                    ┌────────▼───────────┐
                    │  AG02 OCR           │
                    │                    │
                    │  Evalúa la calidad │
                    │  del texto extraído│
                    │  de cada página    │
                    └────────┬───────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │ AG03          │ │ AG04          │ │ AG05          │
   │ COHERENCIA    │ │ LEGAL         │ │ FIRMAS        │
   │               │ │               │ │               │
   │ Verifica que  │ │ Verifica que  │ │ Detecta si    │
   │ los números   │ │ se cumpla la  │ │ los documentos│
   │ cuadren:      │ │ normativa     │ │ están firmados│
   │ SINAD, SIAF,  │ │ aplicable     │ │ (digital o    │
   │ RUC, montos   │ │ (directivas)  │ │ manuscrita)   │
   └───────┬───────┘ └───────┬───────┘ └──────────────┘
           │                 │
   ┌───────▼───────┐ ┌──────▼───────┐
   │ AG07           │ │ AG06          │
   │ PENALIDADES    │ │ INTEGRIDAD    │
   │                │ │               │
   │ Evalúa si      │ │ Verifica que  │
   │ corresponde    │ │ estén todos   │
   │ aplicar multas │ │ los documentos│
   │ o penalidades  │ │ requeridos    │
   └───────┬───────┘ └───────────────┘
           │
   ┌───────▼───────┐
   │ AG08           │
   │ SUNAT          │
   │                │
   │ Consulta el    │
   │ estado del RUC │
   │ del proveedor  │
   │ (solo público) │
   └───────┬───────┘
           │
           ▼
   ┌──────────────────┐
   │  AG09 DECISOR     │
   │                    │
   │  Consolida TODO:   │
   │  hallazgos de los  │
   │  8 agentes previos │
   │  y emite veredicto │
   │  final con         │
   │  evidencia          │
   └──────────────────┘
```

---

## 5. Estructura de Carpetas del Proyecto

```
AG-EVIDENCE/
│
├── agentes/                    # Los 9 agentes del sistema
│   ├── agente_01_clasificador.py
│   ├── agente_02_ocr.py
│   ├── agente_03_coherencia.py
│   ├── agente_04_legal.py
│   ├── agente_05_firmas.py
│   ├── agente_06_integridad.py
│   ├── agente_07_penalidades.py
│   ├── agente_08_sunat.py
│   └── agente_09_decisor.py
│
├── src/                        # Código fuente estructurado
│   ├── domain/                 #   Reglas de negocio
│   ├── extraction/             #   Cadena de custodia + logger (Fase 1)
│   ├── orchestration/          #   Coordinación de agentes (futuro)
│   └── tools/                  #   Herramientas (OCR, PDF, etc.)
│
├── config/                     # Configuración del sistema
│   └── settings.py
│
├── utils/                      # Utilidades compartidas
│   ├── llm_local.py            #   Conexión con el modelo de IA
│   └── exportador_excel.py     #   Generación de reportes Excel
│
├── tests/                      # Pruebas automáticas
│   ├── unit/                   #   Pruebas de funciones individuales
│   └── integration/            #   Pruebas del sistema completo
│
├── data/                       # Datos (NO se suben a internet)
│   ├── directivas/             #   Normativa oficial (PDFs)
│   └── expedientes/            #   Expedientes de prueba
│
├── docs/                       # Documentación
│   ├── AGENT_GOVERNANCE_RULES.md  # Reglas de los agentes
│   ├── ARCHITECTURE_SNAPSHOT.md   # Foto del sistema actual
│   ├── ARCHITECTURE_VISUAL.md     # Este archivo
│   ├── CURRENT_STATE.md           # Estado del proyecto
│   ├── GLOSSARY.md                # Glosario de términos
│   └── GOVERNANCE_RULES.md        # Reglas de gobernanza
│
├── output/                     # Reportes generados (NO se suben)
│
├── orquestador.py              # Coordinador de los 9 agentes
├── chat_asistente.py           # Interfaz de chat (CLI)
└── ejecutar_control_previo.py  # Análisis masivo de expedientes
```

---

## 6. Flujo de Ramas (Control de Versiones)

```
GitHub (repositorio remoto)
        │
        ▼
   ┌─────────┐
   │  main   │  ← Versión estable y presentable
   └────┬────┘
        │ sincronización
        │
   ┌────┴──────────────┐
   │  dev / feature     │  ← Ramas de desarrollo activo
   └───────────────────┘

Regla: Todo cambio se hace en una rama de desarrollo
       y luego se incorpora a main cuando está listo.
```

---

## 7. Fases del Plan de Desarrollo

```
AHORA                                                    FUTURO
  │                                                        │
  ▼                                                        ▼

┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
│ FASE 1 │→│ FASE 2 │→│ FASE 3 │→│ FASE 4 │→│ FASE 5 │→│ FASE 6 │
│        │  │        │  │        │  │        │  │        │  │        │
│Trazabi-│  │Contrato│  │  Qwen  │  │Valida- │  │Evalua- │  │ Motor  │
│lidad + │  │de datos│  │Fallback│  │ciones  │  │ción +  │  │ Legal  │
│  OCR   │  │+ Router│  │quirúr- │  │aritmé- │  │prep.   │  │        │
│        │  │        │  │gico    │  │ticas   │  │legal   │  │        │
│7 tareas│  │5 tareas│  │5 tareas│  │3 tareas│  │5 tareas│  │6 tareas│
└────────┘  └────────┘  └────────┘  └────────┘  └────────┘  └────────┘
  Sem 1-4    Sem 3-6     Sem 5-8    Sem 7-8     Sem 9-10   Sem 11-14

                    TOTAL: 31 tareas en ~14 semanas
```

---

## 8. Principios Fundamentales

```
┌─────────────────────────────────────────────────────┐
│              PRINCIPIOS AG-EVIDENCE                  │
│                                                      │
│  1. EVIDENCIA PRIMERO                                │
│     Todo hallazgo cita: archivo + página + texto     │
│                                                      │
│  2. CERO INVENCIÓN                                   │
│     Si no hay dato, se dice "no consta"              │
│     Jamás se inventa información                     │
│                                                      │
│  3. LOCAL PRIMERO                                    │
│     Todo se procesa en tu máquina                    │
│     Ningún dato sale a internet                      │
│                                                      │
│  4. CADENA DE CUSTODIA                               │
│     El PDF original nunca se modifica                │
│     Cualquier auditor puede reproducir el resultado  │
│                                                      │
│  5. ABSTENCIÓN OPERATIVA                             │
│     Prefiere un vacío honesto                        │
│     a un dato inventado                              │
│                                                      │
│  6. MOTOR INTERCAMBIABLE                             │
│     El OCR se puede cambiar sin tocar                │
│     el resto del sistema                             │
└─────────────────────────────────────────────────────┘
```

---

**Ubicación:** `docs/ARCHITECTURE_VISUAL.md`
**Última actualización:** 2026-02-10
