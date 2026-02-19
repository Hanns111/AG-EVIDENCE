# ADR-010 — Evidence Reuse Layer (ERL): Cache de Validaciones Idempotente

**Estado:** Propuesto (Pendiente Fase 2)
**Fecha:** 2026-02-19
**Autor:** Hans (definicion de necesidad) + Claude Code (formalizacion tecnica)
**Requiere aprobacion de:** Hans
**Depende de:** ADR-004 (LangGraph), ADR-005 (Separacion Dominio/Orquestacion/Herramientas), ADR-008 (OCR GPU), ADR-009 (VLM)
**Impacta:** Capa 2 (Orquestacion) y Capa 3 (Herramientas)

---

## 1. Contexto del Problema

### 1.1 Situacion actual

El pipeline de AG-EVIDENCE procesa expedientes administrativos ejecutando
secuencialmente los agentes AG01→AG09. Cada ejecucion reprocesa el expediente
completo desde cero, incluyendo:

- OCR/VLM sobre cada pagina (operacion mas costosa: ~1.5s GPU por pagina OCR,
  ~15-45s por pagina VLM)
- Extraccion de campos estructurados
- Validaciones de coherencia, normativas, firmas, integridad, SUNAT

### 1.2 Problema concreto

Cuando un expediente se reprocesa (por correccion de regla, cambio de motor,
o revision iterativa), **todas las validaciones se ejecutan de nuevo**, incluso
aquellas cuyo resultado no pudo haber cambiado porque:

1. El documento fuente no cambio (mismo SHA-256).
2. La regla aplicada no cambio (misma version de directiva).
3. El motor de extraccion no cambio (misma version de pipeline).

### 1.3 Impacto observado (estimaciones, sin benchmark formal en repo)

> **Nota:** Las cifras de esta seccion son estimaciones basadas en mediciones
> puntuales durante desarrollo (expedientes ODI2026 y DEBEDSAR2026), NO en
> un benchmark formal documentado en el repositorio. Se incluyen como
> referencia de orden de magnitud, sujetas a validacion con benchmark
> controlado antes de implementar ERL.

| Operacion | Tiempo estimado por expediente | Repetible sin cambio |
|-----------|-------------------------------|---------------------|
| OCR GPU (PaddleOCR PP-OCRv5) | ~1.5s × N paginas | SI — si documento no cambio |
| VLM (Qwen2.5-VL-7B) | ~15-45s × N paginas imagen | SI — si documento no cambio |
| Extraccion regex PyMuPDF | <1s × N paginas texto | SI — si documento no cambio |
| Validacion RUC SUNAT | ~2s × N comprobantes | SI — si RUC no cambio |
| Validacion normativa | <0.5s × N comprobantes | DEPENDE — si regla no cambio |

Un expediente tipico (70 paginas, 17 comprobantes) toma estimadamente ~5-10 minutos.
Se observa reprocesamiento significativo cuando se re-ejecuta un expediente
sin cambios en documento, regla ni motor. ERL busca reducir ese reproceso
reutilizando resultados previamente validados con evidencia completa.

### 1.4 Restricciones de gobernanza

Cualquier solucion de cache DEBE:

- Mantener flujo secuencial AG01→AG09 (Art. 2 AGENT_GOVERNANCE_RULES)
- Preservar estandar probatorio: archivo + pagina + snippet (Art. 4)
- No inventar datos: reutilizar solo resultados con evidencia completa
- Permitir invalidacion cuando cambie regla o motor (degradacion)
- Registrar todo en TraceLogger (trazabilidad total, Art. 17)

---

## 2. Decision Propuesta

Implementar una **Evidence Reuse Layer (ERL)** como componente de Capa 3
(Herramientas) que actue como cache de resultados de validacion, consultable
por el Orquestador (Capa 2) antes de invocar cada agente.

### 2.1 Principio rector

> "Si el documento no cambio, la regla no cambio, y el motor no cambio,
> el resultado de la validacion es el mismo."

### 2.2 Posicion en la arquitectura

```
Expediente PDF
    |
    v
[Cadena de Custodia] → SHA-256 del documento
    |
    v
[Orquestador LangGraph]
    |
    +--→ ¿Existe cache_key valido en ERL?
    |       SI → Reutilizar resultado + registrar cache_hit en TraceLogger
    |       NO → Ejecutar agente normalmente + guardar resultado en ERL
    |
    v
AG01 → AG02 → ... → AG09
    |
    v
[Reporte final]
```

ERL se ubica en **Capa 3 (Herramientas)**, implementada como adaptador
(ADR-005). El Orquestador (Capa 2) decide si consulta el cache antes de
cada invocacion. La logica de dominio (Capa 1) NO conoce ni depende de ERL.

---

## 3. Alcance

### 3.1 Que ENTRA en esta ADR

| Elemento | Incluido | Justificacion |
|----------|----------|---------------|
| Cache de resultados OCR/VLM | SI | Operacion mas costosa y mas idempotente |
| Cache de extraccion estructurada | SI | Determinista si documento+motor no cambian |
| Cache de validacion RUC SUNAT | SI | Consulta idempotente por RUC |
| Indice de invalidacion | SI | Necesario para mantener consistencia |
| Registro en TraceLogger | SI | Obligatorio por gobernanza (Art. 17) |
| Metricas de cache hit/miss | SI | Necesario para evaluar beneficio |

### 3.2 Que NO ENTRA en esta ADR

| Elemento | Excluido | Justificacion |
|----------|----------|---------------|
| Cache de resultado de AG09 (Decisor) | NO | La decision final siempre debe re-evaluarse |
| Cache inter-expediente | NO | Cada expediente es independiente |
| Cache de respuestas LLM conversacionales | NO | No aplica a flujo batch |
| Modificacion de logica de agentes | NO | ERL es transparente para Capa 1 |
| Cambio de flujo AG01→AG09 | NO | Se mantiene secuencia (Art. 2.1) |
| Cache distribuido o en red | NO | Viola ADR-001 (local-first) |

---

## 4. Diseno Tecnico Minimo

### 4.1 Cache Key (clave de idempotencia)

```python
cache_key = sha256(
    sha256_documento        # Hash del PDF fuente (de Cadena de Custodia)
    + nivel_granularidad    # "pagina:5" | "comprobante:F001-468" | "documento"
    + tipo_validacion       # "ocr", "vlm", "extraccion", "ruc_sunat", "normativa", etc.
    + version_regla         # Definido abajo (Seccion 4.1.1)
    + version_pipeline      # Version del motor (ej: "paddleocr_3.4.0_ppv5_server")
    + parametros_hash       # Hash de parametros relevantes (DPI, idioma, prompt)
)
```

#### 4.1.1 Granularidad del cache_key

La granularidad define a que nivel se cachea un resultado. Usar el nivel
incorrecto causa "falsos hits" (R2). Definicion explicita:

| Tipo de validacion | Granularidad | Ejemplo de nivel_granularidad |
|-------------------|-------------|------------------------------|
| OCR (PaddleOCR) | **Por pagina** | `"pagina:5"` |
| VLM (Qwen2.5-VL) | **Por pagina** | `"pagina:20"` |
| Extraccion PyMuPDF | **Por pagina** | `"pagina:3"` |
| Validacion RUC SUNAT | **Por comprobante** | `"comprobante:F001-468"` |
| Validacion normativa | **Por comprobante** | `"comprobante:F001-468"` |
| Validacion IGV | **Por comprobante** | `"comprobante:F001-468"` |
| Clasificacion expediente (AG01) | **Por documento** | `"documento"` |

**Regla:** Nunca cachear a granularidad mayor que la del proceso.
Si OCR opera por pagina, su cache es por pagina, NO por documento completo.

#### 4.1.2 Definicion de `version_regla`

`version_regla` identifica univocamente la regla o directiva aplicada.
Se compone de:

```python
version_regla = f"{identificador_regla}:{hash_o_version}"
```

| Tipo de regla | identificador_regla | hash_o_version | Ejemplo |
|--------------|--------------------|-----------------------|---------|
| Directiva de viaticos | `DIR_VIATICOS` | SHA-256 del PDF de directiva | `DIR_VIATICOS:a3f8c2...` |
| Regla de detraccion SPOT | `REGLA_SPOT` | Version del modulo `detraccion_spot.py` | `REGLA_SPOT:1.0.0` |
| Regla TDR | `REGLA_TDR` | Version del modulo `tdr_requirements.py` | `REGLA_TDR:1.0.0` |
| Validacion aritmetica (Grupo J) | `ARIT_GRUPO_J` | Version del validador | `ARIT_GRUPO_J:1.0.0` |
| Motor OCR (sin regla normativa) | `MOTOR_ONLY` | `"N/A"` | `MOTOR_ONLY:N/A` |

**Cuando cambia `version_regla`:** Al actualizar una directiva PDF (nuevo SHA-256)
o al modificar la logica de un modulo de reglas (nueva version en su docstring),
todos los registros de cache con la version anterior se invalidan automaticamente.

**Caso especial — OCR/VLM:** Las operaciones de extraccion pura (OCR, VLM, PyMuPDF)
no dependen de reglas normativas. Su `version_regla` es `"MOTOR_ONLY:N/A"`.
Solo se invalidan por cambio de `version_pipeline` o `parametros_hash`.

### 4.2 Estructura del registro de cache

```python
@dataclass
class RegistroCache:
    cache_key: str              # SHA-256 compuesto
    tipo_validacion: str        # "ocr" | "vlm" | "extraccion" | "ruc" | "normativa"
    estado: str                 # "success" | "failed" | "incierto"
    resultado_json: str         # Resultado serializado (ExpedienteJSON parcial)
    evidencia_completa: bool    # True si tiene archivo+pagina+snippet
    sha256_documento: str       # Hash del documento fuente
    version_regla: str          # Version de regla aplicada
    version_pipeline: str       # Version del motor
    timestamp_creacion: str     # ISO 8601
    trace_id_origen: str        # trace_id de la ejecucion original
    motivo_invalidacion: Optional[str]  # None si vigente
    timestamp_invalidacion: Optional[str]
```

### 4.3 Almacenamiento: DuckDB local

DuckDB ya esta reconocido en el proyecto (CLAUDE.md: "DuckDB 1.4.4 instalado,
base analitica") y en ARCHITECTURE.md (Capa 3, herramientas planificadas).

```sql
CREATE TABLE erl_cache (
    cache_key           VARCHAR PRIMARY KEY,
    tipo_validacion     VARCHAR NOT NULL,
    estado              VARCHAR NOT NULL,  -- 'success', 'failed', 'incierto'
    resultado_json      JSON NOT NULL,
    evidencia_completa  BOOLEAN NOT NULL,
    sha256_documento    VARCHAR NOT NULL,
    version_regla       VARCHAR NOT NULL,
    version_pipeline    VARCHAR NOT NULL,
    timestamp_creacion  TIMESTAMP NOT NULL,
    trace_id_origen     VARCHAR NOT NULL,
    motivo_invalidacion VARCHAR,
    timestamp_invalidacion TIMESTAMP
);

-- Indice para consulta rapida por documento
CREATE INDEX idx_erl_documento ON erl_cache(sha256_documento);

-- Indice para invalidacion por version de regla
CREATE INDEX idx_erl_regla ON erl_cache(version_regla);
```

**Archivo:** `data/erl_cache.duckdb` (local, excluido de git via .gitignore)

### 4.4 Politica de reutilizacion

```
ANTES de ejecutar agente/validacion:
  1. Calcular cache_key
  2. Consultar ERL:
     a) Si HIT + estado="success" + evidencia_completa=True
        + motivo_invalidacion IS NULL
        → REUTILIZAR resultado
        → Registrar en TraceLogger: evento="cache_hit", cache_key, trace_id_origen
     b) Si HIT pero estado="incierto" o evidencia_completa=False
        → RE-EJECUTAR (no reutilizar resultados dudosos)
        → Registrar: evento="cache_skip_incierto"
     c) Si HIT pero motivo_invalidacion IS NOT NULL
        → RE-EJECUTAR (cache invalidado)
        → Registrar: evento="cache_invalidated", motivo
     d) Si MISS
        → EJECUTAR agente normalmente
        → Guardar resultado en ERL
        → Registrar: evento="cache_miss"
```

#### 4.4.1 Guardrail probatorio: degradacion obligatoria (Art. 4 y 5)

**Regla critica:** Un resultado cacheado que contenga observaciones CRITICAS
o MAYORES solo puede reutilizarse si su `evidencia_completa = True`.

Si por cualquier razon un registro de cache tiene:
- `estado = "success"` pero `evidencia_completa = False`, o
- Observaciones CRITICAS/MAYORES sin archivo+pagina+snippet

Entonces:
1. El resultado NO se reutiliza (se trata como `cache_skip_incierto`).
2. Se re-ejecuta la validacion desde cero.
3. Si la re-ejecucion sigue sin producir evidencia completa, las
   observaciones se degradan a INCIERTO con `requiere_revision_humana = True`
   segun Art. 5 de AGENT_GOVERNANCE_RULES.

**Fundamento:** La gobernanza establece que solo observaciones CRITICAS
con evidencia completa tienen capacidad de bloqueo (Art. 5.2).
ERL no puede crear un atajo que eluda esta regla. Un cache hit sin
evidencia probatoria completa es equivalente a una afirmacion sin respaldo.

### 4.5 Politica de invalidacion

| Evento | Accion | Registro |
|--------|--------|---------|
| Cambio de version de regla/directiva | Invalidar todos los registros con esa version_regla | `cache_invalidated: regla_actualizada` |
| Cambio de version de pipeline/motor | Invalidar todos los registros con esa version_pipeline | `cache_invalidated: pipeline_actualizado` |
| Cambio de parametros (DPI, prompt) | Invalidar registros con parametros_hash diferente | `cache_invalidated: parametros_cambiados` |
| Documento re-ingresado con mismo SHA-256 | NO invalidar (mismo contenido) | `cache_hit` |
| Documento re-ingresado con SHA-256 diferente | No aplica (cache_key diferente, sera MISS) | `cache_miss` |
| Limpieza manual por operador | Comando `erl_cache.truncate()` | `cache_cleared: manual` |

### 4.6 Integracion con TraceLogger

Todo evento de cache se registra en el TraceLogger JSONL existente:

```json
{
  "trace_id": "...",
  "timestamp": "2026-03-01T10:15:00Z",
  "nivel": "INFO",
  "evento": "cache_hit",
  "cache_key": "abc123...",
  "tipo_validacion": "ocr",
  "trace_id_origen": "xyz789...",
  "ahorro_estimado_ms": 1500
}
```

---

## 5. Riesgos y Mitigaciones

| # | Riesgo | Probabilidad | Impacto | Mitigacion |
|---|--------|-------------|---------|------------|
| R1 | Reutilizar resultado con regla desactualizada | MEDIA | ALTO | Versionar regla en cache_key; invalidar al detectar cambio |
| R2 | "Falso hit" por granularidad incorrecta | BAJA | ALTO | Separar cache por tipo_validacion Y por nivel (pagina/comprobante) |
| R3 | Opacidad operativa (no saber que viene de cache) | MEDIA | MEDIO | Todo hit/miss/invalidation registrado en TraceLogger |
| R4 | Cache corrupto o inconsistente | BAJA | MEDIO | Verificacion de integridad al leer; `evidencia_completa` como guardia |
| R5 | Crecimiento excesivo de DuckDB | BAJA | BAJO | Politica de retencion: 90 dias o N expedientes; comando de limpieza |
| R6 | ERL introduce complejidad innecesaria antes de tiempo | MEDIA | MEDIO | Implementar SOLO cuando pipeline end-to-end funcione (Tarea #21+) |
| R7 | Cache no invalida correctamente en edge cases | BAJA | ALTO | Tests de invalidacion obligatorios; modo `--no-cache` para bypass |

---

## 6. Metricas de Exito

| Metrica | Objetivo | Medicion |
|---------|----------|---------|
| Cache hit rate (reproceso mismo expediente) | >80% | Conteo cache_hit / (cache_hit + cache_miss) |
| Reduccion de tiempo por reproceso | >70% | Tiempo con cache / Tiempo sin cache |
| Cero perdida de trazabilidad | 100% | Toda salida tiene archivo+pagina+snippet |
| Cero violaciones de gobernanza | 0 | Tests automatizados contra Art. 4 y Art. 5 |
| Cero resultados stale (regla obsoleta) | 0 | Tests de invalidacion por cambio de regla |

---

## 7. Criterios de Aceptacion

### 7.1 Para aprobar esta ADR

- [ ] Hans confirma que el problema de reproceso es prioritario
- [ ] El pipeline end-to-end (AG01→AG09) esta operativo (Tarea #21 completada)
- [ ] Existe al menos 1 expediente de referencia para benchmark antes/despues
- [ ] No hay conflicto con Tareas #18-21 (Router, Confidence, integracion)

### 7.2 Para considerar ERL implementada

- [ ] `src/tools/erl_cache.py` con adaptador DuckDB
- [ ] Politica de reutilizacion con 4 casos (hit, skip, invalidated, miss)
- [ ] Integracion con TraceLogger (eventos de cache)
- [ ] Integracion con Orquestador LangGraph (consulta antes de cada agente)
- [ ] Modo `--no-cache` para bypass completo
- [ ] Tests: idempotencia, invalidacion, integracion, edge cases
- [ ] Benchmark comparativo antes/despues con expediente real
- [ ] Cero tests de gobernanza rotos

---

## 8. Plan de Implementacion Incremental

### Fase A — OCR + Extraccion (con Tarea #21 completada)

**Alcance:** Cache de resultados OCR y extraccion estructurada.
**Justificacion:** Es la operacion mas costosa (~90% del tiempo) y mas
determinista (mismo documento + mismo motor = mismo resultado).

| Paso | Descripcion | Estimacion |
|------|-------------|-----------|
| A.1 | Crear `src/tools/erl_cache.py` con esquema DuckDB | 2h |
| A.2 | Implementar cache_key para OCR (sha256_doc + pagina + motor + dpi) | 1h |
| A.3 | Wrapper en Orquestador: consultar ERL antes de AG02 | 2h |
| A.4 | Registrar eventos en TraceLogger | 1h |
| A.5 | Tests unitarios de idempotencia e invalidacion | 2h |
| A.6 | Benchmark con expediente DEBEDSAR2026-INT-0146130 | 1h |

### Fase B — Validaciones por comprobante (Fase 3+)

**Alcance:** Cache de validaciones RUC, IGV, fechas, normativa.
**Depende de:** Agentes AG03, AG04, AG08 operativos.

| Paso | Descripcion |
|------|-------------|
| B.1 | Cache_key por comprobante (sha256_doc + serie_numero + tipo_validacion + version_regla) |
| B.2 | Integracion con AG03 (coherencia), AG04 (legal), AG08 (SUNAT) |
| B.3 | Politica de invalidacion por cambio de directiva |

### Fase C — Metricas y optimizacion (Fase 4+)

**Alcance:** Dashboard de metricas, politicas de retencion, limpieza.

| Paso | Descripcion |
|------|-------------|
| C.1 | Vista SQL de metricas (hit rate, ahorro acumulado, cache size) |
| C.2 | Politica de retencion automatica (90 dias) |
| C.3 | Comando CLI: `python -m tools.erl_cache --stats / --clear / --invalidate` |

---

## 9. Consecuencias

### 9.1 Positivas

- Reduccion significativa de tiempo en reprocesos (estimado >70%)
- Reutilizacion de trabajo ya validado sin perdida de trazabilidad
- Base para metricas operativas (que se reprocesa, cuanto se ahorra)
- DuckDB ya esta instalado y reconocido en el proyecto

### 9.2 Negativas

- Complejidad adicional en el Orquestador (consulta de cache)
- Nuevo modulo que mantener y testear
- Riesgo de resultados stale si la invalidacion tiene bugs
- Espacio en disco para DuckDB (estimado <500MB para miles de expedientes)

### 9.3 Neutrales

- No modifica logica de dominio de ningun agente
- No cambia flujo AG01→AG09
- No afecta estandar probatorio (reutiliza resultados CON evidencia completa)
- No introduce dependencias nuevas (DuckDB ya esta)

---

## 10. Impacto en Documentos Existentes

| Documento | Cambio requerido | Cuando | Obligatorio |
|-----------|-----------------|--------|-------------|
| `docs/ARCHITECTURE.md` | Agregar ERL en Capa 3 (Herramientas), seccion "Ejemplos planificados" | Al aprobar ADR | **SI** — ERL altera flujo de orquestacion (consulta cache antes de agente) |
| `docs/ADR.md` | Agregar referencia a ADR-010 | Al aprobar ADR | SI (ya hecho como resumen) |
| `config/settings.py` | Agregar `ERL_CONFIG` (enabled, max_age_days, db_path) | Al implementar Fase A |
| `.gitignore` | Agregar `data/erl_cache.duckdb` | Al implementar Fase A |
| `ROADMAP.md` | Agregar ERL como sub-tarea de Fase 2 o Fase 3 | Al aprobar ADR |
| `CLAUDE.md` | Registrar decision y estado | Al aprobar ADR |
| `docs/security/RISK_REGISTER.md` | Agregar RSK para cache stale | Al aprobar ADR |
| `docs/GOBERNANZA_TECNICA_TRANSVERSAL.md` | **SIN CAMBIO** — ERL no altera reglas tecnicas | — |
| `docs/AGENT_GOVERNANCE_RULES.md` | **SIN CAMBIO** — flujo AG01→AG09 intacto | — |

---

## 11. Puntos INCIERTOS (requieren investigacion o decision de Hans)

| # | Punto | Estado | Accion requerida |
|---|-------|--------|-----------------|
| I1 | Tamano real de cache DuckDB por expediente | INCIERTO | Medir con expediente real tras Fase A |
| I2 | Impacto en VRAM si DuckDB y PaddleOCR corren simultaneamente | INCIERTO | DuckDB usa RAM no VRAM, pero verificar empiricamente |
| I3 | Granularidad optima de cache_key para VLM (por pagina vs por comprobante) | INCIERTO | Evaluar tras Fase A con benchmark |
| I4 | Si el cache de AG09 (Decisor) deberia incluirse eventualmente | INCIERTO | Hans decide; riesgo de ocultar cambios en ponderacion final |
| I5 | Politica de retencion: 90 dias vs N expedientes vs tamano en disco | INCIERTO | Definir con datos reales de uso |
| I6 | Si ERL debe ser Fase 2 (con Router) o Fase 3 (post-pipeline) | INCIERTO | Depende de si el pipeline end-to-end esta listo antes de ERL |

---

## 12. Checklist de Aprobacion

| Criterio | Cumple |
|----------|--------|
| Respeta flujo secuencial AG01→AG09 | SI |
| Mantiene estandar probatorio (Art. 4) | SI |
| No modifica logica de dominio (Capa 1) | SI |
| Se ubica en Capa 3 (Herramientas) con adaptador | SI |
| Usa tecnologia ya aprobada (DuckDB) | SI |
| Registra todo en TraceLogger | SI |
| Incluye politica de invalidacion | SI |
| Incluye modo bypass (--no-cache) | SI |
| No viola ADR-001 (local-first) | SI |
| No introduce dependencias nuevas | SI |
| Tiene plan incremental por fases | SI |
| Tiene metricas de exito medibles | SI |
| Marca puntos INCIERTOS explicitamente | SI |

---

**Nota:** Esta ADR NO autoriza implementacion inmediata.
Requiere aprobacion explicita de Hans y cumplimiento de los
criterios de aceptacion (Seccion 7.1) antes de comenzar codigo.

---

*ADR redactada por Claude Code bajo solicitud directa de Hans.*
*Basada en arquitectura vigente (ADR-001 a ADR-009) y*
*AGENT_GOVERNANCE_RULES.md v1.0.0.*
