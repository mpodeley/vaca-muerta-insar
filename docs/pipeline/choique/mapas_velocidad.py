#!/usr/bin/env python
"""Bajo del Choique — mapa de velocidad LOS + desplazamiento acumulado del bloque.

Panel doble: velocidad media [mm/año] y desplazamiento acumulado a la última
fecha [mm], con laterales de pozos y contorno de la concesión. Exporta además
la velocidad recortada como GeoTIFF (para QGIS / demos).

Salidas: choique_velocity.png + _data/choique_velocity_mm_yr.tif

    ~/miniforge3/bin/mamba run -n insar python exploraciones/choique/mapas_velocidad.py
    ... mapas_velocidad.py --src ../../t18_f1050 --suffix _80m
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

import h5py
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from pyproj import Transformer

from gradiente import load_velocity, HERE, DATA, CONC, BLOQUE_ID, LON0, LAT0, LON1, LAT1

WELLS = DATA / "choique_wells_all.json"


def load_cumdisp(src: Path, g):
    """acumulado [mm]: media de las últimas 3 épocas − media de las primeras 3
    (promediar extremos baja la atmósfera de una fecha suelta ~√3)."""
    ts = src / "timeseries_ERA5_ramp_demErr.h5"
    if not ts.exists():
        ts = src / "timeseries.h5"
    with h5py.File(ts) as f:
        at = dict(f.attrs)
        x0, y0 = float(at["X_FIRST"]), float(at["Y_FIRST"])
        dx, dy = float(at["X_STEP"]), float(at["Y_STEP"])
        c0 = int(round((g["x0"] - x0) / dx)); r0 = int(round((g["y0"] - y0) / dy))
        dates = [d.decode() for d in f["date"][:]]
        last = f["timeseries"][-3:].mean(axis=0) * 1000.0
        first = f["timeseries"][:3].mean(axis=0) * 1000.0
    cum = (last - first)[r0:, c0:]
    return cum, dates[0], dates[-1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=str(HERE / "mintpy_int80"))
    ap.add_argument("--suffix", default="")
    args = ap.parse_args()
    src = Path(args.src)

    v, g = load_velocity(src)
    cum, d0, d1 = load_cumdisp(src, g)
    cum = cum[:v.shape[0], :v.shape[1]]
    cum[~np.isfinite(v)] = np.nan

    tr_fw = Transformer.from_crs("EPSG:4326", f"EPSG:{g['epsg']}", always_xy=True)
    ext = [g["x0"], g["x0"] + v.shape[1] * g["dx"], g["y0"] + v.shape[0] * g["dy"], g["y0"]]

    wells = json.load(open(WELLS)) if WELLS.exists() else {}
    gj = json.load(open(CONC))
    geom = next(f["geometry"] for f in gj["features"] if f["properties"].get("id") == BLOQUE_ID)
    rings = geom["coordinates"] if geom["type"] == "Polygon" else [r for p in geom["coordinates"] for r in p]

    fig, axs = plt.subplots(1, 2, figsize=(13.6, 6.4))
    for ax, dat, ttl, unit in (
        (axs[0], v, "Velocidad LOS media", "mm/año"),
        (axs[1], cum, f"Desplazamiento acumulado {d0[:4]}-{d0[4:6]} → {d1[:4]}-{d1[4:6]}", "mm"),
    ):
        vmax = np.nanpercentile(np.abs(dat), 99)
        im = ax.imshow(dat, extent=ext, cmap="RdBu", norm=TwoSlopeNorm(0, -vmax, vmax))
        for w in wells.values():
            pts = w["traj"] if w["has_traj"] else None
            if pts:
                xs, ys = tr_fw.transform([p[0] for p in pts], [p[1] for p in pts])
                ax.plot(xs, ys, "-", color="0.25", lw=0.45, alpha=0.6)
            else:
                x, y = tr_fw.transform(w["boca"][0], w["boca"][1])
                ax.plot(x, y, "o", color="0.25", ms=1.6, alpha=0.6)
        for ring in rings:
            xs, ys = tr_fw.transform([p[0] for p in ring], [p[1] for p in ring])
            ax.plot(xs, ys, "k--", lw=1.1)
        ax.set_xticks([]); ax.set_yticks([]); ax.set_aspect("equal")
        ax.set_title(f"{ttl} [{unit}]  (− = subsidencia)", fontsize=11)
        plt.colorbar(im, ax=ax, shrink=0.85)

    fig.suptitle("Bajo del Choique — subsidencia InSAR (track 18 ASC) y pozos", fontsize=13.5)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out_png = HERE / f"choique_velocity{args.suffix}.png"
    fig.savefig(out_png, dpi=145)
    print("guardado:", out_png)

    # GeoTIFF de velocidad recortada
    import rasterio
    from rasterio.transform import from_origin
    out_tif = DATA / f"choique_velocity_mm_yr{args.suffix}.tif"
    with rasterio.open(out_tif, "w", driver="GTiff", height=v.shape[0], width=v.shape[1],
                       count=1, dtype="float32", crs=f"EPSG:{g['epsg']}",
                       transform=from_origin(g["x0"], g["y0"], abs(g["dx"]), abs(g["dy"])),
                       nodata=np.nan) as dst:
        dst.write(v.astype("float32"), 1)
    print("guardado:", out_tif)


if __name__ == "__main__":
    main()
