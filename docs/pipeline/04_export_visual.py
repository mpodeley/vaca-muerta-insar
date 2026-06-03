#!/usr/bin/env python
"""Paso 4 — Exportar GeoTIFF y armar el visual presentable.

A partir de velocity.h5 (MintPy) produce, aplicando la máscara de coherencia
temporal (maskTempCoh.h5) para mostrar solo pixels confiables:
  1. velocity_mm_yr.tif  — GeoTIFF georreferenciado (UTM), enmascarado, en mm/año
  2. velocity_mintpy.png — figura estática estándar de MintPy (respaldo)
  3. demo_subsidencia.html — mapa interactivo AUTOCONTENIDO (folium): overlay de
     velocidad sobre imagen satelital, con leyenda mm/año y los bloques del
     clúster productivo. Abrible en cualquier navegador, ideal para mostrar.

    conda activate insar
    cd fase1 && python 04_export_visual.py

Convención: negativo = subsidencia (rojo), positivo = uplift (azul).
"""

from __future__ import annotations

import base64
import io
import subprocess
import sys
from pathlib import Path

import numpy as np

import aoi

HERE = Path(__file__).parent
VELOCITY_H5 = HERE / "velocity.h5"
MASK_H5 = HERE / "maskTempCoh.h5"
GEOTIFF = HERE / "velocity_mm_yr.tif"          # UTM, enmascarado, mm/año (entregable)
GEOTIFF_WGS84 = HERE / "_velocity_wgs84.tif"   # auxiliar para el overlay folium
PNG_STATIC = HERE / "velocity_mintpy.png"
HTML_OUT = HERE / "demo_subsidencia.html"

_RAW = HERE / "_velocity_raw.tif"
_MASK = HERE / "_mask.tif"


def _save_gdal(h5: Path, dset: str, out: Path) -> None:
    subprocess.run(["save_gdal.py", str(h5), "-d", dset, "-o", str(out)], check=True)


def export_geotiff() -> None:
    """Exporta velocidad enmascarada (UTM mm/año) y una versión WGS84 para el mapa."""
    import rasterio
    from rasterio.warp import Resampling, calculate_default_transform, reproject

    print("==> Exportando velocidad + máscara (save_gdal.py)")
    _save_gdal(VELOCITY_H5, "velocity", _RAW)
    _save_gdal(MASK_H5, "mask", _MASK)

    with rasterio.open(_RAW) as src:
        v = src.read(1).astype("float32") * 1000.0  # m/año → mm/año
        profile = src.profile
    with rasterio.open(_MASK) as msk:
        keep = msk.read(1) > 0
    v[~keep] = np.nan

    # GeoTIFF entregable (UTM, con NaN como nodata)
    profile.update(dtype="float32", count=1, nodata=np.nan)
    with rasterio.open(GEOTIFF, "w", **profile) as dst:
        dst.write(v, 1)
    print(f"    {GEOTIFF.name} ({int(keep.sum())} pixels confiables)")

    # Reproyección a EPSG:4326 para que el overlay calce con el basemap satelital
    with rasterio.open(GEOTIFF) as src:
        dt, w, h = calculate_default_transform(
            src.crs, "EPSG:4326", src.width, src.height, *src.bounds
        )
        prof = src.profile.copy()
        prof.update(crs="EPSG:4326", transform=dt, width=w, height=h, nodata=np.nan)
        with rasterio.open(GEOTIFF_WGS84, "w", **prof) as dst:
            reproject(
                source=rasterio.band(src, 1), destination=rasterio.band(dst, 1),
                src_transform=src.transform, src_crs=src.crs,
                dst_transform=dt, dst_crs="EPSG:4326",
                resampling=Resampling.nearest, src_nodata=np.nan, dst_nodata=np.nan,
            )


def export_static_png() -> None:
    print(f"==> view.py → {PNG_STATIC.name}")
    subprocess.run(
        ["view.py", str(VELOCITY_H5), "velocity",
         "--noverbose", "--nodisplay", "-o", str(PNG_STATIC)],
        check=True,
    )


def build_html() -> None:
    import folium
    import rasterio
    from matplotlib import cm, colors

    print(f"==> Armando {HTML_OUT.name}")
    with rasterio.open(GEOTIFF_WGS84) as src:
        v = src.read(1)  # ya en mm/año, EPSG:4326, NaN = no-data
        w, s, e, n = src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top

    finite = v[np.isfinite(v)]
    vmax = float(np.nanpercentile(np.abs(finite), 98)) or 10.0
    norm = colors.TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    cmap = cm.get_cmap("RdBu")  # rojo = negativo (subsidencia), azul = uplift

    rgba = cmap(norm(v))
    rgba[..., 3] = np.where(np.isfinite(v), 0.78, 0.0)  # transparente donde no hay dato
    png_b64 = _rgba_to_png_b64(rgba)

    m = folium.Map(location=[(s + n) / 2, (w + e) / 2], zoom_start=11, tiles=None)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/"
        "World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Satélite",
    ).add_to(m)
    folium.raster_layers.ImageOverlay(
        image=f"data:image/png;base64,{png_b64}",
        bounds=[[s, w], [n, e]], opacity=1.0, name="Velocidad LOS (mm/año)",
    ).add_to(m)
    folium.Marker(
        list(aoi.ANELO), tooltip="Añelo",
        icon=folium.Icon(color="gray", icon="home"),
    ).add_to(m)
    folium.LayerControl().add_to(m)
    m.get_root().html.add_child(folium.Element(_legend_html(vmax)))
    m.save(str(HTML_OUT))

    for tmp in (_RAW, _MASK):
        tmp.unlink(missing_ok=True)


def _rgba_to_png_b64(rgba: np.ndarray) -> str:
    from matplotlib import pyplot as plt

    buf = io.BytesIO()
    plt.imsave(buf, rgba, format="png")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _legend_html(vmax: float) -> str:
    return f"""
    <div style="position: fixed; bottom: 24px; left: 24px; z-index: 9999;
                background: rgba(255,255,255,0.9); padding: 10px 14px;
                border-radius: 6px; font: 12px sans-serif; color: #111;">
      <b>Velocidad de deformación (LOS, mm/año)</b><br>
      <span style="color:#b2182b">■</span> subsidencia (−{vmax:.0f})
      &nbsp;·&nbsp; 0 &nbsp;·&nbsp;
      <span style="color:#2166ac">■</span> uplift (+{vmax:.0f})<br>
      <span style="font-size:11px;color:#555">
        Demo Fase 1 — Sentinel-1/SBAS 2019–2020, track 112 DESC, tropo ERA5.
        Pixels con coherencia temporal &gt;0.7. Muestra correlación, no causalidad.</span>
    </div>"""


def main() -> None:
    if not VELOCITY_H5.exists():
        sys.exit(f"No existe {VELOCITY_H5}. Corré fase1/03_timeseries.sh primero.")
    export_geotiff()
    try:
        export_static_png()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"  (aviso: PNG estático de MintPy omitido: {exc})")
    build_html()
    print(f"\nListo. Abrí {HTML_OUT} en el navegador para mostrar la demo.")


if __name__ == "__main__":
    main()
