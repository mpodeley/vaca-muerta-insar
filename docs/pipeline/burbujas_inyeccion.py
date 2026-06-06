#!/usr/bin/env python
"""Mapa de 'burbujas' de inyección: cada inyector dibujado con el RADIO real del volumen de agua
inyectada acumulada, asumiendo un espesor (h) y porosidad (φ) del horizonte receptor.

Modelo radial idealizado: el agua inyectada (volumen de reservorio V = iny_agua·Bw) llena el poro de
un cilindro de espesor h → r = sqrt(V / (π·h·φ)). El círculo se dibuja a escala geográfica real
(folium.Circle usa metros), coloreado por la velocidad LOS local para ver si el footprint de inyección
cae sobre uplift o subsidencia. Incluye una escala de radio para volúmenes de referencia.

    ~/miniforge3/bin/mamba run -n insar python exploraciones/escala_pozo/burbujas_inyeccion.py
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
GEO = Path("/var/home/matias/Projects/estado-del-sistema/public/data/concesiones_neuquina.geojson")
CSV = HERE / "pozos_geomec.csv"

# --- supuestos del horizonte receptor (CONFIGURABLES, representativos de un acuífero/horizonte
#     convencional permeable somero; el radio escala como 1/sqrt(h·φ)) ---
BW = 1.03          # factor de volumen del agua (rm³/sm³)
H_M = 30.0         # espesor neto receptor [m]
PHI = 0.15         # porosidad [-]


def radius_m(iny_agua_m3: float) -> float:
    """Radio del cilindro de poro equivalente [m]."""
    V = max(iny_agua_m3, 0) * BW
    return float(np.sqrt(V / (np.pi * H_M * PHI))) if V > 0 else 0.0


def main():
    import folium
    from matplotlib import colors, colormaps
    df = pd.read_csv(CSV)
    inj = df[(df.iny_agua > 0)].copy()
    inj["r_m"] = inj.iny_agua.map(radius_m)
    inj = inj.sort_values("r_m", ascending=False)
    print(f"inyectores: {len(inj)}  | radio m: med={inj.r_m.median():.0f} "
          f"p90={inj.r_m.quantile(.9):.0f} max={inj.r_m.max():.0f}  (h={H_M} m, φ={PHI})")

    m = folium.Map(location=[-38.4, -69.0], zoom_start=9, tiles=None)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
                     "MapServer/tile/{z}/{y}/{x}", attr="Esri", name="Satélite").add_to(m)
    if GEO.exists():
        folium.GeoJson(json.load(open(GEO)), name="Concesiones",
                       style_function=lambda _f: {"fillOpacity": 0, "color": "#fff",
                                                  "weight": 0.6, "opacity": 0.5}).add_to(m)
    vmax = float(np.nanpercentile(np.abs(df.vel), 98)) or 10
    norm = colors.TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)
    cmap = colormaps["RdBu"]
    fg = folium.FeatureGroup(name="Burbujas de inyección (radio = footprint de poro)").add_to(m)
    for _, w in inj.iterrows():
        folium.Circle(
            [w.lat, w.lon], radius=w.r_m,
            color="#1b6", weight=1.0, opacity=0.7,
            fill=True, fillColor=colors.to_hex(cmap(norm(w.vel))), fillOpacity=0.45,
            popup=folium.Popup(
                f"<b>{w.conc}</b><br>Inyección acum.: {w.iny_agua:,.0f} m³<br>"
                f"Radio equivalente: {w.r_m:,.0f} m<br>Vel LOS: {w.vel:+.1f} mm/yr",
                max_width=260),
            tooltip=f"r≈{w.r_m:,.0f} m · {w.iny_agua:,.0f} m³").add_to(fg)

    # escala de radio para volúmenes de referencia
    refs = [0.1e6, 0.5e6, 1.0e6, 2.5e6]
    rows = "".join(f"<tr><td>{v/1e6:.1f} Mm³</td><td>r ≈ {radius_m(v):,.0f} m</td></tr>" for v in refs)
    legend = (f'<div style="position:fixed;bottom:24px;left:24px;z-index:9999;'
              f'background:rgba(255,255,255,.92);padding:10px 14px;border-radius:6px;'
              f'font:12px sans-serif;color:#111">'
              f'<b>Footprint de inyección</b><br>'
              f'radio del poro equivalente: r = √(V·Bw / (π·h·φ))<br>'
              f'<span style="font-size:11px;color:#555">supuestos: h={H_M:.0f} m, φ={PHI:.2f}, '
              f'Bw={BW}</span>'
              f'<table style="font-size:11px;margin-top:4px">{rows}</table>'
              f'<span style="font-size:11px">relleno = velocidad LOS '
              f'(<span style="color:#b2182b">rojo</span> subsidencia / '
              f'<span style="color:#2166ac">azul</span> uplift)</span></div>')
    m.get_root().html.add_child(folium.Element(legend))
    folium.LayerControl(collapsed=False).add_to(m)
    out = HERE / "demo_inyeccion_burbujas.html"
    m.save(str(out))
    print(f"→ {out}  ({out.stat().st_size/1e6:.1f} MB)")
    fig_static(inj, df)


def fig_static(inj, df):
    """Bubble-chart estático: área ∝ volumen inyectado, color = velocidad LOS."""
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import colors
    fig, ax = plt.subplots(figsize=(9.5, 8))
    ax.set_facecolor("#eef1f3")
    if GEO.exists():
        gj = json.load(open(GEO))
        for f in gj["features"]:
            g = f["geometry"]
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            for poly in polys:
                rng = np.array(poly[0]); ax.plot(rng[:, 0], rng[:, 1], color="#888", lw=0.3, alpha=0.5)
    vmax = float(np.nanpercentile(np.abs(df.vel), 98)) or 10
    s = 6 + 600 * (inj.iny_agua / inj.iny_agua.max())          # área ∝ volumen
    sc = ax.scatter(inj.lon, inj.lat, s=s, c=inj.vel.clip(-vmax, vmax), cmap="RdBu",
                    norm=colors.TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax),
                    edgecolor="#1b6", linewidth=0.6, alpha=0.75)
    ax.set_xlim(-70.6, -68.2); ax.set_ylim(-39.2, -37.3)
    ax.set_xlabel("Longitud"); ax.set_ylabel("Latitud")
    ax.set_title(f"Burbujas de inyección de agua (área ∝ volumen acumulado)\n"
                 f"color = velocidad LOS · radio físico equivalente con h={H_M:.0f} m, φ={PHI:.2f}")
    cb = fig.colorbar(sc, ax=ax, shrink=0.8); cb.set_label("velocidad LOS (mm/yr)")
    # leyenda de tamaño con radio físico
    for v in (0.5e6, 1.0e6, 2.5e6):
        ax.scatter([], [], s=6 + 600 * (v / inj.iny_agua.max()), c="#ccc", edgecolor="#1b6",
                   label=f"{v/1e6:.1f} Mm³  (r≈{radius_m(v):,.0f} m)")
    ax.legend(title="Inyección acum. (radio físico)", loc="lower left", fontsize=8, framealpha=0.9)
    fig.tight_layout(); fig.savefig(HERE / "inyeccion_burbujas.png", dpi=130); plt.close(fig)
    print("→ inyeccion_burbujas.png")


if __name__ == "__main__":
    main()
