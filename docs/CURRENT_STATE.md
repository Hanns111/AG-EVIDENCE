# ESTADO ACTUAL DEL PROYECTO – AG-EVIDENCE

## Fecha de Corte
2026-02-07

---

## 1. Estado General

🟡 EN REESTRUCTURACIÓN CONTROLADA

El proyecto AG-EVIDENCE se encuentra en transición desde un
prototipo inicial (Windows + Ollama) hacia una arquitectura
profesional basada en:

- WSL2 (Ubuntu 22.04)
- vLLM
- Modelos cuantizados compatibles con RTX 5090 (sm_120)

No se ha descartado la lógica previa del proyecto.
Se está **profesionalizando**, no reiniciando.

---

## 2. Lo que YA existe

- Concepto AG-EVIDENCE definido
- Enfoque probatorio y de control previo (MINEDU)
- Experiencia previa con OCR, gating y validaciones
- Directivas y lógica normativa identificadas
- Decisión de arquitectura local-first confirmada

---

## 3. Cambios Recientes

- Decisión de migrar ejecución a Linux vía WSL2
- Abandono de Ollama como servidor principal
- Aprobación de vLLM como motor de inferencia
- Definición formal de documentos de gobernanza
- **Integración de nueva Directiva DI-003-01-MINEDU v03 (023-2026-MINEDU)**
  - Vigente desde 06.02.2026
  - Sistema ahora determina versión de directiva según fecha de inicio de trámite
  - Expedientes con fecha >= 06.02.2026 aplican nueva directiva v03
  - Expedientes con fecha < 06.02.2026 aplican directiva 011-2020 (versión anterior)
- **Decisión técnica sobre MCPs:**
  - Se descartó definitivamente `readpdfx`
  - El proyecto usa **UN solo MCP**: `pdf-handler`
- **Arquitectura OCR WSL2-Only:**
  - El OCR se ejecuta exclusivamente en WSL2 (Ubuntu)
  - Windows actúa solo como host/editor y orquestador
  - Dependencias OCR instaladas en WSL2:
    - `ocrmypdf` v13.4.0+dfsg
    - `tesseract-ocr` con idioma `spa`
    - `ghostscript`
  - Los chequeos o warnings de OCR en Windows son irrelevantes y no forman parte del runtime soportado

---

## 4. Lo que NO se ha hecho aún

- Configurar entorno WSL2 limpio y definitivo
- Desplegar vLLM con modelos aprobados
- Reimplementar OCR/visión con Qwen2.5-VL
- Integrar LangGraph con agentes reales
- Crear golden tests
- **Próximo paso técnico OCR:**
  - Implementar el adaptador `src/tools/ocr_preprocessor.py` para integrar OCRmyPDF al pipeline existente

---

## 5. Riesgos Actuales

- Confusión entre arquitectura antigua y nueva
- Tentación de "empezar de cero" innecesariamente
- Saturación de contexto si no se usa este archivo

---

## 6. Próximos Pasos Inmediatos

1. Crear carpeta docs/ con los archivos de gobernanza
2. Confirmar entorno WSL2 + GPU funcional
3. Inicializar repositorio limpio manteniendo dominio
4. Implementar primer agente mínimo funcional
5. Actualizar este archivo al finalizar cada sesión

---

## 7. Regla de Cierre de Sesión

Antes de cerrar cualquier sesión con una IA:

- Generar versión actualizada de este archivo
- Guardar en local
- Commit:
  - docs(state): update project state YYYY-MM-DD
