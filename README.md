# AG-EVIDENCE

**Automated Prior Control System for Administrative Records**
*Multi-Agent Document Analysis with Evidentiary Standards*

---

## Overview

AG-EVIDENCE is an automated prior control system that analyzes administrative records (expedientes) using a pipeline of nine specialized AI agents. Each document undergoes classification, text extraction, cross-reference validation, legal compliance verification, and a final decision — all backed by strict evidentiary standards.

The system produces structured verdicts: **PROCEED**, **PROCEED WITH OBSERVATIONS**, or **DO NOT PROCEED** — with every finding traceable to a specific file, page, and text excerpt.

Designed for the Ministry of Education of Peru (MINEDU), with architecture and compliance standards suitable for European public sector institutions and international auditing requirements.

---

## Key Capabilities

| Capability | Description |
|---|---|
| **9-Agent Pipeline** | Classification, OCR, Coherence, Legal, Signatures, Integrity, Penalties, Tax Authority, Decision |
| **Evidentiary Standard** | Every critical finding requires: source file + page number + verbatim excerpt |
| **Chain of Custody** | Immutable PDF copies with SHA-256 hash verification |
| **Structured Traceability** | JSONL trace logs with UUID per document, correlating all processing steps |
| **Anti-Hallucination Policy** | Strict prohibition on inferred data; uncertain findings degraded to INCONCLUSIVE |
| **Local-First Architecture** | All processing runs on-premises; no cloud dependencies; GDPR-aligned |
| **LLM Integration** | Local inference via Ollama (Qwen3 32B) on NVIDIA RTX 5090 |

---

## Architecture

```
                         ORCHESTRATOR
                             |
    +--------+--------+------+------+--------+--------+
    |        |        |      |      |        |        |
  AG01     AG02     AG03   AG04   AG05     AG06     AG07
Classify    OCR   Coherence Legal Signatures Integrity Penalties
    |        |        |      |      |        |        |
    +--------+--------+------+------+--------+--------+
                             |
                      +------+------+
                      |             |
                    AG08          AG09
                 Tax Authority   Decision
```

| Agent | Role | Output |
|---|---|---|
| AG01 Classifier | Detects document type (travel expenses, petty cash, supplier payment, etc.) | Nature + applicable directive |
| AG02 OCR | Extracts text with quality gating (native PDF / OCR / manual fallback) | Extracted text + confidence score |
| AG03 Coherence | Cross-references SINAD, record numbers, contract identifiers | Inconsistency report |
| AG04 Legal | Validates against applicable directive requirements | Compliance checklist |
| AG05 Signatures | Verifies authorized signatories per applicable regulations | Signature verification report |
| AG06 Integrity | Checks documentation completeness (TDR, CCI, compliance certificates) | Missing documents list |
| AG07 Penalties | Evaluates penalty applicability for delivery delays | Penalty assessment |
| AG08 Tax Authority | Public RUC lookup (status, condition, business activity) | Tax authority report |
| AG09 Decision | Consolidates all findings into final structured verdict | PROCEED / OBSERVATIONS / DO NOT PROCEED |

---

## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Runtime | Python 3.8+ | Core application |
| PDF Processing | PyMuPDF (fitz) | Native text extraction |
| OCR Engine | Tesseract + ocrmypdf | Scanned document processing |
| LLM Inference | Ollama + Qwen3:32B | Local AI reasoning |
| GPU | NVIDIA RTX 5090 (32 GB VRAM) | Hardware-accelerated inference |
| Execution Environment | WSL2 (Ubuntu 22.04) | Production runtime |
| Integrity | SHA-256 + JSONL registry | Chain of custody |
| Traceability | JSONL + UUID trace_id | Structured audit trail |

---

## Installation

### Prerequisites

- Python 3.8 or higher
- Windows 10/11 (development) or WSL2 Ubuntu 22.04 (production)
- Ollama installed with Qwen3:32B model (for AI features)

### Setup

```bash
git clone https://github.com/Hanns111/AG-EVIDENCE.git
cd AG-EVIDENCE
pip install -r requirements.txt
```

### Verify Installation

```bash
python -c "import fitz; print('PyMuPDF OK')"
python -m pytest tests/test_custody_chain.py tests/test_trace_logger.py -v
```

---

## Usage

### Batch Analysis

```bash
# Analyze documents in default directory
python ejecutar_control_previo.py

# Specify document folder
python ejecutar_control_previo.py --carpeta "/path/to/documents"

# Save report automatically
python ejecutar_control_previo.py --guardar

# Silent mode with auto-save
python ejecutar_control_previo.py --silencioso --guardar
```

### Conversational Assistant

```bash
# Natural language queries about documents and directives
python chat_asistente.py --modo conversacional --backend llm

# Load specific PDFs
python chat_asistente.py --pdf "document.pdf" --backend llm

# Regex-only mode (no LLM required)
python chat_asistente.py --backend regex
```

### Python API

```python
from orquestador import ejecutar_control_previo

result = ejecutar_control_previo("/path/to/documents")
print(result.decision)  # PROCEDE / NO_PROCEDE / PROCEDE_CON_OBSERVACIONES
```

### Chain of Custody

```python
from src.ingestion import CustodyChain

chain = CustodyChain()
record = chain.ingest("document.pdf", sinad="EXP-2026-0001")
verification = chain.verify(record.custody_id)
assert verification.is_intact
```

### Structured Tracing

```python
from src.ingestion import TraceLogger

logger = TraceLogger()
ctx = logger.start_trace(sinad="EXP-2026-0001", source="batch")
logger.info("Classification complete", agent_id="AG01", context={"type": "TRAVEL"})
logger.set_agent("AG02", "ocr_extract")
logger.info("OCR extraction complete", duration_ms=3200)
summary = logger.end_trace(status="success")
```

---

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | PROCEED |
| 1 | PROCEED WITH OBSERVATIONS |
| 2 | DO NOT PROCEED |
| 130 | Cancelled by user (Ctrl+C) |

---

## Project Structure

```
AG-EVIDENCE/
├── agentes/                    # 9 specialized agents + conversational + directives
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
├── src/                        # Core modules
│   ├── ingestion/              # PDF extraction + chain of custody + trace logger
│   │   ├── pdf_text_extractor.py
│   │   ├── custody_chain.py
│   │   └── trace_logger.py
│   ├── ocr/                    # OCR engine (Tesseract/PaddleOCR)
│   ├── rules/                  # Validation rules
│   └── tools/                  # Technical tools
│
├── config/
│   └── settings.py             # Global configuration, enums, dataclasses
│
├── utils/                      # LLM client, exporters, validators
├── tests/                      # Unit and integration tests (82 passing)
├── docs/                       # Governance and architecture documentation
│
├── orquestador.py              # Multi-agent orchestrator
├── ejecutar_control_previo.py  # Batch analysis entrypoint
├── chat_asistente.py           # CLI conversational assistant
├── requirements.txt            # Python dependencies
├── pyproject.toml              # Python packaging configuration
├── CHANGELOG.md                # Version history (Keep a Changelog)
├── CONTRIBUTING.md             # Contribution guidelines
└── LICENSE                     # MIT License
```

---

## Documentation

| Document | Purpose |
|---|---|
| [AGENT_GOVERNANCE_RULES.md](docs/AGENT_GOVERNANCE_RULES.md) | Normative rules governing agent behavior |
| [ARCHITECTURE_SNAPSHOT.md](docs/ARCHITECTURE_SNAPSHOT.md) | Current system architecture and technical state |
| [ARCHITECTURE_VISUAL.md](docs/ARCHITECTURE_VISUAL.md) | Visual diagrams of system architecture |
| [PROJECT_SPEC.md](docs/PROJECT_SPEC.md) | Project specification and objectives |
| [GOVERNANCE_RULES.md](docs/GOVERNANCE_RULES.md) | Project governance framework |
| [OCR_SPEC.md](docs/OCR_SPEC.md) | OCR technical specification |
| [GLOSSARY.md](docs/GLOSSARY.md) | Technical terminology reference |
| [ADR.md](docs/ADR.md) | Architectural Decision Records |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute to the project |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

---

## Testing

```bash
# Run all infrastructure tests (custody chain + trace logger)
python -m pytest tests/test_custody_chain.py tests/test_trace_logger.py -v

# Run all tests (requires PyMuPDF)
python -m pytest tests/ -v
```

### Test Coverage

| Module | Tests | Status |
|---|---|---|
| Chain of Custody (Task #10) | 27 | Passing |
| Trace Logger (Task #11) | 55 | Passing |
| **Total Infrastructure** | **82** | **All Passing** |

---

## Compliance and Standards

### Evidentiary Standard

Every critical or major finding produced by the system must include:

1. **Source file** — which document contains the finding
2. **Page number** — specific location within the document
3. **Verbatim excerpt** — exact text supporting the finding

Findings without evidence are automatically degraded to INCONCLUSIVE.

### Privacy and Data Protection

- **Local-first architecture**: no data leaves the premises
- **No cloud dependencies**: all processing runs on local hardware
- **GDPR-aligned**: Privacy by Design principles from the ground up
- **No paid APIs**: zero operational cost for AI inference

### Auditability

- **Chain of Custody**: every ingested document is copied to an immutable vault with SHA-256 hash verification
- **Structured Tracing**: every processing step is recorded in JSONL with UUID correlation
- **Append-only logs**: audit records cannot be modified after creation
- **Semantic versioning**: all changes tracked via Conventional Commits

### Security Boundaries

- No access to Clave SOL (tax authority credentials)
- No authenticated SIRE integration
- No paid services or external API dependencies
- Tax authority queries limited to public RUC lookup
- All tax authority results marked as INFORMATIONAL

---

## Versioning

This project follows [Semantic Versioning](https://semver.org/) and [Keep a Changelog](https://keepachangelog.com/).

| Version | Date | Highlights |
|---|---|---|
| v2.2.0 | 2026-02-10 | Chain of custody, structured trace logger, project governance |
| v2.1.0 | 2025-12 | Conversational agent with local LLM (Ollama + Qwen) |
| v2.0.0 | 2025-12 | Evidentiary standard with strict anti-hallucination policy |
| v1.0.0 | 2025-12 | Initial release with 9-agent pipeline |

See [CHANGELOG.md](CHANGELOG.md) for detailed release notes.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Contact

Developed for the Ministry of Education of Peru.
Prior Control — General Administration Office (OGA).
