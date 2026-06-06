#!/usr/bin/env python
"""Bandurria Sur — análisis detallado: voidage de reservorio por pozo (elipse orientada al
lateral) vs subsidencia acumulada InSAR, en varios timesteps + panel temporal del bloque.

Universo: los 220 pozos del bloque. 115 tienen TRAYECTORIA (elipse orientada al lateral, en el
centroide de la rama); los 105 restantes (muchos 2024-2025, sin trayectoria cargada todavía) van
en la BOCA como círculo (marcador distinto, menor precisión posicional). Así no quedan pozos
"invisibles" sobre el drenaje reciente.

Mapas (6 timesteps):
  Fondo   = desplazamiento LOS acumulado [mm] a esa fecha (ref 2019-01).
  Elipse  = pozo con trayectoria, orientada al lateral. Círculo = pozo solo-boca.
            Anillo = voidage de producción TOTAL acumulado [rm³]; relleno = parte PETRÓLEO (Np·Bo).
Panel inferior (análisis detallado del bloque):
  Áreas apiladas = voidage acumulado del bloque descompuesto (petróleo/agua/gas) [Mm³ res].
  Eje derecho    = subsidencia mediana sobre los pozos [mm].

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
A_MIN = 260.0                     # marcador mínimo [m] al completarse el pozo (aún sin volumen)
INJ_EC = "#1560d0"               # color inyección de agua

tr = Transformer.from_crs("EPSG:4326", "EPSG:32719", always_xy=True)


def lateral_angle(x, y) -> float:
    pts = np.column_stack([x - x.mean(), y - y.mean()])
    _, _, vt = np.linalg.svd(pts, full_matrices=False)
    return np.degrees(np.arctan2(vt[0][1], vt[0][0]))


def main() -> None:
    wells = json.load(open(DATA / "bsur_wells_all.json"))
    mon = pd.read_csv(DATA / "bsur_monthly_perwell_all.csv").sort_values("ym")
    mon["v_oil"] = mon.prod_pet.clip(lower=0) * BO
    mon["v_wat"] = mon.prod_agua.clip(lower=0) * BW
    mon["v_gas"] = mon.prod_gas.clip(lower=0) * 1000.0 * BG
    mon["v_inj"] = mon.iny_agua.clip(lower=0) * BW
    mon["v_tot"] = mon.v_oil + mon.v_wat + mon.v_gas
    g = mon.groupby("idpozo")
    mon["cum_tot"] = g.v_tot.cumsum()
    mon["cum_oil"] = g.v_oil.cumsum()
    mon["cum_inj"] = g.v_inj.cumsum()

    # geometría: centroide de la rama (con trayectoria) o boca (sin)
    for idp, w in wells.items():
        if w["has_traj"]:
            xs, ys = tr.transform([p[0] for p in w["traj"]], [p[1] for p in w["traj"]])
            xs, ys = np.array(xs), np.array(ys)
            w["cx"], w["cy"] = float(xs.mean()), float(ys.mean())
            w["ang"] = float(lateral_angle(xs, ys))
        else:
            x, y = tr.transform(w["boca"][0], w["boca"][1])
            w["cx"], w["cy"] = float(x), float(y)
            w["ang"] = None

    with h5py.File(TS, "r") as f:
        X0 = float(f.attrs["X_FIRST"]); Y0 = float(f.attrs["Y_FIRST"])
        xstep = float(f.attrs["X_STEP"]); ystep = float(f.attrs["Y_STEP"])
        dates = [d.decode() for d in f["date"][:]]
        allx = np.array([w["cx"] for w in wells.values()])
        ally = np.array([w["cy"] for w in wells.values()])
        c0 = max(int((allx.min() - X0) / xstep) - MARGIN_PX, 0)
        c1 = int((allx.max() - X0) / xstep) + MARGIN_PX
        r0 = max(int((ally.max() - Y0) / ystep) - MARGIN_PX, 0)
        r1 = int((ally.min() - Y0) / ystep) + MARGIN_PX
        idx = np.linspace(0, len(dates) - 1, NPANELS).round().astype(int)
        cube = f["timeseries"][idx, r0:r1, c0:c1] * 1000.0
        wcx = np.array([int((w["cx"] - X0) / xstep) for w in wells.values()])
        wcy = np.array([int((w["cy"] - Y0) / ystep) for w in wells.values()])
        ry0, ry1 = wcy.min(), wcy.max() + 1
        cx0, cx1 = wcx.min(), wcx.max() + 1
        crop = f["timeseries"][:, ry0:ry1, cx0:cx1]
        ly, lx = wcy - ry0, wcx - cx0
        sub_t = np.nanmedian(crop[:, ly, lx], axis=1) * 1000.0
        sel_dates = [dates[i] for i in idx]
        ext = [X0 + c0 * xstep, X0 + c1 * xstep, Y0 + r1 * ystep, Y0 + r0 * ystep]

    vmin = float(np.nanpercentile(cube[-1], 1))
    vmax = float(max(0.0, np.nanpercentile(cube, 99)))
    vtot_max = mon.cum_tot.max()

    def axes_for(vol):
        a = A_MAX * np.sqrt(max(vol, 0) / vtot_max)
        return a, a / ASPECT

    def cum_at(ym):
        s = mon[mon.ym <= ym].groupby("idpozo")[["cum_tot", "cum_oil", "cum_inj"]].last()
        return s.to_dict("index")

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
            # aparece a partir de su completion (o, si falta, del 1er volumen)
            comp = w.get("comp")
            c = cum.get(int(idp))
            ct = c["cum_tot"] if c else 0.0
            ci = c["cum_inj"] if c else 0.0
            completed = (comp is not None and ym >= comp) or ct > 0 or ci > 0
            if not completed:
                continue
            if w["has_traj"]:
                ax.plot(*tr.transform([p[0] for p in w["traj"]], [p[1] for p in w["traj"]]),
                        "-", color="0.3", lw=0.4, alpha=0.5, zorder=3)
            ang = w["ang"] if w["has_traj"] else 0.0
            asp = ASPECT if w["has_traj"] else 1.0  # solo-boca = círculo
            ls = "solid" if w["has_traj"] else (0, (2, 1.4))
            # inyección de agua (azul) — misma escala volumétrica
            if ci > 0:
                ai, _ = axes_for(ci); bi = ai / asp
                ax.add_patch(Ellipse((w["cx"], w["cy"]), ai, bi, angle=ang, facecolor=INJ_EC,
                                     edgecolor=INJ_EC, lw=0.8, ls=ls, alpha=0.30, zorder=6))
                ax.add_patch(Ellipse((w["cx"], w["cy"]), ai, bi, angle=ang, facecolor="none",
                                     edgecolor=INJ_EC, lw=0.9, ls=ls, alpha=0.9, zorder=6))
            # producción: anillo = voidage total, relleno = petróleo (mínimo al completarse)
            aw = max(axes_for(ct)[0], A_MIN); bw = aw / asp
            ec = "k" if w["has_traj"] else "#1f4eb4"
            ax.add_patch(Ellipse((w["cx"], w["cy"]), aw, bw, angle=ang, facecolor="none",
                                 edgecolor=ec, lw=0.7, ls=ls, alpha=0.85, zorder=5))
            if c and c["cum_oil"] > 0:
                ao = axes_for(c["cum_oil"])[0]; bo = ao / asp
                ax.add_patch(Ellipse((w["cx"], w["cy"]), ao, bo, angle=ang, facecolor="#1a1a1a",
                                     edgecolor="none", alpha=0.32, zorder=4))
        ax.set_title(ym, fontsize=11)
        ax.set_xticks([]); ax.set_yticks([])

    fig.colorbar(im, ax=map_axes, shrink=0.55, location="right", pad=0.01,
                 label="Desplazamiento LOS acumulado [mm]  (− = subsidencia)")

    leg = []
    for frac in (0.3, 0.6, 1.0):
        aw, bw = axes_for(frac * vtot_max)
        leg.append(map_axes[0].add_patch(Ellipse((np.nan, np.nan), aw, bw, angle=0,
                   facecolor="none", edgecolor="k", lw=0.7,
                   label=f"{frac*vtot_max/1e3:.0f} mil rm³")))
    leg.append(map_axes[0].add_patch(Ellipse((np.nan, np.nan), 1, 1, facecolor="#1a1a1a",
               alpha=0.32, label="parte petróleo")))
    leg.append(map_axes[0].add_patch(Ellipse((np.nan, np.nan), 1, 1, facecolor=INJ_EC,
               edgecolor=INJ_EC, alpha=0.4, label="inyección de agua")))
    leg.append(map_axes[0].add_patch(Ellipse((np.nan, np.nan), 1, 1, facecolor="none",
               edgecolor="#1f4eb4", ls=(0, (2, 1.4)), lw=0.9, label="pozo solo-boca (s/trayect.)")))
    map_axes[0].legend(handles=leg, title="Voidage acum. (anillo=total)",
                       loc="lower left", fontsize=7.5, title_fontsize=8, framealpha=0.92)

    axd = fig.add_subplot(gs[2, :])
    blk = mon.groupby("ym")[["v_oil", "v_wat", "v_gas", "v_inj"]].sum().sort_index()
    cumb = blk.cumsum() / 1e6
    t = pd.to_datetime(blk.index + "-01")
    axd.stackplot(t, cumb.v_oil, cumb.v_wat, cumb.v_gas,
                  labels=["petróleo (Np·Bo)", "agua (Wp·Bw)", "gas (Gp·Bg)"],
                  colors=["#4d4d4d", "#74add1", "#f4a582"], alpha=0.9)
    net = cumb.v_oil + cumb.v_wat + cumb.v_gas - cumb.v_inj
    axd.plot(t, net, "k--", lw=1.5, label="voidage NETO (− iny. agua)")
    axd.plot(t, cumb.v_inj, color=INJ_EC, lw=1.6, label="inyección de agua (Wi·Bw)")
    axd.set_ylabel("Voidage acumulado del bloque [Mm³ reservorio]")
    axd.set_xlabel("fecha")
    axd.legend(loc="upper left", fontsize=8, ncol=3)
    axd.grid(alpha=0.25)

    ax2 = axd.twinx()
    td = pd.to_datetime(dates, format="%Y%m%d")
    ax2.plot(td, sub_t, color="#b2182b", lw=2.2, marker="o", ms=2.5,
             label="subsidencia mediana de los pozos")
    ax2.set_ylabel("Desplazamiento LOS mediano [mm]", color="#b2182b")
    ax2.tick_params(axis="y", labelcolor="#b2182b")
    ax2.legend(loc="lower left", fontsize=8)
    axd.set_title("Análisis detallado Bandurria Sur — voidage acumulado del bloque (220 pozos) vs subsidencia",
                  fontsize=11)

    fig.suptitle("Bandurria Sur — voidage por pozo (elipse=trayectoria, círculo=solo boca) "
                 f"vs subsidencia InSAR  ·  ref {dates[0][:4]}-{dates[0][4:6]}", fontsize=14)
    out = HERE / "bsur_timesteps.png"
    fig.savefig(out, dpi=135)
    n_tr = sum(w["has_traj"] for w in wells.values())
    print("guardado:", out, f"| pozos {len(wells)} (trayect {n_tr}, boca {len(wells)-n_tr})")
    print(f"voidage bloque final oil {cumb.v_oil.iloc[-1]:.2f} agua {cumb.v_wat.iloc[-1]:.2f} "
          f"gas {cumb.v_gas.iloc[-1]:.2f} Mm³ | subsid mediana final {sub_t[-1]:.0f} mm")


if __name__ == "__main__":
    main()
