# Reglas de Verificacion Visual de Comprobantes de Pago

> Documentado: 2026-02-13 | Basado en: Revision visual de Hans sobre expediente OPRE2026-INT-0131766
> Este archivo se actualiza con cada hallazgo nuevo identificado durante validacion humana.

---

## 1. Proposito

Este archivo registra las reglas de verificacion que Hans identifica durante
la revision visual de comprobantes extraidos. Cada regla nace de un caso real
y debe ser implementada en el sistema de validacion automatica (Fase 4).

---

## 2. Reglas Activas

### RV-001: Comprobante Parcialmente Cortado/Recortado

**Identificado en:** Factura E001-29 (GRUPO EMPRESARIAL PEMO S.A.C.)
**Expediente:** OPRE2026-INT-0131766
**Fecha:** 2026-02-13

**Descripcion:** El escaneo del comprobante no muestra el documento completo.
La imagen esta cortada o recortada, faltando informacion visible.

**Accion requerida:**
- Marcar en Observaciones: "Comprobante parcialmente cortado/recortado en el escaneo"
- Recomendar: "Devolver al area usuaria para re-escaneo"
- Extraer datos de la porcion visible e indicar que son parciales
- Clasificacion: **ALERTA** (no critico pero requiere accion del area usuaria)

**Deteccion automatica (futuro):**
- Verificar que las dimensiones del comprobante sean consistentes con formato estandar
- Verificar que campos obligatorios (RUC, total, serie-numero) esten presentes
- Si faltan campos obligatorios + imagen cortada → alerta automatica

---

### RV-002: Gasto Desproporcionado para Comision Individual

**Identificado en:** Factura F001-00009765 (RESTAURANT A&W EIRL - EDUARDO EL BRUJO)
**Expediente:** OPRE2026-INT-0131766
**Fecha:** 2026-02-13

**Descripcion:** La factura registra 2 platos principales (platos fuertes) para
1 sola persona en comision:
- Ceviche de Conchas Negras: S/70.00
- Pescado Frito Entero: S/60.00
- Total solo platos fuertes: S/130.00 de S/136.00 total

**Accion requerida:**
- Marcar en Observaciones: "Consumo potencialmente desproporcionado para comision individual"
- Incluir detalle: cantidad de platos principales y monto
- Recomendar: "Someter a evaluacion del especialista"
- Clasificacion: **OBSERVACION** (no invalida el gasto, pero requiere revision)

**Deteccion automatica (futuro):**
- Si cantidad de platos principales > 1 para mesa de 1 persona → observacion
- Si monto total alimentacion > tope diario permitido → alerta
- Cruzar con numero de comensales en factura (campo "Mesa" o "Personas")

---

### RV-003: Servicio de Transporte Exonerado de IGV

**Identificado en:** Factura E001-1450 (RAMOS TOLA MATEO) y F012-00018700 (PROACCION EMPRESARIAL)
**Expediente:** OPRE2026-INT-0131766
**Fecha:** 2026-02-13

**Descripcion:** Servicios de taxi/transporte terrestre con IGV exonerado.
Esto es CORRECTO segun normativa vigente para servicios de transporte.

**Validacion:**
- Servicio de transporte terrestre → IGV exonerado = VALIDO
- No marcar como error o alerta
- Clasificacion: **INFORMATIVO** (extraccion correcta, no requiere accion)

---

### RV-004: Declaracion Jurada con Gastos Sin Comprobante

**Identificado en:** Anexo N°4, Pagina 3 del PDF de rendicion
**Expediente:** OPRE2026-INT-0131766
**Fecha:** 2026-02-13

**Descripcion:** La Declaracion Jurada puede contener gastos reales sin
comprobante de pago. NO es siempre vacia.

**Accion requerida:**
- SIEMPRE verificar si existe Anexo N°4 en el expediente
- Extraer TODOS los gastos declarados: fecha, concepto, tipo, importe
- Sumar total y verificar que coincida con el total declarado
- Incluir total en el Anexo 3 como "Gastos sin documentacion sustentatoria"
- Clasificacion: **CRITICO** (si se omite, la rendicion queda incompleta)

**Error previo:** En la primera generacion del Excel, la DJ se genero vacia
cuando en realidad tenia 9 gastos por S/187.00. Esto es un error grave
de completitud.

---

## 3. Registro de Hallazgos por Expediente

| Expediente | Regla | Comprobante | Resultado |
|------------|-------|-------------|-----------|
| OPRE2026-INT-0131766 | RV-001 | E001-29 (PEMO) | Parcialmente cortado, devolver para re-escaneo |
| OPRE2026-INT-0131766 | RV-002 | F001-00009765 (Eduardo El Brujo) | 2 platos principales para 1 persona, observacion |
| OPRE2026-INT-0131766 | RV-003 | E001-1450 (Taxi ida) | Exonerado correcto |
| OPRE2026-INT-0131766 | RV-003 | F012-00018700 (Taxi retorno) | Exonerado correcto |
| OPRE2026-INT-0131766 | RV-004 | Anexo N°4 (DJ) | 9 gastos sin CP, S/187.00 |

---

## 4. Proceso de Actualizacion

1. Hans revisa el Excel generado contra los documentos originales
2. Identifica discrepancias, errores, o situaciones que requieren regla
3. Claude Code crea la regla con codigo RV-XXX
4. Se registra el hallazgo en la tabla de la seccion 3
5. Se actualiza el script de generacion para incorporar la logica

---

## 5. Vigencia

Este archivo entra en vigor el 2026-02-13 y se actualiza incrementalmente
con cada expediente procesado. Las reglas son acumulativas.
