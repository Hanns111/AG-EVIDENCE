# Politica de Gobernanza de Seguridad — AG-EVIDENCE

> Documento normativo. Define los principios, roles y controles de seguridad
> que aplican a todo el sistema AG-EVIDENCE.

**Identificador:** SEC-GOV-001
**Version:** 1.0.0
**Fecha:** 2026-02-19
**Autor:** Hans (definicion) + Claude Code (formalizacion)
**Estado:** VIGENTE
**Alineamiento:** NIS2, GDPR Art.32, NIST CSF 2.0, NIST SSDF SP 800-218, CISA Secure by Design

---

## 1. Alcance

Esta politica aplica a:
- Todo el codigo fuente en `src/`, `scripts/`, `config/`, `tests/`.
- Todos los datos procesados en `data/` y `output/`.
- Todas las herramientas externas integradas (PaddleOCR, Tesseract, Ollama, DuckDB).
- Toda documentacion de gobernanza en `docs/`.

**Exclusiones:** Ninguna. Todo modulo, script y pipeline queda sujeto a esta politica.

---

## 2. Principios de Seguridad

### 2.1 Local-First (GDPR Art.32, NIS2 Art.21)

Ningun dato sale del entorno local. El sistema:
- NO usa APIs cloud para procesamiento de datos.
- NO envia documentos a servicios externos.
- NO requiere conexion a internet para operar (excepto consultas publicas SUNAT).
- Todos los modelos de IA se ejecutan localmente (Ollama + Qwen).

### 2.2 Minimalismo de Privilegios (NIST CSF PR.AA)

- El sistema opera con los permisos minimos necesarios.
- No requiere credenciales de Clave SOL ni SIRE autenticado.
- Solo accede a consultas publicas de SUNAT.
- Los archivos temporales se crean con permisos restrictivos.

### 2.3 Integridad Probatoria (CISA Secure by Design)

- Toda observacion CRITICA/MAYOR requiere: archivo + pagina + snippet + regla.
- Los datos extraidos llevan hash SHA-256 para verificar integridad.
- La cadena de custodia registra cada transformacion del documento.
- Abstencion antes que fabricacion: si un dato no es legible, se marca ILEGIBLE.

### 2.4 Trazabilidad Total (NIS2 Art.23, NIST CSF DE.AE)

- Todo dato extraido registra: fuente, pagina, confianza OCR, motor.
- Logger estructurado JSONL con trace_id unico por operacion.
- Cadena de custodia SHA-256 por documento procesado.

### 2.5 Defensa en Profundidad (NIST CSF PR.DS)

- Validacion de entrada en cada capa del pipeline.
- Separacion estricta: Extraccion / Validacion / Analisis (Regla 8).
- La IA local NUNCA puede escribir campos probatorios (Capa C confinada).

---

## 3. Clasificacion de Datos

| Nivel | Tipo | Ejemplos | Controles |
|-------|------|----------|-----------|
| **CONFIDENCIAL** | Datos personales de servidores publicos | DNI, nombres, cargos en expedientes | Solo local, no en git, no en logs |
| **RESTRINGIDO** | Datos financieros del Estado | Montos, RUC, comprobantes | Solo local, hash obligatorio, no en git |
| **INTERNO** | Documentacion tecnica del proyecto | Codigo fuente, ADRs, specs | En git (GitHub privado), backups locales |
| **PUBLICO** | Documentacion general | README, LICENSE | GitHub publico (futuro) |

### 3.1 Datos que NUNCA se versionan en git

- PDFs de expedientes (`data/expedientes/`)
- PDFs de directivas (`data/directivas/`)
- Archivos Excel generados con datos reales (`output/`)
- Logs con datos personales (`output/*.jsonl`)
- Archivos temporales de OCR (`output/ocr_temp/`)

### 3.2 Datos que SI se versionan en git

- Codigo fuente (`src/`)
- Tests (`tests/`)
- Configuracion (`config/`)
- Scripts (`scripts/`)
- Documentacion (`docs/`)
- JSON de reglas normativas (`data/normativa/`)

---

## 4. Controles de Seguridad por Fase

### Fase 1 — Estructura (AHORA)

| Control | ID | Estado | Modulo |
|---------|----|--------|--------|
| Hash SHA-256 por documento | SEC-INT-001 | IMPLEMENTADO | custody_chain.py |
| Logger JSONL con trace_id | SEC-AUD-001 | IMPLEMENTADO | trace_logger.py |
| Abstencion formal (no inventar datos) | SEC-INT-002 | IMPLEMENTADO | abstencion.py |
| Validacion de dimensiones de imagen | SEC-INP-001 | IMPLEMENTADO | core.py |
| .gitignore completo (datos sensibles) | SEC-DAT-001 | IMPLEMENTADO | .gitignore |
| Contrato tipado JSON intermedio | SEC-INT-003 | IMPLEMENTADO | expediente_contract.py |
| Anti-duplicidad de comprobantes | SEC-INT-004 | IMPLEMENTADO | expediente_contract.py |
| Bloqueo de campos probatorios para IA | SEC-IAC-001 | IMPLEMENTADO | local_analyst.py |
| Limpieza de archivos temporales | SEC-TMP-001 | PENDIENTE | En implementacion |
| Proteccion contra path traversal | SEC-INP-002 | PENDIENTE | En implementacion |
| Validacion de esquema JSON | SEC-INP-003 | PENDIENTE | En implementacion |

### Fase 2 — Flujo Estable (cuando pipeline completo)

| Control | ID | Estado | Modulo |
|---------|----|--------|--------|
| Validacion de dependencias (requirements.txt) | SEC-SUP-001 | PENDIENTE | requirements.txt |
| Politica de retencion de logs | SEC-AUD-002 | PENDIENTE | trace_logger.py |
| Sanitizacion de salida Excel | SEC-OUT-001 | PENDIENTE | excel_writer.py |
| Verificacion de integridad de modelos | SEC-IAM-001 | PENDIENTE | Fase 3 |

### Fase 3 — Pre-Produccion

| Control | ID | Estado | Modulo |
|---------|----|--------|--------|
| Cifrado de datos en reposo | SEC-CRY-001 | PENDIENTE | Futuro |
| Threat model formal | SEC-THR-001 | PENDIENTE | docs/security/ |
| Plan de respuesta a incidentes | SEC-INC-001 | DOCUMENTADO | INCIDENT_RESPONSE.md |
| Hardening de configuracion | SEC-CFG-001 | PENDIENTE | Futuro |

---

## 5. Roles y Responsabilidades

| Rol | Persona | Responsabilidad |
|-----|---------|----------------|
| **Propietario del sistema** | Hans | Decisiones finales, aprobacion de cambios de seguridad |
| **Implementador principal** | Claude Code | Desarrollo de controles, auditorias automatizadas |
| **Implementador secundario** | Cursor | Ediciones puntuales bajo supervision de Claude Code |

---

## 6. Revision y Actualizacion

- Esta politica se revisa en cada cambio de fase del ROADMAP.
- Toda nueva funcionalidad debe evaluarse contra los controles listados.
- Los hallazgos de seguridad se registran en RISK_REGISTER.md.

---

## 7. Alineamiento Normativo

| Norma | Articulo/Seccion | Aplicacion en AG-EVIDENCE |
|-------|-----------------|--------------------------|
| **NIS2** | Art.21 (medidas de gestion de riesgos) | Controles por fase, clasificacion de datos |
| **NIS2** | Art.23 (notificacion de incidentes) | INCIDENT_RESPONSE.md |
| **GDPR** | Art.32 (seguridad del tratamiento) | Local-first, cifrado pendiente, integridad SHA-256 |
| **NIST CSF 2.0** | GV (Govern) | Esta politica + RISK_REGISTER.md |
| **NIST CSF 2.0** | PR (Protect) | Validacion de entrada, controles de acceso |
| **NIST CSF 2.0** | DE (Detect) | Logger JSONL, cadena de custodia |
| **NIST SSDF** | PO.1 (Politica de seguridad) | Este documento |
| **NIST SSDF** | PS.1 (Proteger software) | Anti-hardcode, abstencion, bloqueo IA |
| **CISA Secure by Design** | Principio 1 (seguridad por defecto) | Abstencion, local-first, minimo privilegio |
| **CISA Secure by Design** | Principio 3 (transparencia) | Trazabilidad total, logs estructurados |

---

## Historial de Versiones

| Version | Fecha | Cambio |
|---------|-------|--------|
| 1.0.0 | 2026-02-19 | Documento inicial |

---

*Documento generado por Claude Code bajo instruccion directa de Hans.*
*Forma parte del sistema de gobernanza de seguridad de AG-EVIDENCE.*
