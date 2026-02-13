# Estrategia de Fallback OCR para PDFs Escaneados

> Documentado: 2026-02-13 | Aprobado por: Hans (sesion de validacion visual)

---

## 1. Principio

**Si el ojo humano puede leerlo, la maquina tambien debe poder.**

No se acepta "OCR ilegible" ni "no capturado" como resultado final.
Se debe iterar con TODOS los fallbacks hasta obtener el dato.

---

## 2. Cadena de Fallbacks (Orden Obligatorio)

| Paso | Herramienta | Comando | Cuando Usar |
|------|-------------|---------|-------------|
| **1** | `pdftotext` | `pdftotext "archivo.pdf" "archivo.txt"` | Siempre intentar primero. Es el mas rapido. Funciona con PDFs que tienen texto embebido. |
| **2** | `ocrmypdf --force-ocr` | `ocrmypdf "archivo.pdf" "archivo_ocr.pdf" --force-ocr` + `pdftotext "archivo_ocr.pdf" "archivo.txt"` | Cuando pdftotext produce texto vacio, garbled, o con caracteres ilegibles. Rasteriza TODAS las paginas y aplica Tesseract OCR. |
| **3** | `pdftotext` por pagina | `pdftotext -f $i -l $i "archivo_ocr.pdf" "pagina_$i.txt"` | Despues de ocrmypdf, para extraer pagina por pagina y mapear exactamente que documento esta en cada pagina. |
| **4** | Ollama/Qwen | `ollama run qwen3:32b` | ULTIMO RECURSO. Solo si los pasos 1-3 fallan en extraer datos visibles. Usar la IA para interpretar texto degradado. |

---

## 3. Tecnica Exitosa: ocrmypdf --force-ocr

### Caso real: Expediente OPRE2026-INT-0131766

**Problema:** El PDF de 30 paginas tenia mezcla de texto embebido y paginas escaneadas.
`pdftotext` directo produjo 1640 lineas con:
- Caracteres garbled: `Ã©`, `Ã³`, `â€"`, `Â°`
- Paginas escaneadas completamente ilegibles
- Datos de facturas parcialmente capturados

**Solucion:**
```bash
# Paso 1: Forzar OCR en todas las paginas
ocrmypdf "20260212144251EXPEDIENTE202602RENDICIONPARAREVI.pdf" \
         "expediente_ocr.pdf" \
         --force-ocr

# Paso 2: Extraer texto del PDF con OCR
pdftotext "expediente_ocr.pdf" "expediente_ocr.txt"

# Paso 3: Extraer pagina por pagina para mapeo preciso
for i in $(seq 1 30); do
  pdftotext -f $i -l $i "expediente_ocr.pdf" "pagina_${i}.txt"
done
```

**Resultado:**
- De 1640 lineas → **2147 lineas** (30% mas informacion)
- 12 comprobantes de pago: **100% extraidos correctamente**
- Facturas escaneadas con OCR degradado: **recuperadas al 100%**
- Boarding pass y tiquetes aereos: **legibles completamente**

### Por que funciona

`ocrmypdf --force-ocr` hace tres cosas:
1. **Rasteriza** cada pagina del PDF a imagen
2. **Aplica Tesseract OCR** sobre la imagen rasterizada
3. **Reemplaza** el texto (bueno o malo) con el resultado de OCR

Esto elimina el problema de texto embebido corrupto/codificado mal,
porque no usa el texto original — genera texto nuevo desde la imagen.

---

## 4. Prerequisitos (WSL2)

```bash
# Instalar una vez
sudo apt install poppler-utils  # pdftotext
pip install ocrmypdf             # ocrmypdf
sudo apt install tesseract-ocr   # motor OCR
```

---

## 5. Decision de cuando usar cada paso

```
PDF recibido
  |
  v
[pdftotext directo]
  |
  +-- Texto limpio y completo? --> USAR ESTE RESULTADO
  |
  +-- Texto vacio o garbled? --> [ocrmypdf --force-ocr]
                                    |
                                    v
                                  [pdftotext sobre PDF con OCR]
                                    |
                                    +-- Texto legible? --> USAR ESTE
                                    |
                                    +-- Aun ilegible? --> [Ollama/Qwen]
```

---

## 6. Vigencia

Esta estrategia entra en vigor el 2026-02-13 y aplica a todo procesamiento
de PDFs del proyecto AG-EVIDENCE.

Documentada tras exito en expediente OPRE2026-INT-0131766 donde la tecnica
`ocrmypdf --force-ocr` rescato informacion de 12 comprobantes escaneados
con calidad degradada.
