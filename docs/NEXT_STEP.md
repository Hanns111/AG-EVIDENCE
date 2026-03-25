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
