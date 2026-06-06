#!/usr/bin/env python
"""¿La subsidencia escala con la INTENSIDAD DE FRACTURA por pozo? (Adjunto IV, dato público)

Métricas de intensidad: arena total (tn), agua inyectada en fractura (m³), nº de fracturas,
largo de rama horizontal (m) y sus densidades (arena/m, agua/m, fracturas/m = espaciamiento).
Join por idpozo con coordenadas (capitulo-iv-pozos), filtro AOI, muestreo de velocidad LOS.

    ~/miniforge3/bin/mamba run -n insar python exploraciones/escala_pozo/fractura.py
"""
from __future__ import annotations
import csv, json
from pathlib import Path

import numpy as np
import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = HERE / "_data"
VEL_TIF = ROOT / "t18_f1050" / "_velocity_wgs84.tif"
FRAC_URL = ("http://datos.energia.gob.ar/dataset/71fa2e84-0316-4a1b-af68-7f35e41f58d7/resource/"
            "2280ad92-6ed3-403e-a095-50139863ab0d/download/"
            "datos-de-fractura-de-pozos-de-hidrocarburos-adjunto-iv-actualizacin-diaria.csv")
LON0, LON1, LAT0, LAT1 = -70.6, -68.2, -39.2, -37.3
HDRS = {"User-Agent": "Mozilla/5.0"}
csv.field_size_limit(1 << 24)


def coords() -> dict:
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
                out[idp] = (float(g["coordinates"][0]), float(g["coordinates"][1]))
            except Exception:
                continue
    return out


def main() -> None:
    import rasterio
    from scipy.stats import spearmanr, pearsonr

    fpath = DATA / "fractura_adjiv.csv"
    if not fpath.exists():
        with requests.get(FRAC_URL, headers=HDRS, stream=True, timeout=300) as r:
            r.raise_for_status()
            fpath.write_bytes(r.content)
        print(f"bajado {fpath} ({fpath.stat().st_size/1e6:.1f} MB)")

    fr = pd.read_csv(fpath, encoding="utf-8-sig")
    fr.columns = [c.strip() for c in fr.columns]
    fr = fr[fr["cuenca"].astype(str).str.upper() == "NEUQUINA"].copy()
    print(f"filas Neuquina (frac jobs): {len(fr)}  | rango años: "
          f"{fr['anio_if'].min()}–{fr['anio_if'].max()}  | pozos únicos: {fr['idpozo'].nunique()}")

    num = ["longitud_rama_horizontal_m", "cantidad_fracturas", "arena_bombeada_nacional_tn",
           "arena_bombeada_importada_tn", "agua_inyectada_m3", "co2_inyectado_m3",
           "presion_maxima_psi"]
    for c in num:
        fr[c] = pd.to_numeric(fr[c], errors="coerce")
    # agregar por pozo (puede haber varias etapas/filas)
    g = fr.groupby("idpozo").agg(
        largo=("longitud_rama_horizontal_m", "max"),
        nfrac=("cantidad_fracturas", "sum"),
        arena=("arena_bombeada_nacional_tn", "sum"),
        arena_imp=("arena_bombeada_importada_tn", "sum"),
        agua=("agua_inyectada_m3", "sum"),
        pres=("presion_maxima_psi", "max"),
    ).reset_index()
    g["arena_tot"] = g.arena.fillna(0) + g.arena_imp.fillna(0)
    g["arena_m"] = g.arena_tot / g.largo.replace(0, np.nan)
    g["agua_m"] = g.agua / g.largo.replace(0, np.nan)
    g["frac_m"] = g.nfrac / g.largo.replace(0, np.nan)

    cc = coords()
    g["lon"] = g.idpozo.map(lambda i: cc.get(i, (np.nan, np.nan))[0])
    g["lat"] = g.idpozo.map(lambda i: cc.get(i, (np.nan, np.nan))[1])
    g = g.dropna(subset=["lon", "lat"])
    g = g[g.lon.between(LON0, LON1) & g.lat.between(LAT0, LAT1)]
    with rasterio.open(VEL_TIF) as src:
        g["vel"] = [float(next(src.sample([(lo, la)]))[0]) for lo, la in zip(g.lon, g.lat)]
    g = g[np.isfinite(g.vel) & (g.vel != 0.0)]
    print(f"pozos fracturados en AOI con velocidad: {len(g)}  vel_med={g.vel.median():+.2f}")

    print("\n-- vel vs intensidad de fractura (Spearman) --")
    for c, lab in [("arena_tot", "arena total (tn)"), ("agua", "agua fractura (m³)"),
                   ("nfrac", "nº fracturas"), ("largo", "largo rama (m)"),
                   ("arena_m", "arena/m"), ("agua_m", "agua/m"), ("frac_m", "fracturas/m")]:
        d = g[g[c] > 0]
        if len(d) < 20:
            print(f"  {lab:18s} n={len(d)} (insuf)"); continue
        rho, ps = spearmanr(d[c], d.vel)
        r, pr = pearsonr(np.log10(d[c].clip(lower=1e-6)), d.vel)
        print(f"  {lab:18s} n={len(d):5d}  Spearman rho={rho:+.3f} (p={ps:.1e})  Pearson(log) r={r:+.3f}")

    g.to_csv(HERE / "fractura_vel.csv", index=False)
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(13, 5.2))
    d = g[g.arena_tot > 0]
    ax[0].scatter(d.arena_tot, d.vel, s=10, alpha=0.5, c=d.vel.clip(-15, 4), cmap="RdBu",
                  vmin=-15, vmax=4)
    ax[0].axhline(0, color="#999", lw=0.8)
    ax[0].set_xlabel("Arena bombeada total (tn)"); ax[0].set_ylabel("Velocidad LOS (mm/yr)")
    ax[0].set_title(f"Intensidad de fractura vs subsidencia (n={len(d)})")
    d2 = g[g.agua_m > 0]
    ax[1].scatter(d2.agua_m, d2.vel, s=10, alpha=0.5, c=d2.vel.clip(-15, 4), cmap="RdBu",
                  vmin=-15, vmax=4)
    ax[1].axhline(0, color="#999", lw=0.8)
    ax[1].set_xlabel("Agua de fractura por metro de rama (m³/m)")
    ax[1].set_ylabel("Velocidad LOS (mm/yr)"); ax[1].set_title("Densidad de fractura vs subsidencia")
    fig.tight_layout(); fig.savefig(HERE / "fractura.png", dpi=130)
    print(f"\nfigura -> {HERE / 'fractura.png'}")


if __name__ == "__main__":
    main()
