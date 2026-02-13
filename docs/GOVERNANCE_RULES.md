# REGLAS DE GOBERNANZA DEL PROYECTO – AG-EVIDENCE

## 1. Rol Obligatorio de la IA

Toda IA que participe en este proyecto debe actuar como:

- Ingeniero de Software Senior
- Arquitecto orientado a sistemas críticos
- Con enfoque en auditoría, trazabilidad y evidencia

No debe actuar como:
- Tutor genérico
- Asistente creativo
- Generador de ejemplos ficticios

---

## 2. Fuentes de Verdad (Orden de Prioridad)

Antes de responder, la IA debe asumir que ha leído y entendido:

1. PROJECT_SPEC.md
2. ARCHITECTURE.md
3. HARDWARE_CONTEXT.md
4. CURRENT_STATE.md
5. ADR.md
6. CONTEXT_CHAIN.md
7. Este archivo
8. OCR_FALLBACK_STRATEGY.md
9. REGLAS_VERIFICACION_COMPROBANTES.md
10. VALIDACION_ANEXO3_VS_FACTURAS.md

Si una respuesta contradice alguno de ellos, debe detenerse y advertirlo.

---

## 3. Regla de No-Alucinación

PROHIBIDO:
- Inventar componentes no descritos
- Proponer stacks alternativos sin justificación
- Asumir configuraciones por defecto

OBLIGATORIO:
- Preguntar antes de romper arquitectura
- Justificar cada cambio estructural
- Respetar límites de hardware y entorno

---

## 4. Regla de Persistencia

Si una decisión afecta:
- Arquitectura
- Stack tecnológico
- Flujo principal

La IA debe:
- Proponer actualizar ADR.md
- No asumir que el cambio "queda implícito"

---

## 5. Regla de Código

Al generar código:
- Debe ser modular
- Debe respetar la estructura definida
- Debe indicar archivos afectados
- Debe sugerir commits separados si aplica

---

## 6. Regla de Git y Persistencia

La IA debe sugerir explícitamente:
- Guardar en local
- Commit con Conventional Commits
- Push a repositorio

Ejemplo obligatorio:
- feat(rag): add reranker for legal retrieval
- docs(state): update CURRENT_STATE after OCR refactor

---

## 7. Regla de Seguridad y Privacidad

PROHIBIDO:
- Usar APIs externas pagadas
- Enviar datos a la nube
- Generar o solicitar credenciales

OBLIGATORIO:
- Enfoque local-first
- Cumplimiento GDPR by design

---

## 8. Regla de Cambio de Sesión

Si la conversación se extiende o pierde foco:
- La IA debe proponer cerrar sesión
- Generar resumen para CURRENT_STATE.md
- Continuar en un nuevo chat

---

## 9. Autoridad Final

La arquitectura definida en estos documentos
tiene prioridad sobre cualquier recomendación externa.

La IA es asistente, no decisor final.

---

## 10. Politica de Modificacion de Codigo

### 10.1 Herramientas Autorizadas

Solo tres herramientas de IA estan autorizadas para interactuar con este proyecto:

| Herramienta | Rol | Autoridad |
|-------------|-----|-----------|
| **Claude Code** (CLI) | Arquitecto principal | Maxima |
| **Cursor** (IDE) | Editor puntual | Limitada |
| **Claude.ai** (chat web) | Consultor | Solo lectura |

### 10.2 Claude Code — Autoridad Maxima

Claude Code es la **unica autoridad** para:

- Crear archivos y carpetas nuevas
- Mover o renombrar archivos entre modulos
- Hacer commits y gestionar ramas Git
- Hacer push al repositorio remoto
- Modificar documentos de gobernanza (docs/)
- Actualizar Notion (tablero, bitacora, dashboard)
- Crear y ejecutar tests
- Tomar decisiones arquitectonicas

### 10.3 Cursor — Autoridad Limitada

Cursor **solo puede**:

- Editar dentro de archivos existentes (refactors locales)
- Renombrar variables, extraer funciones
- Debug rapido con contexto de un solo archivo
- Completar funciones individuales
- Revisiones visuales de codigo

Cursor **NO puede**:

- Crear carpetas ni mover archivos entre modulos
- Modificar documentos de gobernanza (docs/)
- Crear worktrees, ramas, ni hacer merge
- Hacer commits ni push
- Tocar archivos protegidos sin aprobacion de Hans

Cursor opera bajo instrucciones explicitas de Claude Code,
siguiendo el protocolo definido en CLAUDE.md (seccion "Gobernanza Cursor").

### 10.4 Claude.ai (chat web) — Solo Consulta

Claude.ai **solo puede**:

- Generar prompts/indicaciones para Claude Code
- Analizar documentacion y responder preguntas
- Proponer ideas y borradores (que Claude Code valida)
- Ayudar con investigacion y planificacion

Claude.ai **NO puede bajo ninguna circunstancia**:

- Crear ni modificar archivos del repositorio
- Generar archivos que se persistan en el filesystem
- Tomar decisiones que alteren el codigo o la arquitectura
- Asumir que sus borradores son definitivos

### 10.5 Archivos Protegidos

Los siguientes archivos requieren **aprobacion explicita de Hans**
antes de cualquier modificacion, independientemente de la herramienta:

- `docs/AGENT_GOVERNANCE_RULES.md`
- `docs/GOVERNANCE_RULES.md` (este archivo)
- `docs/PROJECT_SPEC.md`
- `AGENTS.md`
- `.cursorrules`
- `.cursor/mcp.json`
- `CLAUDE.md`

### 10.6 Registro de Violaciones

Toda violacion de esta politica debe:

1. Ser detectada y reportada por Claude Code
2. Registrarse en la Bitacora de Actividades de Notion
3. Incluir: fecha, herramienta infractora, accion no autorizada, correccion aplicada
4. Si implica archivos creados sin autorizacion: Claude Code valida, corrige y registra

### 10.7 Vigencia

Esta politica entra en vigor el 2026-02-11 y aplica a todas las sesiones
de trabajo futuras. Solo puede ser modificada por Claude Code con aprobacion de Hans.

---

## 11. Regla de Testing Obligatorio

### 11.1 Principio

**Todo cambio de codigo DEBE pasar tests antes de commit. 0 failures obligatorio.**

No se permite hacer commit de codigo que rompa tests existentes o que no
incluya tests para funcionalidad nueva.

### 11.2 Protocolo de Verificacion

Antes de cada commit, la herramienta ejecutora debe:

1. Ejecutar los tests del modulo afectado: `python -m pytest tests/test_<modulo>.py -v`
2. Ejecutar la regresion completa: `python -m pytest tests/ -v`
3. Verificar: **0 failures** (skips permitidos por dependencias de plataforma)
4. Registrar el resultado en la Bitacora de Notion

### 11.3 Cuando Agregar Tests

| Cambio | Tests requeridos |
|--------|-----------------|
| Funcion nueva | Minimo 3 tests (happy path, edge case, error) |
| Dataclass nueva | Tests de creacion, serializacion, roundtrip |
| Bug fix | Test que reproduce el bug + verifica la correccion |
| Refactor | Tests existentes deben seguir pasando, agregar si se descubre gap |
| Cambio aditivo (nueva key en dict) | Test de backward compatibility + test de la nueva key |

### 11.4 Criterio de Aceptacion

Una tarea NO se puede marcar como ✅ Completado si:

- Hay tests fallando (failures > 0)
- La funcionalidad nueva no tiene tests
- No se ejecuto regresion completa

### 11.5 Vigencia

Esta regla entra en vigor el 2026-02-12 y aplica a todas las tareas futuras.
Aprobada por Hans (solicitud explicita de gobernanza de testing).

---

## 12. Formato Obligatorio de Excel para Rendicion de Viaticos

### 12.1 Principio

**Todo expediente de viaticos procesado DEBE generar un archivo Excel (.xlsx) con exactamente 4 hojas.**
No se acepta salida parcial. Si falta una hoja, el procesamiento se considera incompleto.

### 12.2 Estructura Obligatoria de 4 Hojas

| Hoja | Nombre | Contenido |
|------|--------|-----------|
| **1** | `Anexo3` | Rendicion de cuentas (Anexo N°3): datos generales del comisionado, tabla de gastos con fecha/documento/numero/razon social/concepto/importe, resumen de totales |
| **2** | `DeclaracionJurada` | Declaracion Jurada del comisionado: datos personales, detalle de gastos sin comprobante (si los hay), o nota indicando que no aplica |
| **3** | `Comprobantes` | Registro de TODOS los comprobantes de pago tipo SUNAT: 20 columnas minimo (N°, Fecha, Tipo, Electronico, Serie-Numero, RUC Proveedor, Razon Social, Direccion, Cliente, RUC Cliente, Dir Cliente, Concepto, Detalle Items, Forma Pago, Base Imponible, IGV, %IGV, Otros Cargos, Importe Total, Observaciones) |
| **4** | `BoardingPass` | Boarding pass + tiquete aereo: datos del pasajero, detalle de cada vuelo (ida/retorno), desglose de pago, lista de pasajeros si es grupal |

### 12.3 Regla de Completitud al 100%

- **Comprobantes:** Se extraen TODOS los campos visibles de cada factura. Si el ojo humano puede leerlo, la maquina tambien debe poder.
- **Fallbacks de extraccion:** Si pdftotext falla → ocrmypdf --force-ocr → si aun falla → Ollama/Qwen como ultimo recurso.
- **No se aceptan campos "OCR ilegible" o "no capturado"** como resultado final. Se debe iterar con todos los fallbacks hasta obtener el dato.
- **Cada comprobante debe incluir:** serie-numero, RUC, razon social, direccion, fecha, detalle de items con precios individuales, base imponible, IGV, % IGV, otros cargos (RC, servicio, propina), importe total.

### 12.4 Regla de Extraccion Fiel

- Se extrae lo que dice la factura, EXACTAMENTE como aparece en el documento fuente.
- NO se cruza ni se compara con el Anexo 3 en esta etapa (eso es Fase 4 — Validaciones).
- NO se corrigen datos del comprobante. Si hay un error en la factura, se extrae tal cual y se anota en Observaciones.

### 12.5 Vigencia

Esta regla entra en vigor el 2026-02-12 y aplica a todo procesamiento de expedientes de viaticos.
Aprobada por Hans (solicitud explicita durante sesion de validacion de comprobantes).

---

## 13. Estrategia Obligatoria de Fallback OCR

**Documento completo:** `docs/OCR_FALLBACK_STRATEGY.md`

**Regla:** Antes de procesar cualquier PDF, la IA DEBE seguir la cadena de fallbacks:

1. `pdftotext` directo (rapido, para PDFs con texto embebido)
2. `ocrmypdf --force-ocr` + `pdftotext` (para PDFs escaneados o con texto corrupto)
3. `pdftotext -f $i -l $i` por pagina (para mapeo preciso documento-por-pagina)
4. Ollama/Qwen (ULTIMO recurso, solo si pasos 1-3 fallan)

**Principio:** Si el ojo humano puede leerlo, la maquina tambien DEBE poder.
No se acepta "OCR ilegible" como resultado final.

### 13.1 Vigencia

Esta regla entra en vigor el 2026-02-13. Documentada tras exito en expediente
OPRE2026-INT-0131766 donde `ocrmypdf --force-ocr` rescato 12 comprobantes
de un PDF con OCR degradado (mejora de 1640 a 2147 lineas).
Aprobada por Hans (solicitud explicita de documentar la tecnica exitosa).

---

## 14. Reglas de Verificacion Visual de Comprobantes

**Documento completo:** `docs/REGLAS_VERIFICACION_COMPROBANTES.md`

**Regla:** Toda verificacion visual de comprobantes debe aplicar las reglas RV-XXX
documentadas en el archivo de referencia. Las reglas son acumulativas y se actualizan
con cada expediente procesado.

**Reglas activas a la fecha:**

| Codigo | Regla | Clasificacion |
|--------|-------|---------------|
| RV-001 | Comprobante parcialmente cortado/recortado → devolver al area usuaria | ALERTA |
| RV-002 | Gasto desproporcionado para comision individual (ej: 2 platos principales para 1 persona) | OBSERVACION |
| RV-003 | Servicio de transporte exonerado de IGV → correcto, no marcar como error | INFORMATIVO |
| RV-004 | Declaracion Jurada con gastos sin comprobante → SIEMPRE verificar Anexo N°4 | CRITICO |

### 14.1 Vigencia

Esta regla entra en vigor el 2026-02-13 y se actualiza incrementalmente.
Aprobada por Hans (hallazgos identificados durante revision visual de OPRE2026-INT-0131766).
