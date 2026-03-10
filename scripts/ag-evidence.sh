#!/bin/bash
# ag-evidence.sh — Setup de workstation para AG-EVIDENCE
# Uso: source scripts/ag-evidence.sh (desde WSL2)

PROJECT_PATH="/mnt/c/Users/Hans/Proyectos/AG-EVIDENCE"

clear
echo "=================================================="
echo "  AG-EVIDENCE PROFESSIONAL WORKSTATION"
echo "=================================================="

# Entrar al proyecto
cd "$PROJECT_PATH" || exit

# Mostrar ubicacion
echo ""
echo "Proyecto:"
pwd

# Mostrar branch
CURRENT_BRANCH=$(git branch --show-current)
echo ""
echo "Branch actual: $CURRENT_BRANCH"

# Verificar sincronia con origin
echo ""
echo "Sincronizando con origin..."
git fetch origin >/dev/null 2>&1

LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse @{u} 2>/dev/null)
BASE=$(git merge-base @ @{u} 2>/dev/null)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "[OK] Sincronizado con origin"
elif [ "$LOCAL" = "$BASE" ]; then
    echo "[!!] Hay commits pendientes de pull"
elif [ "$REMOTE" = "$BASE" ]; then
    echo "[!!] Hay commits pendientes de push"
else
    echo "[!!] Rama divergente"
fi

# Verificar cambios sin commit
echo ""
if [[ -n $(git status --porcelain) ]]; then
    echo "[!!] Hay cambios sin commit"
else
    echo "[OK] Working tree limpio"
fi

# Alias profesionales (sin git add . por seguridad)
alias gs="git status -sb"
alias gp="git pull"
alias gpush="git push"
alias gc="git commit -m"

# Prompt profesional
export PS1="\[\e[1;32m\]\u@\h\[\e[0m\]:\[\e[1;34m\]\w\[\e[0m\] (AG-EVIDENCE) \$ "

echo ""
echo "Entorno listo."
echo "=================================================="
echo ""

exec bash
