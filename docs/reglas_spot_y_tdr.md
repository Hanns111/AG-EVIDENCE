# Reglas SPOT y TDR — Documentación Técnica

## Propósito

Este documento explica las reglas implementadas en los módulos:
- `src/rules/detraccion_spot.py` — Validación de detracción SPOT
- `src/rules/tdr_requirements.py` — Extracción de requisitos del TDR

---

## 1. DETRACCIÓN SPOT

### Base Normativa

| Norma | Descripción |
|-------|-------------|
| **Pautas para Remisión de Expedientes (11/07/2020)** | "Cuenta de detracción, cuando corresponda" |
| **RS 183-2004/SUNAT** | Sistema de Pago de Obligaciones Tributarias (SPOT) |
| **Anexo 3 de RS 183** | Lista de servicios sujetos a detracción |

### Por qué se implementa SPOT

La Pauta establece "cuando corresponda" sin definir el criterio. Este módulo implementa la determinación de cuándo corresponde basándose en:

1. **Indicios explícitos en el comprobante:**
   - "Operación sujeta al SPOT"
   - "Sujeto a detracción"
   - "Cuenta de detracciones"
   - "Constancia de depósito de detracción"

2. **Matching con Anexo 3:**
   - Si el tipo de servicio coincide con algún servicio listado en el Anexo 3
   - Archivo local: `data/normativa/spot_anexo3.json`

3. **Umbral de monto:**
   - S/ 700.00 (monto mínimo para SPOT)
   - Solo informativo, no determinante

### Alcance MVP

| Funcionalidad | Estado |
|---------------|--------|
| Determinar SI/NO aplica SPOT | ✅ Implementado |
| Verificar constancia de depósito | ✅ Implementado |
| Verificar cuenta BN de detracciones | ✅ Implementado |
| Calcular porcentaje de detracción | ❌ No implementado |
| Calcular monto a detraer | ❌ No implementado |

### Uso

```python
from src.rules.detraccion_spot import SPOTValidator, DocumentoAnalizado

# Crear documentos analizados
doc = DocumentoAnalizado(
    nombre="factura_001.pdf",
    texto="Operación sujeta al SPOT\nMonto: S/ 5,000.00",
    paginas=[(1, "...")]
)

# Validar
validator = SPOTValidator()
resultado = validator.spot_aplica([doc], monto_operacion=5000.0)

print(f"Aplica SPOT: {resultado.aplica}")
print(f"Motivo: {resultado.motivo}")
print(f"Observaciones: {len(resultado.observaciones)}")
```

### Observaciones Generadas

| Condición | Nivel | Descripción |
|-----------|-------|-------------|
| SPOT aplica + falta constancia depósito | MAYOR | "No se detectó constancia de depósito de detracción" |
| SPOT aplica + falta cuenta BN | MAYOR | "No se detectó cuenta de detracciones del Banco de la Nación" |

---

## 2. REQUISITOS DEL TDR

### Principio Fundamental

> **CV/Perfil/Experiencia NO es requisito universal de la Pauta.**
> Solo se exige si el TDR lo solicita explícitamente.

### Base Normativa

| Norma | Texto Literal |
|-------|---------------|
| Pautas (Anexo 1, fila 21) | "Documentos requeridos en los Términos de Referencia, Especificaciones Técnicas o Expediente Técnico" |

### Comportamiento

1. **Si el TDR menciona CV/experiencia/título:**
   - El módulo extrae el requisito
   - Lo marca como obligatorio o deseable según el contexto
   - Genera observación si el documento falta en el expediente

2. **Si el TDR NO menciona CV/experiencia:**
   - NO se detecta ningún requisito
   - NO se genera observación por CV faltante
   - El sistema NO asume que debe existir

### Tipos de Requisitos Detectados

| Tipo | Keywords |
|------|----------|
| CV | currículum, CV, hoja de vida |
| EXPERIENCIA | experiencia, años de experiencia, acreditar experiencia |
| TITULO | título profesional, bachiller, licenciado, ingeniero |
| COLEGIATURA | colegiatura, habilitación, colegiado |
| CAPACITACION | capacitación, certificación, diplomado |
| REGISTRO_RNP | RNP, registro nacional de proveedores |

### Uso

```python
from src.rules.tdr_requirements import (
    TDRRequirementExtractor,
    validar_requisitos_tdr,
    tdr_requiere_cv
)

# Verificación rápida
texto_tdr = "El consultor deberá presentar CV documentado"
print(f"¿Requiere CV? {tdr_requiere_cv(texto_tdr)}")  # True

# Extracción completa
extractor = TDRRequirementExtractor()
resultado = extractor.extraer_requisitos(texto_tdr, "TDR.pdf")

for req in resultado.requisitos:
    print(f"- {req.tipo}: {req.descripcion} (obligatorio: {req.obligatorio})")

# Validación contra documentos presentes
docs_presentes = {"FACTURA", "CONFORMIDAD"}  # Sin CV
observaciones = validar_requisitos_tdr(resultado.requisitos, docs_presentes)

for obs in observaciones:
    print(f"[{obs.nivel.value}] {obs.descripcion}")
```

### Ejemplo: TDR sin requisitos de perfil

```python
texto_limpieza = """
SERVICIO DE LIMPIEZA
I. OBJETO: Limpieza de oficinas
II. PLAZO: 30 días
III. PAGO: Mensual contra conformidad
"""

resultado = extractor.extraer_requisitos(texto_limpieza)
print(f"Requisitos: {len(resultado.requisitos)}")  # 0

# NO genera observaciones por CV/experiencia faltante
observaciones = validar_requisitos_tdr(resultado.requisitos, {"FACTURA"})
print(f"Observaciones: {len(observaciones)}")  # 0
```

---

## 3. Integración con AG-EVIDENCE

### Cuándo ejecutar estas reglas

| Regla | Cuándo |
|-------|--------|
| **SPOT** | Siempre (en todo expediente de pago a proveedor) |
| **TDR** | Solo en primera armada + si existe documento TDR |

### Flujo recomendado

```
1. Orquestador carga documentos
2. Agente Clasificador (AG01) determina naturaleza
3. Si es PAGO_PROVEEDOR o similar:
   a. Ejecutar SPOTValidator sobre todos los documentos
   b. Si es_primera_armada AND existe TDR:
      - Ejecutar TDRRequirementExtractor sobre TDR
      - Validar requisitos contra documentos del expediente
4. Consolidar observaciones en AG09 (Decisor)
```

### Archivo de datos SPOT

Ubicación: `data/normativa/spot_anexo3.json`

```json
{
  "servicios": [
    {
      "codigo": "020",
      "descripcion": "Demás servicios gravados con IGV",
      "tasa": 12,
      "keywords": ["consultoría", "asesoría", "locación de servicios"]
    }
  ],
  "monto_minimo": 700.00,
  "indicadores_texto_spot": [
    "operación sujeta al spot",
    "cuenta de detracciones"
  ]
}
```

---

## 4. Tests

### Ejecutar tests

```bash
# Todos los tests
pytest tests/test_detraccion_spot.py tests/test_tdr_requirements.py -v

# Solo SPOT
pytest tests/test_detraccion_spot.py -v

# Solo TDR
pytest tests/test_tdr_requirements.py -v
```

### Casos de prueba clave

| Test | Descripción | Esperado |
|------|-------------|----------|
| `test_detecta_operacion_sujeta_spot` | Texto con "operación sujeta al SPOT" | aplica = True |
| `test_no_detecta_sin_indicios` | Texto sin indicios SPOT | aplica = False |
| `test_detecta_cv_explicito` | TDR con "currículum vitae" | CV detectado |
| `test_no_detecta_cv_si_no_menciona` | TDR sin mención de CV | CV NO detectado |
| `test_no_genera_observacion_si_tdr_no_pide` | TDR vacío de requisitos | Sin observaciones |

---

## 5. Reglas de Gobernanza Aplicadas

### Del documento AGENT_GOVERNANCE_RULES.md:

| Artículo | Aplicación |
|----------|------------|
| Art. 4 (Estándar Probatorio) | Toda observación incluye evidencia: archivo + página + snippet |
| Art. 5 (Degradación) | Si no hay evidencia completa, degrada a INCIERTO |
| Art. 8 (Pauta Obligatoria) | Si no hay pauta identificada (TDR vacío), no se exige |
| Art. 11.3 (Prohibición inferir) | NO se asume CV obligatorio si TDR no lo menciona |

---

## 6. Limitaciones Conocidas

1. **SPOT no calcula montos:** Solo determina SI/NO aplica, no el monto a detraer.

2. **Matching Anexo 3 es heurístico:** Usa keywords, puede tener falsos negativos si la descripción del servicio es muy diferente.

3. **TDR debe tener texto legible:** Si el TDR es imagen escaneada sin OCR, no se detectarán requisitos.

4. **No valida contenido de CV:** Solo verifica si existe archivo tipo CV, no si cumple la experiencia solicitada.

---

**Última actualización:** 2025-12-30  
**Autor:** Sistema AG-EVIDENCE  
**Versión:** 1.0.0


