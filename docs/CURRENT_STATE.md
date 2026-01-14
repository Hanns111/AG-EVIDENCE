# ESTADO ACTUAL DEL PROYECTO – AG-EVIDENCE

## Fecha de Corte
2026-01-14

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

---

## 4. Lo que NO se ha hecho aún

- Configurar entorno WSL2 limpio y definitivo
- Desplegar vLLM con modelos aprobados
- Reimplementar OCR/visión con Qwen2.5-VL
- Integrar LangGraph con agentes reales
- Crear golden tests

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
