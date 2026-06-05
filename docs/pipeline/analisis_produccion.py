#!/usr/bin/env python
"""Cruce producción acumulada (por área) vs subsidencia media InSAR.

Para cada concesión (polígono) calcula la velocidad media de deformación dentro
del área (zonal stats sobre _velocity_wgs84.tif) y la junta con la producción
acumulada gas/petróleo/agua (estado-del-sistema). Imprime tabla + correlaciones.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask as rio_mask

HERE = Path(__file__).parent
VEL = HERE / "_velocity_wgs84.tif"
DATA = Path("/var/home/matias/Projects/estado-del-sistema/public/data")
GEOJSON = DATA / "concesiones_neuquina.geojson"
HIST = DATA / "produccion_neuquina_historico.json"
MIN_PIX = 200  # mínimo de pixels confiables dentro del área para considerarla


def load_production() -> pd.DataFrame:
    d = json.load(open(HIST))["data"]
    df = pd.DataFrame(d)
    agg = df.groupby("area", as_index=False).agg(
        gas=("gas_acumulado_mm3", "sum"),
        pet=("pet_acumulado_m3", "sum"),
        agua=("agua_acumulada_m3", "sum"),
    )
    return agg.set_index("area")


def zonal_mean(src, geom) -> tuple[float, int]:
    try:
        out, _ = rio_mask(src, [geom], crop=True, nodata=np.nan, filled=True)
    except Exception:
        return np.nan, 0
    v = out[0]
    v = v[np.isfinite(v)]
    return (float(v.mean()), v.size) if v.size else (np.nan, 0)


def main() -> None:
    prod = load_production()
    gj = json.load(open(GEOJSON))
    rows = []
    with rasterio.open(VEL) as src:
        for f in gj["features"]:
            name = f["properties"]["nombre"]
            op = f["properties"].get("operador", "")
            mean_v, n = zonal_mean(src, f["geometry"])
            if n < MIN_PIX or name not in prod.index:
                continue
            p = prod.loc[name]
            rows.append(dict(area=name, operador=op, vel=mean_v, npix=n,
                             gas=p.gas, pet=p.pet, agua=p.agua))
    df = pd.DataFrame(rows).sort_values("vel")
    pd.set_option("display.width", 160, "display.max_rows", 100)
    print(f"\n{len(df)} áreas con ≥{MIN_PIX} px confiables dentro del raster\n")
    show = df.copy()
    show["vel"] = show["vel"].round(1)
    for c in ["gas", "pet", "agua"]:
        show[c] = (show[c] / 1e6).round(1)  # millones de unidades
    print(show[["area", "operador", "vel", "npix", "gas", "pet", "agua"]].to_string(index=False))
    print("\n(vel = mm/año, negativo=subsidencia; gas Mmm3, pet/agua Mm3 acumulados 2006-2026)\n")

    # correlaciones (vel vs log producción)
    from scipy.stats import pearsonr, spearmanr
    print("Correlación velocidad-media vs producción acumulada (log):")
    for c in ["gas", "pet", "agua"]:
        x = np.log10(df[c].clip(lower=1)); y = df["vel"]
        pr = pearsonr(x, y); sp = spearmanr(x, y)
        print(f"  {c:5s}: Pearson r={pr.statistic:+.2f} (p={pr.pvalue:.3f})  "
              f"Spearman ρ={sp.statistic:+.2f} (p={sp.pvalue:.3f})")
    print("\n(r negativo = más producción → velocidad más negativa = más subsidencia)")
    df.to_csv(HERE / "produccion_vs_subsidencia.csv", index=False)
    print(f"→ {HERE/'produccion_vs_subsidencia.csv'}")


if __name__ == "__main__":
    main()
