#!/usr/bin/env python
"""Análisis escala-pozo (rápido, sin re-bajar): productores vs inyectores, inyección↔velocidad,
y Bandurria Norte/Sur a escala pozo. Usa _data/pozos_agg.csv (de fetch_aggregate.py) +
_data/capitulo_iv_pozos.csv (coords de TODOS los pozos) + velocidad InSAR del paper.

    ~/miniforge3/bin/mamba run -n insar python exploraciones/escala_pozo/analyze.py
"""
from __future__ import annotations
import csv, json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = HERE / "_data"
VEL_TIF = ROOT / "t18_f1050" / "_velocity_wgs84.tif"
LON0, LON1, LAT0, LAT1 = -70.6, -68.2, -39.2, -37.3
csv.field_size_limit(1 << 24)


def coords() -> dict:
    """idpozo -> (lon, lat) wellhead, desde capitulo-iv-pozos (Point)."""
    out = {}
    with open(DATA / "capitulo_iv_pozos.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if (row.get("cuenca") or "").strip().upper() != "NEUQUINA":
                continue
            gj = row.get("geojson")
            if not gj:
                continue
            try:
                idp = int(row["idpozo"]); g = json.loads(gj)
                if g["type"] != "Point":
                    continue
                lon, lat = float(g["coordinates"][0]), float(g["coordinates"][1])
            except Exception:
                continue
            out[idp] = (lon, lat)
    return out


def main() -> None:
    import rasterio
    cc = coords()
    agg = pd.read_csv(DATA / "pozos_agg.csv")
    agg["lon"] = agg.idpozo.map(lambda i: cc.get(i, (np.nan, np.nan))[0])
    agg["lat"] = agg.idpozo.map(lambda i: cc.get(i, (np.nan, np.nan))[1])
    agg = agg.dropna(subset=["lon", "lat"])
    agg = agg[(agg.lon.between(LON0, LON1)) & (agg.lat.between(LAT0, LAT1))]
    print(f"pozos en AOI con coords: {len(agg)}")

    with rasterio.open(VEL_TIF) as src:
        vals = [next(src.sample([(lo, la)]))[0] for lo, la in zip(agg.lon, agg.lat)]
    agg["vel"] = np.array(vals, float)
    agg = agg[np.isfinite(agg.vel) & (agg.vel != 0.0)]
    print(f"pozos con velocidad válida: {len(agg)}")

    # clasificar
    prod = agg.prod_pet + agg.prod_gas
    agg["es_inyector"] = (agg.iny_agua > 0) & (prod < agg.iny_agua * 0.01)
    agg["es_productor"] = (prod > 0) & (agg.iny_agua <= prod * 0.01)
    inj = agg[agg.es_inyector]; pro = agg[agg.es_productor]
    print(f"\ninyectores: {len(inj)}  (vel media {inj.vel.mean():+.2f} mm/yr, "
          f"mediana {inj.vel.median():+.2f})")
    print(f"productores: {len(pro)} (vel media {pro.vel.mean():+.2f} mm/yr, "
          f"mediana {pro.vel.median():+.2f})")
    print(f"% inyectores en uplift (vel>0): {100*(inj.vel>0).mean():.0f}%  | "
          f"productores en uplift: {100*(pro.vel>0).mean():.0f}%")

    from scipy.stats import spearmanr, mannwhitneyu
    if len(inj) > 10 and len(pro) > 10:
        u, p = mannwhitneyu(inj.vel, pro.vel, alternative="greater")
        print(f"Mann-Whitney inyectores>productores en velocidad: p={p:.1e}")
    d = agg[agg.iny_agua > 0]
    if len(d) > 20:
        rho, ps = spearmanr(np.log10(d.iny_agua), d.vel)
        print(f"corr iny_agua↔vel (n={len(d)}): Spearman rho={rho:+.3f} (p={ps:.1e})")

    # Bandurria a escala pozo
    print("\n=== BANDURRIA (escala pozo) ===")
    for c in sorted([x for x in agg.conc.unique() if "BANDURRIA" in str(x).upper()]):
        s = agg[agg.conc == c]
        print(f"  {c}: n={len(s)}  vel_med={s.vel.median():+.2f}  "
              f"gas={s.prod_gas.sum():.0f}  pet={s.prod_pet.sum():.0f}  "
              f"iny_agua={s.iny_agua.sum():.0f}  inyectores={int(s.es_inyector.sum())}")

    agg.to_csv(HERE / "pozos_inyeccion.csv", index=False)

    # figura: mapa inyectores vs productores
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(13, 5.4))
    sc = ax[0].scatter(pro.lon, pro.lat, s=8, c=pro.vel.clip(-12, 4), cmap="RdBu",
                       vmin=-12, vmax=4)
    ax[0].scatter(inj.lon, inj.lat, s=22, facecolors="none", edgecolors="lime", lw=0.8,
                  label=f"inyectores (n={len(inj)})")
    ax[0].legend(loc="upper right", fontsize=8)
    ax[0].set_title("Productores (color=vel) e inyectores (verde)")
    ax[0].set_xlabel("Lon"); ax[0].set_ylabel("Lat")
    fig.colorbar(sc, ax=ax[0], shrink=0.85, label="mm/yr")
    bins = np.linspace(-20, 8, 40)
    ax[1].hist(pro.vel, bins=bins, alpha=0.6, density=True, label="productores", color="#b2182b")
    ax[1].hist(inj.vel, bins=bins, alpha=0.6, density=True, label="inyectores", color="#2166ac")
    ax[1].axvline(0, color="#444", lw=0.8)
    ax[1].set_xlabel("Velocidad LOS (mm/yr)"); ax[1].set_ylabel("densidad")
    ax[1].set_title("Distribución de velocidad"); ax[1].legend()
    fig.tight_layout(); fig.savefig(HERE / "inyeccion.png", dpi=130)
    print(f"\nfigura -> {HERE / 'inyeccion.png'}")


if __name__ == "__main__":
    main()
