#!/usr/bin/env bash
# Paso 3 — Serie de tiempo SBAS con MintPy (local). Genera velocity.h5.
#
#   conda activate insar
#   cd fase1&& ./03_timeseries.sh
#
# Requiere ./products poblado por 02_submit_hyp3.py --submit.
set -euo pipefail
cd "$(dirname "$0")"

if ! compgen -G "products/*/*_unw_phase.tif" > /dev/null; then
  echo "No hay productos en ./products. Corré 02_submit_hyp3.py --submit primero." >&2
  exit 1
fi

echo "==> Preparando stack HyP3 para MintPy (prep_hyp3.py)"
prep_hyp3.py products/*/*_unw_phase.tif
prep_hyp3.py products/*/*_corr.tif
prep_hyp3.py products/*/*_dem.tif

echo "==> Corriendo smallbaselineApp.py (red, inversión SBAS, correcciones, velocidad)"
smallbaselineApp.py vacamuerta.cfg

echo "==> Listo. Salida principal:"
ls -lh velocity.h5 2>/dev/null || echo "  (revisá la carpeta de salida de MintPy)"
echo "Visualizá con: python 04_export_visual.py"
