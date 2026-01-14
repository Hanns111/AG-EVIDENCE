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

## Regla de Actualización

Si una decisión:
- Cambia stack
- Cambia modelo
- Cambia flujo crítico

Debe agregarse una nueva ADR.
Nunca se edita una ADR antigua: se crea otra.
