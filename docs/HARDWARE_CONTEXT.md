# CONTEXTO TÉCNICO Y DE HARDWARE – AG-EVIDENCE (INMUTABLE)

## 1. Hardware Crítico

- Equipo principal: Laptop MSI Titan
- GPU: NVIDIA RTX 5090 Laptop
- Arquitectura: Blackwell
- Compute Capability: sm_120
- VRAM disponible: 32 GB
- CPU y RAM: No limitantes para este proyecto

Este hardware NO es estándar y requiere configuraciones específicas.

---

## 2. Sistema Operativo y Entorno

- Host: Windows 11 (solo para UI, IDE y gestión de archivos)
- Entorno de ejecución OBLIGATORIO:
  - Ubuntu 22.04 LTS sobre WSL2
- Todo procesamiento de IA ocurre en Linux (WSL2), no en Windows nativo.

---

## 3. Framework de IA

- Framework: PyTorch NIGHTLY (build Linux)
- Motivo:
  - PyTorch estable NO soporta sm_120
  - Windows NO es compatible con sm_120 a fecha 2026

Regla:
Nunca sugerir PyTorch estable ni builds Windows.

---

## 4. Reglas de Comandos

PROHIBIDO:
- PowerShell
- CMD
- Instalaciones nativas de IA en Windows

REQUERIDO:
- Bash
- Entorno Python venv dentro de WSL2
- CUDA y nvidia-smi solo se consideran válidos dentro de WSL2

---

## 5. Modelos Permitidos por VRAM

- LLM texto principal:
  - Qwen2.5-32B Instruct (AWQ o GPTQ Int4)
- Modelo de visión:
  - Qwen2.5-VL-7B Instruct
- No se permite cargar modelos 70B en FP16 en esta máquina.

---

## 6. Recuperación de Desastres

Existe un checkpoint físico externo:

- Medio: USB
- Archivo: ubuntu_gpu_ok_2026-01-13.tar
- Contiene: Entorno funcional WSL + GPU validada

Regla:
Ante corrupción severa del entorno, se debe restaurar este checkpoint
antes de intentar depuración destructiva.

---

## 7. Prioridad de este Documento

Si cualquier IA propone:
- Un stack incompatible
- Un comando fuera de WSL
- Un modelo que no cabe en VRAM

Debe detenerse y corregirse usando este documento.
