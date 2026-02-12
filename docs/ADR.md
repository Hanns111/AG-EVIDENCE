# REGISTRO DE DECISIONES DE ARQUITECTURA – AG-EVIDENCE (ADR)

## Propósito

Este documento registra decisiones arquitectónicas relevantes
para que el proyecto mantenga coherencia técnica en el tiempo.

Toda decisión aquí registrada se considera vigente
hasta que otra ADR la reemplace explícitamente.

---

## ADR-001 – Enfoque Local-First y Costo Cero

**Estado:** Aceptada  
**Fecha:** 2026-01-14

### Contexto
El proyecto se usa con datos sensibles y debe ser portable a la UE.
Las APIs cloud pagadas introducen riesgos de privacidad y dependencia.

### Decisión
Todo el sistema opera:
- De forma local
- Sin APIs externas pagadas
- Sin envío de datos a terceros

### Consecuencias
- Mayor control
- Mayor complejidad inicial
- Cumplimiento GDPR por diseño

---

## ADR-002 – Uso de vLLM como Servidor de Inferencia

**Estado:** Aceptada  
**Fecha:** 2026-01-14

### Contexto
Ollama es adecuado para prototipos, pero limitado para producción avanzada.

### Decisión
Se adopta vLLM como servidor principal de inferencia local.

### Consecuencias
- Mejor uso de VRAM
- Mayor throughput
- Configuración más técnica

---

## ADR-003 – Modelos Seleccionados por VRAM

**Estado:** Aceptada  
**Fecha:** 2026-01-14

### Decisión
- Texto: Qwen2.5-32B Instruct cuantizado
- Visión: Qwen2.5-VL-7B Instruct

### Motivo
Equilibrio entre capacidad cognitiva y límites físicos de la RTX 5090.

---

## ADR-004 – Orquestación mediante LangGraph

**Estado:** Aceptada  
**Fecha:** 2026-01-14

### Decisión
Se adopta LangGraph para modelar flujos con ciclos y validaciones.

### Motivo
Los procesos de auditoría requieren reintentos y validación cruzada.

---

## ADR-005 – Separación Dominio / Orquestación / Herramientas

**Estado:** Aceptada  
**Fecha:** 2026-01-14

### Decisión
Arquitectura en capas estrictamente desacopladas.

### Consecuencia
Alta portabilidad del sistema a otros países o instituciones.

---

## ADR-006 — PaddleOCR PP-OCRv5 como Motor OCR Primario

**Estado:** Aceptada
**Fecha:** 2026-02-11

### Contexto
Tesseract OCR era el motor OCR inicial. Pruebas con documentos administrativos
peruanos (expedientes con sellos, tablas y firmas) mostraron que PaddleOCR PP-OCRv5
logra mayor precision para texto espanol mixto. PP-OCRv5 reporta +13% accuracy
sobre PP-OCRv4 y soporta 106 idiomas.

### Decision
PaddleOCR PP-OCRv5 (modelos server: PP-OCRv5_server_det + PP-OCRv5_server_rec)
es el motor OCR primario, con GPU acelerado via RTX 5090 (CUDA).
Tesseract se mantiene como fallback automatico si PaddleOCR no esta disponible
o falla en runtime. La interfaz publica de `src/ocr/core.py` no cambia
(solo se agrega campo `motor_ocr` al resultado, cambio aditivo).

### Consecuencias
- Mayor precision OCR para documentos administrativos en espanol
- Uso de GPU (CUDA) para inferencia acelerada
- Dependencia adicional: `paddlepaddle-gpu` + `paddleocr` (~2GB disco)
- Tesseract sigue siendo necesario como fallback
- Patron singleton para instancias PaddleOCR (carga pesada de modelos)

---

## Regla de Actualización

Si una decisión:
- Cambia stack
- Cambia modelo
- Cambia flujo crítico

Debe agregarse una nueva ADR.
Nunca se edita una ADR antigua: se crea otra.
