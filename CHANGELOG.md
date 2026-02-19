# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [3.3.0] - 2026-02-18

### Added
- **Expediente DEBEDSAR2026-INT-0146130 procesado completo** (`scripts/generar_excel_DEBEDSAR2026.py`): Script de generacion Excel con estrategia mixta PyMuPDF + Qwen2.5-VL a 500 DPI. 17 comprobantes, 7 gastos DJ movilidad, 4 boletos terrestres. 4 hojas Excel (Anexo 3, Comprobantes Fuente, DJ Movilidad, Boletos Terrestres).
- **Regla NULL vs Blank**: NULL (celda roja) = motor no pudo leer campo existente. Blank = campo no aplicable al tipo de documento.
- **Regla de Boleta de Venta**: RUC comprador debe ser institucional (20xxx), no DNI personal. Inscripcion personal no permitida.

### Changed
- CLAUDE.md actualizado con expediente DEBEDSAR2026, errores VLM documentados, reglas de negocio aprendidas.
- Qwen2.5-VL renderizado a 500 DPI (antes 200 DPI) elimina casi todos los NULL de extraccion.

### Known Issues
- VLM confunde caracteres similares: 0/9 (F205-00012200 vs 12299), ll/lli (Calli vs gallina), ñ/n (Canaa vs Canga).
- Pendiente herramienta de lectura fina (crop+zoom o modelo mayor).

---

## [3.2.0] - 2026-02-18

### Added
- **Qwen2.5-VL-7B via Ollama** (`scripts/extraer_con_qwen_vl.py`): Motor VLM para extraccion visual de comprobantes de pago. Modelo qwen2.5vl:7b (Q4_K_M, 6GB) operando en RTX 5090 Laptop GPU via Ollama 0.16.2. Prompt forense de 11 grupos (A-K) con validacion aritmetica Python (Grupo J).
- **PARSING_COMPROBANTES_SPEC.md** (`docs/`): Especificacion obligatoria para parseo de comprobantes peruanos. 11 grupos de campos, Regla de Oro de Literalidad Forense.
- **ADR-009**: Decision arquitectonica de adoptar Qwen2.5-VL como motor VLM con estrategia mixta PyMuPDF + Qwen-VL.
- **Scripts de exploracion**: `explorar_expediente.py`, `extraer_expediente_diri.py`, `setup_ollama.sh` para procesamiento de expedientes DIRI2026-INT-0068815.
- **Fase A completada**: 3 facturas de referencia extraidas con >90% campos correctos.

### Changed
- CLAUDE.md actualizado con permisos completos de proyecto, stack Ollama/Qwen-VL, resultados Fase A.
- ARCHITECTURE_SNAPSHOT.md actualizado con nuevo motor VLM y estrategia mixta.

---

## [2.2.0] - 2026-02-10

### Added
- **Chain of Custody** (`src/ingestion/custody_chain.py`): immutable PDF vault with SHA-256 hash verification, JSONL registry, duplicate detection, and integrity verification on demand. 529 lines, 27 tests.
- **Structured Trace Logger** (`src/ingestion/trace_logger.py`): JSONL-based audit trail with UUID trace_id per document, 5 severity levels, daily file rotation, query by trace_id/SINAD/level. 638 lines, 55 tests.
- **Project Governance**: `.cursorrules` with 12 explicit guardrails (G1-G12), `CLAUDE.md` for session continuity, `CONTRIBUTING.md` with Cursor + Claude Code protocol.
- **Architecture Documentation**: `ARCHITECTURE_VISUAL.md` with 8 ASCII diagrams, `GLOSSARY.md` with 35+ terms.
- 82 infrastructure tests passing (0.48s total execution).

### Changed
- README.md rewritten to enterprise standard (English, compliance-focused, investor-ready).
- Project structure updated: `src/ingestion/` now contains custody chain and trace logger modules.

---

## [2.1.0] - 2025-12

### Added
- Conversational agent with local LLM (Ollama + Qwen).
- Specific value search (SINAD, RUC, etc.) across documents.
- Auto-detection backend mode (LLM if available, regex fallback).
- Free-form natural language queries.

---

## [2.0.0] - 2025-12

### Added
- Evidentiary standard with detailed evidence per finding.
- Automatic validation of all findings.
- Severity degradation for findings without evidence.
- Enhanced JSON/TXT export with full evidence chain.

---

## [1.0.0] - 2025-12

### Added
- 9 specialized agents (Classifier, OCR, Coherence, Legal, Signatures, Integrity, Penalties, SUNAT, Decision).
- OCR with quality detection and gating.
- Cross-document coherence verification.
- Public SUNAT RUC lookup.
- Digit error detection in identifiers.
- Signature verification.
- Penalty assessment for delivery delays.
- Structured report generation.

---

[2.2.0]: https://github.com/Hanns111/AG-EVIDENCE/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/Hanns111/AG-EVIDENCE/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/Hanns111/AG-EVIDENCE/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/Hanns111/AG-EVIDENCE/releases/tag/v1.0.0
