# Roadmap: Ampliación AG-EVIDENCE a Expedientes OS/OC

> **Estado:** FUTURO — No implementar hasta que viáticos esté completo (Fases 3-6).
> **Fuente:** Proyecto experimental `control-previo-ai` (NotebookLM).

---

## Qué se amplía

AG-EVIDENCE actualmente procesa **viáticos** (rendiciones de gastos de comisión).
La ampliación cubriría **expedientes de pago a proveedores** según Pautas MINEDU 2020:

- 5.1.1 Licitación Pública
- 5.1.2 Concurso Público
- 5.1.3 Adjudicación Simplificada
- 5.1.4 Consultores Individuales
- 5.1.5 Subasta Inversa Electrónica
- 5.1.6 Comparación de Precios
- 5.1.7 Contratación Directa
- 5.1.8 Compras Corporativas
- 5.1.9 Menores a 8 UIT
- 5.1.10 Catálogos Electrónicos (Acuerdo Marco)
- 5.1.11 Otros (Servicios Básicos, Adelantos, Procuraduría)

## Qué se reutiliza de AG-EVIDENCE

| Componente actual | Uso en ampliación |
|---|---|
| `custody_chain.py` | Mismo — trazabilidad SHA-256 |
| `ocr/core.py` (PaddleOCR) | Mismo — extracción texto de PDFs |
| `trace_logger.py` | Mismo — auditoría JSONL |
| `confidence_router.py` | Extender — nuevos tipos de evaluación |
| `expediente_contract.py` | Extender — nuevos grupos de datos para OS/OC |
| `excel_writer.py` | Extender — nuevas hojas diagnóstico |
| `abstencion.py` | Mismo — política de abstención |

## Qué se necesita nuevo

1. **Checklists por tipo de contratación** — 11 listas de documentos obligatorios (ya documentadas en REFERENCIA_CHECKLISTS_CONSOLIDADO.md del experimento)
2. **Validador de presencia documental** — verificar que cada documento del checklist existe en el expediente
3. **Verificador de firmas** — matriz de qué documentos requieren firma digital/manuscrita
4. **Conciliación cruzada** — 9 cruces obligatorios (Proveído↔OS, Proveído↔Conformidad, RUC consistente, etc.)
5. **Clasificador de tipo de contratación** — determinar automáticamente si es 5.1.1, 5.1.9, etc.
6. **Protocolo anti-observación-falsa** — verificación triple antes de declarar documento faltante

## Archivos fuente del experimento

Ubicación: `C:\Users\Hans\Downloads\PAUTAS OS OC\control-previo-ai\`

| Archivo | Contenido | Prioridad para absorción |
|---|---|---|
| `REFERENCIA_CHECKLISTS_CONSOLIDADO.md` | 11 checklists completos | ALTA — convertir a JSON |
| `REFERENCIA_REGLAS_CONSOLIDADO.md` | Reglas firmas, cruces, tributarias | ALTA — convertir a JSON |
| `skill_cross_reference_validation.md` | 9 cruces obligatorios detallados | ALTA |
| `skill_document_validation.md` | Verificación presencia + firmas | MEDIA |
| `skill_final_audit.md` | Protocolo anti-falso-positivo | MEDIA |
| `skill_procurement_classification.md` | Clasificador de tipo | MEDIA |
| `skill_deep_pdf_scanner.md` | Scanner dual-capa | BAJA (ya tenemos mejor) |
| `skill_evidence_extraction.md` | Extracción de campos | BAJA (ya tenemos mejor) |
| `preprocess_expediente.py` | Preprocesador PyMuPDF | BAJA (ya tenemos mejor) |

## Prerrequisitos

- Fase 3 viáticos completada (parseo profundo comprobantes)
- Fase 4 viáticos completada (validaciones)
- Al menos 1 expediente OS/OC real procesado end-to-end como prueba
