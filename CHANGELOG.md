# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
