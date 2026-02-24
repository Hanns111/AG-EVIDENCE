# Linea Base de Seguridad — AG-EVIDENCE

> Estado actual de controles de seguridad, resultado de la auditoria
> realizada el 2026-02-19.

**Identificador:** SEC-BAS-001
**Version:** 1.0.0
**Fecha:** 2026-02-19
**Auditor:** Claude Code
**Metodo:** Revision estatica de codigo + analisis de configuracion

---

## 1. Resumen Ejecutivo

| Categoria | Estado | Detalle |
|-----------|--------|---------|
| Secretos y credenciales | PASS | Ningun secreto hardcodeado en codigo |
| Validacion de entrada | PARCIAL | Validacion de imagenes OK; falta validacion de paths y JSON schema |
| Manejo de archivos | RIESGO | Archivos temporales sin limpieza automatica |
| Subprocesos | PASS | No hay uso de `shell=True` ni inyeccion de comandos |
| Funciones peligrosas | PASS | No se usa `eval()`, `exec()`, `pickle.loads()` |
| Parsing JSON | RIESGO | Sin validacion de schema; sin limites de tamano |
| Logging | MIXTO | JSONL estructurado excelente; falta politica de retencion |
| Hashing e integridad | EXCELENTE | SHA-256 en cadena de custodia con patron robusto |
| Manejo de errores | BUENO | Try/except consistente; sin exposicion de stack traces |
| Dependencias | ROTO | requirements.txt incompleto o desactualizado |
| .gitignore | EXCELENTE | Datos sensibles correctamente excluidos |
| Autenticacion | ACEPTABLE | Sistema local sin red; Ollama sin auth es aceptable |
| Criptografia | DEBIL | Solo hashing; sin cifrado de datos en reposo |
| Documentacion de seguridad | NUEVO | Este documento inaugura la documentacion formal |

---

## 2. Detalle por Modulo

### 2.1 src/ingestion/custody_chain.py

| Aspecto | Estado | Detalle |
|---------|--------|---------|
| Hash SHA-256 | EXCELENTE | Implementacion robusta con multiples algoritmos |
| Registro JSONL | OK | Cada documento registra hash + timestamp |
| Path handling | PARCIAL | Usa `os.path` pero sin validacion de traversal |
| Temp files | NO APLICA | No crea archivos temporales |

### 2.2 src/ingestion/trace_logger.py

| Aspecto | Estado | Detalle |
|---------|--------|---------|
| Estructura JSONL | EXCELENTE | trace_id unico, timestamps ISO, niveles tipados |
| Retencion | AUSENTE | Sin politica de rotacion ni limpieza |
| Datos sensibles en logs | RIESGO | Podria registrar fragmentos OCR con datos personales |
| Concurrencia | OK | Escritura secuencial, sin locks necesarios |

### 2.3 src/ocr/core.py

| Aspecto | Estado | Detalle |
|---------|--------|---------|
| Validacion de dimensiones | IMPLEMENTADO | `_validar_dimensiones()` con tests |
| Timeout | CONFIGURADO | 120s por defecto en `OCR_CONFIG` |
| Archivos temporales | RIESGO | Crea imagenes en `output/ocr_temp/` sin limpieza |
| Manejo de errores | BUENO | Try/except con fallback Tesseract |

### 2.4 src/extraction/abstencion.py

| Aspecto | Estado | Detalle |
|---------|--------|---------|
| Politica de abstencion | EXCELENTE | 550 lineas, 66 tests, robusta |
| CampoExtraido tipado | EXCELENTE | Enum status, confianza, bbox, motor |
| Serialization | OK | `to_dict()`/`from_dict()` con validacion |

### 2.5 src/extraction/expediente_contract.py

| Aspecto | Estado | Detalle |
|---------|--------|---------|
| Contrato tipado | EXCELENTE | 1161 lineas, 84 tests |
| Hash de expediente | IMPLEMENTADO | `generar_hash()` con SHA-256 |
| Anti-duplicidad | IMPLEMENTADO | `verificar_unicidad_comprobantes()` |
| Serialization roundtrip | VERIFICADO | JSON to/from con tests |

### 2.6 src/extraction/local_analyst.py

| Aspecto | Estado | Detalle |
|---------|--------|---------|
| Feature flag | OK | `enabled=False` por defecto |
| Bloqueo de campos probatorios | IMPLEMENTADO | `_bloquear_valores_probatorios()` |
| Confinamiento de IA | IMPLEMENTADO | Capa C no puede escribir datos criticos |

### 2.7 src/ingestion/pdf_text_extractor.py

| Aspecto | Estado | Detalle |
|---------|--------|---------|
| Manejo de PDF | OK | PyMuPDF con manejo de errores |
| Validacion post-rotacion | IMPLEMENTADO | Dimensiones verificadas |
| Path handling | PARCIAL | Sin proteccion contra traversal |

### 2.8 config/settings.py

| Aspecto | Estado | Detalle |
|---------|--------|---------|
| Credenciales | LIMPIO | Sin secretos hardcodeados |
| Configuracion sensible | OK | Solo parametros tecnicos |
| Feature flags | OK | `LOCAL_ANALYST_CONFIG["enabled"] = False` |

---

## 3. Hallazgos Criticos

### 3.1 HAL-001: Archivos temporales sin limpieza

- **Severidad:** MEDIA
- **Ubicacion:** `src/ocr/core.py`, directorio `output/ocr_temp/`
- **Descripcion:** El pipeline OCR crea imagenes temporales durante el renderizado de paginas PDF. Estos archivos no se eliminan automaticamente al finalizar el procesamiento.
- **Riesgo:** Acumulacion de datos potencialmente sensibles en disco.
- **Remediacion:** Implementar context manager con limpieza en `finally` block.
- **Estado:** PENDIENTE Fase 1

### 3.2 HAL-002: Sin validacion de esquema JSON

- **Severidad:** MEDIA
- **Ubicacion:** `src/extraction/expediente_contract.py` (`from_json`)
- **Descripcion:** El metodo `from_json()` deserializa JSON sin validar contra un schema formal. Un JSON malformado podria causar errores no controlados.
- **Riesgo:** Datos corruptos o inesperados en el pipeline.
- **Remediacion:** Agregar validacion de schema en `from_json()` con errores descriptivos.
- **Estado:** PENDIENTE Fase 1

### 3.3 HAL-003: requirements.txt incompleto

- **Severidad:** ALTA
- **Ubicacion:** Raiz del proyecto
- **Descripcion:** Dependencias criticas (PaddlePaddle, PyMuPDF, openpyxl, etc.) no estan listadas o estan desactualizadas en requirements.txt.
- **Riesgo:** Builds no reproducibles; dependencias no auditables.
- **Remediacion:** Regenerar requirements.txt con `pip freeze` filtrado.
- **Estado:** PENDIENTE Fase 2

### 3.4 HAL-004: Sin proteccion contra path traversal

- **Severidad:** MEDIA
- **Ubicacion:** Multiples modulos que reciben paths de archivo
- **Descripcion:** Las funciones que reciben rutas de archivo no validan contra traversal (e.g., `../../etc/passwd`).
- **Riesgo:** Bajo en contexto local, pero viola best practices.
- **Remediacion:** Funcion de validacion centralizada de paths.
- **Estado:** PENDIENTE Fase 1

### 3.5 HAL-005: Sin politica de retencion de logs

- **Severidad:** BAJA
- **Ubicacion:** `src/ingestion/trace_logger.py`
- **Descripcion:** Los logs JSONL crecen indefinidamente sin rotacion ni limpieza.
- **Riesgo:** Consumo de disco; posible acumulacion de datos personales.
- **Remediacion:** Agregar rotacion por tamano o fecha.
- **Estado:** PENDIENTE Fase 2

---

## 4. Controles Existentes (Fortalezas)

| Control | Modulo | Calificacion |
|---------|--------|-------------|
| SHA-256 cadena de custodia | custody_chain.py | A+ |
| Logger JSONL estructurado | trace_logger.py | A |
| Abstencion formal | abstencion.py | A+ |
| Contrato tipado con hash | expediente_contract.py | A |
| Anti-duplicidad | expediente_contract.py | A |
| Bloqueo de IA en campos probatorios | local_analyst.py | A |
| Validacion de dimensiones de imagen | core.py | A |
| .gitignore (datos sensibles) | .gitignore | A+ |
| Sin secretos en codigo | Todo el proyecto | A+ |
| Sin subprocesos inseguros | Todo el proyecto | A |
| Branch protection + CI (4 jobs) | .github/workflows/ci-lint.yml | A |
| Governance file integrity (SHA-256) | governance/integrity_manifest.json | A+ |
| Pre-commit hooks (ruff + guard) | .pre-commit-config.yaml | A |
| CODEOWNERS ownership control | .github/CODEOWNERS | A |
| Merge protection (gitattributes) | .gitattributes | A |
| Author verification (CI hard block) | .github/workflows/ci-lint.yml | A+ |
| Repo integrity audit (7 checks) | scripts/audit_repo_integrity.py | A+ |

---

## 5. Metricas de Seguridad

| Metrica | Valor | Objetivo |
|---------|-------|----------|
| Controles implementados | 17/18 | 18/18 |
| Hallazgos criticos | 0 | 0 |
| Hallazgos medios | 4 | 0 |
| Hallazgos bajos | 1 | 0 |
| Tests de seguridad | ~15 | 30+ |
| Cobertura de modulos auditados | 8/8 | 8/8 |

---

## Historial de Versiones

| Version | Fecha | Cambio |
|---------|-------|--------|
| 1.0.0 | 2026-02-19 | Auditoria inicial completa |
| 1.1.0 | 2026-02-24 | Blindaje repositorio: 4 capas defensa en profundidad |

---

*Auditoria realizada por Claude Code. Validacion pendiente por Hans.*
