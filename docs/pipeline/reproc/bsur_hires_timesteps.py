#!/usr/bin/env python
"""Zoom de alta resolución (20 m) a la zona de pozos CON TRAYECTORIA de Bandurria Sur,
subsidencia acumulada en varios timesteps 2022→2026. Para ver el detalle cercano al pozo
que el 80 m no resuelve.

    ~/miniforge3/bin/mamba run -n insar python bsur_hires_timesteps.py
"""
from __future__ import annotations
import json
from pathlib import Path

import h5py
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pyproj import Transformer

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "_data"
TS = HERE / "mintpy_int20" / "timeseries_ERA5_ramp_demErr.h5"
NPANELS = 6
REF_BOX = (-68.885, -38.232, -68.845, -38.210)   # caja estable para re-referenciar
tr = Transformer.from_crs("EPSG:4326", "EPSG:32719", always_xy=True)
fwd = lambda lo, la: tr.transform(lo, la)


def main():
    wells = json.load(open(DATA / "bsur_wells_all.json"))
    traj = [v["traj"] for v in wells.values() if v["has_traj"]]
    # bbox a percentiles de los centroides de rama (zoom al cluster, sin esquinas vacías)
    cx = np.array([np.mean([p[0] for p in t]) for t in traj])
    cy = np.array([np.mean([p[1] for p in t]) for t in traj])
    lo0, lo1 = np.percentile(cx, 2), np.percentile(cx, 98)
    la0, la1 = np.percentile(cy, 2), np.percentile(cy, 98)
    mlon, mlat = 0.012, 0.010
    bbox = (lo0 - mlon, la0 - mlat, lo1 + mlon, la1 + mlat)

    with h5py.File(TS, "r") as h:
        dates = [x.decode() for x in h["date"][:]]
        X0 = float(h.attrs["X_FIRST"]); Y0 = float(h.attrs["Y_FIRST"])
        xs = float(h.attrs["X_STEP"]); ys = float(h.attrs["Y_STEP"])
        W = int(h.attrs["WIDTH"]); L = int(h.attrs["LENGTH"])
        xmin, ymin = fwd(bbox[0], bbox[1]); xmax, ymax = fwd(bbox[2], bbox[3])
        c0 = max(int((xmin - X0) / xs), 0); c1 = min(int((xmax - X0) / xs), W)
        r0 = max(int((ymax - Y0) / ys), 0); r1 = min(int((ymin - Y0) / ys), L)
        idx = np.linspace(0, len(dates) - 1, NPANELS).round().astype(int)
        cube = h["timeseries"][idx, r0:r1, c0:c1] * 1000.0
        i0 = idx[0]
        base = h["timeseries"][i0, r0:r1, c0:c1] * 1000.0
        sel = [dates[i] for i in idx]
        ext = [X0 + c0 * xs, X0 + c1 * xs, Y0 + r1 * ys, Y0 + r0 * ys]
        # caja de referencia → pixel window (relativo al recorte)
        bx0, by0 = fwd(REF_BOX[0], REF_BOX[1]); bx1, by1 = fwd(REF_BOX[2], REF_BOX[3])
        bc0 = int((bx0 - X0) / xs) - c0; bc1 = int((bx1 - X0) / xs) - c0
        br1 = int((by0 - Y0) / ys) - r0; br0 = int((by1 - Y0) / ys) - r0

    # cum respecto al primer panel (2022) + re-referencia a la caja
    cum = cube - base
    for k in range(len(idx)):
        box = cum[k, max(br0, 0):br1, max(bc0, 0):bc1]
        ref = np.nanmedian(box) if box.size else np.nan
        if np.isfinite(ref):
            cum[k] -= ref
    vmax = float(np.nanpercentile(np.abs(cum[-1]), 99)) or 30.0

    trj_utm = [tr.transform([p[0] for p in t], [p[1] for p in t]) for t in traj]

    ncol = 3; nrow = 2
    fig, axes = plt.subplots(nrow, ncol, figsize=(5.4 * ncol, 4.6 * nrow),
                             constrained_layout=True)
    axes = axes.ravel()
    im = None
    for k, ax in enumerate(axes):
        im = ax.imshow(cum[k], extent=ext, origin="upper", cmap="RdYlBu",
                       vmin=-vmax, vmax=vmax, aspect="equal")
        for xs_, ys_ in trj_utm:
            ax.plot(xs_, ys_, "-", color="k", lw=0.7, alpha=0.7)
        d = sel[k]
        ax.set_title(f"{d[:4]}-{d[4:6]}", fontsize=11)
        ax.set_xticks([]); ax.set_yticks([])
    fig.colorbar(im, ax=axes, shrink=0.6, location="right",
                 label="Subsidencia acumulada desde 2022 [mm] (− = hundimiento)")
    fig.suptitle("Bandurria Sur — subsidencia a 20 m sobre los pozos con trayectoria (zoom, por timestep)",
                 fontsize=13)
    out = HERE / "bsur_hires_timesteps.png"
    fig.savefig(out, dpi=145)
    print("guardado:", out, "| bbox", [round(b, 4) for b in bbox], "| vmax", round(vmax))
    print("fechas:", sel)


if __name__ == "__main__":
    main()
