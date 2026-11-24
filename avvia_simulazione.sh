#!/usr/bin/env bash
# Avvia denoising_live in modalita' simulazione sul PC di sviluppo (Linux).
# Usa l'ambiente conda "denoising_live" (vedi environment.yml e README).
# Argomenti aggiuntivi vengono passati a main.py (es. --file riferimenti/dati/071210_001.wcp).
set -e
QUI="$(cd "$(dirname "$0")" && pwd)"
if [ -n "$DLIVE_PYTHON" ]; then
    PY="$DLIVE_PYTHON"
elif [ -x "$HOME/miniforge3/envs/denoising_live/bin/python" ]; then
    PY="$HOME/miniforge3/envs/denoising_live/bin/python"
elif command -v conda >/dev/null 2>&1 && [ -x "$(conda info --base)/envs/denoising_live/bin/python" ]; then
    PY="$(conda info --base)/envs/denoising_live/bin/python"
else
    PY=python3
fi
cd "$QUI"
exec "$PY" main.py --simulazione "$@"
