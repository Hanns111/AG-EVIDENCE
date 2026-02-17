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

**Estado:** Superseded por ADR-007
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

## ADR-007 — PaddleOCR 2.9.1 CPU reemplaza PP-OCRv5 GPU (RTX 5090 incompatible)

**Estado:** Superseded por ADR-008
**Fecha:** 2026-02-17
**Supersede:** ADR-006

### Contexto
ADR-006 establecio PaddleOCR PP-OCRv5 con GPU (RTX 5090) como motor primario.
Al implementarlo se descubrio que:

1. **RTX 5090 (sm_120 Blackwell)** no es compatible con PaddlePaddle 3.3.0 CUDA 12.6.
   Los kernels CUDA no incluyen sm_120, produciendo `CUDA error 209: no kernel image
   is available for execution on the device`. PaddleOCR inicializa pero retorna
   resultados vacios (rec_texts: [], rec_scores: []).

2. **PaddleOCR 3.x (PP-OCRv5)** tampoco funciona en CPU: falla con
   `NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support`.

3. **PaddleOCR 2.9.1** con PaddlePaddle 3.0.0 (CPU) funciona correctamente
   usando modelos PP-OCRv3 y la API 2.x (`ocr.ocr(img, cls=True)`).

### Prueba empirica (Caja Chica N.3, 112 paginas, 16 comprobantes)

| Metrica | Tesseract | PaddleOCR 2.9.1 | Mejora |
|---------|-----------|-----------------|--------|
| Precision total | 20.3% | 36.2% | +78% |
| Match exacto | 14 | 25 | +79% |
| No extraido | 31 | 17 | -45% |
| Serie/Numero | 5/16 | 10/16 | +100% |
| Total (monto) | 5/16 | 8/16 | +60% |
| IGV | 1/9 | 7/9 | +600% |
| Fecha | 2/16 | 6/16 | +200% |
| RUC | 1/12 | 1/12 | sin cambio |

### Decision
PaddleOCR 2.9.1 (CPU, modelos PP-OCRv3) es el motor OCR primario.
API: `PaddleOCR(use_angle_cls=True, lang=..., show_log=False)` con
`ocr.ocr(img_numpy, cls=True)`.

Tesseract se mantiene como fallback automatico.

GPU queda pendiente hasta que PaddlePaddle publique kernels compatibles
con sm_120 (Blackwell) o hasta que NVIDIA CUDA Toolkit 13.x lo soporte.

### Consecuencias
- +78% precision vs Tesseract solo, sin GPU
- Dependencias: `paddlepaddle==3.0.0` (CPU) + `paddleocr==2.9.1` (~1.5GB disco)
- Sin aceleracion GPU (CPU only) — ~2-5s por pagina vs ~0.3s estimado con GPU
- Modelos PP-OCRv3 (no v5) — upgrade pendiente cuando soporte sm_120
- API 2.x: `.ocr(img, cls=True)` retorna `[[[box, (text, score)], ...]]`
- Interfaz publica `ejecutar_ocr()` no cambia (cambio interno transparente)
- RUC sigue siendo el campo mas dificil (1/12) — requiere post-procesamiento
  o validacion SUNAT via DuckDB

---

## ADR-008 — PaddleOCR PP-OCRv5 GPU restaurado (RTX 5090 via CUDA 12.9)

**Estado:** Aceptada
**Fecha:** 2026-02-17
**Supersede:** ADR-007

### Contexto
ADR-007 declaro GPU incompatible porque PaddlePaddle 3.3.0 con CUDA 12.6
no soportaba sm_120 (Blackwell). Se descubrio que:

1. **PaddlePaddle GPU 3.3.0 con CUDA 12.9** (cu129) SI soporta sm_120.
   Instalacion desde indice oficial: `pip install paddlepaddle-gpu==3.3.0
   -i https://www.paddlepaddle.org.cn/packages/stable/cu129/`

2. El problema original era un **conflicto de paquetes**: `paddlepaddle==3.0.0`
   (CPU) y `paddlepaddle-gpu==3.3.0` coexistian, y Python cargaba la version CPU.
   Solucion: desinstalar ambos y reinstalar solo `paddlepaddle-gpu` desde cu129.

3. **PaddleOCR 3.4.0** con API 3.x (`.predict()`) funciona correctamente con
   modelos PP-OCRv5 server en GPU RTX 5090.

4. **Diferencia de API**: PaddleOCR 3.x retorna `OCRResult` con `json["res"]`
   conteniendo `rec_texts`, `rec_scores`, `dt_polys`. Distinto de la API 2.x
   que retornaba `[[[box, (text, score)], ...]]`.

5. **LD_LIBRARY_PATH**: WSL2 requiere `export LD_LIBRARY_PATH=/usr/lib/wsl/lib:$LD_LIBRARY_PATH`
   para acceder a libcuda.so.

### Prueba empirica (Caja Chica N.3, 112 paginas, 16 comprobantes)

| Metrica | Tesseract | PaddleOCR 2.9.1 CPU | PP-OCRv5 GPU | Mejora GPU vs Tess |
|---------|-----------|---------------------|--------------|-------------------|
| Precision total | 20.3% | 36.2% | 42.0% | +107% |
| Match exacto | 14 | 25 | 29 | +107% |
| No extraido | 31 | 17 | 15 | -52% |
| Error | 24 | 27 | 25 | — |

**Por campo (PP-OCRv5 GPU):**

| Campo | Evaluables | Match | Error | NoExtr | Precision |
|-------|-----------|-------|-------|--------|-----------|
| Serie/Numero | 16 | 10 | 2 | 4 | 62.5% |
| IGV | 10 | 7 | 1 | 2 | 70.0% |
| Total (monto) | 16 | 7 | 3 | 6 | 43.8% |
| Fecha | 16 | 5 | 8 | 3 | 31.2% |
| RUC | 11 | 0 | 11 | 0 | 0.0% |

### Decision
PaddleOCR 3.4.0 PP-OCRv5 server (GPU RTX 5090 via CUDA 12.9) es el motor OCR primario.

**Stack:**
- `paddlepaddle-gpu==3.3.0` (cu129, soporta sm_120 Blackwell)
- `paddleocr==3.4.0` + `paddlex==3.4.2`
- Modelos: `PP-OCRv5_server_det` + `PP-OCRv5_server_rec`
- API 3.x: `PaddleOCR(..., device="gpu:0").predict(img)`

Tesseract se mantiene como fallback automatico si PaddleOCR falla.

### Consecuencias
- +107% precision vs Tesseract, +16% vs PaddleOCR 2.9.1 CPU
- GPU acelerado: ~1.5s por pagina (primera pagina ~8s por carga de modelos)
- PP-OCRv5 server = maxima precision disponible en PaddleOCR
- CPU fallback para PP-OCRv5 NO funciona (NotImplementedError) — fallback va a Tesseract
- RUC sigue siendo 0% — requiere validacion SUNAT via DuckDB o Qwen-VL (Fase 3)
- Fechas 31.2% — OCR lee fechas pero confunde entre multiples fechas en documento
- `LD_LIBRARY_PATH` debe incluir `/usr/lib/wsl/lib` en WSL2

---

## Regla de Actualización

Si una decisión:
- Cambia stack
- Cambia modelo
- Cambia flujo crítico

Debe agregarse una nueva ADR.
Nunca se edita una ADR antigua: se crea otra.
