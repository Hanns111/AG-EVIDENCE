# Glosario AG-EVIDENCE

> Términos técnicos explicados en lenguaje simple.
> Para stakeholders, inversionistas y equipo no técnico.

---

## Términos del Sistema

| Término | Qué es | Analogía simple |
|---------|--------|-----------------|
| **Agente** | Un programa especializado que hace UNA tarea específica dentro del sistema. AG-EVIDENCE tiene 9 agentes que trabajan en cadena. | Como un empleado especialista en una oficina: uno revisa firmas, otro verifica montos, otro busca en SUNAT. |
| **Pipeline** | La secuencia ordenada de pasos que sigue un expediente desde que entra hasta que sale con su reporte. | Como una línea de producción en una fábrica: cada estación hace su parte. |
| **Orquestador** | El programa que coordina a los 9 agentes, decidiendo cuál trabaja primero y pasando los resultados al siguiente. | Como el jefe de mesa que organiza el flujo de trabajo. |
| **OCR** (Optical Character Recognition) | Tecnología que "lee" texto de imágenes o documentos escaneados y lo convierte en texto digital editable. | Como un empleado que transcribe a mano lo que ve en una fotocopia. |
| **LLM** (Large Language Model) | Modelo de inteligencia artificial que entiende y genera texto. AG-EVIDENCE usa uno local (Qwen) para analizar documentos. | Como un analista experto que lee documentos y extrae conclusiones, pero funciona dentro de tu computadora. |

---

## Términos de Arquitectura

| Término | Qué es | Analogía simple |
|---------|--------|-----------------|
| **WSL2** (Windows Subsystem for Linux) | Permite correr Linux dentro de Windows. AG-EVIDENCE usa esto para ejecutar herramientas que solo funcionan bien en Linux. | Como tener una computadora Linux virtual dentro de tu PC Windows. |
| **vLLM** | Motor optimizado para ejecutar modelos de IA a máxima velocidad con la GPU. Reemplazará a Ollama. | Como cambiar el motor de un auto por uno de carrera: mismo auto, pero mucho más rápido. |
| **Ollama** | Herramienta actual para ejecutar el modelo de IA localmente. Funcional pero será reemplazada por vLLM. | El motor actual del sistema, que funciona pero no aprovecha al máximo la GPU. |
| **GPU** (Graphics Processing Unit) | Tarjeta gráfica RTX 5090 con 32GB de memoria. Es lo que le da potencia al sistema para procesar IA localmente. | Como el motor de un auto: mientras más potente, más rápido procesa. Tu RTX 5090 es un motor de Fórmula 1. |
| **VRAM** | Memoria de la tarjeta gráfica. Con 32GB puedes correr modelos de IA grandes sin depender de internet. | La memoria del motor: con 32GB puedes cargar modelos que otros no pueden. |
| **Qwen** | Modelo de IA open-source creado por Alibaba. AG-EVIDENCE usa la versión de 32 mil millones de parámetros. | El "cerebro" del sistema que analiza documentos. Open-source significa que es gratuito y no envía datos a nadie. |

---

## Términos de Datos y Seguridad

| Término | Qué es | Analogía simple |
|---------|--------|-----------------|
| **Hash SHA-256** | Huella digital única de un archivo. Si alguien modifica un solo carácter del PDF, el hash cambia completamente. | Como la huella dactilar de un documento: única e irrepetible. Si cambia algo, se nota inmediatamente. |
| **Cadena de custodia** | Registro inmutable que prueba que el documento original nunca fue alterado desde que entró al sistema. | Como el acta notarial de un documento: certifica que nadie lo tocó. |
| **trace_id** | Identificador único que permite rastrear cada paso del análisis de un expediente. | Como el número de seguimiento de un paquete: puedes ver exactamente qué pasó en cada etapa. |
| **JSONL** | Formato de archivo donde cada línea es un registro independiente. Se usa para los logs del sistema. | Como un libro contable donde cada línea es una operación, con fecha, hora y detalle. |
| **Local-first** | Filosofía donde todo se procesa en tu máquina y ningún dato viaja por internet. | Como un cajero fuerte: todo se queda dentro de la oficina. |
| **GDPR** | Regulación europea de protección de datos personales. AG-EVIDENCE está diseñado para cumplirla desde el inicio. | La ley europea que obliga a proteger datos personales. El sistema la cumple porque nada sale de tu PC. |

---

## Términos de Control Previo (Dominio MINEDU)

| Término | Qué es | Analogía simple |
|---------|--------|-----------------|
| **Expediente** | Conjunto de documentos que respaldan una operación de gasto público (facturas, órdenes, conformidades, etc.). | La carpeta completa con todos los papeles de un trámite. |
| **Control previo** | Revisión que se hace ANTES de autorizar un pago, verificando que todo cumpla la normativa. | Como el control de calidad antes de enviar un producto: si algo falla, se devuelve. |
| **SINAD** | Sistema Nacional de Archivo Digital del MINEDU. | El sistema donde se registran los expedientes digitalmente. |
| **SIAF** | Sistema Integrado de Administración Financiera del Estado peruano. | El sistema contable del gobierno donde se registran los pagos. |
| **RUC** | Registro Único de Contribuyentes. Número de 11 dígitos que identifica a cada empresa o persona en SUNAT. | Como el DNI de una empresa. |
| **SUNAT** | Superintendencia Nacional de Aduanas y de Administración Tributaria. | La entidad que recauda impuestos en Perú (equivalente al IRS en EEUU o la AEAT en España). |
| **Directiva** | Norma interna del MINEDU que establece las reglas para un tipo de gasto (viáticos, caja chica, etc.). | El manual de procedimientos que dice exactamente qué documentos se necesitan y qué reglas se deben cumplir. |
| **Observación** | Hallazgo que indica un incumplimiento. Puede ser CRÍTICA, MAYOR o MENOR según su gravedad. | Como una nota del auditor diciendo "falta este documento" o "este monto no cuadra". |
| **Naturaleza del expediente** | Tipo de gasto: VIAT (viáticos), CAJA (caja chica), ENCA (encargo interno), PAGO (pago a proveedor), CONT (contrato). | La categoría del trámite, como "viaje de trabajo" o "compra de materiales". |

---

## Términos del Plan de Desarrollo

| Término | Qué es | Analogía simple |
|---------|--------|-----------------|
| **Fase** | Grupo de tareas relacionadas que se completan juntas. El plan tiene 6 fases. | Como los capítulos de un libro: cada uno cubre un tema específico. |
| **Trazabilidad** | Capacidad de rastrear cada dato hasta su origen exacto (archivo, página, línea). | Como poder seguir la cadena: "este número viene de la página 3 de la factura X". |
| **Contrato de datos** | Cada dato extraído declara de dónde viene, qué tan confiable es y cómo se obtuvo. | Como la etiqueta de un producto que dice ingredientes, origen y fecha de vencimiento. |
| **Confidence Router** | Componente que decide automáticamente si un dato es confiable o necesita verificación adicional. | Como un semáforo: verde (confiable), amarillo (revisar), rojo (no usar). |
| **Golden dataset** | Conjunto de expedientes ya verificados manualmente que sirven como referencia para probar el sistema. | Como los exámenes de prueba con respuestas correctas: sirven para verificar que el sistema da las respuestas correctas. |
| **Benchmark** | Prueba comparativa entre dos tecnologías para ver cuál funciona mejor. | Como probar dos marcas de un producto y comparar cuál rinde más. |
| **Fallback** | Plan B automático. Si una herramienta falla, el sistema usa otra alternativa. | Como tener un generador eléctrico: si se corta la luz, se enciende automáticamente. |
| **PaddleOCR** | Motor OCR alternativo creado por Baidu, más preciso que Tesseract para documentos administrativos. | Como cambiar de lupa a microscopio: ve mejor los detalles. |
| **Tesseract** | Motor OCR open-source de Google. Funcional pero menos preciso que PaddleOCR para español. | La lupa estándar: funciona bien pero PaddleOCR ve mejor. |
| **LangGraph** | Framework para coordinar agentes de IA. Reemplazará al orquestador actual. | Como pasar de dirigir una orquesta a mano a tener un sistema automatizado que coordina a todos los músicos. |

---

## Términos de Desarrollo (Git/Código)

| Término | Qué es | Analogía simple |
|---------|--------|-----------------|
| **Repositorio (repo)** | La carpeta del proyecto con todo su historial de cambios. Está en GitHub. | Como una caja fuerte que guarda todas las versiones de todos los documentos del proyecto. |
| **Commit** | Un punto de guardado con descripción de qué cambió. | Como guardar una partida en un videojuego con una nota de qué hiciste. |
| **Branch (rama)** | Una línea paralela de desarrollo. Permite trabajar sin afectar la versión principal. | Como hacer una copia de un documento para editarla sin tocar el original. |
| **Merge** | Incorporar los cambios de una rama a otra. | Como pasar en limpio las correcciones del borrador al documento final. |
| **Main** | La rama principal, la versión "oficial" del proyecto. | El documento maestro, la versión final. |
| **Push** | Subir los cambios locales al repositorio en internet (GitHub). | Como hacer un backup en la nube: subes tu versión local a internet. |
| **MCP** (Model Context Protocol) | Protocolo que permite a herramientas de IA interactuar con programas externos (leer PDFs, etc.). | Como un adaptador que permite a la IA conectarse con herramientas específicas. |
| **Worktree** | Una copia de trabajo del repositorio en otra carpeta. Permite trabajar en paralelo sin interferir con la rama principal. | Como tener dos escritorios: cada uno trabaja en su versión, pero al final se juntan los cambios. |

---

**Ubicación:** `docs/GLOSSARY.md`
**Última actualización:** 2026-02-10
