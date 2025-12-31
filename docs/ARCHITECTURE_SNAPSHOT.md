# ARCHITECTURE_SNAPSHOT.md
## AG-EVIDENCE — Sistema de Análisis Probatorio de Expedientes

**Ministerio de Educación del Perú**  
**Fecha de snapshot:** 2025-12-18  
**Versión:** 2.0.0 (Estándar Probatorio)

---

## 1. Objetivo del Sistema

Sistema multi-agente para revisión automatizada de expedientes administrativos del sector público peruano (MINEDU). Analiza documentos PDF de expedientes de pago (viáticos, caja chica, encargos, pagos a proveedores) y genera un informe de Control Previo con decisión estructurada: **PROCEDE**, **PROCEDE CON OBSERVACIONES** o **NO PROCEDE**. Implementa una política anti-alucinación estricta: toda observación crítica/mayor debe tener evidencia probatoria (archivo + página + snippet literal).

---

## 2. Flujos Principales

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        FLUJO PRINCIPAL DE CONTROL PREVIO                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  PDFs Expediente                                                                │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────┐                                                            │
│  │ pdf_extractor   │──► Extracción texto + imágenes (PyMuPDF/fitz)             │
│  └────────┬────────┘                                                            │
│           │                                                                     │
│           ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        ORQUESTADOR (9 Agentes)                          │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │ AG01 Clasificador ──► Naturaleza (Viáticos/Caja Chica/Pago Proveedor)   │   │
│  │ AG02 OCR          ──► Calidad texto, páginas escaneadas                 │   │
│  │ AG03 Coherencia   ──► SINAD/SIAF/RUC/Montos consistentes                │   │
│  │ AG04 Legal        ──► Cumplimiento directiva, requisitos                │   │
│  │ AG05 Firmas       ──► Detección firmas digitales/manuscritas            │   │
│  │ AG06 Integridad   ──► Documentos faltantes según naturaleza             │   │
│  │ AG07 Penalidades  ──► Mora, cálculo penalidades contractuales           │   │
│  │ AG08 SUNAT        ──► Consulta RUC pública (informativo)                │   │
│  │ AG09 Decisor      ──► Consolidación + decisión final                    │   │
│  └────────────────────────────────────────────────────────────────────────┘    │
│           │                                                                     │
│           ▼                                                                     │
│  ┌─────────────────┐                                                            │
│  │ ValidadorEvid.  │──► Degrada CRÍTICO/MAYOR sin evidencia → INCIERTO         │
│  └────────┬────────┘                                                            │
│           │                                                                     │
│           ▼                                                                     │
│  ┌─────────────────┐                                                            │
│  │ ExportadorJSON  │──► output/*.json + output/*.txt (estándar probatorio)     │
│  └─────────────────┘                                                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────┐
│                        FLUJO CHAT ASISTENTE (CONVERSACIONAL)                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  PDFs Directivas + Expediente JSON                                              │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────┐                                                            │
│  │ Carga Docs      │──► cargar_pdf() / cargar_carpeta() / cargar_expediente_json│
│  └────────┬────────┘                                                            │
│           │                                                                     │
│           ▼                                                                     │
│  ┌─────────────────┐                                                            │
│  │ Indexación      │──► _indexar_texto() → Dict[palabra → (archivo, pág, ctx)] │
│  └────────┬────────┘                                                            │
│           │                                                                     │
│           ▼                                                                     │
│  ┌─────────────────┐                                                            │
│  │ Retrieval       │──► retrieval() determinístico (términos → evidencias)     │
│  └────────┬────────┘                                                            │
│           │                                                                     │
│           ▼                                                                     │
│  ┌─────────────────┐                                                            │
│  │ LLM Local       │──► Ollama/Qwen (reformulación, NO inferencia)             │
│  └────────┬────────┘                                                            │
│           │                                                                     │
│           ▼                                                                     │
│  ┌─────────────────┐                                                            │
│  │ Validación      │──► _validar_numeracion_en_snippet() → anti-alucinación    │
│  └────────┬────────┘                                                            │
│           │                                                                     │
│           ▼                                                                     │
│  Respuesta con citas (archivo + página + snippet)                               │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Módulos/Archivos Clave y Responsabilidades

| Archivo | Propósito | Entradas | Salidas |
|---------|-----------|----------|---------|
| `ejecutar_control_previo.py` | CLI principal para análisis batch de expedientes | `--carpeta`, `--guardar`, `--silencioso` | Exit code (0=PROCEDE, 1=OBS, 2=NO_PROCEDE) |
| `orquestador.py` | Coordina ejecución secuencial de 9 agentes | Lista de `DocumentoPDF` | `InformeControlPrevio` |
| `chat_asistente.py` | Chat interactivo con retrieval + LLM | `--pdf`, `--carpeta`, `--expediente_json`, `--backend`, `--modo` | Respuestas con citas |
| `config/settings.py` | Enums, dataclasses, configuración global | — | `NaturalezaExpediente`, `Observacion`, `EvidenciaProbatoria`, etc. |
| `utils/pdf_extractor.py` | Extrae texto/imágenes de PDFs | Ruta PDF | `DocumentoPDF` (páginas + texto + metadatos) |
| `utils/llm_local.py` | Cliente Ollama con política anti-alucinación | Prompt + contexto JSON | `RespuestaLLM` validada |
| `utils/validador_evidencia.py` | Valida que CRÍTICO/MAYOR tengan evidencia completa | `Observacion` | Degrada a INCIERTO si falla |
| `utils/exportador_json.py` | Exporta hallazgos a JSON/TXT probatorio | `InformeControlPrevio` | Archivos en `output/` |
| `agentes/agente_01_clasificador.py` | Detecta naturaleza (Viáticos/Caja Chica/Pago Proveedor) | Documentos | `ResultadoAgente` |
| `agentes/agente_02_ocr.py` | Evalúa calidad de texto, páginas escaneadas | Documentos | `ResultadoAgente` |
| `agentes/agente_03_coherencia.py` | Verifica consistencia SINAD/SIAF/RUC/Montos | Documentos | `ResultadoAgente` |
| `agentes/agente_04_legal.py` | Verifica cumplimiento de directiva aplicable | Documentos + Naturaleza | `ResultadoAgente` |
| `agentes/agente_05_firmas.py` | Detecta firmas digitales/manuscritas | Documentos | `ResultadoAgente` |
| `agentes/agente_06_integridad.py` | Verifica documentos requeridos según naturaleza | Documentos + Naturaleza | `ResultadoAgente` |
| `agentes/agente_07_penalidades.py` | Calcula penalidades por mora/incumplimiento | Documentos | `ResultadoAgente` |
| `agentes/agente_08_sunat.py` | Consulta RUC pública (informativo) | Documentos | `ResultadoAgente` |
| `agentes/agente_09_decisor.py` | Consolida hallazgos y emite decisión final | Lista de `ResultadoAgente` | `InformeControlPrevio` |

---

## 4. CLI/Flags Disponibles y Ejemplos de Ejecución

### 4.1 Análisis Batch de Expedientes

```powershell
# Análisis sobre carpeta Downloads (default)
python ejecutar_control_previo.py

# Análisis sobre carpeta específica con guardado automático
python ejecutar_control_previo.py --carpeta "C:\ruta\AG-EVIDENCE\data\expedientes\pruebas\01_rendicion" --guardar

# Modo silencioso
python ejecutar_control_previo.py --silencioso --guardar --output "output\mi_informe.txt"
```

**Exit codes:**
- `0` = PROCEDE
- `1` = PROCEDE CON OBSERVACIONES
- `2` = NO PROCEDE

### 4.2 Chat Asistente Conversacional

```powershell
# Modo conversacional con LLM (carga directivas por defecto)
python chat_asistente.py --modo conversacional --backend llm

# Con PDFs específicos (--pdf puede repetirse)
python chat_asistente.py --modo conversacional --backend llm --pdf "data\expedientes\pruebas\01_rendicion\archivo1.pdf" --pdf "data\expedientes\pruebas\01_rendicion\archivo2.pdf"

# Con carpeta completa
python chat_asistente.py --carpeta "data\expedientes\pruebas\01_rendicion" --backend llm

# Con JSON de expediente analizado
python chat_asistente.py --expediente_json "output\informe_control_previo_20251215_172759.json" --backend llm

# Sin LLM (solo retrieval + regex)
python chat_asistente.py --backend regex
```

**Comandos internos del chat:**
| Comando | Descripción |
|---------|-------------|
| `resumen` | Resumen ≤5 líneas del expediente |
| `devolver` | Texto formal para devolución al área usuaria + citas |
| `subsanable` | Lista observaciones subsanables |
| `evidencia N` | Muestra evidencia N completa (archivo + página + snippet) |
| `modo` | Alternar entre técnico/conversacional |
| `info` | Estado del sistema (backend, PDFs cargados, memoria) |
| `memoria` | Historial de preguntas |
| `exit` | Salir del chat |

---

## 5. Estructura de Carpetas Relevante

```
AG-EVIDENCE/
├── agentes/                          # 9 agentes especializados
│   ├── agente_01_clasificador.py
│   ├── agente_02_ocr.py
│   ├── agente_03_coherencia.py
│   ├── agente_04_legal.py
│   ├── agente_05_firmas.py
│   ├── agente_06_integridad.py
│   ├── agente_07_penalidades.py
│   ├── agente_08_sunat.py
│   └── agente_09_decisor.py
├── config/
│   └── settings.py                   # Enums, dataclasses, configuración
├── data/
│   ├── directivas/
│   │   └── vigentes_2025_11_26/      # PDFs de directivas MINEDU
│   │       ├── CAJA CHICA/
│   │       ├── ENCARGO/
│   │       ├── PAUTAS/
│   │       └── VIÁTICO/
│   └── expedientes/
│       └── pruebas/                  # Expedientes de prueba
│           ├── 01_rendicion/
│           ├── 02_encargo/
│           ├── 03_caja_chica/
│           └── 99_mixtos/
├── docs/                             # Documentación
│   ├── AGENT_GOVERNANCE_RULES.md     # Reglas de gobernanza (normativo)
│   ├── ARCHITECTURE_SNAPSHOT.md      # Estado actual del sistema
│   └── OCR_SPEC.md                   # Especificación técnica OCR
├── output/                           # Informes generados (JSON + TXT)
├── tests/                            # Tests unitarios
├── utils/
│   ├── exportador_json.py            # Exportación probatoria
│   ├── llm_local.py                  # Cliente Ollama
│   ├── pdf_extractor.py              # Extracción PDFs
│   └── validador_evidencia.py        # Validación estándar probatorio
├── chat_asistente.py                 # Chat conversacional (entrypoint CLI)
├── ejecutar_control_previo.py        # Análisis batch (entrypoint CLI)
├── orquestador.py                    # Coordinador multi-agente
├── AGENTS.md                         # Reglas para agentes IA
├── README.md
└── requirements.txt
```

---

## 6. Estado Actual: Qué Funciona y Qué Falla

### ✅ Funciona Hoy

| Funcionalidad | Estado | Notas |
|---------------|--------|-------|
| Extracción de texto PDF (PyMuPDF) | ✅ Operativo | Texto directo, sin OCR real |
| Clasificación de naturaleza (AG01) | ✅ Operativo | Viáticos, Caja Chica, Pago Proveedor, etc. |
| Detección de inconsistencias (AG03) | ✅ Operativo | SINAD, SIAF, RUC, Montos |
| Verificación de integridad (AG06) | ✅ Operativo | Documentos faltantes según naturaleza |
| Decisión final (AG09) | ✅ Operativo | PROCEDE / CON OBS / NO PROCEDE |
| Exportación JSON/TXT probatoria | ✅ Operativo | Con evidencias (archivo + pág + snippet) |
| Chat con retrieval determinístico | ✅ Operativo | Sin LLM funciona con regex |
| Chat con LLM (Ollama/Qwen) | ✅ Operativo | Requiere Ollama corriendo en localhost:11434 |
| Validación anti-alucinación de numerales | ✅ Operativo | Reemplaza Art/Numeral no citados en snippet |
| Degradación a INCIERTO sin evidencia | ✅ Operativo | CRÍTICO/MAYOR → INCIERTO si falta evidencia |

### ⚠️ Funciona Parcialmente

| Funcionalidad | Estado | Error/Limitación |
|---------------|--------|------------------|
| Consulta SUNAT (AG08) | ⚠️ Parcial | APIs públicas pueden fallar; solo informativo |
| OCR real (AG02) | ⚠️ Parcial | Solo evalúa calidad, no hace OCR de imágenes escaneadas |
| Verificación de firmas (AG05) | ⚠️ Parcial | Heurística simple (busca keywords), no valida criptográficamente |
| Penalidades (AG07) | ⚠️ Parcial | Detección básica, cálculo no implementado completamente |

### ❌ No Funciona / No Implementado

| Funcionalidad | Estado | Razón |
|---------------|--------|-------|
| OCR de imágenes escaneadas | ❌ | No hay Tesseract/EasyOCR integrado |
| SIRE / Clave SOL | ❌ | Restricción de diseño (solo APIs públicas) |
| UI/Visor web | ❌ | Solo CLI |
| Extracción de tablas estructuradas | ❌ | Heurística básica, no robusto |

---

## 7. Deuda Técnica y Riesgos

### 7.1 Anti-Alucinación

| Área | Estado | Riesgo |
|------|--------|--------|
| Retrieval determinístico | ✅ Implementado | Bajo |
| Validación de numerales en snippet | ✅ Implementado | Bajo |
| Degradación CRÍTICO→INCIERTO sin evidencia | ✅ Implementado | Bajo |
| Preguntas prohibidas (subjetivas) | ✅ Implementado | Bajo |
| **LLM puede inventar datos no solicitados** | ⚠️ Riesgo medio | El prompt es estricto pero LLM puede desviarse |

### 7.2 Citación y Evidencia

| Área | Estado | Riesgo |
|------|--------|--------|
| Cita archivo + página + snippet | ✅ Implementado | Bajo |
| Evidencias en JSON probatorio | ✅ Implementado | Bajo |
| **Documentos faltantes sin evidencia positiva** | ⚠️ Riesgo | Se marca INCIERTO, pero el hallazgo existe |

### 7.3 JSON Expediente

| Área | Estado | Riesgo |
|------|--------|--------|
| Estructura JSON v2.0 probatoria | ✅ Implementado | Bajo |
| Compatibilidad con chat_asistente | ✅ Implementado | Bajo |
| **No hay versionado de esquema** | ⚠️ Riesgo bajo | Cambios futuros podrían romper compatibilidad |

### 7.4 OCR

| Área | Estado | Riesgo |
|------|--------|--------|
| Detección de páginas escaneadas | ✅ Implementado | Bajo |
| **OCR real no implementado** | ❌ Alto riesgo | Expedientes escaneados no se leen correctamente |

### 7.5 UI/Visor

| Área | Estado | Riesgo |
|------|--------|--------|
| CLI funcional | ✅ Implementado | Bajo |
| **No hay UI web** | ⚠️ Riesgo UX | Usuarios no técnicos no pueden usar el sistema |

---

## 8. Próximos 5 Pasos Recomendados (Priorizados)

| # | Prioridad | Tarea | Impacto | Esfuerzo |
|---|-----------|-------|---------|----------|
| 1 | 🔴 CRÍTICA | **Implementar OCR real** (Tesseract o EasyOCR) para páginas escaneadas | Alto: muchos expedientes MINEDU son escaneados | Medio |
| 2 | 🟠 ALTA | **Agregar tests de integración** con expedientes reales en `data/expedientes/pruebas/` | Alto: validar flujo completo | Bajo |
| 3 | 🟠 ALTA | **Mejorar agente de penalidades (AG07)** con cálculo real de mora | Medio: evita errores en montos | Medio |
| 4 | 🟡 MEDIA | **Crear UI web básica** (FastAPI + HTML) para usuarios no técnicos | Alto: adopción del sistema | Alto |
| 5 | 🟡 MEDIA | **Implementar caché de consultas SUNAT** para evitar llamadas repetidas | Bajo: mejora performance | Bajo |

---

## 9. CURRENT_STATE

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           CURRENT_STATE (2025-12-18)                         │
├──────────────────────────────────────────────────────────────────────────────┤
│ ✅ Sistema multi-agente (9 agentes) operativo para análisis de expedientes   │
│ ✅ Chat conversacional con retrieval + LLM (Ollama/Qwen) funcionando         │
│ ✅ Estándar probatorio implementado (archivo + página + snippet)             │
│ ✅ Anti-alucinación: validación de numerales + degradación a INCIERTO        │
│ ✅ Exportación JSON/TXT probatorio en output/                                │
│ ✅ Directivas MINEDU vigentes cargadas en data/directivas/                   │
│ ⚠️ OCR real NO implementado (solo detección de páginas escaneadas)           │
│ ⚠️ SUNAT solo informativo (APIs públicas, sin SOL/SIRE)                      │
│ ⚠️ Penalidades: detección básica, cálculo incompleto                        │
│ ❌ No hay UI web — solo CLI                                                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

**Documento generado automáticamente por análisis de código.**  
**Última actualización:** 2025-12-18

