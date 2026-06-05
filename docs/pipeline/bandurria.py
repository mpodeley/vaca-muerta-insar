#!/usr/bin/env python
"""Investiga el uplift de Bandurria Norte: serie temporal de zona vs Bandurria Sur."""
from __future__ import annotations
import json
from datetime import date
from pathlib import Path
import numpy as np
import h5py
import rasterio
from rasterio.features import geometry_mask

HERE = Path(__file__).parent
DATA = Path("/var/home/matias/Projects/estado-del-sistema/public/data")
TS = HERE / "timeseries_ERA5_ramp_demErr.h5"
VELW = HERE / "_velocity_wgs84.tif"


def zone_mask(geom, transform, shape):
    return ~geometry_mask([geom], out_shape=shape, transform=transform, invert=False)


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    gj = json.load(open(DATA / "concesiones_neuquina.geojson"))
    geoms = {f["properties"]["nombre"]: f["geometry"] for f in gj["features"]}

    # serie temporal en grilla UTM (timeseries.h5); construir máscara reproyectando el polígono
    with h5py.File(TS, "r") as h:
        ts = h["timeseries"][:] * 1000.0  # mm
        dates = [d.decode() for d in h["date"][:]]
        a = dict(h.attrs)
    msk = h5py.File(HERE / "maskTempCoh.h5", "r")["mask"][:].astype(bool)
    H, W = ts.shape[1:]
    transform = rasterio.transform.Affine(float(a["X_STEP"]), 0, float(a["X_FIRST"]),
                                          0, float(a["Y_STEP"]), float(a["Y_FIRST"]))
    crs = rasterio.crs.CRS.from_epsg(int(a["EPSG"]))
    days = np.array([(date(int(d[:4]), int(d[4:6]), int(d[6:8])) -
                      date(int(dates[0][:4]), int(dates[0][4:6]), int(dates[0][6:8]))).days
                     for d in dates])

    from rasterio.warp import transform_geom
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.axhline(0, color="#bbb", lw=0.8)
    out = {}
    for name, color in [("BANDURRIA NORTE", "#2166ac"), ("BANDURRIA SUR", "#b2182b")]:
        gutm = transform_geom("EPSG:4326", crs, geoms[name])
        zm = zone_mask(gutm, transform, (H, W)) & msk
        n = int(zm.sum())
        rel = ts - ts[0]
        series = np.array([np.nanmean(rel[i][zm]) for i in range(len(dates))])
        ax.plot(days, series, "o-", color=color, lw=1.8, ms=3.5, label=f"{name} ({n} px)")
        out[name] = series
        print(f"{name}: {n} px | total={series[-1]:+.1f} mm | "
              f"min={series.min():+.1f} max={series.max():+.1f}")
    for yr in sorted({int(d[:4]) for d in dates}):
        d0 = (date(yr, 1, 1) - date(int(dates[0][:4]), int(dates[0][4:6]), int(dates[0][6:8]))).days
        if days.min() <= d0 <= days.max():
            ax.axvline(d0, color="#eee", lw=1, zorder=0)
    ax.set_xlabel(f"Días desde {dates[0]}"); ax.set_ylabel("Desplazamiento LOS acumulado (mm)")
    ax.set_title("Bandurria Norte (uplift) vs Bandurria Sur (subsidencia) — serie temporal", fontsize=12)
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout(); fig.savefig(HERE / "bandurria.png", dpi=150)
    print("→ bandurria.png")


if __name__ == "__main__":
    main()
