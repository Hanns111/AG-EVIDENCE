# Reglas de Validacion: Anexo 3 vs Facturas (Comprobantes de Pago)

> Documento de gobernanza para la etapa de validacion (Fase 4+).
> Origen: Instruccion directa de Hans (2026-02-12) durante procesamiento de
> expediente OTIC2026-INT-0115085.

---

## 1. Documento Fuente

**La factura (comprobante de pago) es SIEMPRE el documento fuente.**

El Anexo 3 (Rendicion de Cuentas por Comision de Servicios) es un formulario
llenado manualmente por el comisionado. Puede contener errores humanos.

Por lo tanto:
- La hoja "Comprobantes" del Excel refleja **exactamente lo que dice cada factura**
- NO se compara ni se ajusta contra el Anexo 3 en la etapa de extraccion
- La validacion cruzada Anexo 3 vs Factura es una **etapa posterior** (Fase 4+)

---

## 2. Reglas de Validacion Cruzada (para Fase 4)

### 2.1 Regla de Monto: Anexo 3 <= Factura (nunca mayor)

| Condicion | Estado | Explicacion |
|-----------|--------|-------------|
| Anexo 3 == Factura | OK | Montos coinciden |
| Anexo 3 < Factura | OK (practica valida) | El comisionado puede poner montos menores para no superar topes diarios |
| Anexo 3 > Factura | ALERTA CRITICA | Nunca debe ocurrir; el Anexo 3 no puede reflejar mas de lo que dice la factura |

### 2.2 Practica valida: Distribucion de hospedaje por dia

El comisionado puede tomar UNA factura de hotel que cubre N noches y distribuirla
en el Anexo 3 como N lineas (una por dia). Esto es practica comun y valida.

**Ejemplo real (OTIC2026-INT-0115085):**
- Factura E001-8998 (El Meson Hotel): S/260 por 2 noches (02-04 Feb)
- Anexo 3: 2 lineas de S/130 (una para 02/Feb, otra para 03/Feb)
- Validacion: S/130 + S/130 = S/260 == factura -> OK

### 2.3 Practica valida: Factura unica sin distribuir

Alternativamente, el comisionado puede reflejar la factura de hospedaje como
una sola linea en el Anexo 3 sin distribuir por dia. El especialista de control
previo debe verificar que los dias de la factura correspondan a los dias de
la comision.

### 2.4 Practica valida: Monto menor en Anexo 3

El comisionado puede declarar en Anexo 3 un monto menor al de la factura para
mantenerse dentro de los topes presupuestales diarios por concepto.

**Ejemplo real (OTIC2026-INT-0115085):**
- Factura FN5E-00000194 (Arcos Dorados/McDonald's): S/27.40 (incluye RCC S/0.23)
- Anexo 3: S/25.00
- Diferencia: S/2.40 (comisionado declaro menos, dentro de practica valida)
- Validacion: S/25 < S/27.40 -> OK (Anexo 3 < Factura)

---

## 3. Hallazgos del Expediente OTIC2026-INT-0115085

Hallazgos identificados durante la extraccion que deben ser verificados en
la etapa de validacion:

### 3.1 Discrepancias de Monto (Anexo 3 < Factura)

| Factura | Monto Factura | Monto Anexo 3 | Diferencia | Estado |
|---------|--------------|---------------|------------|--------|
| FN5E-00000194 (Arcos Dorados) | S/27.40 | S/25.00 | -S/2.40 | OK (< factura) |
| E001-8998 (El Meson, 2 noches) | S/260.00 | S/130 x 2 = S/260 | S/0 | OK (distribuido por dia) |

### 3.2 Cargos adicionales en facturas

| Factura | Concepto adicional | Monto |
|---------|-------------------|-------|
| FN5E-00000194 (Arcos Dorados) | RCC (Recargo Consumo Combustible) 1% | S/0.23 |
| F001-00002309 (Nuqanchik/Biru) | Propina voluntaria | S/1.00 |
| F009-00004337 (13 Monjas) | RC (Recargo al Consumo) | S/2.75 |

### 3.3 Fecha de emision vs fecha de servicio

| Factura | Fecha emision | Fecha servicio | Observacion |
|---------|--------------|----------------|-------------|
| E001-394 (Mantari, retorno) | 08/02/2026 | 04/02/2026 | Emitida 4 dias despues del servicio |

### 3.4 Tasas de IGV aplicadas

| Factura | IGV | Base legal |
|---------|-----|-----------|
| E001-8998 (El Meson Hotel) | 10% MYPE | Ley 31556 + 32219 |
| FA01-00001245 (Rooftop77) | 10% MYPE | Ley 31556 + 32219 |
| FPP1-027804 (Glorieta Tacnena) | 10% MYPE | Ley 31556 + 32219 |
| F005-1302 (Ganadera Malaga) | 10% MYPE | Ley 31556 + 32219 |
| F001-00002309 (Nuqanchik) | 10% MYPE | Ley 31556 + 32219 |
| F009-00004337 (13 Monjas) | 10% MYPE | Ley 31556 + 32219 |
| FN5E-00000194 (Arcos Dorados) | 18% general | Regimen general |
| E001-390, E001-394 (Mantari) | 0% exonerado | Persona natural (taxi) |

---

## 4. Verificaciones Pendientes (Fase 4)

Para implementar en el modulo de validacion:

1. **Consistencia Anexo 3 vs Facturas**: Verificar que cada factura del Anexo 3
   tenga su comprobante escaneado y que monto Anexo 3 <= monto factura

2. **Topes presupuestales diarios**: Verificar que los montos por concepto
   (alimentacion, hospedaje, movilidad local) no excedan los topes diarios
   segun la directiva vigente

3. **Verificacion RUC SUNAT**: Para cada RUC de factura, consultar:
   - Actividad economica (MYPE restaurante/hotel para IGV 10%)
   - Condicion de contribuyente (activo/habido)
   - Coherencia tasa IGV aplicada vs regimen del emisor

4. **Fechas de emision**: Verificar que las fechas de emision de facturas
   estan dentro del periodo de la comision (o rango razonable)

5. **Duplicados**: Detectar facturas duplicadas escaneadas (pag 50 y 53
   son la misma factura E001-8998)

---

## 5. Implementacion Tecnica

Estas reglas se implementaran como parte del:
- **Integrity Checkpoint** (Tarea #18, nodo en Router LangGraph)
- **Modulo de validacion** (Fase 4, Tareas #27-29)
- **EvidenceEnforcer** (post-contrato tipado, snippet + pagina + regla)

Cada hallazgo debe generar un `integrity_status`:
- `OK`: Todo conforme
- `WARNING`: Discrepancia menor (ej: Anexo 3 < Factura, practica valida)
- `CRITICAL`: Discrepancia mayor (ej: Anexo 3 > Factura, factura sin RUC valido)

---

*Documentado: 2026-02-12 por Claude Code*
*Fuente: Instruccion directa de Hans durante sesion de procesamiento*
