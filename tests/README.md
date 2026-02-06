# Tests — AG-EVIDENCE

## Estructura de Tests

Este directorio contiene los tests del sistema AG-EVIDENCE.

### Tests Unitarios

- `test_agente_directivas.py` - Tests del agente de directivas
- `test_chat_asistente.py` - Tests del chat asistente
- `test_detraccion_spot.py` - Tests de detracciones SPOT
- `test_enrutamiento_os_oc.py` - Tests de enrutamiento OS/OC
- `test_estandar_probatorio.py` - Tests del estándar probatorio
- `test_modo_conversacional.py` - Tests del modo conversacional
- `test_pdf_text_extractor.py` - Tests de extracción de PDF
- `test_tdr_requirements.py` - Tests de requisitos TDR

### Tests Rápidos

- `run_quick_test.py` - Tests rápidos de los 4 FIX aplicados

## Ejecutar Tests

### Todos los tests

```bash
python -m pytest tests/ -v
```

### Test específico

```bash
python -m pytest tests/test_agente_directivas.py -v
```

### Tests rápidos

```bash
python tests/run_quick_test.py
```

## Configuración

Ver `pytest.ini` para configuración de pytest y markers personalizados.

## Notas

- Los tests que requieren EasyOCR/torch se skipean automáticamente si no están instaladas las dependencias
- Los tests de PDF requieren archivos de prueba en `data/expedientes/pruebas/`
