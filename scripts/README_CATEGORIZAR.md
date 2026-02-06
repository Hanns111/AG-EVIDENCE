# Script de Categorización de Expedientes

## Uso

### Categorizar expedientes de una carpeta (COPIA)

```bash
python scripts/categorizar_expedientes.py "C:\ruta\a\expedientes" --destino "data/expedientes/pruebas"
```

### Categorizar y MOVER expedientes

```bash
python scripts/categorizar_expedientes.py "C:\ruta\a\expedientes" --destino "data/expedientes/pruebas" --mover
```

## Tipos de Expediente Soportados

- **VIATICOS**: Viáticos y comisiones de servicio
- **CAJA_CHICA**: Caja chica y fondos fijos
- **ENCARGO**: Encargos internos
- **ORDEN_SERVICIO**: Órdenes de servicio
- **ORDEN_COMPRA**: Órdenes de compra
- **CONTRATO**: Contratos
- **SUBVENCIONES**: Subvenciones, transferencias, donaciones
- **PAGO_PROVEEDOR**: Pagos a proveedores (genérico)
- **OTROS**: Otros tipos no clasificados

## Estructura de Salida

```
data/expedientes/pruebas/
├── viaticos/
├── caja_chica/
├── encargo/
├── ordenes_servicio/
├── ordenes_compra/
├── contratos/
├── subvenciones/
├── pago_proveedor/
└── otros/
```

## Ejemplo

```bash
# Categorizar expedientes de CONTROL_PREVIO_2026_EN_LOCAL (copiar)
python scripts/categorizar_expedientes.py "CONTROL_PREVIO_2026_EN_LOCAL" --destino "data/expedientes/pruebas"

# Categorizar y mover (elimina del origen)
python scripts/categorizar_expedientes.py "CONTROL_PREVIO_2026_EN_LOCAL" --destino "data/expedientes/pruebas" --mover
```
