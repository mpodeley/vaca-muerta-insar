#!/usr/bin/env python
"""La Calera — mapa interactivo de discontinuidades (Leaflet, autocontenido).

Capas conmutables sobre imagen satelital Esri:
  - Velocidad LOS [mm/año] (RdBu) y |∇v| [mm/año/km] (magma), como overlays base64;
  - laterales de pozos, contorno del bloque, estructuras SEGEMAR;
  - lineamientos candidatos CLICKEABLES: el popup muestra azimut/largo/|∇v|, la
    clasificación del ajuste de escalón (falla/flexura, salto, ancho) y un PNG
    embebido con el perfil transversal + la serie diferencial d(t)=B−A.

Salida: demo_calera_fallas.html

    ~/miniforge3/bin/mamba run -n insar python exploraciones/calera/calera_fallas_map.py
    ... calera_fallas_map.py --src ../../t18_f1050 --suffix _80m
"""
from __future__ import annotations
import argparse, base64, io, json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import cm, colors
from pyproj import Transformer
from scipy.ndimage import map_coordinates
from scipy.special import erf

from gradiente import load_velocity, smooth_robust, HERE, DATA, CONC, BLOQUE_ID
from transectas import fit_models, sample

WELLS = DATA / "calera_wells_all.json"
SEGEMAR = DATA / "fallas_segemar.geojson"
OUT = HERE / "demo_calera_fallas.html"
OFF_M = 200.0


def reproject_4326(arr, g):
    import rasterio
    from rasterio.warp import Resampling, calculate_default_transform, reproject
    h, w = arr.shape
    transform = rasterio.transform.Affine(g["dx"], 0, g["x0"], 0, g["dy"], g["y0"])
    crs = rasterio.crs.CRS.from_epsg(int(g["epsg"]))
    dt, dw, dh = calculate_default_transform(crs, "EPSG:4326", w, h,
        *rasterio.transform.array_bounds(h, w, transform))
    dst = np.full((dh, dw), np.nan, "float32")
    reproject(source=arr.astype("float32"), destination=dst, src_transform=transform,
              src_crs=crs, dst_transform=dt, dst_crs="EPSG:4326",
              resampling=Resampling.nearest, src_nodata=np.nan, dst_nodata=np.nan)
    south, west = dt.f + dh * dt.e, dt.c
    north, east = dt.f, dt.c + dw * dt.a
    return dst, (south, west, north, east)


def png_b64(arr, norm, cmap, alpha=0.78):
    rgba = cmap(norm(arr))
    rgba[..., 3] = np.where(np.isfinite(arr), alpha, 0.0)
    buf = io.BytesIO(); plt.imsave(buf, rgba, format="png")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def fig_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def popup_png(prof, dts, dseries, derr, titulo):
    """mini-figura para el popup: perfil transversal + d(t)."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.4))
    a1.plot(prof["x"] / 1000, prof["y"], ".", ms=2, color="0.5")
    a1.plot(prof["x"] / 1000, prof["escalon"], "-", lw=1.4, color="#b2182b")
    a1.axvline(prof["x0"] / 1000, color="#b2182b", ls=":", lw=1)
    a1.set_xlabel("dist. [km]", fontsize=7); a1.set_ylabel("mm/año", fontsize=7)
    a1.set_title("perfil ⊥", fontsize=8)
    a2.axhline(0, color="0.85", lw=0.8)
    a2.fill_between(dts, dseries - derr, dseries + derr, color="#b2182b", alpha=0.2, lw=0)
    a2.plot(dts, dseries, "-", color="#b2182b", lw=1.2)
    a2.set_title("d(t) = B − A [mm]", fontsize=8)
    for a in (a1, a2):
        a.tick_params(labelsize=6.5); a.grid(alpha=0.25)
    fig.suptitle(titulo, fontsize=9)
    return fig_b64(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=str(HERE / "mintpy_int40"))
    ap.add_argument("--suffix", default="")
    args = ap.parse_args()
    src = Path(args.src)

    v, g = load_velocity(src)
    vs = smooth_robust(v)
    step_m = abs(g["dx"])
    gy, gx = np.gradient(vs, step_m, step_m)
    grad = np.hypot(gx, gy) * 1000.0

    # overlays
    varr, bounds = reproject_4326(vs, g)
    vmax = float(np.nanpercentile(np.abs(vs), 99))
    vel_png = png_b64(varr, colors.TwoSlopeNorm(0, -vmax, vmax), cm.get_cmap("RdBu"))
    garr, _ = reproject_4326(grad, g)
    gmax = float(np.nanpercentile(grad, 99.5))
    grad_png = png_b64(garr, colors.Normalize(0, gmax), cm.get_cmap("magma"))

    # lineamientos + clasificación de transectas
    cands = json.load(open(DATA / f"grad_candidates{args.suffix}.geojson"))["features"]
    steps = pd.read_csv(DATA / f"transect_steps{args.suffix}.csv")
    steps["lid"] = pd.to_numeric(steps.lineamiento, errors="coerce")

    tr_fw = Transformer.from_crs("EPSG:4326", f"EPSG:{g['epsg']}", always_xy=True)
    ts_file = src / "timeseries_ERA5_ramp_demErr.h5"
    if not ts_file.exists():
        ts_file = src / "timeseries.h5"

    feats_out = []
    with h5py.File(ts_file) as f:
        at = dict(f.attrs)
        tx0, ty0 = float(at["X_FIRST"]), float(at["Y_FIRST"])
        tdx, tdy = float(at["X_STEP"]), float(at["Y_STEP"])
        dts = pd.to_datetime([d.decode() for d in f["date"][:]], format="%Y%m%d")

        def series(px, py):
            c = int((px - tx0) / tdx); r = int((py - ty0) / tdy)
            win = f["timeseries"][:, max(r-1, 0):r+2, max(c-1, 0):c+2] * 1000.0
            flat = win.reshape(win.shape[0], -1)
            return np.nanmean(flat, axis=1), np.nanstd(flat, axis=1) / np.sqrt(flat.shape[1])

        for ft in cands:
            p = ft["properties"]
            row = steps[steps.lid == p["id"]]
            cc = ft["geometry"]["coordinates"]
            xs, ys = tr_fw.transform([q[0] for q in cc], [q[1] for q in cc])
            cx, cy = float(np.mean(xs)), float(np.mean(ys))
            az = np.radians(p["azimut_deg"] + 90.0)
            ux, uy = np.sin(az), np.cos(az)
            d, vals = sample(vs, g, cx - 2000 * ux, cy - 2000 * uy,
                             cx + 2000 * ux, cy + 2000 * uy)
            fitr = fit_models(d, vals)
            mA, eA = series(cx - OFF_M * ux, cy - OFF_M * uy)
            mB, eB = series(cx + OFF_M * ux, cy + OFF_M * uy)
            dser, derr = mB - mA, np.hypot(eA, eB)
            info = dict(p)
            if len(row):
                r0 = row.iloc[0]
                info.update(clase=str(r0.clase) if r0.es_escalon else "suave",
                            salto=float(r0.salto_mm_yr), ancho=int(r0.ancho_m),
                            dbic=float(r0.dbic))
            if fitr:
                ttl = (f"L{p['id']} — {info.get('clase','?')}  "
                       f"salto {info.get('salto', 0):+.1f} mm/año  w {info.get('ancho', 0)} m")
                info["png"] = popup_png(fitr, dts, dser, derr, ttl)
            feats_out.append({"geo": [[q[1], q[0]] for q in cc], "p": info})

    # capas de contexto
    wells = json.load(open(WELLS))
    trajs = [[[q[1], q[0]] for q in w["traj"]] for w in wells.values() if w["has_traj"]]
    bocas = [[w["boca"][1], w["boca"][0]] for w in wells.values() if not w["has_traj"]]
    gj = json.load(open(CONC))
    conc = json.dumps({"type": "FeatureCollection",
                       "features": [f for f in gj["features"]
                                    if f["properties"].get("id") == BLOQUE_ID]})
    seg = json.dumps(json.load(open(SEGEMAR))) if SEGEMAR.exists() else "null"

    s, w_, n, e = bounds
    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<title>La Calera — ¿flexuras o fallas? (mapa interactivo)</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
 html,body,#map{{height:100%;margin:0}}
 .legend{{position:absolute;bottom:14px;left:12px;z-index:1000;background:rgba(255,255,255,.93);
   padding:8px 12px;border-radius:6px;font:12px sans-serif;max-width:270px}}
 .bar{{height:10px;width:180px;border:1px solid #999;margin:3px 0}}
 .bl{{display:flex;justify-content:space-between;font-size:11px}}
 .leaflet-popup-content{{margin:10px 12px}}
 .pp img{{max-width:520px;display:block;margin-top:4px}}
 .pp b{{font-size:13px}}
</style></head><body>
<div id="map"></div>
<div class="legend"><b>La Calera — discontinuidades</b>
 <div class="bar" style="background:linear-gradient(to right,#b2182b,#f7f7f7,#2166ac)"></div>
 <div class="bl"><span>−{vmax:.0f}</span><span>vel. LOS [mm/año]</span><span>+{vmax:.0f}</span></div>
 <div class="bar" style="background:linear-gradient(to right,#000004,#b73779,#fcfdbf)"></div>
 <div class="bl"><span>0</span><span>|∇v| [mm/año/km]</span><span>{gmax:.0f}</span></div>
 <div style="margin-top:4px">— <span style="color:#00c2a0"><b>lineamientos</b></span> (click → perfil + d(t))<br>
 — <span style="color:#c51b8a"><b>estructuras SEGEMAR</b></span> · <span style="color:#555">laterales</span></div>
</div>
<script>
const B=[[{s},{w_}],[{n},{e}]];
const map=L.map('map').fitBounds(B);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
  {{attribution:'Esri World Imagery'}}).addTo(map);
const velL=L.imageOverlay('data:image/png;base64,{vel_png}',B).addTo(map);
const gradL=L.imageOverlay('data:image/png;base64,{grad_png}',B);
const CONC={conc};
L.geoJSON(CONC,{{style:{{fill:false,color:'#fff',weight:1.6,dashArray:'5 4'}}}}).addTo(map);
const TR={json.dumps([[[round(a, 6), round(b, 6)] for a, b in t] for t in trajs])};
const BOCAS={json.dumps([[round(a, 6), round(b, 6)] for a, b in bocas])};
const latGrp=L.layerGroup(TR.map(t=>L.polyline(t,{{color:'#222',weight:1,opacity:0.55}}))
  .concat(BOCAS.map(b=>L.circleMarker(b,{{radius:2,color:'#222',weight:1,opacity:0.55,fill:false}})))).addTo(map);
const SEG={seg};
let segGrp=null;
if(SEG) segGrp=L.geoJSON(SEG,{{style:{{color:'#c51b8a',weight:2,opacity:0.9}},
  onEachFeature:(f,l)=>l.bindPopup('<b>SEGEMAR</b> '+(f.properties.capa||'')+'<br>'+(f.properties.tipo||'')+' — '+(f.properties.certidumbre||''))}}).addTo(map);
const LIN={json.dumps(feats_out)};
const linGrp=L.layerGroup(LIN.map(f=>{{
  const pl=L.polyline(f.geo,{{color:'#00c2a0',weight:4,opacity:0.95}});
  let html='<div class="pp"><b>L'+f.p.id+'</b> · azimut '+f.p.azimut_deg+'° · '+f.p.largo_km+' km · |∇v| '+f.p.grad_mmyr_km+' mm/año/km';
  if(f.p.clase) html+='<br>ajuste: <b>'+f.p.clase+'</b> · salto '+(f.p.salto>0?'+':'')+f.p.salto+' mm/año · ancho '+f.p.ancho+' m · ΔBIC '+Math.round(f.p.dbic);
  if(f.p.png) html+='<img src="data:image/png;base64,'+f.p.png+'">';
  html+='</div>';
  pl.bindPopup(html,{{maxWidth:560}});
  return pl;
}})).addTo(map);
L.control.layers(null,{{'Velocidad LOS':velL,'|∇v| (gradiente)':gradL,'Lineamientos':linGrp,
  'Laterales/pozos':latGrp,...(segGrp?{{'SEGEMAR':segGrp}}:{{}})}},{{collapsed:false}}).addTo(map);
</script></body></html>"""
    OUT_ = HERE / f"demo_calera_fallas{args.suffix}.html" if args.suffix else OUT
    OUT_.write_text(html, encoding="utf-8")
    print(f"Listo → {OUT_}  ({len(feats_out)} lineamientos, vmax {vmax:.1f} mm/año)")


if __name__ == "__main__":
    main()
