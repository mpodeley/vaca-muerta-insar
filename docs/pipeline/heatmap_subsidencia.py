#!/usr/bin/env python
"""Heatmap estático de subsidencia sobre el clúster productivo (PNG presentable).

Lee la velocidad enmascarada en lat/lon (_velocity_wgs84.tif, generado por
04_export_visual.py) y produce heatmap_subsidencia.png: mapa de calor con escala
divergente (rojo = subsidencia, azul = uplift), los bloques del clúster marcados,
colorbar en mm/año y subtítulo con método/caveats.

    conda activate insar
    cd fase1 && python heatmap_subsidencia.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

import aoi

HERE = Path(__file__).parent
SRC = HERE / "_velocity_wgs84.tif"  # velocidad mm/año, EPSG:4326, enmascarada
OUT = HERE / "heatmap_subsidencia.png"
CONCESIONES = Path("/var/home/matias/Projects/estado-del-sistema/public/data/"
                   "concesiones_neuquina.geojson")


def _plot_concesiones(ax) -> None:
    """Dibuja solo los contornos de las concesiones (lon/lat), sin relleno."""
    import json
    if not CONCESIONES.exists():
        return
    gj = json.load(open(CONCESIONES))
    for f in gj["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            ring = np.array(poly[0])  # anillo exterior
            ax.plot(ring[:, 0], ring[:, 1], color="#222", lw=0.4, alpha=0.45, zorder=4)


def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import rasterio
    from matplotlib import colors

    if not SRC.exists():
        sys.exit(f"No existe {SRC}. Corré 04_export_visual.py primero.")

    with rasterio.open(SRC) as s:
        v = s.read(1)
        w, sth, e, n = s.bounds.left, s.bounds.bottom, s.bounds.right, s.bounds.top

    finite = v[np.isfinite(v)]
    vmax = float(np.nanpercentile(np.abs(finite), 98)) or 10.0
    norm = colors.TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)

    fig, ax = plt.subplots(figsize=(10, 9))
    ax.set_facecolor("#dfe3e6")  # gris donde no hay dato (baja coherencia / agua)
    im = ax.imshow(
        v, extent=[w, e, sth, n], origin="upper",
        cmap="RdBu", norm=norm, interpolation="nearest",
    )

    # Contornos de las concesiones (solo polígonos, sin relleno).
    _plot_concesiones(ax)

    # Solo Añelo como referencia (los yacimientos no se marcan).
    ax.scatter(*aoi.ANELO[::-1], marker="s", s=70, c="black",
               edgecolor="white", zorder=5, label="Añelo")
    ax.annotate("Añelo", aoi.ANELO[::-1], textcoords="offset points",
                xytext=(6, 4), fontsize=9, color="black", weight="bold")

    ax.set_xlim(w, e); ax.set_ylim(sth, n)
    ax.set_xlabel("Longitud"); ax.set_ylabel("Latitud")
    ax.set_title(
        "Velocidad de deformación del suelo (LOS) — clúster productivo Vaca Muerta",
        fontsize=13, weight="bold",
    )
    ax.text(
        0.5, 1.012,
        "Sentinel-1 / SBAS 2019–2026 (track 18 ASC, frame 1050) · corrección "
        "troposférica ERA5 · pixels con coherencia temporal >0.7",
        transform=ax.transAxes, ha="center", va="bottom", fontsize=8.5, color="#555",
    )
    cb = fig.colorbar(im, ax=ax, shrink=0.85, pad=0.02)
    cb.set_label("mm/año   (negativo = subsidencia, positivo = uplift)")
    fig.tight_layout()
    fig.savefig(OUT, dpi=160, bbox_inches="tight")
    print(f"Listo → {OUT}")


if __name__ == "__main__":
    main()
