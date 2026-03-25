# SIGUIENTE PASO — PROBLEMA 3 (MONTO)

## Contexto

- El sistema ya clasifica páginas correctamente
- El sistema ya segmenta múltiples comprobantes por página

## Problema actual

- Error en extracción de montos
- Ejemplo:
  - p37 → real: 25.00
  - pipeline: 236.00

## Objetivo

Implementar extractor de montos determinístico:

- basado en etiquetas (TOTAL, IMPORTE, etc.)
- sin depender del VLM
- con validación aritmética

## Restricción

- NO permitir alucinación
- si hay duda → NULL

## Estado

LISTO PARA IMPLEMENTAR

---

## 🔴 CAPA FUTURA DEL CORE — CLASIFICACIÓN DE EXPEDIENTE

### Problema detectado

Expedientes que aparentan ser rendición de viáticos pero contienen solicitudes de reembolso.

### Impacto

Clasificación incorrecta implica:

- aplicación de reglas equivocadas
- validación normativa incorrecta
- conclusiones erróneas

### Objetivo

Clasificar el tipo de expediente ANTES del procesamiento de comprobantes.

### Tipos

- RENDICION
- REEMBOLSO
- OTRO

### Reglas iniciales

- “solicitud de reembolso” → REEMBOLSO
- “rendición de viáticos” → RENDICION
- Si ambos → REEMBOLSO (prioridad)

### Ubicación futura

`src/classification/expediente_classifier.py`

### Rol en pipeline

Se ejecuta antes de:

- extracción
- validación

### Estado

PENDIENTE (CORE)

---

## 🔵 FUTURA CAPA — VALIDACIÓN EXTERNA SUNAT

### Objetivo

Validar automáticamente los comprobantes detectados contra SUNAT, replicando el comportamiento de un humano.

### Alcance

- Validación de comprobantes (RUC + serie + número)
- Consulta de estado del RUC (activo/habido)
- Confirmación de validez del comprobante

### Enfoque técnico

- NO usar Selenium tradicional (detectado como bot)
- Evaluar:
  - Playwright (modo stealth)
  - consumo de endpoints internos SUNAT (si se identifican)
- Simular comportamiento humano (delays, interacción real)

### Requisitos

- No usar servicios pagos
- No depender de scraping frágil
- Generar evidencia (respuesta HTML o JSON)

### Diseño futuro

Crear módulo desacoplado:

`src/integration/sunat_validator.py`

### Salida esperada

```json
{
  "valido": true,
  "estado": "VALIDO / NO EXISTE",
  "ruc_activo": true,
  "condicion": "HABIDO / NO HABIDO",
  "fuente": "SUNAT",
  "timestamp": "...",
  "evidencia": "..."
}
```

### Estado

PENDIENTE

### Orden de implementación

Se ejecuta DESPUÉS de:

- Problema 3 (extracción de montos)
