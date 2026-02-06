# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Estructura base enterprise europea
- Documentación de arquitectura y gobernanza
- Sistema de categorización automática de expedientes
- Integración de nueva Directiva DI-003-01-MINEDU v03 (vigente desde 06.02.2026)

### Changed
- Migración a estándar profesional europeo
- Reorganización de estructura de carpetas
- Actualización de .gitignore para excluir datos sensibles

### Security
- Exclusión de PDFs, documentos y datos sensibles del repositorio
- Protección de información confidencial mediante .gitignore

---

## [1.0.0] - 2026-02-06

### Added
- Sistema multi-agente de análisis probatorio
- 9 agentes especializados (Clasificador, OCR, Coherencia, Legal, Firmas, Integridad, Penalidades, SUNAT, Decisor)
- Chat asistente conversacional
- Estándar probatorio estricto (archivo + página + snippet)
- Política anti-alucinación
- Integración con Ollama/Qwen para inferencia local
