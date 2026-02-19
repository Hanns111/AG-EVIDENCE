# Expedientes por Convenio Interinstitucional

> **Versión:** 1.0.0
> **Fecha:** 2026-02-19
> **Autor:** Hans (definición normativa), Claude Code (formalización)
> **Estado:** VIGENTE
> **Identificador:** GOV_RULE_CONVENIOS_INTERINSTITUCIONALES_v1
> **Clasificación:** OTROS_EXPEDIENTES — Pautas 5.1.11

---

## I. Finalidad

Documentar el tratamiento diferenciado que debe aplicar AG-EVIDENCE cuando
evalúe expedientes de pago derivados de **Convenios Interinstitucionales**
entre entidades públicas que generen obligación económica, a fin de evitar
observaciones indebidas bajo criterios propios de contratación pública
ordinaria.

---

## II. Clasificación Normativa

```
CATEGORIA_PRINCIPAL  = OTROS_EXPEDIENTES
SUBCATEGORIA         = CONVENIO_INTERINSTITUCIONAL
BASE_REFERENCIAL     = Pautas 5.1.11
```

Se considerará dentro de esta categoría cuando:

- La contraparte sea una **entidad del Estado**.
- Exista **convenio suscrito vigente**.
- **No** exista procedimiento de selección bajo Ley 30225.
- La obligación económica derive del propio convenio.

---

## III. Naturaleza Jurídica

Relación **Estado–Estado** basada en instrumento de cooperación o
prestación institucional.

**Características:**

- No aplica Ley de Contrataciones del Estado.
- No requiere SEACE.
- No requiere Orden de Servicio SIGA.
- No requiere Factura SUNAT.
- No requiere detracción ni retención.

La obligación nace del convenio y del documento de cobranza institucional.

---

## IV. Documentos Mínimos Exigibles

El sistema deberá verificar la existencia de:

1. **Convenio interinstitucional vigente.**
2. **Documento formal de cobranza** (liquidación, recibo institucional,
   carta de cobranza).
3. **Detalle de consumo o liquidación** del periodo.
4. **Informe técnico del área usuaria** que valide el consumo y monto.
5. **Certificación de Crédito Presupuestario.**
6. **Derivación formal** por sistema institucional (E-SINAD).

Si estos documentos existen y son coherentes:

```
APTO_PARA_DEVENGADO = TRUE
```

---

## V. Conformidad en Convenios

En esta modalidad:

- **No es obligatorio** que exista un documento titulado "CONFORMIDAD".
- La conformidad puede estar contenida en:
  - Informe técnico que valida el consumo.
  - Memorándum que solicita el pago.
  - Documento interno que expresa aceptación del monto.

**Regla:**

```
IF informe_tecnico_valida_monto == TRUE
   AND memo_solicita_pago == TRUE
THEN
   conformidad_funcional = TRUE
```

No debe generarse observación por ausencia de documento formal de
conformidad separado.

---

## VI. Validación de Coherencia Económica (OBLIGATORIA)

El sistema deberá verificar:

```
Monto_Cobranza = Monto_Validado_Informe_Tecnico = Monto_Recibo <= Monto_Certificacion
```

Y que:

```
Periodo_Cobranza == Periodo_Informe
```

Si hay inconsistencia → **Generar Alerta Crítica.**

---

## VII. Flujo Válido

Para convenios interinstitucionales se considera válido el flujo:

```
AREA_USUARIA → OCCP → TESORERIA
```

**No es obligatorio:**

- Proveído de Logística.
- Intervención previa de OEC.
- Registro en SEACE.

El sistema **no debe marcar como observación** la ausencia de proveído
cuando se trate de esta categoría.

---

## VIII. Condiciones de Observación

El sistema debe observar **únicamente** si:

- No existe convenio vigente.
- No existe documento de cobranza formal.
- No existe validación técnica.
- No existe certificación presupuestal.
- Hay inconsistencia de montos.
- Hay periodo no coincidente.
- Se detecta doble cobro del mismo periodo.

---

## IX. Lógica de Clasificación Automática

```
IF entidad_contraparte == "Entidad Pública"
   AND existe_convenio == TRUE
   AND existe_documento_cobranza == TRUE
   AND existe_certificacion == TRUE
THEN
   clasificar = CONVENIO_INTERINSTITUCIONAL
   omitir_validaciones_contratacion_estandar()
   aplicar_validacion_coherencia_economica()
END IF
```

---

## X. Objetivo de Control

**Garantizar:**

- Legalidad del devengado.
- Coherencia documental.
- Sustento presupuestal.
- Trazabilidad del convenio.

**Evitar:**

- Observaciones indebidas por falta de factura.
- Falsos positivos por ausencia de proveído.
- Clasificación errónea como contratación directa.

---

## XI. Integración en AG-EVIDENCE

### Identificador en el sistema

```
GOV_RULE_CONVENIOS_INTERINSTITUCIONALES_v1
```

Se ejecuta **antes** del módulo de validación contractual estándar.

### Impacto en el contrato de datos (Tarea #17)

`ExpedienteJSON` incluye el campo opcional `documentos_convenio` de tipo
`DocumentosConvenio` que contiene:

```
DocumentosConvenio
├── convenio_vigente: CampoExtraido          # Referencia al convenio
├── documento_cobranza: CampoExtraido        # Liquidación/recibo/carta
├── detalle_consumo: CampoExtraido           # Detalle del periodo
├── informe_tecnico: CampoExtraido           # Informe del área usuaria
├── certificacion_presupuestal: CampoExtraido # CCP
├── derivacion_sinad: CampoExtraido          # E-SINAD
├── conformidad_funcional: bool              # Calculado por reglas V
├── coherencia_economica: bool               # Calculado por reglas VI
├── entidad_contraparte: CampoExtraido       # Nombre de la entidad Estado
├── periodo_convenio: CampoExtraido          # Periodo cubierto
```

### Impacto en NaturalezaExpediente (config/settings.py)

Agregar a la enumeración `NaturalezaExpediente`:

```python
CONVENIO_INTERINSTITUCIONAL = "CONVENIO INTERINSTITUCIONAL"
```

### Ejemplo de caso: RENIEC

Cuando AG-EVIDENCE procese un expediente donde la contraparte sea RENIEC
(u otra entidad pública):

- Reconocerá automáticamente la categoría CONVENIO_INTERINSTITUCIONAL.
- **No marcará** como incompleto por falta de proveído.
- **Exigirá** coherencia económica (montos consistentes).
- **Aceptará** conformidad funcional (informe + memo = OK).
- **Permitirá** devengado cuando los 6 documentos mínimos existan.

---

## XII. Historial de Versiones

| Versión | Fecha | Cambio |
|---------|-------|--------|
| 1.0.0 | 2026-02-19 | Documento inicial — reglas de convenio formalizadas |

---

*Documento normativo aprobado por Hans (Owner).*
*Forma parte del sistema de gobernanza de AG-EVIDENCE.*
