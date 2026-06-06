#!/usr/bin/env python
"""Compara subsidencia acumulada 2022→2026 sobre Bandurria Sur a distintas resoluciones:
80 m (actual), 40 m (INT40), 20 m (INT20) y PS (MiaplPy, si está). Mismo recorte, misma
escala de color, con trayectorias/bocas de pozo encima — para ver si la resolución fina
resuelve efectos más cercanos al pozo.

    ~/miniforge3/bin/mamba run -n insar python compare_resolutions.py
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
ROOT = HERE.parent.parent.parent
DATA = HERE.parent / "_data"
WIN0, WIN1 = "20220101", "20260601"           # ventana de comparación
# bbox bloque (lon/lat) → UTM 32719
BBOX_LL = (-68.93, -38.345, -68.62, -38.205)  # W,S,E,N
REF_BOX = (-68.885, -38.232, -68.845, -38.210)  # caja estable NW (W,S,E,N) para re-referenciar
tr = Transformer.from_crs("EPSG:4326", "EPSG:32719", always_xy=True)
fwd = lambda lo, la: tr.transform(lo, la)


def cum_disp(h5path, d0=WIN0, d1=WIN1):
    """LOS acumulado [mm] entre d0 y d1, recortado al bbox y re-referenciado al punto común."""
    with h5py.File(h5path, "r") as h:
        dates = [x.decode() for x in h["date"][:]]
        i0 = min(range(len(dates)), key=lambda i: abs(int(dates[i]) - int(d0)))
        i1 = min(range(len(dates)), key=lambda i: abs(int(dates[i]) - int(d1)))
        X0 = float(h.attrs["X_FIRST"]); Y0 = float(h.attrs["Y_FIRST"])
        xs = float(h.attrs["X_STEP"]); ys = float(h.attrs["Y_STEP"])
        W = int(h.attrs["WIDTH"]); L = int(h.attrs["LENGTH"])
        xmin, ymin = fwd(BBOX_LL[0], BBOX_LL[1]); xmax, ymax = fwd(BBOX_LL[2], BBOX_LL[3])
        c0 = max(int((xmin - X0) / xs), 0); c1 = min(int((xmax - X0) / xs), W)
        r0 = max(int((ymax - Y0) / ys), 0); r1 = min(int((ymin - Y0) / ys), L)
        a = (h["timeseries"][i1, r0:r1, c0:c1] - h["timeseries"][i0, r0:r1, c0:c1]) * 1000.0
        # re-referencia COMÚN: resta la mediana de una caja estable NW (robusto a pixeles enmascarados)
        bx0, by0 = fwd(REF_BOX[0], REF_BOX[1]); bx1, by1 = fwd(REF_BOX[2], REF_BOX[3])
        bc0 = int((bx0 - X0) / xs) - c0; bc1 = int((bx1 - X0) / xs) - c0
        br1 = int((by0 - Y0) / ys) - r0; br0 = int((by1 - Y0) / ys) - r0
        box = a[max(br0, 0):br1, max(bc0, 0):bc1]
        ref = np.nanmedian(box) if box.size else np.nan
        if np.isfinite(ref):
            a = a - ref
        ext = [X0 + c0 * xs, X0 + c1 * xs, Y0 + r1 * ys, Y0 + r0 * ys]
        return a, ext, dates[i0], dates[i1]


def wells_utm():
    w = json.load(open(DATA / "bsur_wells_all.json"))
    out = []
    for v in w.values():
        if v["has_traj"]:
            xs, ys = tr.transform([p[0] for p in v["traj"]], [p[1] for p in v["traj"]])
            out.append(("traj", np.array(xs), np.array(ys)))
        else:
            x, y = fwd(v["boca"][0], v["boca"][1])
            out.append(("boca", x, y))
    return out


def main():
    panels = []
    cand = [("80 m", HERE / "mintpy_int80_local" / "timeseries_ERA5_ramp_demErr.h5"),
            ("40 m", HERE / "mintpy_int40" / "timeseries_ERA5_ramp_demErr.h5"),
            ("20 m", HERE / "mintpy_int20" / "timeseries_ERA5_ramp_demErr.h5")]
    for label, p in cand:
        if p.exists():
            a, ext, da, db = cum_disp(p)
            panels.append((label, a, ext, da, db))
            print(f"{label}: {a.shape} px  {da}→{db}  min {np.nanmin(a):.0f} mm")
    if not panels:
        print("no hay timeseries todavía"); return

    vmax = max(abs(np.nanpercentile(a, 1)) for _, a, _, _, _ in panels)
    wl = wells_utm()
    n = len(panels)
    fig, axes = plt.subplots(1, n, figsize=(5.6 * n, 5.4), constrained_layout=True)
    axes = np.atleast_1d(axes)
    im = None
    for ax, (label, a, ext, da, db) in zip(axes, panels):
        im = ax.imshow(a, extent=ext, origin="upper", cmap="RdYlBu",
                       vmin=-vmax, vmax=vmax, aspect="equal")
        for kind, x, y in wl:
            if kind == "traj":
                ax.plot(x, y, "-", color="k", lw=0.5, alpha=0.6)
            else:
                ax.plot(x, y, "o", ms=2.0, mfc="none", mec="#1f4eb4", mew=0.6, alpha=0.8)
        ax.set_title(f"{label}\n{da[:6]}→{db[:6]}", fontsize=11)
        ax.set_xticks([]); ax.set_yticks([])
    fig.colorbar(im, ax=axes, shrink=0.7, location="right",
                 label="Subsidencia acumulada LOS [mm] (− = hundimiento)")
    fig.suptitle("Bandurria Sur — resolución de la subsidencia vs efectos cercanos al pozo",
                 fontsize=13)
    out = HERE / "compare_resolutions.png"
    fig.savefig(out, dpi=140)
    print("guardado:", out)


if __name__ == "__main__":
    main()
