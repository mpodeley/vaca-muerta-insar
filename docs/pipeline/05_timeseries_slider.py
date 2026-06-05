#!/usr/bin/env python
"""Visualización interactiva: deformación ACUMULADA con slider temporal, sobre mapa.

Lee timeseries_ramp_demErr.h5 (MintPy) — desplazamiento LOS acumulado respecto a
la primera fecha — y arma un HTML autocontenido con un mapa **Leaflet + basemap
satelital** (Web Mercator) y un slider: cada paso es una fecha (~trimestral) y
muestra cuánto se hundió (rojo) o levantó (azul) cada punto hasta ese momento.

    conda activate insar
    cd fase1 && python 05_timeseries_slider.py            # ~trimestral
    cd fase1 && python 05_timeseries_slider.py --every 1  # todas las fechas

Convención: negativo = subsidencia (rojo), positivo = uplift (azul).
"""

from __future__ import annotations

import argparse
import base64
import io
import sys
from pathlib import Path

import numpy as np

import aoi

HERE = Path(__file__).parent
TS_FILES = ["timeseries_ERA5_ramp_demErr.h5", "timeseries_ERA5_ramp.h5",
            "timeseries_ramp_demErr.h5", "timeseries_ramp.h5", "timeseries.h5"]
MASK_H5 = HERE / "maskTempCoh.h5"
OUT = HERE / "demo_acumulado_slider.html"


def _decimal_years(dates: list[str]) -> np.ndarray:
    """YYYYMMDD → año decimal (para pesar el suavizado respetando huecos)."""
    from datetime import date

    out = []
    for d in dates:
        dt = date(int(d[:4]), int(d[4:6]), int(d[6:8]))
        start = date(dt.year, 1, 1)
        out.append(dt.year + (dt - start).days / 365.25)
    return np.array(out, dtype="float64")


def pick_quarterly(dates: list[str]) -> list[int]:
    """Índices ~1 por trimestre (primera adquisición de cada año-trimestre) + última."""
    seen, idx = set(), []
    for i, d in enumerate(dates):
        q = (d[:4], (int(d[4:6]) - 1) // 3)
        if q not in seen:
            seen.add(q)
            idx.append(i)
    if idx[-1] != len(dates) - 1:
        idx.append(len(dates) - 1)
    return idx


def _reproject_to_4326(arr, src_transform, src_crs):
    import rasterio
    from rasterio.warp import Resampling, calculate_default_transform, reproject

    h, w = arr.shape
    dt, dw, dh = calculate_default_transform(src_crs, "EPSG:4326", w, h,
                                             *rasterio.transform.array_bounds(h, w, src_transform))
    dst = np.full((dh, dw), np.nan, dtype="float32")
    reproject(source=arr, destination=dst,
              src_transform=src_transform, src_crs=src_crs,
              dst_transform=dt, dst_crs="EPSG:4326",
              resampling=Resampling.nearest, src_nodata=np.nan, dst_nodata=np.nan)
    west, north = dt.c, dt.f
    east, south = dt.c + dw * dt.a, dt.f + dh * dt.e
    # downsample para que el HTML no pese (área grande → PNGs enormes)
    step = max(1, int(np.ceil(max(dh, dw) / 800)))
    if step > 1:
        dst = dst[::step, ::step]
    return dst, (south, west, north, east)


def _png_b64(arr, norm, cmap):
    from matplotlib import pyplot as plt

    rgba = cmap(norm(arr))
    rgba[..., 3] = np.where(np.isfinite(arr), 0.8, 0.0)
    buf = io.BytesIO()
    plt.imsave(buf, rgba, format="png")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def main() -> None:
    import h5py
    import rasterio
    from matplotlib import cm, colors

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--every", type=int, default=0,
                    help="1 = todas las fechas; 0 = ~trimestral (default).")
    ap.add_argument("--sigma-days", type=float, default=45.0,
                    help="Ancho del suavizado Gaussiano temporal (días).")
    ap.add_argument("--raw", action="store_true",
                    help="Sin suavizado: usar el desplazamiento crudo por fecha.")
    args = ap.parse_args()

    src = next((HERE / f for f in TS_FILES if (HERE / f).exists()), None)
    if src is None:
        sys.exit("No hay timeseries*.h5. Corré fase1/03_timeseries.sh primero.")

    with h5py.File(src, "r") as h:
        ts = h["timeseries"][:]
        dates = [d.decode() if isinstance(d, bytes) else d for d in h["date"][:]]
        a = dict(h.attrs)
    with h5py.File(MASK_H5, "r") as h:
        mask = h["mask"][:].astype(bool)

    sel = list(range(len(dates))) if args.every == 1 else pick_quarterly(dates)
    dates_sel = [dates[i] for i in sel]
    print(f"{src.name}: {len(dates)} fechas → {len(sel)} pasos ({dates_sel[0]}…{dates_sel[-1]})")

    # Suavizado temporal Gaussiano (time-aware) para aplastar el ruido atmosférico
    # residual de fechas puntuales sin tocar la tendencia. --raw lo desactiva.
    if args.raw:
        stack = ts[sel].astype("float32")
    else:
        t = _decimal_years(dates)
        ts_flat = ts.reshape(len(dates), -1)
        rows = []
        for i in sel:
            wts = np.exp(-0.5 * ((t - t[i]) / (args.sigma_days / 365.25)) ** 2)
            wts /= wts.sum()
            rows.append(wts @ ts_flat)
        stack = np.array(rows, dtype="float32").reshape(len(sel), *ts.shape[1:])
        print(f"suavizado Gaussiano temporal σ={args.sigma_days} días")
    stack = stack * 1000.0  # m → mm
    stack[:, ~mask] = np.nan

    src_transform = rasterio.transform.Affine(
        float(a["X_STEP"]), 0, float(a["X_FIRST"]),
        0, float(a["Y_STEP"]), float(a["Y_FIRST"]))
    src_crs = rasterio.crs.CRS.from_epsg(int(a["EPSG"]))

    vmax = float(np.nanpercentile(np.abs(stack[np.isfinite(stack)]), 98)) or 10.0
    norm = colors.TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    cmap = cm.get_cmap("RdBu")

    frames = []
    bounds = None
    for k, i in enumerate(sel):
        arr4326, bnds = _reproject_to_4326(stack[k], src_transform, src_crs)
        bounds = bnds
        d = dates_sel[k]
        frames.append({"label": f"{d[:4]}-{d[4:6]}-{d[6:]}",
                       "png": _png_b64(arr4326, norm, cmap)})
    s, w, n, e = bounds

    _write_html(frames, (s, w, n, e), vmax)
    print(f"Listo → {OUT}")


def _write_html(frames, bounds, vmax):
    import json
    s, w, n, e = bounds
    cy, cx = (s + n) / 2, (w + e) / 2
    data = json.dumps(frames)
    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<title>Deformación acumulada — Vaca Muerta</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html,body,#map{{height:100%;margin:0}}
  .panel{{position:absolute;bottom:18px;left:50%;transform:translateX(-50%);z-index:1000;
    background:rgba(255,255,255,.94);padding:10px 16px;border-radius:8px;
    font:13px sans-serif;box-shadow:0 1px 6px rgba(0,0,0,.3);width:min(560px,86vw)}}
  .panel b{{font-size:14px}} #date{{font-weight:bold;color:#222}}
  input[type=range]{{width:100%}}
  .legend{{position:absolute;top:12px;right:12px;z-index:1000;background:rgba(255,255,255,.92);
    padding:8px 12px;border-radius:6px;font:12px sans-serif}}
  .bar{{height:10px;width:180px;background:linear-gradient(to right,#b2182b,#f7f7f7,#2166ac);
    border:1px solid #999;margin:3px 0}}
  .bl{{display:flex;justify-content:space-between;font-size:11px}}
</style></head><body>
<div id="map"></div>
<div class="legend"><b>Deformación acumulada (LOS)</b>
  <div class="bar"></div>
  <div class="bl"><span>−{vmax:.0f} mm (subsidencia)</span><span>0</span><span>+{vmax:.0f} mm (uplift)</span></div>
</div>
<div class="panel">
  <div><b>Deformación acumulada</b> &nbsp; <span id="date"></span></div>
  <input type="range" id="sl" min="0" max="{len(frames)-1}" value="{len(frames)-1}" step="1">
  <div style="font-size:11px;color:#666;text-align:center">
    Sentinel-1/SBAS 2019–2026 · track 18 ASC · tropo ERA5 · suavizado · respecto a la 1ª fecha</div>
</div>
<script>
const FR = {data};
const B = [[{s},{w}],[{n},{e}]];
const map = L.map('map').fitBounds(B);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
  {{attribution:'Esri World Imagery'}}).addTo(map);
const layers = FR.map(f => L.imageOverlay('data:image/png;base64,'+f.png, B, {{opacity:0}}).addTo(map));
L.marker([{aoi.ANELO[0]},{aoi.ANELO[1]}]).addTo(map).bindTooltip('Añelo');
const sl = document.getElementById('sl'), dt = document.getElementById('date');
function show(i){{ layers.forEach((l,k)=>l.setOpacity(k==i?1:0)); dt.textContent = FR[i].label; }}
sl.addEventListener('input', e=>show(+e.target.value));
show(FR.length-1);
</script></body></html>"""
    OUT.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
