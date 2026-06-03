#!/usr/bin/env python
"""Series temporales puntuales: ¿la subsidencia es estacional o acumulativa?

Para apoyar la interpretación: grafica el desplazamiento LOS acumulado vs tiempo
en (a) el punto MÁS subsidente y (b) un punto ESTABLE de referencia. Si el punto
subsidente oscila con las estaciones → apunta a humedad de suelo / riego; si baja
de forma sostenida → apunta a extracción de agua / compactación.

    conda activate insar
    cd fase1 && python point_timeseries.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
TS = HERE / "timeseries_ERA5_ramp_demErr.h5"
VEL = HERE / "velocity.h5"
MASK = HERE / "maskTempCoh.h5"
OUT = HERE / "point_timeseries.png"


def _dt(d: str) -> date:
    return date(int(d[:4]), int(d[4:6]), int(d[6:8]))


def main() -> None:
    import h5py
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with h5py.File(VEL, "r") as h:
        vel = h["velocity"][:] * 1000.0  # mm/año
    with h5py.File(MASK, "r") as h:
        mask = h["mask"][:].astype(bool)
    with h5py.File(TS, "r") as h:
        ts = h["timeseries"][:] * 1000.0  # mm
        dates = [d.decode() for d in h["date"][:]]
        ref_y, ref_x = int(h.attrs["REF_Y"]), int(h.attrs["REF_X"])

    days = np.array([(_dt(d) - _dt(dates[0])).days for d in dates])

    # promedio por ZONA (reduce ruido ~/sqrt(N)): zona de máxima subsidencia vs zona estable
    v = np.where(mask, vel, np.nan)
    sub_zone = mask & (v < -8.0)          # subsidencia clara
    sta_zone = mask & (np.abs(v) < 0.5)   # estable
    n_sub, n_sta = int(sub_zone.sum()), int(sta_zone.sum())

    def zone_series(zone):
        # serie media (referida a la 1ª fecha) sobre todos los pixels de la zona
        rel = ts - ts[0]
        return np.array([np.nanmean(rel[i][zone]) for i in range(len(dates))])

    sub_s, sta_s = zone_series(sub_zone), zone_series(sta_zone)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.axhline(0, color="#bbb", lw=0.8)
    ax.plot(days, sub_s, "o-", color="#b2182b", lw=1.8, ms=4,
            label=f"Zona de máxima subsidencia (media de {n_sub} px, vel < −8 mm/año)")
    ax.plot(days, sta_s, "o-", color="#2166ac", lw=1.8, ms=4,
            label=f"Zona estable (media de {n_sta} px, |vel| < 0.5 mm/año)")
    # marcas de año
    for yr in sorted({_dt(d).year for d in dates}):
        d0 = (date(yr, 1, 1) - _dt(dates[0])).days
        if days.min() <= d0 <= days.max():
            ax.axvline(d0, color="#eee", lw=1, zorder=0)
            ax.text(d0 + 5, ax.get_ylim()[0], str(yr), fontsize=8, color="#999", va="bottom")

    ax.set_xlabel(f"Días desde {dates[0]}")
    ax.set_ylabel("Desplazamiento LOS acumulado (mm)")
    ax.set_title("Serie temporal de deformación — punto subsidente vs estable\n"
                 "(¿oscilación estacional → humedad/riego · descenso sostenido → extracción?)",
                 fontsize=12)
    ax.legend(loc="lower left", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150)
    print(f"Listo → {OUT}")
    print(f"zona subsidente: {n_sub} px | zona estable: {n_sta} px | ref y/x={ref_y},{ref_x}")
    print(f"subsidente: total={sub_s[-1]:.1f} mm  min={sub_s.min():.1f}  max={sub_s.max():.1f}  "
          f"pico-a-pico={sub_s.max()-sub_s.min():.1f} mm")
    print(f"estable:    total={sta_s[-1]:.1f} mm  pico-a-pico={sta_s.max()-sta_s.min():.1f} mm")


if __name__ == "__main__":
    main()
