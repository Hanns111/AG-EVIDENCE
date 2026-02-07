# Contributing to AG-EVIDENCE

Gracias por tu interés en contribuir a AG-EVIDENCE. Este documento proporciona guías para contribuir al proyecto.

---

## 🚀 Inicio Rápido

### 1. Clonar el Repositorio

```bash
git clone https://github.com/Hanns111/AG-EVIDENCE.git
cd AG-EVIDENCE
```

### 2. Crear Entorno Virtual

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / WSL2
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno

```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar .env con tus valores (si es necesario)
# Por defecto, Ollama debe estar corriendo en http://localhost:11434
```

### 5. Verificar Instalación

```bash
# Verificar Ollama
ollama list

# Verificar desde el sistema
python -c "from utils.llm_local import verificar_ollama; print(verificar_ollama())"
```

---

## 🏗️ Estructura del Proyecto

```
AG-EVIDENCE/
├── agentes/              # 9 agentes especializados del sistema
├── config/               # Configuración global (settings.py)
├── data/                 # Datos (NO versionados - .gitignore)
│   ├── directivas/       # PDFs de normativas
│   ├── expedientes/      # Expedientes de prueba
│   └── normativa/        # Datos normativos estructurados
├── docs/                 # Documentación de gobernanza
│   ├── AGENT_GOVERNANCE_RULES.md
│   ├── ARCHITECTURE_SNAPSHOT.md
│   └── ...
├── scripts/              # Scripts de utilidad
├── src/                  # Código fuente estructurado (en desarrollo)
│   ├── domain/           # Lógica de dominio
│   ├── orchestration/    # Orquestación (futuro: LangGraph)
│   ├── agents/           # Agentes (futuro)
│   └── tools/            # Herramientas técnicas
├── tests/                # Tests
│   ├── unit/             # Tests unitarios
│   ├── integration/      # Tests de integración
│   └── *.py              # Tests existentes
├── utils/                # Utilidades
└── output/               # Informes generados (NO versionado)
```

---

## 📝 Convención de Commits

Este proyecto sigue **Conventional Commits** para mantener un historial claro y semántico.

### Formato

```
<tipo>(<ámbito>): <descripción>

[descripción opcional detallada]
```

### Tipos

- `feat`: Nueva funcionalidad
- `fix`: Corrección de bug
- `docs`: Cambios en documentación
- `chore`: Tareas de mantenimiento (build, config, etc.)
- `refactor`: Refactorización de código
- `test`: Agregar o modificar tests
- `perf`: Mejoras de rendimiento

### Ejemplos

```bash
feat(agents): add new legal agent for directive validation
fix(ocr): correct text extraction for scanned PDFs
docs(readme): update installation instructions
chore(deps): update requirements.txt
refactor(orchestrator): simplify agent execution flow
test(unit): add tests for agent_04_legal
```

### Reglas

- Usar presente: "add" no "added" ni "adds"
- Primera letra en minúscula
- No terminar con punto
- Máximo 72 caracteres en la descripción

---

## 🧪 Ejecutar Tests

### Todos los Tests

```bash
python -m pytest tests/ -v
```

### Tests Unitarios

```bash
python -m pytest tests/unit/ -v
```

### Tests de Integración

```bash
python -m pytest tests/integration/ -v
```

### Test Específico

```bash
python -m pytest tests/test_agente_directivas.py -v
```

---

## 🔧 Desarrollo

### Ejecutar el Sistema

```bash
# Modo batch (análisis de expedientes)
python ejecutar_control_previo.py

# Chat asistente conversacional
python chat_asistente.py --modo conversacional --backend llm
```

### Verificar Código

```bash
# Linting (si está configurado)
pylint agentes/
black --check .

# Tests antes de commit
python -m pytest tests/ -v
```

---

## 📋 Proceso de Contribución

1. **Fork** el repositorio
2. **Crea una rama** para tu feature (`git checkout -b feat/mi-nueva-funcionalidad`)
3. **Commit** tus cambios (`git commit -m 'feat(scope): descripción'`)
4. **Push** a la rama (`git push origin feat/mi-nueva-funcionalidad`)
5. **Abre un Pull Request**

---

## ⚠️ Reglas Importantes

- **NO** subir PDFs, documentos sensibles o datos personales
- **NO** modificar `.gitignore` para incluir archivos sensibles
- **SÍ** seguir la arquitectura definida en `docs/ARCHITECTURE_SNAPSHOT.md`
- **SÍ** respetar las reglas de gobernanza en `docs/AGENT_GOVERNANCE_RULES.md`
- **SÍ** agregar tests para nuevas funcionalidades

---

## 📞 Soporte

Para preguntas o dudas sobre contribuciones, abre un issue en el repositorio.

---

**Gracias por contribuir a AG-EVIDENCE! 🚀**
