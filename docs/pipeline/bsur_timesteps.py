#!/usr/bin/env python
"""Bandurria Sur — análisis detallado: voidage de reservorio por pozo (elipse orientada al
lateral) vs subsidencia acumulada InSAR, en varios timesteps + panel temporal del bloque.

Mapas (6 timesteps):
  Fondo   = desplazamiento LOS acumulado [mm] a esa fecha (ref 2019-01).
  Líneas  = trayectorias horizontales.
  Elipse  = orientada a lo largo del lateral del pozo. Anillo negro = voidage de producción
            TOTAL acumulado [rm³]; relleno = la parte que es PETRÓLEO (Np·Bo). Misma escala
            volumétrica → el anillo visible es agua+gas de reservorio.
Panel inferior (análisis detallado del bloque):
  Áreas apiladas = voidage acumulado del bloque descompuesto (petróleo/agua/gas) [Mm³ res].
  Línea         = voidage NETO (producción − inyección de agua).
  Eje derecho   = subsidencia mediana sobre los pozos [mm].

    ~/miniforge3/bin/mamba run -n insar python exploraciones/escala_pozo/bsur_timesteps.py
"""
from __future__ import annotations
import json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
from matplotlib.gridspec import GridSpec
from pyproj import Transformer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = HERE / "_data"
TS = ROOT / "t18_f1050" / "timeseries_ERA5_ramp_demErr.h5"
NPANELS = 6
MARGIN_PX = 12
BO, BW, BG = 1.4, 1.03, 0.0035   # FVF rm³/sm³ (consistente con voidage.py)
ASPECT = 3.2                      # elipse: eje mayor / eje menor
A_MAX = 2300.0                    # eje mayor [m] para el voidage máximo

tr = Transformer.from_crs("EPSG:4326", "EPSG:32719", always_xy=True)


def lateral_angle(x, y) -> float:
    """Azimut del lateral por PCA (grados, eje mayor)."""
    pts = np.column_stack([x - x.mean(), y - y.mean()])
    _, _, vt = np.linalg.svd(pts, full_matrices=False)
    vx, vy = vt[0]
    return np.degrees(np.arctan2(vy, vx))


def main() -> None:
    wells = json.load(open(DATA / "bsur_wells.json"))
    mon = pd.read_csv(DATA / "bsur_monthly_perwell.csv").sort_values("ym")
    # voidage mensual por pozo [rm³]
    mon["v_oil"] = mon.prod_pet.clip(lower=0) * BO
    mon["v_wat"] = mon.prod_agua.clip(lower=0) * BW
    mon["v_gas"] = mon.prod_gas.clip(lower=0) * 1000.0 * BG
    mon["v_inj"] = mon.iny_agua.clip(lower=0) * BW
    mon["v_tot"] = mon.v_oil + mon.v_wat + mon.v_gas
    g = mon.groupby("idpozo")
    mon["cum_tot"] = g.v_tot.cumsum()
    mon["cum_oil"] = g.v_oil.cumsum()

    # geometría de pozos -> UTM, centroide, azimut del lateral
    for idp, w in wells.items():
        xs, ys = tr.transform([p[0] for p in w["coords"]], [p[1] for p in w["coords"]])
        xs, ys = np.array(xs), np.array(ys)
        w["x"], w["y"] = xs, ys
        w["cx"], w["cy"] = float(xs.mean()), float(ys.mean())
        w["ang"] = lateral_angle(xs, ys)

    with h5py.File(TS, "r") as f:
        X0 = float(f.attrs["X_FIRST"]); Y0 = float(f.attrs["Y_FIRST"])
        xstep = float(f.attrs["X_STEP"]); ystep = float(f.attrs["Y_STEP"])
        dates = [d.decode() for d in f["date"][:]]
        allx = np.concatenate([w["x"] for w in wells.values()])
        ally = np.concatenate([w["y"] for w in wells.values()])
        c0 = max(int((allx.min() - X0) / xstep) - MARGIN_PX, 0)
        c1 = int((allx.max() - X0) / xstep) + MARGIN_PX
        r0 = max(int((ally.max() - Y0) / ystep) - MARGIN_PX, 0)
        r1 = int((ally.min() - Y0) / ystep) + MARGIN_PX
        idx = np.linspace(0, len(dates) - 1, NPANELS).round().astype(int)
        cube = f["timeseries"][idx, r0:r1, c0:c1] * 1000.0          # mm
        # subsidencia mediana sobre los centroides de pozo, todas las fechas (panel temporal)
        wcx = np.array([int((w["cx"] - X0) / xstep) for w in wells.values()])
        wcy = np.array([int((w["cy"] - Y0) / ystep) for w in wells.values()])
        ry0, ry1 = wcy.min(), wcy.max() + 1
        cx0, cx1 = wcx.min(), wcx.max() + 1
        crop = f["timeseries"][:, ry0:ry1, cx0:cx1]            # (T, h, w)
        ly, lx = wcy - ry0, wcx - cx0
        sub_t = np.nanmedian(crop[:, ly, lx], axis=1) * 1000.0  # mm, mediana sobre pozos
        sel_dates = [dates[i] for i in idx]
        ext = [X0 + c0 * xstep, X0 + c1 * xstep, Y0 + r1 * ystep, Y0 + r0 * ystep]

    vmin = float(np.nanpercentile(cube[-1], 1))
    vmax = float(max(0.0, np.nanpercentile(cube, 99)))
    vtot_max = mon.cum_tot.max()

    def area_to_axes(vol):
        a = A_MAX * np.sqrt(max(vol, 0) / vtot_max)
        return a, a / ASPECT  # (mayor, menor)

    def cum_at(ym):
        s = mon[mon.ym <= ym].groupby("idpozo")[["cum_tot", "cum_oil"]].last()
        return s.to_dict("index")

    # ---- figura ----
    fig = plt.figure(figsize=(16.5, 13))
    gs = GridSpec(3, 3, figure=fig, height_ratios=[1, 1, 0.85],
                  hspace=0.12, wspace=0.06, left=0.04, right=0.91, top=0.93, bottom=0.07)
    map_axes = [fig.add_subplot(gs[i // 3, i % 3]) for i in range(NPANELS)]

    im = None
    for k, (ax, d) in enumerate(zip(map_axes, sel_dates)):
        ym = f"{d[:4]}-{d[4:6]}"
        im = ax.imshow(cube[k], extent=ext, origin="upper", cmap="RdYlBu",
                       vmin=vmin, vmax=vmax, aspect="equal")
        cum = cum_at(ym)
        for idp, w in wells.items():
            ax.plot(w["x"], w["y"], "-", color="0.3", lw=0.4, alpha=0.5, zorder=3)
            c = cum.get(int(idp))
            if not c or c["cum_tot"] <= 0:
                continue
            aw, bw = area_to_axes(c["cum_tot"])
            ax.add_patch(Ellipse((w["cx"], w["cy"]), aw, bw, angle=w["ang"],
                                 facecolor="none", edgecolor="k", lw=0.7, alpha=0.85, zorder=5))
            ao, bo = area_to_axes(c["cum_oil"])
            ax.add_patch(Ellipse((w["cx"], w["cy"]), ao, bo, angle=w["ang"],
                                 facecolor="#1a1a1a", edgecolor="none", alpha=0.35, zorder=4))
        ax.set_title(f"{ym}", fontsize=11)
        ax.set_xticks([]); ax.set_yticks([])

    cb = fig.colorbar(im, ax=map_axes, shrink=0.55, location="right", pad=0.01,
                      label="Desplazamiento LOS acumulado [mm]  (− = subsidencia)")

    # leyenda de tamaño de elipse (voidage)
    leg = []
    for frac in (0.3, 0.6, 1.0):
        aw, bw = area_to_axes(frac * vtot_max)
        leg.append(map_axes[0].add_patch(Ellipse((np.nan, np.nan), aw, bw, angle=0,
                   facecolor="none", edgecolor="k", lw=0.7,
                   label=f"{frac*vtot_max/1e3:.0f} mil rm³")))
    h0 = map_axes[0].add_patch(Ellipse((np.nan, np.nan), 1, 1, facecolor="#1a1a1a",
                                       alpha=0.35, label="parte petróleo"))
    map_axes[0].legend(handles=leg + [h0], title="Voidage acum. (anillo=total)",
                       loc="lower left", fontsize=7.5, title_fontsize=8, framealpha=0.92)

    # ---- panel de análisis detallado ----
    axd = fig.add_subplot(gs[2, :])
    blk = mon.groupby("ym")[["v_oil", "v_wat", "v_gas", "v_inj"]].sum().sort_index()
    cumb = blk.cumsum() / 1e6  # Mm³
    t = pd.to_datetime(blk.index + "-01")
    axd.stackplot(t, cumb.v_oil, cumb.v_wat, cumb.v_gas,
                  labels=["petróleo (Np·Bo)", "agua (Wp·Bw)", "gas (Gp·Bg)"],
                  colors=["#4d4d4d", "#74add1", "#f4a582"], alpha=0.9)
    net = (cumb.v_oil + cumb.v_wat + cumb.v_gas) - cumb.v_inj
    axd.plot(t, net, "k--", lw=1.6, label="voidage NETO (− iny. agua)")
    axd.set_ylabel("Voidage acumulado del bloque [Mm³ reservorio]")
    axd.set_xlabel("fecha")
    axd.legend(loc="upper left", fontsize=8, ncol=2)
    axd.grid(alpha=0.25)

    ax2 = axd.twinx()
    td = pd.to_datetime([d for d in dates], format="%Y%m%d")
    ax2.plot(td, sub_t, color="#b2182b", lw=2.2, marker="o", ms=2.5,
             label="subsidencia mediana de los pozos")
    ax2.set_ylabel("Desplazamiento LOS mediano [mm]", color="#b2182b")
    ax2.tick_params(axis="y", labelcolor="#b2182b")
    ax2.legend(loc="lower left", fontsize=8)
    axd.set_title("Análisis detallado Bandurria Sur — voidage acumulado del bloque vs subsidencia",
                  fontsize=11)

    fig.suptitle("Bandurria Sur — voidage por pozo (elipse: anillo=total, relleno=petróleo) "
                 f"vs subsidencia InSAR  ·  ref {dates[0][:4]}-{dates[0][4:6]}", fontsize=14)
    out = HERE / "bsur_timesteps.png"
    fig.savefig(out, dpi=135)
    print("guardado:", out)
    print("fechas:", sel_dates)
    print(f"color subsid: [{vmin:.0f},{vmax:.0f}] mm | voidage max/pozo {vtot_max/1e3:.0f} mil rm³")
    print(f"voidage bloque final: oil {cumb.v_oil.iloc[-1]:.2f} | agua {cumb.v_wat.iloc[-1]:.2f} "
          f"| gas {cumb.v_gas.iloc[-1]:.3f} | NETO {net.iloc[-1]:.2f} Mm³")
    print(f"subsidencia mediana final: {sub_t[-1]:.0f} mm")


if __name__ == "__main__":
    main()
