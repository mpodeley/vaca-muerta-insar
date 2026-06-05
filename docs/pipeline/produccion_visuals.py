#!/usr/bin/env python
"""Visuales del cruce producción↔subsidencia: ranking (PNG) + mapa coroplético (HTML)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
CSV = HERE / "produccion_vs_subsidencia.csv"
DATA = Path("/var/home/matias/Projects/estado-del-sistema/public/data")
GEOJSON = DATA / "concesiones_neuquina.geojson"
BAR = HERE / "produccion_ranking.png"
MAP = HERE / "demo_produccion.html"


def ranking():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = pd.read_csv(CSV).sort_values("vel").head(20)[::-1]
    ops = df["operador"].str.replace(r"\s*(S\.A\.|SAU|S\.R\.L\.|SL).*", "", regex=True).str.strip()
    cats = {o: i for i, o in enumerate(sorted(ops.unique()))}
    cmap = plt.get_cmap("tab10")
    colors = [cmap(cats[o] % 10) for o in ops]

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(df["area"], df["vel"], color=colors)
    ax.set_xlabel("Velocidad media de deformación LOS (mm/año)  ·  negativo = subsidencia")
    ax.set_title("Top 20 áreas por subsidencia media — Vaca Muerta (Sentinel-1, 2019–2026)",
                 fontsize=12, weight="bold")
    ax.axvline(0, color="#888", lw=0.8)
    # leyenda de operadores
    from matplotlib.patches import Patch
    handles = [Patch(color=cmap(i % 10), label=o) for o, i in cats.items()]
    ax.legend(handles=handles, fontsize=8, loc="lower left", title="Operador")
    fig.tight_layout()
    fig.savefig(BAR, dpi=150)
    print(f"→ {BAR}")


def choropleth():
    import folium
    from matplotlib import cm, colors as mc

    df = pd.read_csv(CSV).set_index("area")
    gj = json.load(open(GEOJSON))
    vmax = 12.0
    norm = mc.TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    cmap = cm.get_cmap("RdBu")

    m = folium.Map(location=[-38.4, -69.0], zoom_start=9, tiles=None)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/"
        "World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Satélite").add_to(m)

    for f in gj["features"]:
        name = f["properties"]["nombre"]
        if name not in df.index:
            continue
        r = df.loc[name]
        hexc = mc.to_hex(cmap(norm(r.vel)))
        popup = folium.Popup(
            f"<b>{name}</b><br>{r.operador}<br>"
            f"Subsidencia media: <b>{r.vel:.1f} mm/año</b><br>"
            f"Gas acum: {r.gas/1e3:.0f} MMm³ · Pet: {r.pet/1e6:.1f} Mm³ · "
            f"Agua: {r.agua/1e6:.1f} Mm³", max_width=260)
        folium.GeoJson(
            f["geometry"],
            style_function=lambda x, c=hexc: {
                "fillColor": c, "color": "#333", "weight": 0.6, "fillOpacity": 0.75},
            popup=popup, tooltip=f"{name} ({r.vel:.1f} mm/año)").add_to(m)

    # leyenda
    legend = ("""<div style="position:fixed;bottom:24px;left:24px;z-index:9999;
      background:rgba(255,255,255,.92);padding:10px 14px;border-radius:6px;font:12px sans-serif">
      <b>Subsidencia media por área (mm/año)</b><br>
      <span style="color:#b2182b">■</span> −12 (subsidencia) ·
      <span style="color:#f7f7f7;background:#ccc">■</span> 0 ·
      <span style="color:#2166ac">■</span> +12 (uplift)<br>
      <span style="font-size:11px;color:#555">InSAR Sentinel-1 2019–2026 (LOS asc) ×
      concesiones (energianeuquen). Click = producción acumulada.</span></div>""")
    m.get_root().html.add_child(folium.Element(legend))
    folium.LayerControl().add_to(m)
    m.save(str(MAP))
    print(f"→ {MAP}")


if __name__ == "__main__":
    ranking()
    choropleth()
