#!/usr/bin/env python
"""Parte C — Cruce con Sentinel-2 NDVI: ¿la subsidencia coincide con riego?

Testea la hipótesis de agua subterránea: si las cubetas de subsidencia caen sobre
parcelas regadas (NDVI alto), refuerza el caso de extracción de agua; si no, lo
debilita. Usa Sentinel-2 L2A de Microsoft Planetary Computer (STAC anónimo, libre).

Produce:
  1. ndvi_median.tif        — NDVI mediana de verano (EPSG:4326)
  2. demo_ndvi.html         — overlay NDVI + cubetas de subsidencia + concesiones (folium)
  3. ndvi_vs_subsidencia.png — distribución de NDVI en zona subsidente vs estable + correlación

Requiere (env insar, red): pystac-client planetary-computer odc-stac rioxarray.

    ~/miniforge3/bin/mamba run -n insar python ndvi_overlay.py    # sandbox OFF

Convención InSAR: negativo = subsidencia (rojo), positivo = uplift (azul).
"""

from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

import numpy as np

import aoi

HERE = Path(__file__).parent
VEL_WGS84 = HERE / "_velocity_wgs84.tif"   # velocidad mm/año EPSG:4326 (de 04_export_visual.py)
NDVI_TIF = HERE / "ndvi_median.tif"
HTML_OUT = HERE / "demo_ndvi.html"
SCATTER_OUT = HERE / "ndvi_vs_subsidencia.png"
CONCESIONES = Path("/var/home/matias/Projects/estado-del-sistema/public/data/"
                   "concesiones_neuquina.geojson")

# Veranos recientes (riego máximo en el hemisferio sur); todos con baseline S2 nuevo
# (offset −1000 DN), así que la conversión a reflectancia es uniforme.
SUMMER_MONTHS = {12, 1, 2}
DATE_RANGE = "2022-12-01/2025-03-15"
MAX_CLOUD = 10
RES_DEG = 0.0006   # ~60 m sobre los ~210×210 km del AOI; chunks espaciales acotan la RAM
SUB_THRESH = -8.0  # mm/año: umbral de "subsidencia fuerte" (consistente con el resto del análisis)
# Procesa TODAS las escenas de verano nubes<MAX_CLOUD (~630). Pesado (~30 min) pero da
# el mejor composite libre de nubes; la mediana temporal con chunks espaciales es memory-safe.


# --------------------------------------------------------------------------- S2
def fetch_ndvi() -> None:
    """Descarga S2 L2A, compone NDVI mediana de verano y lo guarda como GeoTIFF."""
    import odc.stac
    import planetary_computer as pc
    import pystac_client
    import rioxarray  # noqa: F401  (registra el accessor .rio)

    bbox = [aoi.WEST, aoi.SOUTH, aoi.EAST, aoi.NORTH]
    print(f"==> STAC query S2 L2A | bbox={bbox} | {DATE_RANGE} | nubes<{MAX_CLOUD}%")
    cat = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=pc.sign_inplace,
    )
    search = cat.search(
        collections=["sentinel-2-l2a"], bbox=bbox, datetime=DATE_RANGE,
        query={"eo:cloud_cover": {"lt": MAX_CLOUD}},
    )
    items = [it for it in search.items() if it.datetime.month in SUMMER_MONTHS]
    if not items:
        sys.exit("No se encontraron escenas S2 (ajustar fechas/nubosidad).")
    print(f"    {len(items)} escenas de verano (nubes<{MAX_CLOUD}%)")

    ds = odc.stac.load(
        items, bands=["B04", "B08"], bbox=bbox, crs="EPSG:4326",
        resolution=RES_DEG, groupby="solar_day",
        chunks={"time": 1, "latitude": 2048, "longitude": 2048},
        dtype="float32", nodata=np.nan,
    )
    # Reflectancia de superficie (baseline nuevo: refl = (DN − 1000)/10000), clip a ≥0.
    red = (ds["B04"] - 1000.0).clip(min=0) / 10000.0
    nir = (ds["B08"] - 1000.0).clip(min=0) / 10000.0
    ndvi = (nir - red) / (nir + red)
    ndvi = ndvi.where(np.isfinite(ndvi))
    print("    componiendo mediana temporal (quita nubes)...")
    ndvi_med = ndvi.median(dim="time", skipna=True).compute()
    ndvi_med.rio.write_crs("EPSG:4326", inplace=True)
    ndvi_med.rio.to_raster(NDVI_TIF, driver="GTiff", compress="deflate")
    print(f"    {NDVI_TIF.name} ({ndvi_med.shape[0]}×{ndvi_med.shape[1]} px)")


# ------------------------------------------------------------------- análisis
def _read_velocity_on(ref_tif: Path):
    """Velocidad (mm/año) remuestreada a la grilla del NDVI, para alinear pixel-a-pixel."""
    import rasterio
    from rasterio.warp import Resampling, reproject

    with rasterio.open(ref_tif) as ndv:
        dst = np.full((ndv.height, ndv.width), np.nan, dtype="float32")
        with rasterio.open(VEL_WGS84) as src:
            reproject(
                source=rasterio.band(src, 1), destination=dst,
                src_transform=src.transform, src_crs=src.crs,
                dst_transform=ndv.transform, dst_crs=ndv.crs,
                resampling=Resampling.average, src_nodata=np.nan, dst_nodata=np.nan,
            )
    return dst


def analyse_and_plot() -> None:
    """Correlación NDVI↔velocidad y NDVI en zona subsidente vs estable."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import rasterio
    from scipy import stats

    with rasterio.open(NDVI_TIF) as s:
        ndvi = s.read(1).astype("float32")
    vel = _read_velocity_on(NDVI_TIF)

    ok = np.isfinite(ndvi) & np.isfinite(vel)
    ndvi_o, vel_o = ndvi[ok], vel[ok]
    if ndvi_o.size < 1000:
        sys.exit("Muy pocos pixels válidos solapados NDVI↔velocidad.")

    r, p = stats.pearsonr(vel_o, ndvi_o)
    rho, p_s = stats.spearmanr(vel_o, ndvi_o)

    sub = vel_o < SUB_THRESH                      # subsidencia fuerte
    sta = np.abs(vel_o) < 0.5                      # estable
    ndvi_sub, ndvi_sta = ndvi_o[sub], ndvi_o[sta]
    # ¿la zona subsidente está MÁS regada (NDVI más alto) que la estable?
    u, p_u = stats.mannwhitneyu(ndvi_sub, ndvi_sta, alternative="greater")

    print("\n=== NDVI vs subsidencia ===")
    print(f"pixels solapados: {ndvi_o.size:,}")
    print(f"correlación velocidad↔NDVI: Pearson r={r:+.3f} (p={p:.1e})  "
          f"Spearman ρ={rho:+.3f} (p={p_s:.1e})")
    print(f"NDVI mediana — subsidente(<{SUB_THRESH:g}): {np.median(ndvi_sub):.3f} "
          f"(n={ndvi_sub.size:,}) | estable: {np.median(ndvi_sta):.3f} (n={ndvi_sta.size:,})")
    print(f"Mann-Whitney (subsidente NDVI > estable): p={p_u:.1e}")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    ax1.hexbin(ndvi_o, vel_o, gridsize=60, bins="log", cmap="viridis", mincnt=1)
    ax1.axhline(SUB_THRESH, color="#b2182b", lw=1, ls="--")
    ax1.set_xlabel("NDVI (summer median)")
    ax1.set_ylabel("LOS velocity (mm/yr)")
    ax1.set_title(f"NDVI vs deformation velocity\nSpearman ρ={rho:+.3f} (p={p_s:.0e})")

    bins = np.linspace(-0.1, 0.9, 40)
    ax2.hist(ndvi_sta, bins=bins, density=True, alpha=0.6, color="#2166ac",
             label=f"stable (n={ndvi_sta.size:,})")
    ax2.hist(ndvi_sub, bins=bins, density=True, alpha=0.6, color="#b2182b",
             label=f"subsiding < {SUB_THRESH:g} mm/yr (n={ndvi_sub.size:,})")
    ax2.set_xlabel("NDVI (summer median)")
    ax2.set_ylabel("density")
    ax2.set_title("Vegetation cover: subsiding vs stable")
    ax2.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(SCATTER_OUT, dpi=150)
    print(f"Listo → {SCATTER_OUT}")


# ----------------------------------------------------------------------- mapa
def _rgba_to_png_b64(rgba: np.ndarray) -> str:
    from matplotlib import pyplot as plt
    buf = io.BytesIO()
    plt.imsave(buf, rgba, format="png")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _add_concesiones(folium, m) -> None:
    import json
    if not CONCESIONES.exists():
        return
    folium.GeoJson(
        json.load(open(CONCESIONES)), name="Concesiones",
        style_function=lambda _f: {"fillOpacity": 0, "color": "#ffffff",
                                   "weight": 0.7, "opacity": 0.6},
    ).add_to(m)


def build_html() -> None:
    import folium
    import rasterio
    from matplotlib import cm, colors

    print(f"==> Armando {HTML_OUT.name}")
    with rasterio.open(NDVI_TIF) as s:
        ndvi = s.read(1)
        w, sth, e, n = s.bounds.left, s.bounds.bottom, s.bounds.right, s.bounds.top

    # Capa NDVI (verde): 0 = suelo desnudo, alto = vegetación/riego.
    norm = colors.Normalize(vmin=0.0, vmax=0.7)
    rgba = cm.get_cmap("YlGn")(norm(np.nan_to_num(ndvi, nan=0.0)))
    rgba[..., 3] = np.where(np.isfinite(ndvi), 0.7, 0.0)
    ndvi_b64 = _rgba_to_png_b64(rgba)

    # Capa de cubetas de subsidencia (rojo onde vel < umbral), desde la velocidad.
    vel = _read_velocity_on(NDVI_TIF)
    sub_rgba = np.zeros((*vel.shape, 4), dtype=float)
    sub_mask = np.isfinite(vel) & (vel < SUB_THRESH)
    sub_rgba[sub_mask] = [0.70, 0.10, 0.17, 0.85]  # rojo
    sub_b64 = _rgba_to_png_b64(sub_rgba)

    m = folium.Map(location=[(sth + n) / 2, (w + e) / 2], zoom_start=10, tiles=None)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/"
        "World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Satélite",
    ).add_to(m)
    folium.raster_layers.ImageOverlay(
        image=f"data:image/png;base64,{ndvi_b64}", bounds=[[sth, w], [n, e]],
        opacity=1.0, name="NDVI (verde = vegetación/riego)",
    ).add_to(m)
    folium.raster_layers.ImageOverlay(
        image=f"data:image/png;base64,{sub_b64}", bounds=[[sth, w], [n, e]],
        opacity=1.0, name=f"Subsidencia fuerte (< {SUB_THRESH:g} mm/año)",
    ).add_to(m)
    _add_concesiones(folium, m)
    folium.Marker(list(aoi.ANELO), tooltip="Añelo",
                  icon=folium.Icon(color="gray", icon="home")).add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    m.get_root().html.add_child(folium.Element(_legend_html()))
    m.save(str(HTML_OUT))
    print(f"Listo → {HTML_OUT}")


def _legend_html() -> str:
    return f"""
    <div style="position: fixed; bottom: 24px; left: 24px; z-index: 9999;
                background: rgba(255,255,255,0.9); padding: 10px 14px;
                border-radius: 6px; font: 12px sans-serif; color: #111;">
      <b>NDVI Sentinel-2 (mediana de verano) vs subsidencia InSAR</b><br>
      <span style="color:#1a9850">■</span> NDVI alto (vegetación / riego)
      &nbsp;·&nbsp;
      <span style="color:#b2182b">■</span> subsidencia &lt; {SUB_THRESH:g} mm/año<br>
      <span style="font-size:11px;color:#555">
        ¿Las cubetas de subsidencia caen sobre parcelas regadas? — test de la hipótesis de agua.
        Muestra correlación, no causalidad.</span>
    </div>"""


def main() -> None:
    if not VEL_WGS84.exists():
        sys.exit(f"No existe {VEL_WGS84}. Corré 04_export_visual.py primero.")
    if not NDVI_TIF.exists():
        fetch_ndvi()
    else:
        print(f"(usando {NDVI_TIF.name} existente)")
    analyse_and_plot()
    build_html()


if __name__ == "__main__":
    main()
