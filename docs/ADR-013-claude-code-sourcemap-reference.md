# ADR-013 — Source map de Claude Code como referencia conceptual (no base operativa)

- **Estado:** Aceptado  
- **Fecha:** 2026-03-31  
- **Ámbito:** Documentación e investigación arquitectónica; **cero** cambio en `src/`, `config/` ni dependencias de ejecución.

---

## Título

**Uso del source map de Claude Code como referencia conceptual y no como base operativa**

---

## Contexto

1. Existe localmente un archivo de **source map JavaScript** de gran tamaño (`CLAUDE_SOURCE_FINAL_60MB.map`, ~60 MB), **fuera** del repositorio AG-EVIDENCE, que agrupa código fuente embebido de tipo CLI/asistente (herramientas, SDK, integraciones).
2. Ese artefacto puede ser **útil como benchmark conceptual** para comparar patrones de ingeniería (tools, multimodalidad, manejo de contexto) con el diseño probatorio de AG-EVIDENCE.
3. **No** existe requisito normativo MINEDU/SUNAT vinculado a dicho archivo.
4. Incorporar el `.map` al repo o al runtime **rompería** principios de **repositorio liviano**, **local-first disciplinado** y **trazabilidad** (contenido de terceros masivo, no auditable como evidencia de expediente).

Evidencia mínima verificada en inspección local del `.map` (2026-03-31): presencia de claves JSON `sources`, strings con `BetaToolRunner`, `ToolError` con bloques `image`, módulos `FileReadTool`, conjuntos `BINARY_EXTENSIONS` con nota sobre exclusión de PDF en call site, etc. — detalle en `docs/research/CLAUDE_CODE_SOURCEMAP_NOTES.md`.

---

## Decisión

1. El archivo `CLAUDE_SOURCE_FINAL_60MB.map` permanece **fuera** del árbol git de AG-EVIDENCE, en la ruta local documentada en las notas de investigación.
2. AG-EVIDENCE **registra formalmente** su uso **solo** como:
   - material de **consulta arquitectónica** / investigación;
   - **contraste** con el modelo probatorio del proyecto (determinista, citación, `NULL` honesto).
3. Queda **prohibido** usar el `.map` como:
   - dependencia de import en Python/Node del pipeline;
   - sustituto de OCR, VLM o reglas de parsing;
   - fuente para “inferir” comportamiento del producto Claude Code en producción sin verificación independiente.

---

## Justificación

- Separa **inspiración de ingeniería** de **base de ejecución** del sistema de control previo.
- Evita confundir **asistente autónomo genérico** con **motor probatorio** sujeto a gobernanza estricta.
- Documenta límites para futuras IAs humanas o automáticas que propongan “copiar el stack de Claude Code”.

---

## Beneficios

- **Claridad:** una ADR corta evita que el `.map` sea malinterpretado como “SDK interno” de AG-EVIDENCE.
- **Continuidad:** los equipos saben **dónde** mirar (notas + ADR) y **qué no** hacer.
- **Alineación:** refuerza que el cuello de botella real sigue siendo **precisión de extracción** (OCR/parsing/venenos/recuperación), no falta de “agencia” tipo REPL.

---

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Alguien copia el `.map` dentro del repo por error | Patrón en `.gitignore` (`CLAUDE_SOURCE*.map`); revisión en PR. |
| Hype: “con este mapa arreglamos Excel” | Notas de investigación §6 y esta ADR lo niegan explícitamente. |
| Lectura parcial que infiere licencias | No copiar código; solo notas cualitativas; ADR adicional si algún día se adopta patrón concreto reutilizable. |

---

## Límites (resumen)

- **No** altera el comportamiento de `src/extraction/escribano_fiel.py`, `scripts/extract_comprobantes_minedu.py` ni tests.
- **No** sustituye `docs/AGENT_GOVERNANCE_RULES.md` ni el estándar probatorio.
- **No** autoriza integración con servicios cloud ni APIs Anthropic como requisito del producto.

---

## Implicancias para AG-EVIDENCE

1. **Pipeline productivo:** sin cambios.
2. **Documentación:** `docs/research/CLAUDE_CODE_SOURCEMAP_NOTES.md` + actualización mínima de memoria operativa (`CURRENT_STATE.md`, `CLAUDE.md`, `AG_EVIDENCE_MASTER_HANDOFF.txt`) donde corresponda.
3. **Futuro:** cualquier adopción de **patrón de código o flujo** inspirado en el material implica **nueva ADR** y diseño explícito de impacto probatorio.

---

## Estado

**Aceptado** — vigente desde 2026-03-31.

---

*Fin ADR-013.*
