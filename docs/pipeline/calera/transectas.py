#!/usr/bin/env python
"""La Calera — perfiles a través del bowl y detección de escalones (falla vs flexura).

Transectas: 2 largas fijas cruzando el bowl (ejes NW-SE y SW-NE) + 1 perpendicular
automática por lineamiento candidato (azimut del esqueleto + 90°, 4 km centrada).

En cada transecta se ajustan dos modelos y se comparan por BIC:
  (a) suave:   v(x) = a + b·x + c·x²
  (b) escalón: v(x) = a + b·x + (h/2)·(1 + erf((x − x0)/w))   (rampa + escalón erf)
Se declara ESCALÓN si ΔBIC = BIC_suave − BIC_escalón > 10 y |h| > 3·MAD del residuo.
El ancho w clasifica: w ≤ 120 m → candidato a FALLA; 300–1000 m → FLEXURA.

Salidas: calera_transectas.png + _data/transect_steps.csv

    ~/miniforge3/bin/mamba run -n insar python exploraciones/calera/transectas.py
    ... transectas.py --src ../../t18_f1050 --suffix _80m
"""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from pyproj import Transformer
from scipy.ndimage import map_coordinates
from scipy.special import erf

from gradiente import load_velocity, smooth_robust, HERE, DATA, CONC, BLOQUE_ID

# transectas largas fijas [(nombre, lon_a, lat_a, lon_b, lat_b)] — ejes del bowl
FIJAS = [
    ("A-A' (NW-SE)", -69.155, -38.21, -68.90, -38.42),
    ("B-B' (SW-NE)", -69.15, -38.42, -68.90, -38.20),
]
W_GRID = [40, 80, 120, 200, 300, 500, 800, 1200]  # anchos de escalón a probar [m]
DBIC_MIN = 10.0


def bic(rss, n, k):
    return n * np.log(max(rss, 1e-12) / n) + k * np.log(n)


def fit_models(x, y):
    """ajusta suave vs rampa+escalón; devuelve dict con ΔBIC, x0, w, h y curvas."""
    ok = np.isfinite(y)
    if ok.sum() < 20:
        return None
    x, y = x[ok], y[ok]
    n = len(x)
    # (a) suave cuadrático
    A2 = np.column_stack([np.ones(n), x, x**2])
    c2, rss2, *_ = np.linalg.lstsq(A2, y, rcond=None)
    rss2 = float(((y - A2 @ c2) ** 2).sum())
    # (b) cuadrático + escalón erf: mismo fondo curvo que (a), así la erf no absorbe
    # el flanco del bowl; lineal en (a, b, c, h) para (x0, w) fijos → grid search
    best = None
    for x0 in np.linspace(x[0] + 0.2 * (x[-1] - x[0]), x[0] + 0.8 * (x[-1] - x[0]), 60):
        for w in W_GRID:
            s = 0.5 * (1 + erf((x - x0) / w))
            A3 = np.column_stack([np.ones(n), x, x**2, s])
            c3, *_ = np.linalg.lstsq(A3, y, rcond=None)
            rss3 = float(((y - A3 @ c3) ** 2).sum())
            if best is None or rss3 < best[0]:
                best = (rss3, x0, w, c3)
    rss3, x0, w, c3 = best
    dbic = bic(rss2, n, 3) - bic(rss3, n, 6)  # (x0, w) cuentan como parámetros
    modelo = A2 @ c3[:3] + c3[3] * 0.5 * (1 + erf((x - x0) / w))
    resid = y - modelo
    mad = float(np.median(np.abs(resid - np.median(resid)))) * 1.4826
    h = float(c3[3])
    clase = ("falla" if w <= 120 else "flexura" if 300 <= w <= 1200 else "indef.")
    return dict(x=x, y=y, dbic=float(dbic), x0=float(x0), w=float(w), h=h, mad=mad,
                es_escalon=bool(dbic > DBIC_MIN and abs(h) > 3 * mad), clase=clase,
                suave=A2 @ c2, escalon=modelo)


def sample(v, g, xa, ya, xb, yb, step=None):
    """muestreo bilineal de v entre (xa,ya)-(xb,yb) UTM; devuelve dist [m] y valores."""
    step = step or abs(g["dx"])
    L = float(np.hypot(xb - xa, yb - ya))
    n = max(int(L / step), 30)
    xs = np.linspace(xa, xb, n); ys = np.linspace(ya, yb, n)
    cols = (xs - g["x0"]) / g["dx"] - 0.5
    rows = (ys - g["y0"]) / g["dy"] - 0.5
    vals = map_coordinates(v, [rows, cols], order=1, mode="constant", cval=np.nan)
    return np.linspace(0, L, n), vals


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=str(HERE / "mintpy_int40"))
    ap.add_argument("--suffix", default="")
    args = ap.parse_args()

    v, g = load_velocity(Path(args.src))
    vs = smooth_robust(v)
    tr_fw = Transformer.from_crs("EPSG:4326", f"EPSG:{g['epsg']}", always_xy=True)
    tr_inv = Transformer.from_crs(f"EPSG:{g['epsg']}", "EPSG:4326", always_xy=True)

    # transectas: fijas + perpendicular por lineamiento candidato
    tset = []
    for name, lo_a, la_a, lo_b, la_b in FIJAS:
        (xa, xb), (ya, yb) = tr_fw.transform([lo_a, lo_b], [la_a, la_b])
        tset.append((name, xa, ya, xb, yb, None))
    cand_file = DATA / f"grad_candidates{args.suffix}.geojson"
    cands = json.load(open(cand_file))["features"] if cand_file.exists() else []
    for f in cands:
        cc = f["geometry"]["coordinates"]
        xs, ys = tr_fw.transform([p[0] for p in cc], [p[1] for p in cc])
        xs, ys = np.asarray(xs), np.asarray(ys)
        arco = np.concatenate([[0], np.cumsum(np.hypot(np.diff(xs), np.diff(ys)))])
        largo = f["properties"]["largo_km"]
        # lineamientos largos: 3 perpendiculares (25/50/75 % del arco) para ver si
        # el escalón persiste a lo largo del rumbo; cortos: solo el centro
        fracs = [(0.25, "a"), (0.5, "b"), (0.75, "c")] if largo >= 2.0 else [(0.5, "")]
        for fr, sub in fracs:
            s0 = fr * arco[-1]
            i = int(np.searchsorted(arco, s0))
            i = min(max(i, 0), len(xs) - 1)
            cx, cy = float(xs[i]), float(ys[i])
            # azimut local: PCA de los vértices a < 700 m de arco del punto
            cerca = np.abs(arco - s0) < 700
            lx, ly = (xs[cerca], ys[cerca]) if cerca.sum() >= 3 else (xs, ys)
            dxy = np.column_stack([lx - lx.mean(), ly - ly.mean()])
            _, _, vt = np.linalg.svd(dxy, full_matrices=False)
            az_loc = (np.degrees(np.arctan2(vt[0][0], vt[0][1])) + 360) % 180
            az = np.radians(az_loc + 90.0)                       # perpendicular
            dx, dy = np.sin(az) * 2000, np.cos(az) * 2000        # 4 km centrada
            tset.append((f"L{f['properties']['id']}{sub} ⊥", cx - dx, cy - dy,
                         cx + dx, cy + dy, f["properties"]["id"]))

    rows_csv, fits = [], []
    for name, xa, ya, xb, yb, lid in tset:
        d, vals = sample(vs, g, xa, ya, xb, yb)
        if lid is None:
            # transecta larga fija: SOLO visual — el test sintético mostró que el
            # contraste suave-vs-escalón no es confiable en ventanas >> 4 km
            # (el fondo no-cuadrático produce falsos positivos)
            fits.append((name, xa, ya, xb, yb,
                         dict(x=d, y=vals, es_escalon=False, solo_visual=True)))
            continue
        r = fit_models(d, vals)
        if r is None:
            continue
        # x0 en lon/lat
        fx = xa + (xb - xa) * (r["x0"] / d[-1]); fy = ya + (yb - ya) * (r["x0"] / d[-1])
        lon0, lat0 = tr_inv.transform(fx, fy)
        az_t = float(np.degrees(np.arctan2(xb - xa, yb - ya)) % 360)  # rumbo A→B
        fits.append((name, xa, ya, xb, yb, r))
        rows_csv.append([name, lid or "", round(lon0, 5), round(lat0, 5),
                         round(az_t, 1), round(r["h"], 2), int(r["w"]),
                         round(r["dbic"], 1), r["es_escalon"],
                         r["clase"] if r["es_escalon"] else ""])
        tag = f"ESCALÓN {r['clase']}" if r["es_escalon"] else "suave"
        print(f"{name:14s} ΔBIC {r['dbic']:7.1f}  h {r['h']:+6.2f} mm/año  "
              f"w {r['w']:5.0f} m  → {tag}")

    out_csv = DATA / f"transect_steps{args.suffix}.csv"
    with open(out_csv, "w", newline="") as fcsv:
        wtr = csv.writer(fcsv)
        wtr.writerow(["transecta", "lineamiento", "lon_x0", "lat_x0", "az_transecta",
                      "salto_mm_yr", "ancho_m", "dbic", "es_escalon", "clase"])
        wtr.writerows(rows_csv)
    print("persistido:", out_csv)

    # ---------- figura: mapa índice + perfiles apilados ----------
    nprof = len(fits)
    ncols = 2
    nrows = int(np.ceil(nprof / ncols))
    fig = plt.figure(figsize=(16, 4 + 2.1 * nrows))
    gs = fig.add_gridspec(nrows, ncols + 1, width_ratios=[1.35] + [1] * ncols,
                          hspace=0.55, wspace=0.25)

    axm = fig.add_subplot(gs[:, 0])
    ext = [g["x0"], g["x0"] + vs.shape[1] * g["dx"], g["y0"] + vs.shape[0] * g["dy"], g["y0"]]
    vmax = np.nanpercentile(np.abs(vs), 99)
    axm.imshow(vs, extent=ext, cmap="RdBu", norm=TwoSlopeNorm(0, -vmax, vmax))
    gj = json.load(open(CONC))
    geom = next(f["geometry"] for f in gj["features"] if f["properties"].get("id") == BLOQUE_ID)
    rings = geom["coordinates"] if geom["type"] == "Polygon" else [r for p in geom["coordinates"] for r in p]
    for ring in rings:
        xs, ys = tr_fw.transform([p[0] for p in ring], [p[1] for p in ring])
        axm.plot(xs, ys, "k--", lw=1.0)
    for k, (name, xa, ya, xb, yb, r) in enumerate(fits):
        axm.plot([xa, xb], [ya, yb], "-", lw=1.4,
                 color="#00c2a0" if not name.startswith(("A-", "B-")) else "#333")
        axm.annotate(name.split()[0], (xa, ya), fontsize=8, fontweight="bold")
    axm.set_xticks([]); axm.set_yticks([]); axm.set_aspect("equal")
    axm.set_title("Velocidad LOS + transectas")

    for k, (name, xa, ya, xb, yb, r) in enumerate(fits):
        ax = fig.add_subplot(gs[k // ncols, 1 + k % ncols])
        ax.plot(r["x"] / 1000, r["y"], ".", ms=2.5, color="0.45")
        if r.get("solo_visual"):
            ax.set_title(f"{name} — perfil del bowl (solo visual)", fontsize=9)
            ax.grid(alpha=0.25)
            ax.set_ylabel("mm/año", fontsize=8)
            if k // ncols == nrows - 1:
                ax.set_xlabel("distancia [km]")
            continue
        ax.plot(r["x"] / 1000, r["suave"], "-", lw=1.2, color="#888", label="suave")
        ax.plot(r["x"] / 1000, r["escalon"], "-", lw=1.6, color="#b2182b", label="escalón")
        if r["es_escalon"]:
            ax.axvline(r["x0"] / 1000, color="#b2182b", ls=":", lw=1)
            ax.set_title(f"{name} — {r['clase'].upper()}  h={r['h']:+.1f} mm/año  "
                         f"w={r['w']:.0f} m  ΔBIC={r['dbic']:.0f}", fontsize=9, color="#7a1010")
        else:
            ax.set_title(f"{name} — suave (ΔBIC={r['dbic']:.0f})", fontsize=9)
        ax.grid(alpha=0.25)
        if k == len(FIJAS):   # primer panel con ajuste
            ax.legend(fontsize=7)
        if k // ncols == nrows - 1:
            ax.set_xlabel("distancia [km]")
        ax.set_ylabel("mm/año", fontsize=8)

    fig.suptitle("La Calera — perfiles de velocidad y detección de escalones", fontsize=13)
    out_png = HERE / f"calera_transectas{args.suffix}.png"
    fig.savefig(out_png, dpi=140, bbox_inches="tight")
    print("guardado:", out_png)


if __name__ == "__main__":
    main()
