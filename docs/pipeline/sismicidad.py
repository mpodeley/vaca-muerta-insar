#!/usr/bin/env python
"""Mapa: deformación InSAR + sismicidad (USGS) + concesiones.

Superpone los epicentros del catálogo USGS (2015–2026) sobre el mapa de velocidad
y las concesiones. Distingue sismos superficiales/corticales (<30 km, candidatos a
inducidos) de profundos (subducción). Genera demo_sismicidad.html.

USGS solo cataloga M≳3.4 con ubicación ±10-30 km; los micro-sismos inducidos (<M3)
no aparecen. Es una vista de contexto, no un estudio de atribución.
"""
from __future__ import annotations
import base64
import datetime
import io
import json
import urllib.request
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent
VELW = HERE / "_velocity_wgs84.tif"
CONC = Path("/var/home/matias/Projects/estado-del-sistema/public/data/concesiones_neuquina.geojson")
OUT = HERE / "demo_sismicidad.html"
SAUZAL = (-38.05, -69.42)
ANELO = (-38.35, -68.79)


def fetch_usgs():
    url = ("https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
           "&starttime=2015-01-01&endtime=2026-06-30"
           "&minlatitude=-39.2&maxlatitude=-37.3&minlongitude=-70.6&maxlongitude=-68.2"
           "&minmagnitude=0")
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def velocity_overlay():
    import rasterio
    from matplotlib import cm, colors, pyplot as plt
    with rasterio.open(VELW) as s:
        v = s.read(1)
        b = s.bounds
    vmax = float(np.nanpercentile(np.abs(v[np.isfinite(v)]), 98)) or 10.0
    rgba = cm.get_cmap("RdBu")(colors.TwoSlopeNorm(vcenter=0, vmin=-vmax, vmax=vmax)(v))
    rgba[..., 3] = np.where(np.isfinite(v), 0.6, 0.0)
    buf = io.BytesIO(); plt.imsave(buf, rgba, format="png")
    png = base64.b64encode(buf.getvalue()).decode()
    return png, (b.bottom, b.left, b.top, b.right)


def main():
    import folium
    g = fetch_usgs()
    png, (s, w, n, e) = velocity_overlay()

    m = folium.Map(location=[-38.4, -69.0], zoom_start=9, tiles=None)
    folium.TileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
        "MapServer/tile/{z}/{y}/{x}", attr="Esri", name="Satélite").add_to(m)
    folium.raster_layers.ImageOverlay(
        f"data:image/png;base64,{png}", bounds=[[s, w], [n, e]],
        opacity=1, name="Velocidad InSAR (mm/año)").add_to(m)
    folium.GeoJson(json.load(open(CONC)), name="Concesiones",
                   style_function=lambda _f: {"fillOpacity": 0, "color": "#fff",
                                              "weight": 0.6, "opacity": 0.5}).add_to(m)

    n_sh = 0
    for f in g["features"]:
        lon, lat, dep = f["geometry"]["coordinates"]
        p = f["properties"]; mag = p["mag"] or 0
        d = datetime.datetime.utcfromtimestamp(p["time"] // 1000).date()
        shallow = (dep or 0) < 30
        n_sh += shallow
        folium.CircleMarker(
            [lat, lon], radius=2 + 2.2 * mag,
            color="#111", weight=0.8,
            fill=True, fillColor="#ffcc00" if shallow else "#888",
            fillOpacity=0.85 if shallow else 0.5,
            popup=folium.Popup(f"<b>M{mag:.1f}</b> · {d}<br>prof {dep:.0f} km<br>"
                               f"{'cortical (¿inducido?)' if shallow else 'profundo (subducción)'}"
                               f"<br>{p['place']}", max_width=240),
            tooltip=f"M{mag:.1f} ({dep:.0f} km)").add_to(m)

    folium.Marker(list(ANELO), tooltip="Añelo",
                  icon=folium.Icon(color="gray", icon="home")).add_to(m)
    folium.Marker(list(SAUZAL), tooltip="Sauzal Bonito (sismicidad inducida)",
                  icon=folium.Icon(color="red", icon="exclamation-sign")).add_to(m)

    legend = ("""<div style="position:fixed;bottom:24px;left:24px;z-index:9999;
      background:rgba(255,255,255,.93);padding:10px 14px;border-radius:6px;font:12px sans-serif">
      <b>Sismicidad (USGS 2015–2026) + deformación</b><br>
      <span style="color:#ffcc00">●</span> cortical &lt;30 km (¿inducido?) &nbsp;
      <span style="color:#888">●</span> profundo (subducción)<br>
      Tamaño ∝ magnitud · fondo = velocidad InSAR (rojo subsidencia)<br>
      <span style="font-size:11px;color:#555">USGS capta M≳3.4, ubicación ±10-30 km;
      los micro-sismos inducidos no aparecen.</span></div>""")
    m.get_root().html.add_child(folium.Element(legend))
    folium.LayerControl().add_to(m)
    m.save(str(OUT))
    print(f"→ {OUT} | {len(g['features'])} sismos ({n_sh} corticales)")


if __name__ == "__main__":
    main()
