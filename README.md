# 🔒 AG-EVIDENCE — Sistema de Análisis Probatorio de Expedientes

**Ministerio de Educación del Perú**

---

## 📋 Descripción

**AG-EVIDENCE** es un sistema multi-agente para análisis probatorio de expedientes administrativos en procesos de control previo.  

El sistema analiza expedientes en formato PDF y emite conclusiones estructuradas (**PROCEDE / PROCEDE CON OBSERVACIONES / NO PROCEDE**) bajo un **estándar probatorio estricto**, con evidencia verificable (archivo, página y extracto literal).

El proyecto está diseñado para operar en entornos críticos, con políticas explícitas de **anti-alucinación**, **trazabilidad documental** y **restricción de inferencias**.

---

## 📌 Documentos Rectores (Autoridad del Proyecto)

Este proyecto se rige obligatoriamente por los siguientes documentos, los cuales tienen **prioridad normativa sobre cualquier sugerencia automática, refactorización o generación de código**:

### 1. `docs/AGENT_GOVERNANCE_RULES.md`
Documento normativo de gobernanza del sistema.  
Define:
- Reglas obligatorias de comportamiento de los agentes
- Política anti-alucinación
- Enrutamiento por naturaleza del expediente
- Reglas críticas de OCR y legibilidad humana
- Prohibiciones absolutas del sistema

### 2. `docs/ARCHITECTURE_SNAPSHOT.md`
Fotografía técnica del estado actual del sistema.  
Describe:
- Arquitectura multi-agente
- Flujos operativos
- Componentes implementados y pendientes
- Riesgos, deuda técnica y próximos pasos

👉 **Cualquier desarrollo, modificación o análisis debe ser consistente con ambos documentos.**

---

## ⚠️ Advertencia Crítica

Este proyecto **NO es un chatbot genérico**.  

El uso de modelos LLM está **restringido** a reformulación, estructuración y asistencia conversacional **sin inferencia normativa ni creación de requisitos**.

Las observaciones del sistema deben estar respaldadas por evidencia documental. Si no existe evidencia, el sistema debe indicar expresamente: *"No consta información suficiente en los documentos revisados."*

---

## 🏗️ Arquitectura Multi-Agente

```
┌─────────────────────────────────────────────────────────────────┐
│                      ORQUESTADOR PRINCIPAL                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│  │ AGENTE 01  │  │ AGENTE 02  │  │ AGENTE 03  │                │
│  │Clasificador│──│    OCR     │──│ Coherencia │                │
│  └────────────┘  └────────────┘  └────────────┘                │
│         │              │              │                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│  │ AGENTE 04  │  │ AGENTE 05  │  │ AGENTE 06  │                │
│  │   Legal    │──│   Firmas   │──│ Integridad │                │
│  └────────────┘  └────────────┘  └────────────┘                │
│         │              │              │                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│  │ AGENTE 07  │  │ AGENTE 08  │  │ AGENTE 09  │                │
│  │Penalidades │──│   SUNAT    │──│  Decisor   │                │
│  └────────────┘  └────────────┘  └────────────┘                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Descripción de Agentes

| Agente | Nombre | Función |
|--------|--------|---------|
| AG01 | Clasificador | Detecta naturaleza: viáticos, caja chica, encargo, pago proveedor |
| AG02 | OCR Avanzado | Mejora extracción de texto, detecta firmas manuscritas, sellos |
| AG03 | Coherencia | Cruza SINAD, expediente, orden, contrato. Detecta errores de dígitos |
| AG04 | Legal | Aplica directiva/pauta correspondiente, verifica requisitos |
| AG05 | Firmas | Verifica competencia de firmantes según TDR/directiva |
| AG06 | Integridad | Verifica documentación completa (TDR, CCI, conformidad, etc.) |
| AG07 | Penalidades | Evalúa si corresponde aplicar penalidad por mora |
| AG08 | SUNAT | Consulta pública de RUC (estado, condición, actividad) |
| AG09 | Decisor | Consolida hallazgos y determina PROCEDE/NO PROCEDE |

---

## ⚠️ Restricciones de Seguridad

El sistema opera bajo restricciones estrictas:

- ❌ **NO** usa Clave SOL
- ❌ **NO** integra SIRE autenticado
- ❌ **NO** usa servicios de pago
- ❌ **NO** actúa como proveedor autorizado SUNAT
- ✅ Solo consultas públicas SUNAT / APIs gratuitas
- ✅ Todos los resultados SUNAT son **INFORMATIVOS**
- ✅ Si hay duda → reporta **INCERTIDUMBRE** (no inventa)

---

## 🚀 Instalación

### Requisitos

- Python 3.8 o superior
- Windows 10/11

### Pasos

1. **Instalar dependencias:**

```bash
cd AG-EVIDENCE
pip install -r requirements.txt
```

2. **Verificar instalación:**

```bash
python -c "import fitz; print('PyMuPDF OK')"
```

---

## 📖 Uso

### Modo Simple (Carpeta Downloads)

```bash
python ejecutar_control_previo.py
```

### Especificar Carpeta

```bash
python ejecutar_control_previo.py --carpeta "C:\ruta\expediente"
```

### Guardar Informe Automáticamente

```bash
python ejecutar_control_previo.py --guardar
```

### Modo Silencioso

```bash
python ejecutar_control_previo.py --silencioso --guardar
```

### Desde Python

```python
from orquestador import ejecutar_control_previo

# Analizar carpeta de expediente
informe = ejecutar_control_previo("C:\\expedientes\\2025")

# Acceder a la decisión
print(informe.decision)  # PROCEDE / NO_PROCEDE / PROCEDE_CON_OBSERVACIONES
```

---

## 📊 Formato de Salida

El sistema genera un informe estructurado con:

1. **Naturaleza del expediente** (viáticos, pago proveedor, etc.)
2. **Directiva/pauta aplicada**
3. **Resumen ejecutivo**
4. **Observaciones críticas** (🔴 bloquean pago)
5. **Observaciones mayores** (🟡 subsanables)
6. **Observaciones menores** (🟢 informativas)
7. **Riesgos SUNAT** (informativos)
8. **Recomendación final**
9. **Acción requerida y área responsable**

### Ejemplo de Salida

```
====================================================================================================
🔴 DECISIÓN: NO PROCEDE
====================================================================================================

📝 RESUMEN EJECUTIVO:
❌ El expediente NO PROCEDE por observaciones críticas.
   Se detectaron 7 observaciones que bloquean el pago.

🔴 OBSERVACIONES CRÍTICAS (Bloquean pago):
1. Inconsistencia en RUC: 20417494406 vs 20417494409 (error de dígito)
   📌 Evidencia: Documentos afectados: [lista]
   ⚡ Acción: VERIFICAR RUC del proveedor
   👤 Responsable: Oficina de Logística

📋 RECOMENDACIÓN FINAL:
Se recomienda DEVOLVER el expediente al área correspondiente para subsanación.
```

---

## 🛡️ Códigos de Salida

El script retorna códigos útiles para automatización:

| Código | Significado |
|--------|-------------|
| 0 | ✅ PROCEDE |
| 1 | 🟡 PROCEDE CON OBSERVACIONES |
| 2 | 🔴 NO PROCEDE |
| 130 | Cancelado por usuario (Ctrl+C) |

---

## 📁 Estructura del Proyecto

```
AG-EVIDENCE/
├── orquestador.py              # Orquestador principal
├── ejecutar_control_previo.py  # Análisis batch de expedientes
├── chat_asistente.py           # Chat conversacional (entrypoint CLI)
├── requirements.txt
├── README.md
├── AGENTS.md                   # Instrucciones para agentes IA
│
├── agentes/                    # 9 agentes especializados
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
├── config/
│   └── settings.py             # Configuración global
│
├── docs/                       # Documentación del proyecto
│   ├── AGENT_GOVERNANCE_RULES.md
│   ├── ARCHITECTURE_SNAPSHOT.md
│   └── OCR_SPEC.md
│
├── utils/
│   ├── pdf_extractor.py        # Extracción de PDFs
│   ├── llm_local.py            # Cliente LLM (Ollama)
│   ├── validador_evidencia.py  # Validación probatoria
│   └── exportador_json.py      # Exportación JSON/TXT
│
└── output/                     # Informes generados
```

---

## 🔧 Extensibilidad

### Agregar Nueva Directiva

1. Editar `config/settings.py`
2. Agregar keywords en `KEYWORDS_NATURALEZA`
3. Crear requisitos en `agente_04_legal.py`

### Habilitar SIRE (Futuro)

El sistema está preparado para integrar SIRE cuando se disponga de Clave SOL:

```python
# config/settings.py
SUNAT_CONFIG = {
    "sire_habilitado": True,  # Cambiar a True
    "sol_habilitado": True,   # Cambiar a True
    "sol_usuario": "...",
    "sol_clave": "..."
}
```

---

## 📞 Soporte

Sistema desarrollado para uso interno del Ministerio de Educación del Perú.

**Control Previo - Oficina General de Administración**

---

## 🤖 Chat Asistente (v2.1)

El sistema incluye un **Chat Asistente** que permite consultar directivas y expedientes de manera conversacional.

### Uso Básico

```bash
# Modo conversacional con LLM (carga directivas por defecto)
python chat_asistente.py --modo conversacional --backend llm

# Con PDFs específicos (--pdf puede repetirse)
python chat_asistente.py --pdf "data/expedientes/pruebas/archivo.pdf" --backend llm

# Con carpeta de expediente
python chat_asistente.py --carpeta "data/expedientes/pruebas/01_rendicion" --backend llm

# Con JSON de expediente analizado
python chat_asistente.py --expediente_json "output/informe.json" --backend llm

# Solo regex (sin LLM)
python chat_asistente.py --backend regex
```

### Ejemplos de Preguntas

| Tipo | Ejemplo |
|------|---------|
| Decisión | "¿Por qué no procede?" |
| Búsqueda | "¿En qué archivo aparece el 54719?" |
| Inconsistencias | "¿Dónde está la inconsistencia del SINAD?" |
| Escenarios | "¿Qué pasa si se corrige el RUC?" |
| Filtros | "Resume solo lo de firmas" |
| Libre (LLM) | "Explícame los riesgos de este expediente" |

### Backends

| Backend | Descripción | Requisitos |
|---------|-------------|------------|
| **regex** | Patrones predefinidos. Rápido pero limitado. | Ninguno |
| **llm** | Ollama + Qwen. Entiende lenguaje natural libre. | Ollama + modelo |
| **auto** | Usa LLM si disponible, sino regex (default). | Ninguno |

---

## 🧠 Requisitos para LLM Local (Opcional)

Para habilitar el modo LLM con lenguaje natural libre:

### 1. Instalar Ollama

```bash
# Windows: Descargar desde https://ollama.ai/download
# O con winget:
winget install Ollama.Ollama
```

### 2. Descargar Modelo Qwen

```bash
# Modelo recomendado (7B)
ollama pull qwen2.5:7b-instruct

# O modelo más grande (14B, mejor calidad)
ollama pull qwen2.5:14b
```

### 3. Verificar Instalación

```bash
# Listar modelos
ollama list

# Verificar desde el sistema
python -c "from utils.llm_local import verificar_ollama; print(verificar_ollama())"
```

### Modelos Compatibles

| Modelo | Tamaño | Recomendación |
|--------|--------|---------------|
| qwen2.5:7b-instruct | ~4GB | Bueno para uso general |
| qwen2.5:14b | ~8GB | Mejor comprensión |
| qwen2.5:3b | ~2GB | Para equipos con poca RAM |
| llama3.2:3b | ~2GB | Alternativa ligera |

---

## 📝 Notas de Versión

### v2.1.0 (Diciembre 2025)
- ✅ Agente Conversacional con LLM local (Ollama + Qwen)
- ✅ Búsqueda de valores específicos (SINAD, RUC, etc.)
- ✅ Modo auto-detección de backend
- ✅ Preguntas en lenguaje natural libre

### v2.0.0 (Diciembre 2025)
- ✅ Estándar probatorio con evidencia detallada
- ✅ Validación automática de hallazgos
- ✅ Degradación de severidad sin evidencia
- ✅ Exportación JSON/TXT mejorada

### v1.0.0 (Diciembre 2025)
- ✅ 9 agentes especializados
- ✅ OCR con detección de calidad
- ✅ Verificación de coherencia documental
- ✅ Consulta pública SUNAT (RUC)
- ✅ Detección de errores de dígitos
- ✅ Verificación de firmas
- ✅ Evaluación de penalidades
- ✅ Generación de informes estructurados

