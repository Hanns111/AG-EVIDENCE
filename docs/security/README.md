# docs/security/ — Documentacion de Seguridad AG-EVIDENCE

> Directorio de gobernanza de seguridad del proyecto.
> Alineado con NIS2, GDPR Art.32, NIST CSF 2.0, NIST SSDF, CISA Secure by Design.

---

## Documentos

| Archivo | Proposito | ID |
|---------|-----------|-----|
| [SECURITY_GOVERNANCE_POLICY.md](SECURITY_GOVERNANCE_POLICY.md) | Politica general de seguridad: principios, roles, clasificacion de datos, controles | SEC-GOV-001 |
| [SECURITY_BASELINE.md](SECURITY_BASELINE.md) | Estado actual de controles (resultado de auditoria) | SEC-BAS-001 |
| [SECURITY_ROADMAP.md](SECURITY_ROADMAP.md) | Plan de implementacion progresiva de controles por fase | SEC-RDM-001 |
| [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) | Plan de respuesta a incidentes de seguridad | SEC-INC-001 |
| [RISK_REGISTER.md](RISK_REGISTER.md) | Registro vivo de riesgos identificados y su mitigacion | SEC-RSK-001 |

---

## Relacion con otros documentos de gobernanza

```
docs/
  GOVERNANCE_RULES.md            ← Reglas generales del proyecto
  GOBERNANZA_TECNICA_TRANSVERSAL.md  ← Reglas tecnicas (8 reglas)
  AGENT_GOVERNANCE_RULES.md      ← Reglas para agentes IA
  security/                      ← ESTE DIRECTORIO
    SECURITY_GOVERNANCE_POLICY.md  ← Politica de seguridad
    SECURITY_BASELINE.md           ← Estado actual
    SECURITY_ROADMAP.md            ← Plan de implementacion
    INCIDENT_RESPONSE.md           ← Respuesta a incidentes
    RISK_REGISTER.md               ← Registro de riesgos
```

---

## Como usar estos documentos

1. **Al iniciar una tarea nueva:** Consultar SECURITY_GOVERNANCE_POLICY.md para verificar
   que los controles aplicables estan implementados.
2. **Al completar una tarea:** Actualizar SECURITY_BASELINE.md si se implemento
   algun control nuevo.
3. **Al encontrar un riesgo:** Documentar en RISK_REGISTER.md con severidad y
   mitigacion propuesta.
4. **Ante un incidente:** Seguir INCIDENT_RESPONSE.md paso a paso.

---

*Creado: 2026-02-19 por Claude Code*
