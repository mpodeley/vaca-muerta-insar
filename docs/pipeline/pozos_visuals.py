#!/usr/bin/env python
"""Visualizaciones por pozo: mapa interactivo (color=velocidad, tamaño=voidage), campo de
voidage (densidad por km²) vs campo de subsidencia (lado a lado + correlación gridded + mapa
interactivo con capas toggleables), y scatter voidage↔subsidencia + inyectores/productores.

Reusa patrones de t18_f1050/{04_export_visual,sismicidad,produccion_visuals}.py.

    ~/miniforge3/bin/mamba run -n insar python exploraciones/escala_pozo/pozos_visuals.py
"""
from __future__ import annotations
import base64, io, json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
VEL_TIF = ROOT / "t18_f1050" / "_velocity_wgs84.tif"
GEO = Path("/var/home/matias/Projects/estado-del-sistema/public/data/concesiones_neuquina.geojson")
CSV = HERE / "pozos_voidage.csv"
LON0, LON1, LAT0, LAT1 = -70.6, -68.2, -39.2, -37.3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors, colormaps


def _png_b64(rgba: np.ndarray) -> str:
    buf = io.BytesIO()
    plt.imsave(buf, rgba, format="png")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _add_concesiones(folium, m) -> None:
    if not GEO.exists():
        return
    folium.GeoJson(json.load(open(GEO)), name="Concesiones",
                   style_function=lambda _f: {"fillOpacity": 0, "color": "#ffffff",
                                              "weight": 0.7, "opacity": 0.6}).add_to(m)


def load():
    df = pd.read_csv(CSV)
    return df[df.lon.between(LON0, LON1) & df.lat.between(LAT0, LAT1)].copy()


# ----------------------------------------------------- campos en grilla común
def grid_field(df, col, ncell=240, sigma=1.0):
    """Densidad (suma de `col` por km²) en grilla común, suavizada."""
    from scipy.ndimage import gaussian_filter
    xe = np.linspace(LON0, LON1, ncell + 1)
    ye = np.linspace(LAT0, LAT1, ncell + 1)
    H, _, _ = np.histogram2d(df.lat, df.lon, bins=[ye, xe], weights=df[col])
    cnt, _, _ = np.histogram2d(df.lat, df.lon, bins=[ye, xe])
    latm = (LAT0 + LAT1) / 2
    dx_km = (xe[1] - xe[0]) * 111.32 * np.cos(np.radians(latm))
    dy_km = (ye[1] - ye[0]) * 110.57
    dens = H / (dx_km * dy_km)
    return xe, ye, dens, gaussian_filter(dens, sigma), cnt


def velocity_grid(ncell=240):
    import rasterio
    xe = np.linspace(LON0, LON1, ncell + 1)
    ye = np.linspace(LAT0, LAT1, ncell + 1)
    xc = 0.5 * (xe[:-1] + xe[1:]); yc = 0.5 * (ye[:-1] + ye[1:])
    velg = np.full((ncell, ncell), np.nan)
    with rasterio.open(VEL_TIF) as src:
        for j, la in enumerate(yc):
            velg[j] = [v[0] for v in src.sample([(lo, la) for lo in xc])]
    return np.where(np.isfinite(velg), velg, np.nan)


def fig_field(df):
    """Comparativo: voidage VOLUMÉTRICO (no predice) | extracción VM (sí) | subsidencia."""
    from scipy.stats import spearmanr
    ext = [LON0, LON1, LAT0, LAT1]
    _, _, vd, vd_s, cnt = grid_field(df, "voidage_net", sigma=1.0)
    # extracción VM: drenaje localizado (sigma chico)
    _, _, xv, xv_s, cntx = grid_field(df[df.is_vm], "extr_vm_liq", sigma=0.8)
    velg = velocity_grid()

    def gcorr(field, mask):
        m = mask & np.isfinite(velg)
        return spearmanr(field[m], velg[m])[0], int(m.sum())
    rho_v, nv = gcorr(vd, cnt > 0)
    rho_x, nx = gcorr(xv, cntx > 0)
    print(f"gridded ρ:  voidage_net↔vel={rho_v:+.2f} (n={nv})   "
          f"extr_VM↔vel={rho_x:+.2f} (n={nx})")

    fig, ax = plt.subplots(1, 3, figsize=(18, 5.6))
    dpos = np.where(vd_s > 0, vd_s, np.nan)
    im0 = ax[0].imshow(dpos, extent=ext, origin="lower", cmap="inferno",
                       norm=colors.LogNorm(vmin=np.nanpercentile(dpos, 70),
                                           vmax=np.nanpercentile(dpos, 99.5)))
    ax[0].set_title(f"Voidage volumétrico neto\n(no predice: ρ={rho_v:+.2f})")
    fig.colorbar(im0, ax=ax[0], shrink=0.8, label="rm³/km²")
    xpos = np.where(xv_s > 0, xv_s, np.nan)
    im1 = ax[1].imshow(xpos, extent=ext, origin="lower", cmap="inferno",
                       norm=colors.LogNorm(vmin=np.nanpercentile(xpos, 70),
                                           vmax=np.nanpercentile(xpos, 99.5)))
    ax[1].set_title(f"Extracción líquida VM profundo\n(predice: ρ={rho_x:+.2f})")
    fig.colorbar(im1, ax=ax[1], shrink=0.8, label="rm³/km²")
    vmax = float(np.nanpercentile(np.abs(velg), 98)) or 10
    im2 = ax[2].imshow(velg, extent=ext, origin="lower", cmap="RdBu",
                       norm=colors.TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax))
    ax[2].set_title("Subsidencia (velocidad LOS)\nrojo = subsidencia")
    fig.colorbar(im2, ax=ax[2], shrink=0.8, label="mm/yr")
    for a in ax:
        a.set_xlabel("Lon"); a.set_ylabel("Lat")
    fig.suptitle("El campo de extracción del VM profundo —no el voidage volumétrico— "
                 "reproduce los bowls de subsidencia", fontsize=13)
    fig.tight_layout()
    fig.savefig(HERE / "voidage_vs_subsidencia.png", dpi=120)
    plt.close(fig)
    print("→ voidage_vs_subsidencia.png")
    return vd_s, xv_s, velg


# ----------------------------------------------------- mapa interactivo de pozos
def map_pozos(df):
    import folium
    # acotar a los pozos relevantes (VM profundo + inyectores) para aligerar el HTML
    df = df[df.is_vm | df.is_iny].copy()
    m = folium.Map(location=[-38.4, -69.0], zoom_start=9, tiles=None)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
                     "MapServer/tile/{z}/{y}/{x}", attr="Esri", name="Satélite").add_to(m)
    _add_concesiones(folium, m)
    vmax = float(np.nanpercentile(np.abs(df.vel), 98)) or 10
    norm = colors.TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)
    cmap = colormaps["RdBu"]
    vd = df[df.voidage_net > 0].voidage_net
    vmin_r, vmax_r = vd.quantile(0.05), vd.quantile(0.95)
    fg = folium.FeatureGroup(name="Pozos VM + inyectores (color=vel, tamaño=voidage)").add_to(m)
    for _, w in df.iterrows():
        r = 2.0 + 6.0 * np.clip((max(w.voidage_net, 0) - vmin_r) / (vmax_r - vmin_r + 1e-9), 0, 1)
        c = colors.to_hex(cmap(norm(w.vel)))
        folium.CircleMarker(
            [w.lat, w.lon], radius=float(r), color="#222", weight=0.3,
            fill=True, fillColor=c, fillOpacity=0.85,
            popup=folium.Popup(
                f"<b>Pozo {int(w.idpozo)}</b><br>{w.conc}<br>"
                f"Vel: {w.vel:+.1f} mm/yr<br>Voidage neto: {w.voidage_net:,.0f} rm³<br>"
                f"oil {w.prod_pet:,.0f} m³ · gas {w.prod_gas:,.0f} km³ · "
                f"agua {w.prod_agua:,.0f} m³", max_width=260),
            tooltip=f"{w.vel:+.1f} mm/yr").add_to(fg)
    legend = (f'<div style="position:fixed;bottom:24px;left:24px;z-index:9999;'
              f'background:rgba(255,255,255,.9);padding:10px 14px;border-radius:6px;'
              f'font:12px sans-serif;color:#111">'
              f'<b>Pozos — color = velocidad LOS (mm/yr)</b><br>'
              f'<span style="color:#b2182b">■</span> subsidencia (−{vmax:.0f}) · 0 · '
              f'<span style="color:#2166ac">■</span> uplift (+{vmax:.0f})<br>'
              f'<span style="font-size:11px;color:#555">tamaño = voidage neto de reservorio</span></div>')
    m.get_root().html.add_child(folium.Element(legend))
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(str(HERE / "demo_pozos.html"))
    print("→ demo_pozos.html")


# ------------------------------------- mapa interactivo: campos toggleables
def _log_overlay(folium, m, field, name, bounds, show=True):
    pos = np.where(field > 0, field, np.nan)
    n = colors.LogNorm(vmin=np.nanpercentile(pos, 70), vmax=np.nanpercentile(pos, 99.5))
    rgba = colormaps["inferno"](n(pos)); rgba[..., 3] = np.where(np.isfinite(pos), 0.82, 0)
    folium.raster_layers.ImageOverlay(
        image=f"data:image/png;base64,{_png_b64(rgba[::-1])}", bounds=bounds,
        name=name, opacity=1.0, show=show).add_to(m)


def map_voidage_overlays(vd_s, xv_s, velg):
    import folium
    m = folium.Map(location=[-38.4, -69.0], zoom_start=9, tiles=None)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
                     "MapServer/tile/{z}/{y}/{x}", attr="Esri", name="Satélite").add_to(m)
    bounds = [[LAT0, LON0], [LAT1, LON1]]
    _log_overlay(folium, m, xv_s, "Extracción líquida VM (rm³/km²)", bounds, show=True)
    _log_overlay(folium, m, vd_s, "Voidage volumétrico neto (rm³/km²)", bounds, show=False)
    vmax = float(np.nanpercentile(np.abs(velg), 98)) or 10
    nn = colors.TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)
    rgba_s = colormaps["RdBu"](nn(velg)); rgba_s[..., 3] = np.where(np.isfinite(velg), 0.82, 0)
    folium.raster_layers.ImageOverlay(
        image=f"data:image/png;base64,{_png_b64(rgba_s[::-1])}", bounds=bounds,
        name="Subsidencia (velocidad LOS)", opacity=1.0, show=False).add_to(m)
    _add_concesiones(folium, m)
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(str(HERE / "demo_voidage.html"))
    print("→ demo_voidage.html")


# ----------------------------------------------------- scatter + inyectores/productores
def fig_scatter(df):
    from scipy.stats import spearmanr
    fig, ax = plt.subplots(1, 2, figsize=(13, 5.2))
    dx = df[df.is_vm & (df.extr_vm_liq > 0)]
    rx, _ = spearmanr(dx.extr_vm_liq, dx.vel)
    ax[0].scatter(dx.extr_vm_liq, dx.vel, s=8, alpha=0.4, c=dx.vel.clip(-12, 4),
                  cmap="RdBu", vmin=-12, vmax=4)
    ax[0].set_xscale("log"); ax[0].axhline(0, color="#999", lw=0.8)
    ax[0].set_xlabel("Extracción líquida VM profundo (rm³, log)")
    ax[0].set_ylabel("Velocidad LOS (mm/yr)")
    ax[0].set_title(f"Predice: extracción VM  (ρ={rx:+.2f}, n={len(dx)})")
    dv = df[df.voidage_net > 0]
    rv, _ = spearmanr(dv.voidage_net, dv.vel)
    ax[1].scatter(dv.voidage_net, dv.vel, s=8, alpha=0.4, c=dv.vel.clip(-12, 4),
                  cmap="RdBu", vmin=-12, vmax=4)
    ax[1].set_xscale("log"); ax[1].axhline(0, color="#999", lw=0.8)
    ax[1].set_xlabel("Voidage volumétrico neto (rm³, log)")
    ax[1].set_ylabel("Velocidad LOS (mm/yr)")
    ax[1].set_title(f"No predice: voidage volumétrico  (ρ={rv:+.2f}, n={len(dv)})")
    fig.tight_layout(); fig.savefig(HERE / "voidage_scatter.png", dpi=130); plt.close(fig)
    print("→ voidage_scatter.png")


def main():
    df = load()
    print(f"pozos en AOI: {len(df)}")
    vd_s, xv_s, velg = fig_field(df)
    map_pozos(df)
    map_voidage_overlays(vd_s, xv_s, velg)
    fig_scatter(df)


if __name__ == "__main__":
    main()
