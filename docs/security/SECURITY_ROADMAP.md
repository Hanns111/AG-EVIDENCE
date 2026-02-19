# Hoja de Ruta de Seguridad — AG-EVIDENCE

> Plan de implementacion progresiva de controles de seguridad,
> alineado con el ROADMAP de desarrollo del proyecto.

**Identificador:** SEC-RDM-001
**Version:** 1.0.0
**Fecha:** 2026-02-19
**Alineamiento:** NIS2, GDPR Art.32, NIST CSF 2.0, NIST SSDF SP 800-218, CISA Secure by Design

---

## Fase 1 — Estructura y Gobernanza (AHORA — con Tarea #17)

> Objetivo: Establecer la base de seguridad antes de expandir el pipeline.

### Controles a implementar

| # | Control | ID | Prioridad | Estado |
|---|---------|-----|----------|--------|
| 1 | Documentacion de seguridad (este directorio) | SEC-DOC-001 | CRITICA | EN PROGRESO |
| 2 | Limpieza automatica de archivos temporales | SEC-TMP-001 | ALTA | PENDIENTE |
| 3 | Validacion centralizada de paths | SEC-INP-002 | ALTA | PENDIENTE |
| 4 | Validacion de schema en from_json() | SEC-INP-003 | MEDIA | PENDIENTE |
| 5 | Constantes de seguridad en config | SEC-CFG-002 | MEDIA | PENDIENTE |
| 6 | Registro de riesgos (RISK_REGISTER.md) | SEC-DOC-002 | MEDIA | EN PROGRESO |

### Alineamiento normativo Fase 1

- **NIS2 Art.21(a):** Politicas de analisis de riesgos → SEC-DOC-001 + RISK_REGISTER
- **NIST CSF GV.RM:** Gestion de riesgos → RISK_REGISTER.md
- **NIST SSDF PO.1:** Politica de desarrollo seguro → SECURITY_GOVERNANCE_POLICY.md
- **CISA Principio 1:** Seguridad por defecto → Validaciones de entrada

---

## Fase 2 — Pipeline Estable (con Tareas #18-#21)

> Objetivo: Asegurar el flujo de datos cuando el pipeline este completo.

### Controles a implementar

| # | Control | ID | Prioridad | Depende de |
|---|---------|-----|----------|------------|
| 7 | requirements.txt completo y auditado | SEC-SUP-001 | CRITICA | — |
| 8 | Politica de retencion de logs | SEC-AUD-002 | ALTA | trace_logger.py |
| 9 | Sanitizacion de salida Excel | SEC-OUT-001 | ALTA | excel_writer.py |
| 10 | Verificacion de dependencias (pip-audit) | SEC-SUP-002 | MEDIA | requirements.txt |
| 11 | Tests de seguridad especificos | SEC-TST-001 | MEDIA | Todos los modulos |
| 12 | Rate limiting para Ollama | SEC-IAM-002 | BAJA | Fase 3 operativa |

### Alineamiento normativo Fase 2

- **NIS2 Art.21(d):** Seguridad de la cadena de suministro → SEC-SUP-001 + SEC-SUP-002
- **NIST CSF PR.DS:** Proteccion de datos → SEC-OUT-001
- **NIST SSDF PW.4:** Verificar artefactos → pip-audit
- **GDPR Art.32(1)(d):** Pruebas regulares → SEC-TST-001

---

## Fase 3 — Pre-Produccion (con Tareas #27-#34)

> Objetivo: Hardening final antes de uso en produccion real.

### Controles a implementar

| # | Control | ID | Prioridad | Depende de |
|---|---------|-----|----------|------------|
| 13 | Cifrado de datos en reposo | SEC-CRY-001 | ALTA | Evaluacion de volumen |
| 14 | Threat model formal (STRIDE) | SEC-THR-001 | ALTA | Pipeline completo |
| 15 | Plan de respuesta a incidentes | SEC-INC-001 | ALTA | INCIDENT_RESPONSE.md |
| 16 | Hardening de configuracion | SEC-CFG-001 | MEDIA | config/settings.py |
| 17 | Verificacion de integridad de modelos Ollama | SEC-IAM-001 | MEDIA | Modelos estables |
| 18 | Penetration testing basico | SEC-TST-002 | BAJA | Todo lo anterior |

### Alineamiento normativo Fase 3

- **NIS2 Art.21(h):** Cifrado → SEC-CRY-001
- **NIST CSF RS.MA:** Respuesta a incidentes → SEC-INC-001
- **NIST CSF ID.RA:** Evaluacion de riesgos → SEC-THR-001 (STRIDE)
- **GDPR Art.32(1)(a):** Cifrado y pseudonimizacion → SEC-CRY-001

---

## Calendario Estimado

```
2026-02 ████████░░ Fase 1: Documentacion + controles basicos
2026-03 ░░████████ Fase 2: Pipeline asegurado + dependencias
2026-04 ░░░░██████ Fase 3: Hardening + threat model
2026-05 ░░░░░░████ Evaluacion final + certificacion interna
```

> Las fechas dependen del avance del ROADMAP de desarrollo.
> Seguridad avanza en paralelo, no bloquea desarrollo.

---

## Criterios de Transicion entre Fases

### Fase 1 → Fase 2
- [ ] Todos los documentos de docs/security/ creados
- [ ] Limpieza de archivos temporales implementada
- [ ] Validacion de paths centralizada
- [ ] RISK_REGISTER.md con todos los hallazgos documentados

### Fase 2 → Fase 3
- [ ] requirements.txt completo y verificado con pip-audit
- [ ] Politica de retencion de logs implementada
- [ ] Tests de seguridad >= 30
- [ ] Pipeline de extraccion completo (Tarea #21 done)

### Fase 3 → Produccion
- [ ] Threat model STRIDE completado
- [ ] Plan de incidentes probado (tabletop exercise)
- [ ] Cifrado de datos en reposo implementado
- [ ] Zero hallazgos de severidad ALTA sin remediar

---

## Historial de Versiones

| Version | Fecha | Cambio |
|---------|-------|--------|
| 1.0.0 | 2026-02-19 | Hoja de ruta inicial |

---

*Documento generado por Claude Code bajo instruccion directa de Hans.*
