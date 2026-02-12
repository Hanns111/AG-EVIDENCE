# Tasas del IGV para MYPES — Restaurantes, Hoteles y Alojamientos

## Base Legal

| Norma | Descripción |
|-------|-------------|
| **Ley N° 31556** | Ley que promueve la reactivación de MYPES del sector restaurantes, hoteles y alojamientos turísticos |
| **Ley N° 32219** | Modifica la Ley 31556 — amplía vigencia y establece escala progresiva |
| **DS 237-2022-EF** | Decreto Supremo que reglamenta la Ley 31556 (Art. 2 y anexo: actividades SUNAT que califican) |

## Tabla de Tasas Vigentes

| Periodo | IGV | IPM | Total Efectivo | Norma |
|---------|-----|-----|----------------|-------|
| 2022-2024 | 8% | 2% | **10%** | Ley 31556 |
| 2025-2026 | 8% | 2% | **10%** | Ley 32219 (ampliación) |
| 2027 | 12% | 3% | **15%** | Ley 32219 (escala progresiva) |
| 2028+ | 16% | 2% | **18%** | Tasa general (retorno a régimen normal) |

---

## Requisitos para Aplicar la Tasa Especial

### 1. Inscripción en SUNAT (RUC) — OBLIGATORIO

El proveedor debe estar inscrito en el RUC con:
- **Actividad económica principal o secundaria** correspondiente a restaurantes/hoteles/alojamientos
- Códigos SUNAT habilitantes (según DS 237-2022-EF, Art. 2 y anexo):
  - Restaurantes y similares
  - Servicio de hospedaje
  - Hoteles, hostales, posadas
  - Alojamiento turístico
- **RUC activo** (no suspendido, no baja)
- **Clave SOL** para emitir comprobantes electrónicos

### 2. Condición de MYPE — OBLIGATORIO

La empresa debe ser reconocida por SUNAT como micro o pequeña empresa:
- Facturación anual menor a los umbrales establecidos
- No estar clasificado como gran empresa
- **NO se requiere certificación separada** — la condición MYPE es tributaria (SUNAT), no laboral

### 3. Deberes Formales — OBLIGATORIO

- Estar al día en obligaciones tributarias con SUNAT
- No tener infracciones graves
- No estar con suspensión de RUC

### 4. Lo que NO se requiere

| Requisito | ¿Obligatorio? | Nota |
|-----------|:------------:|------|
| Inscripción en SUNAT (RUC) | **SÍ** | Ley 31556 / DS 237-2022-EF |
| Actividad económica correcta en RUC | **SÍ** | DS 237-2022-EF |
| Condición MYPE reconocida por SUNAT | **SÍ** | Ley 31556 |
| Registro en MINTRA | **NO** | No existe obligación específica |
| Certificación laboral MYPE | **NO** | La condición es tributaria, no laboral |
| Inscripción en Ministerio de Turismo | **NO** | No es requisito para la tasa reducida |

---

## Verificación Práctica

### Consulta de RUC en SUNAT
**URL:** https://www.sunat.gob.pe/consultaRUC

Se puede verificar:
1. Estado del RUC (activo/suspendido/baja)
2. Actividad(es) económica(s) registrada(s)
3. Régimen tributario
4. Condición de contribuyente
5. Dirección fiscal

### Para AG-EVIDENCE — Protocolo de Verificación (Fase 4: Validaciones)

Cuando un comprobante muestra IGV distinto al 18%:

```
SI igv_porcentaje ≈ 10% Y proveedor es restaurante/hotel/alojamiento:
    → Verificar RUC en SUNAT:
        - ¿Actividad económica califica? (códigos restaurante/hotel/alojamiento)
        - ¿RUC activo?
        - ¿Condición MYPE?
    → SI todo OK → VÁLIDO (Ley 31556 + Ley 32219)
    → SI no califica → ALERTA: proveedor no habilitado para tasa reducida

SI igv_porcentaje ≈ 0% Y proveedor en zona Amazonía:
    → Verificar ubicación del establecimiento
    → Ley 27037 (Loreto, Ucayali, San Martín, Amazonas, Madre de Dios)

SI igv_porcentaje no es 18%, 10%, ni 0%:
    → ALERTA CRÍTICA: porcentaje no reconocido
```

### Escala Temporal de Validación

| Fecha del comprobante | Tasa MYPE válida | Tasa general |
|----------------------|:----------------:|:------------:|
| 2022-2024 | 10% | 18% |
| 2025-2026 | 10% | 18% |
| 2027 | 15% | 18% |
| 2028+ | 18% | 18% |

---

## Aplicación en Control Previo — Reglas para AG-EVIDENCE

### Tasas que el sistema debe reconocer (2025-2026):

| Régimen | Tasa Total | Condición | Base Legal |
|---------|:---------:|-----------|-----------|
| General | **18%** | Cualquier contribuyente no MYPE | TUO IGV |
| MYPE Restaurantes/Hoteles | **10%** | RUC activo + actividad calificada + condición MYPE | Ley 31556 + Ley 32219 |
| Amazonía (exonerado) | **0%** | Establecimiento en zona de Amazonía | Ley 27037 |
| Apéndice I y II (exonerado) | **Exonerado** | Alimentos básicos, transporte, seguros, etc. | TUO IGV |

### Alertas que AG-EVIDENCE debe generar:

| Situación | Nivel | Acción |
|-----------|:-----:|--------|
| IGV 10% en factura de restaurante/hotel MYPE | INFO | Verificar RUC en SUNAT — probablemente correcto |
| IGV 10% en factura de proveedor NO restaurante/hotel | **ALERTA** | No debería aplicar tasa reducida |
| IGV 10% después de 2026 | **ALERTA** | Desde 2027 la tasa MYPE sube a 15% |
| IGV 0% fuera de zona Amazonía | **ALERTA** | Verificar si aplica exoneración |
| IGV distinto a 18%, 10%, 0% | **CRÍTICA** | Porcentaje no reconocido en normativa vigente |
| Proveedor con RUC inactivo o suspendido | **CRÍTICA** | Comprobante no válido |

---

## Archivos de Respaldo

Ubicados en esta misma carpeta:
- `Ley nro 31556.pdf` — Texto original de la ley (Art. 2: definición de beneficiarios)
- `LEY Nº 32219_modifica Ley 31556.PDF` — Modificatoria: ampliación vigencia + escala progresiva
- `DS237_2022_EF.pdf.pdf` — Reglamento: Art. 2 y anexo con actividades SUNAT habilitadas

---

*Documentado: 2026-02-12 por Claude Code para AG-EVIDENCE v2.0*
*Fuente normativa: Ley 31556, Ley 32219, DS 237-2022-EF*
*Verificación práctica: https://www.sunat.gob.pe/consultaRUC*
