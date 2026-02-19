# Registro de Riesgos de Seguridad — AG-EVIDENCE

> Registro vivo de todos los riesgos de seguridad identificados,
> su estado de mitigacion y acciones pendientes.

**Identificador:** SEC-RSK-001
**Version:** 1.0.0
**Fecha:** 2026-02-19
**Alineamiento:** NIS2 Art.21(a), NIST CSF GV.RM, ISO 27005

---

## Metodologia

Cada riesgo se evalua con:
- **Probabilidad:** BAJA / MEDIA / ALTA
- **Impacto:** BAJO / MEDIO / ALTO / CRITICO
- **Riesgo residual:** Probabilidad x Impacto despues de mitigacion

El contexto de AG-EVIDENCE es:
- Sistema mono-operador (Hans).
- Ejecucion 100% local (RTX 5090, WSL2).
- Sin exposicion a red publica.
- Datos del sector publico peruano (expedientes administrativos).

---

## Riesgos Activos

### RSK-001: Archivos temporales OCR sin limpieza

| Campo | Valor |
|-------|-------|
| **ID** | RSK-001 |
| **Categoria** | Datos en reposo |
| **Probabilidad** | ALTA |
| **Impacto** | MEDIO |
| **Riesgo** | MEDIO-ALTO |
| **Descripcion** | El pipeline OCR crea imagenes temporales en `output/ocr_temp/` que persisten despues del procesamiento. Pueden contener paginas escaneadas con datos personales (DNI, nombres, montos). |
| **Modulo afectado** | src/ocr/core.py |
| **Mitigacion actual** | Ninguna automatica. Limpieza manual por operador. |
| **Mitigacion propuesta** | Context manager con cleanup en `finally`. Implementar en Fase 1. |
| **Hallazgo relacionado** | HAL-001 en SECURITY_BASELINE.md |
| **Estado** | ABIERTO — Pendiente implementacion |

---

### RSK-002: JSON de expediente sin validacion de schema

| Campo | Valor |
|-------|-------|
| **ID** | RSK-002 |
| **Categoria** | Validacion de entrada |
| **Probabilidad** | MEDIA |
| **Impacto** | MEDIO |
| **Riesgo** | MEDIO |
| **Descripcion** | `ExpedienteJSON.from_json()` deserializa sin validar estructura. Un JSON corrupto o malformado podria causar errores no controlados o datos inconsistentes. |
| **Modulo afectado** | src/extraction/expediente_contract.py |
| **Mitigacion actual** | Tipado de dataclasses (validacion parcial en construccion). |
| **Mitigacion propuesta** | Agregar validacion de campos obligatorios en `from_json()` con errores descriptivos. |
| **Hallazgo relacionado** | HAL-002 en SECURITY_BASELINE.md |
| **Estado** | ABIERTO — Pendiente implementacion |

---

### RSK-003: requirements.txt incompleto

| Campo | Valor |
|-------|-------|
| **ID** | RSK-003 |
| **Categoria** | Cadena de suministro |
| **Probabilidad** | ALTA |
| **Impacto** | ALTO |
| **Riesgo** | ALTO |
| **Descripcion** | Las dependencias del proyecto no estan completamente listadas ni versionadas. Impide reproduccion de builds y auditoria de vulnerabilidades con pip-audit. |
| **Modulo afectado** | requirements.txt |
| **Mitigacion actual** | Instalacion manual de paquetes. |
| **Mitigacion propuesta** | Regenerar con `pip freeze`, filtrar, verificar con pip-audit. Fase 2. |
| **Hallazgo relacionado** | HAL-003 en SECURITY_BASELINE.md |
| **Estado** | ABIERTO — Programado para Fase 2 |

---

### RSK-004: Sin proteccion contra path traversal

| Campo | Valor |
|-------|-------|
| **ID** | RSK-004 |
| **Categoria** | Validacion de entrada |
| **Probabilidad** | BAJA |
| **Impacto** | MEDIO |
| **Riesgo** | BAJO-MEDIO |
| **Descripcion** | Funciones que reciben paths de archivo no validan contra traversal (`../../../`). En contexto mono-operador local el riesgo es bajo, pero viola best practices. |
| **Modulo afectado** | Multiples: custody_chain.py, pdf_text_extractor.py, core.py |
| **Mitigacion actual** | Operador unico (Hans) controla entradas. |
| **Mitigacion propuesta** | Funcion centralizada `validar_ruta_segura()` en src/utils/security.py. |
| **Hallazgo relacionado** | HAL-004 en SECURITY_BASELINE.md |
| **Estado** | ABIERTO — Pendiente implementacion |

---

### RSK-005: Logs JSONL sin politica de retencion

| Campo | Valor |
|-------|-------|
| **ID** | RSK-005 |
| **Categoria** | Gestion de datos |
| **Probabilidad** | MEDIA |
| **Impacto** | BAJO |
| **Riesgo** | BAJO |
| **Descripcion** | Los logs JSONL crecen sin limite. Con el tiempo pueden acumular fragmentos de texto OCR que contengan datos personales. |
| **Modulo afectado** | src/ingestion/trace_logger.py |
| **Mitigacion actual** | Ninguna automatica. |
| **Mitigacion propuesta** | Rotacion por tamano (max 50MB) o por fecha (30 dias). Fase 2. |
| **Hallazgo relacionado** | HAL-005 en SECURITY_BASELINE.md |
| **Estado** | ABIERTO — Programado para Fase 2 |

---

### RSK-006: Datos personales en fragmentos OCR de logs

| Campo | Valor |
|-------|-------|
| **ID** | RSK-006 |
| **Categoria** | Privacidad |
| **Probabilidad** | ALTA |
| **Impacto** | MEDIO |
| **Riesgo** | MEDIO |
| **Descripcion** | El TraceLogger puede registrar snippets de texto OCR que contengan DNI, nombres de servidores publicos, montos de viaticos. Estos datos personales quedan en logs de texto plano. |
| **Modulo afectado** | src/ingestion/trace_logger.py |
| **Mitigacion actual** | Logs en directorio local, excluidos de git. |
| **Mitigacion propuesta** | (1) Sanitizar snippets antes de log, truncando datos personales. (2) Cifrar logs en reposo (Fase 3). |
| **Estado** | ABIERTO — Evaluacion en Fase 2 |

---

### RSK-007: Sin cifrado de datos en reposo

| Campo | Valor |
|-------|-------|
| **ID** | RSK-007 |
| **Categoria** | Criptografia |
| **Probabilidad** | BAJA |
| **Impacto** | ALTO |
| **Riesgo** | MEDIO |
| **Descripcion** | Los expedientes procesados, resultados Excel y logs se almacenan sin cifrado. Si el equipo es robado o comprometido, los datos son accesibles. |
| **Modulo afectado** | Todo el sistema |
| **Mitigacion actual** | Laptop personal con cifrado de disco (BitLocker/LUKS presumido). |
| **Mitigacion propuesta** | Cifrado a nivel de aplicacion para `output/` y `data/`. Fase 3. |
| **Estado** | ABIERTO — Programado para Fase 3 |

---

## Riesgos Mitigados (Cerrados)

### RSK-M01: IA generando datos probatorios

| Campo | Valor |
|-------|-------|
| **ID** | RSK-M01 |
| **Categoria** | Integridad de datos |
| **Probabilidad** | MUY BAJA (mitigado) |
| **Impacto** | CRITICO |
| **Riesgo residual** | BAJO |
| **Descripcion** | La IA local (Capa C) podria generar valores probatorios (RUC, montos, fechas) sin fuente verificable. |
| **Mitigacion implementada** | `_bloquear_valores_probatorios()` en local_analyst.py. Feature flag `enabled=False`. Tests de seguridad. |
| **Estado** | CERRADO — Mitigacion implementada y testeada |

---

### RSK-M02: Alucinacion de datos por hardcode

| Campo | Valor |
|-------|-------|
| **ID** | RSK-M02 |
| **Categoria** | Integridad de datos |
| **Probabilidad** | BAJA (en nuevos modulos) |
| **Impacto** | ALTO |
| **Riesgo residual** | BAJO |
| **Descripcion** | Scripts con datos hardcodeados no son verificables contra fuente. |
| **Mitigacion implementada** | Regla 1 de Gobernanza Tecnica. Contrato tipado (expediente_contract.py). Pipeline formal obligatorio. |
| **Estado** | PARCIALMENTE CERRADO — 3 scripts legacy aun violan Regla 1, pero nuevos modulos cumplen |

---

### RSK-M03: Datos sensibles en repositorio git

| Campo | Valor |
|-------|-------|
| **ID** | RSK-M03 |
| **Categoria** | Exposicion de datos |
| **Probabilidad** | MUY BAJA (mitigado) |
| **Impacto** | CRITICO |
| **Riesgo residual** | BAJO |
| **Descripcion** | PDFs de expedientes o datos personales podrian subirse a GitHub. |
| **Mitigacion implementada** | .gitignore completo: `data/expedientes/`, `data/directivas/`, `output/`, archivos temporales. |
| **Estado** | CERRADO — .gitignore auditado y verificado |

---

## Resumen de Riesgos

| Nivel | Activos | Cerrados |
|-------|---------|----------|
| ALTO | 1 (RSK-003) | 0 |
| MEDIO-ALTO | 1 (RSK-001) | 0 |
| MEDIO | 3 (RSK-002, RSK-006, RSK-007) | 0 |
| BAJO-MEDIO | 1 (RSK-004) | 0 |
| BAJO | 1 (RSK-005) | 3 (RSK-M01, RSK-M02, RSK-M03) |

**Total activos:** 7
**Total mitigados:** 3

---

## Historial de Versiones

| Version | Fecha | Cambio |
|---------|-------|--------|
| 1.0.0 | 2026-02-19 | Registro inicial con 10 riesgos documentados |

---

*Registro mantenido por Claude Code. Revision periodica por Hans.*
