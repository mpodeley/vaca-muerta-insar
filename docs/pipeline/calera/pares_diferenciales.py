#!/usr/bin/env python
"""La Calera — series temporales diferenciales A−B a través de cada escalón detectado.

Para cada escalón confirmado en transect_steps.csv toma dos puntos A y B a ±200 m
del cruce (a lo largo de la transecta), extrae la serie temporal (media 3×3) de
timeseries_ERA5_ramp_demErr.h5 y grafica d(t) = B(t) − A(t) con banda de error.

d(t) es a la vez producto y validación: un escalón real crece de forma monótona,
acoplado a la producción; un artefacto (atmósfera, unwrapping) es ruido sin
tendencia. Overlay: terminaciones de pozos a <2 km y producción acumulada del
bloque (eje derecho, convención del sitio).

Salida: calera_pares_diferenciales.png

    ~/miniforge3/bin/mamba run -n insar python exploraciones/calera/pares_diferenciales.py
    ... pares_diferenciales.py --src ../../t18_f1050 --suffix _80m
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pyproj import Transformer

from gradiente import HERE, DATA

WELLS = DATA / "calera_wells_all.json"
MONTHLY = DATA / "calera_monthly_perwell.csv"
OFF_M = 200.0     # distancia de A y B al cruce [m]
R_POZOS = 2000.0  # radio para marcar terminaciones [m]
MAX_PANELES = 12  # los ΔBIC más altos si hay más


def series_3x3(f, r, c):
    """media y σ de la ventana 3×3 de la serie temporal [mm]."""
    win = f["timeseries"][:, max(r - 1, 0):r + 2, max(c - 1, 0):c + 2] * 1000.0
    flat = win.reshape(win.shape[0], -1)
    return np.nanmean(flat, axis=1), np.nanstd(flat, axis=1) / np.sqrt(flat.shape[1])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=str(HERE / "mintpy_int40"))
    ap.add_argument("--suffix", default="")
    args = ap.parse_args()
    src = Path(args.src)

    steps = pd.read_csv(DATA / f"transect_steps{args.suffix}.csv")
    steps = steps[steps.es_escalon == True].sort_values("dbic", ascending=False)  # noqa: E712
    if len(steps) > MAX_PANELES:
        print(f"({len(steps)} escalones; grafico los {MAX_PANELES} de mayor ΔBIC)")
        steps = steps.head(MAX_PANELES)

    ts_file = src / "timeseries_ERA5_ramp_demErr.h5"
    if not ts_file.exists():
        ts_file = src / "timeseries.h5"
    with h5py.File(ts_file) as f:
        at = dict(f.attrs)
        epsg = at.get("EPSG", "32719")
        epsg = epsg.decode() if isinstance(epsg, bytes) else str(int(float(epsg)))
        x0, y0 = float(at["X_FIRST"]), float(at["Y_FIRST"])
        dx, dy = float(at["X_STEP"]), float(at["Y_STEP"])
        dates = pd.to_datetime([d.decode() for d in f["date"][:]], format="%Y%m%d")
        tr = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)

        curvas = []
        for _, s in steps.iterrows():
            x, y = tr.transform(s.lon_x0, s.lat_x0)
            az = np.radians(s.az_transecta)
            ux, uy = np.sin(az), np.cos(az)
            pts = {}
            for lbl, sgn in (("A", -1), ("B", +1)):
                px, py = x + sgn * OFF_M * ux, y + sgn * OFF_M * uy
                c = int((px - x0) / dx); r = int((py - y0) / dy)
                m, e = series_3x3(f, r, c)
                pts[lbl] = (m, e)
            d = pts["B"][0] - pts["A"][0]
            err = np.hypot(pts["B"][1], pts["A"][1])
            curvas.append((s, d, err))

    wells = json.load(open(WELLS))
    mon = pd.read_csv(MONTHLY)
    blk = mon.groupby("ym")[["prod_pet", "prod_gas", "prod_agua"]].sum().sort_index()
    liq_cum = (blk.prod_pet + blk.prod_agua).cumsum() / 1e6      # Mm³ líquido
    t_prod = pd.to_datetime(blk.index + "-01")

    tr_ll = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    n = len(curvas)
    ncols = 2
    nrows = int(np.ceil(n / ncols))
    fig, axs = plt.subplots(nrows, ncols, figsize=(15, 2.9 * nrows),
                            sharex=True, squeeze=False)
    for k, (s, d, err) in enumerate(curvas):
        ax = axs[k // ncols][k % ncols]
        ax.axhline(0, color="0.8", lw=0.8)
        ax.fill_between(dates, d - err, d + err, color="#b2182b", alpha=0.18, lw=0)
        ax.plot(dates, d, "-", color="#b2182b", lw=1.4, marker="o", ms=2)
        # terminaciones de pozos a < 2 km del cruce
        x, y = tr_ll.transform(s.lon_x0, s.lat_x0)
        comps = []
        for w in wells.values():
            wx, wy = tr_ll.transform(w["boca"][0], w["boca"][1])
            if np.hypot(wx - x, wy - y) <= R_POZOS and w.get("comp"):
                comps.append(w["comp"])
        comps = [cm for cm in comps
                 if dates[0] <= pd.to_datetime(cm + "-01") <= dates[-1]]
        for cm in sorted(set(comps)):
            ax.axvline(pd.to_datetime(cm + "-01"), color="#1560d0", lw=0.8, alpha=0.5)
        ax.set_xlim(dates[0] - pd.Timedelta(days=60), dates[-1] + pd.Timedelta(days=60))
        # tendencia por mitades (¿el escalón crece?)
        half = len(dates) // 2
        for sl_lbl, sl in (("1ª mitad", slice(0, half)), ("2ª mitad", slice(half, None))):
            tt = (dates[sl] - dates[0]).days / 365.25
            ok = np.isfinite(d[sl])
            if ok.sum() > 5:
                p = np.polyfit(tt[ok], d[sl][ok], 1)
                ax.plot(dates[sl], np.polyval(p, tt), "--", color="0.3", lw=1)
        ax2 = ax.twinx()
        ax2.plot(t_prod, liq_cum, color="0.55", lw=1.2, alpha=0.8)
        ax2.set_ylabel("líquido acum. [Mm³]", color="0.45", fontsize=7)
        ax2.tick_params(axis="y", labelcolor="0.45", labelsize=7)
        ax.set_title(f"{s.transecta}: d(t)=B−A  salto {s.salto_mm_yr:+.1f} mm/año  "
                     f"w={s.ancho_m:.0f} m  [{s.clase}]  ({len(set(comps))} pozos <2 km, azul)",
                     fontsize=9)
        ax.set_ylabel("d(t) [mm]", fontsize=8)
        ax.grid(alpha=0.25)
    for k in range(n, nrows * ncols):
        axs[k // ncols][k % ncols].axis("off")

    fig.suptitle("La Calera — diferenciales punto-a-punto a través de cada escalón "
                 "(A y B a ±200 m del cruce)", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = HERE / f"calera_pares_diferenciales{args.suffix}.png"
    fig.savefig(out, dpi=140)
    print("guardado:", out, f"| {n} escalones")


if __name__ == "__main__":
    main()
