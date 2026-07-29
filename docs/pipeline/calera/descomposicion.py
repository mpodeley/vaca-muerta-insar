#!/usr/bin/env python
"""La Calera — descomposición vertical / este-oeste (asc track 18 + desc track 10).

Ventana común: 2025-08 → 2026-06 (S1C descendente disponible desde 2025-08).
1. velocidad ASC de la ventana (timeseries2velocity sobre el stack int40)
2. asc_desc2horz_vert.py (MintPy) con geometrías por píxel → v_up, v_east
3. figura: paneles v_up/v_east + perfiles descompuestos a través de los
   lineamientos candidatos a falla (L2a, L6) y de la flexura del flanco este.

Ambos stacks comparten la MISMA referencia fija (-38.41858,-68.96676), condición
necesaria para descomponer.

    ~/miniforge3/bin/mamba run -n insar python exploraciones/calera/descomposicion.py
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

import h5py
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from pyproj import Transformer
from scipy.ndimage import map_coordinates


_PROJECTS = Path(__file__).resolve().parents[5]  # ~/Projects
HERE = Path(__file__).resolve().parent
DATA = HERE / "_data"
ASC, DESC = HERE / "mintpy_int40", HERE / "mintpy_d10"
T0, T1 = "20250803", "20260624"
CONC = _PROJECTS / "activos/estado-red-gas/public/data/concesiones_neuquina.geojson"


def run(cmd):
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def main() -> None:
    vel_asc = ASC / "velocity_desde202508.h5"
    if not vel_asc.exists():
        run(["timeseries2velocity.py", str(ASC / "timeseries_ERA5_ramp_demErr.h5"),
             "--start-date", T0, "--end-date", T1, "-o", str(vel_asc)])
    hz, up = HERE / "calera_hz.h5", HERE / "calera_up.h5"
    run(["asc_desc2horz_vert.py", str(vel_asc), str(DESC / "velocity.h5"),
         "-g", str(ASC / "inputs" / "geometryGeo.h5"), str(DESC / "inputs" / "geometryGeo.h5"),
         "-o", str(hz), str(up)])

    with h5py.File(up) as f:
        at = dict(f.attrs)
        vu = f[list(f.keys())[0]][:] * 1000.0
    with h5py.File(hz) as f:
        ve = f[list(f.keys())[0]][:] * 1000.0
    epsg = at.get("EPSG", "32719")
    epsg = epsg.decode() if isinstance(epsg, bytes) else str(int(float(epsg)))
    x0, y0 = float(at["X_FIRST"]), float(at["Y_FIRST"])
    dx, dy = float(at["X_STEP"]), float(at["Y_STEP"])
    ext = [x0, x0 + vu.shape[1] * dx, y0 + vu.shape[0] * dy, y0]
    tr_fw = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)

    # máscaras de coherencia de ambos stacks (remuestreo por índice, misma grilla 40 m)
    def mask_of(root):
        with h5py.File(root / "maskTempCoh.h5") as f:
            m = f["mask"][:].astype(bool)
            a = dict(f.attrs)
        mx0, my0 = float(a["X_FIRST"]), float(a["Y_FIRST"])
        c = int(round((x0 - mx0) / dx)); r = int(round((y0 - my0) / dy))
        out = np.zeros_like(vu, dtype=bool)
        rr = slice(max(r, 0), min(r + vu.shape[0], m.shape[0]))
        cc = slice(max(c, 0), min(c + vu.shape[1], m.shape[1]))
        out[rr.start - r:rr.stop - r, cc.start - c:cc.stop - c] = m[rr, cc]
        return out
    mm = mask_of(ASC) & mask_of(DESC)
    vu[~mm] = np.nan
    ve[~mm] = np.nan
    print(f"descompuesto: {np.isfinite(vu).mean()*100:.0f}% válido | "
          f"v_up p1 {np.nanpercentile(vu, 1):+.1f}  min {np.nanmin(vu):+.1f} mm/año | "
          f"v_east p1 {np.nanpercentile(ve, 1):+.1f}  p99 {np.nanpercentile(ve, 99):+.1f}")

    # contexto: bloque + lineamientos
    gj = json.load(open(CONC))
    geom = next(f["geometry"] for f in gj["features"] if f["properties"].get("id") == "LCA")
    rings = geom["coordinates"] if geom["type"] == "Polygon" else [r for p in geom["coordinates"] for r in p]
    cands = json.load(open(DATA / "grad_candidates.geojson"))["features"]

    fig, axs = plt.subplots(1, 2, figsize=(13.6, 6.6))
    for ax, dat, ttl, cm_ in ((axs[0], vu, "Velocidad VERTICAL [mm/año] (2025-08 → 2026-06)", "RdBu"),
                              (axs[1], ve, "Velocidad ESTE-OESTE [mm/año] (+ = hacia el este)", "PuOr")):
        vmax = np.nanpercentile(np.abs(dat), 99)
        im = ax.imshow(dat, extent=ext, cmap=cm_, norm=TwoSlopeNorm(0, -vmax, vmax))
        for ring in rings:
            xs, ys = tr_fw.transform([p[0] for p in ring], [p[1] for p in ring])
            ax.plot(xs, ys, "k--", lw=1.1)
        for f in cands:
            cc2 = f["geometry"]["coordinates"]
            xs, ys = tr_fw.transform([p[0] for p in cc2], [p[1] for p in cc2])
            ax.plot(xs, ys, "-", color="#00c2a0", lw=1.8)
            ax.annotate(f"L{f['properties']['id']}", (np.mean(xs), np.mean(ys)),
                        color="#007a63", fontsize=8, fontweight="bold")
        ax.set_xticks([]); ax.set_yticks([]); ax.set_aspect("equal")
        ax.set_title(ttl, fontsize=11)
        plt.colorbar(im, ax=ax, shrink=0.85)
    fig.suptitle("La Calera — descomposición asc (track 18) + desc (track 10, S1C) · "
                 "ventana común de 11 meses", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out = HERE / "calera_vertical.png"
    fig.savefig(out, dpi=145)
    print("guardado:", out)

    # perfiles descompuestos a través de los lineamientos (4 km, perpendicular)
    def sample(dat, xa, ya, xb, yb):
        n = 100
        xs = np.linspace(xa, xb, n); ys = np.linspace(ya, yb, n)
        cols = (xs - x0) / dx - 0.5; rows = (ys - y0) / dy - 0.5
        return np.linspace(0, np.hypot(xb - xa, yb - ya), n) / 1000, \
            map_coordinates(dat, [rows, cols], order=1, mode="constant", cval=np.nan)

    sel = [f for f in cands if f["properties"]["id"] in (1, 2, 6)]
    fig2, axs2 = plt.subplots(1, len(sel), figsize=(5.2 * len(sel), 3.6), squeeze=False)
    for k, f in enumerate(sel):
        p = f["properties"]
        cc2 = f["geometry"]["coordinates"]
        xs, ys = tr_fw.transform([q[0] for q in cc2], [q[1] for q in cc2])
        cx, cy = float(np.mean(xs)), float(np.mean(ys))
        az = np.radians(p["azimut_deg"] + 90)
        ux, uy = np.sin(az) * 2000, np.cos(az) * 2000
        ax = axs2[0][k]
        for dat, lbl, col in ((vu, "vertical", "#b2182b"), (ve, "este-oeste", "#7a3fb0")):
            d, vals = sample(dat, cx - ux, cy - uy, cx + ux, cy + uy)
            ax.plot(d, vals, "-", lw=1.5, color=col, label=lbl)
        ax.axvline(2.0, color="0.6", ls=":", lw=1)
        ax.axhline(0, color="0.85", lw=0.8)
        ax.set_title(f"L{p['id']} (az {p['azimut_deg']:.0f}°) ⊥", fontsize=10)
        ax.set_xlabel("dist. [km]"); ax.grid(alpha=0.25)
        if k == 0:
            ax.set_ylabel("mm/año"); ax.legend(fontsize=8)
    fig2.suptitle("Perfiles descompuestos a través de los lineamientos", fontsize=12)
    fig2.tight_layout(rect=[0, 0, 1, 0.92])
    out2 = HERE / "calera_vertical_perfiles.png"
    fig2.savefig(out2, dpi=145)
    print("guardado:", out2)


if __name__ == "__main__":
    main()
