# PARSING DE COMPROBANTES DE PAGO — Especificación Obligatoria

> **Versión:** 1.0
> **Fecha:** 2026-02-17
> **Autor:** Hans (Owner), validado por confrontación multi-IA (Codex, Gemini, Claude)
> **Estado:** VIGENTE — Documento rector para toda extracción de comprobantes

---

## Regla de Oro: Literalidad Forense

> **"La IA extrae LITERALMENTE lo que ve. Python valida aritméticamente."**

- ZERO INFERENCE: El modelo NO calcula, NO autocompleta, NO deduce
- Si un campo no es visible en el documento → `null`
- Si un valor es parcialmente legible → extraer lo visible + `"confianza": "baja"`
- Python es quien valida sumas, IGV, consistencia aritmética (Grupo J)

---

## Grupos de Campos Obligatorios

### Grupo A — Datos del Emisor
| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `ruc_emisor` | string | Sí | RUC del emisor/proveedor (11 dígitos) |
| `razon_social` | string | Sí | Razón social o nombre comercial |
| `nombre_comercial` | string | No | Nombre comercial si difiere de razón social |
| `direccion_emisor` | string | No | Dirección fiscal del emisor |
| `ubigeo_emisor` | string | No | Distrito - Provincia - Departamento |

### Grupo B — Datos del Comprobante
| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `tipo_comprobante` | string | Sí | FACTURA, BOLETA, NOTA_CREDITO, NOTA_DEBITO, RECIBO_HONORARIOS |
| `serie` | string | Sí | Serie del comprobante (ej: E001, F011, EB01) |
| `numero` | string | Sí | Número correlativo |
| `fecha_emision` | string | Sí | Fecha de emisión (DD/MM/YYYY) |
| `fecha_vencimiento` | string | No | Fecha de vencimiento si existe |
| `moneda` | string | Sí | PEN, USD, EUR |
| `forma_pago` | string | No | CONTADO, CREDITO |
| `es_electronico` | boolean | Sí | true si es comprobante electrónico |

### Grupo C — Datos del Adquirente
| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `ruc_adquirente` | string | Sí | RUC del comprador/cliente |
| `razon_social_adquirente` | string | Sí | Nombre del comprador |
| `direccion_adquirente` | string | No | Dirección del comprador |

### Grupo D — Condiciones Comerciales
| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `condicion_pago` | string | No | Condiciones de pago especiales |
| `guia_remision` | string | No | Número de guía de remisión si existe |
| `orden_compra` | string | No | Número de orden de compra |
| `observaciones` | string | No | Observaciones o notas del comprobante |

### Grupo E — Detalle de Ítems
| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `items` | array | Sí | Lista de ítems/servicios |
| `items[].cantidad` | number | Sí | Cantidad |
| `items[].unidad` | string | No | Unidad de medida (UND, NIU, ZZ, etc.) |
| `items[].descripcion` | string | Sí | Descripción del ítem/servicio |
| `items[].valor_unitario` | number | Sí | Valor unitario sin IGV |
| `items[].importe` | number | Sí | Importe de línea (cantidad × valor_unitario) |

### Grupo F — Totales y Tributos
| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `subtotal` | number | Sí | Valor de venta (base imponible, sin IGV) |
| `igv_tasa` | number | No | Tasa de IGV aplicada (18, 10, 0) |
| `igv_monto` | number | Sí | Monto del IGV |
| `total_gravado` | number | No | Total gravado (operaciones gravadas) |
| `total_exonerado` | number | No | Total exonerado |
| `total_inafecto` | number | No | Total inafecto |
| `total_gratuito` | number | No | Total gratuito |
| `otros_cargos` | number | No | Otros cargos (propinas, recargos) |
| `descuentos` | number | No | Descuentos globales |
| `importe_total` | number | Sí | Importe total a pagar |
| `monto_letras` | string | No | Monto en letras si existe |

### Grupo G — Clasificación del Gasto
| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `categoria_gasto` | string | Sí | ALIMENTACION, HOSPEDAJE, TRANSPORTE, MOVILIDAD_LOCAL, OTROS |
| `subcategoria` | string | No | Detalle adicional de la categoría |

### Grupo H — Datos Específicos de Hospedaje
| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `fecha_checkin` | string | Condicional | Fecha de check-in (si hospedaje) |
| `fecha_checkout` | string | Condicional | Fecha de check-out (si hospedaje) |
| `numero_noches` | number | Condicional | Cantidad de noches |
| `numero_habitacion` | string | No | Número de habitación |
| `nombre_huesped` | string | No | Nombre del huésped registrado |
| `numero_reserva` | string | No | Número de reserva |

### Grupo I — Datos Específicos de Movilidad
| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `origen` | string | Condicional | Punto de origen (si transporte) |
| `destino` | string | Condicional | Punto de destino |
| `fecha_servicio` | string | No | Fecha del servicio de transporte |
| `placa_vehiculo` | string | No | Placa del vehículo |
| `nombre_pasajero` | string | No | Nombre del pasajero |

### Grupo J — Validaciones Aritméticas (EJECUTA PYTHON, NO LA IA)
| Validación | Fórmula | Tolerancia |
|-----------|---------|------------|
| Suma de ítems | Σ(cantidad × valor_unitario) = subtotal | ±0.02 |
| IGV | subtotal × tasa_igv = igv_monto | ±0.02 |
| Total | subtotal + igv_monto + otros_cargos - descuentos = importe_total | ±0.02 |
| Noches (hospedaje) | (checkout - checkin).days = numero_noches | Exacto |

### Grupo K — Metadatos de Extracción
| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `pagina_origen` | number | Sí | Número de página en el PDF |
| `metodo_extraccion` | string | Sí | pymupdf, paddleocr_gpu, qwen_vl |
| `confianza_global` | string | Sí | alta, media, baja |
| `campos_no_encontrados` | array | Sí | Lista de campos obligatorios no encontrados |
| `timestamp_extraccion` | string | Sí | ISO 8601 |

---

## Notas de Implementación

1. **Orden de prioridad de motores:**
   - PyMuPDF (texto embebido) → rápido, gratis, preciso para PDFs digitales
   - Qwen2.5-VL-7B (Ollama) → para páginas escaneadas/imagen
   - PaddleOCR GPU → fallback intermedio

2. **Formato de salida:** JSON tipado conforme a este esquema

3. **Validación:** Python ejecuta Grupo J post-extracción, NUNCA la IA

---

*Documento rector aprobado por el Owner del proyecto.*
