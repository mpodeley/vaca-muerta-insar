#!/usr/bin/env python
"""Bandurria Sur — deformación acumulada en el tiempo (slider) + voidage por pozo que crece
con el slider. Estilo Leaflet + basemap satelital, como t18_f1050/05_timeseries_slider.py.

Cada paso del slider muestra, hasta esa fecha:
  - raster = desplazamiento LOS acumulado (rojo=subsidencia, azul=uplift), recortado al bloque;
  - elipses por pozo (orientadas al lateral): anillo = voidage de reservorio total acumulado,
    relleno = parte petróleo (misma escala rm³). Dibujadas en JS desde centro+azimut+volumen.

    ~/miniforge3/bin/mamba run -n insar python exploraciones/escala_pozo/bsur_slider.py
"""
from __future__ import annotations
import base64, io, json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = HERE / "_data"
TS = ROOT / "t18_f1050" / "timeseries_ERA5_ramp_demErr.h5"
MASK = ROOT / "t18_f1050" / "maskTempCoh.h5"
CONC = Path("/var/home/matias/Projects/estado-del-sistema/public/data/concesiones_neuquina.geojson")
OUT = HERE / "demo_bsur_slider.html"
MARGIN_PX = 16
BO, BW, BG = 1.4, 1.03, 0.0035
SIGMA_DAYS = 45.0


def decimal_years(dates):
    from datetime import date
    out = []
    for d in dates:
        dt = date(int(d[:4]), int(d[4:6]), int(d[6:8]))
        out.append(dt.year + (dt - date(dt.year, 1, 1)).days / 365.25)
    return np.array(out)


def pick_quarterly(dates):
    seen, idx = set(), []
    for i, d in enumerate(dates):
        q = (d[:4], (int(d[4:6]) - 1) // 3)
        if q not in seen:
            seen.add(q); idx.append(i)
    if idx[-1] != len(dates) - 1:
        idx.append(len(dates) - 1)
    return idx


def reproject_4326(arr, transform, crs):
    import rasterio
    from rasterio.warp import Resampling, calculate_default_transform, reproject
    h, w = arr.shape
    dt, dw, dh = calculate_default_transform(crs, "EPSG:4326", w, h,
        *rasterio.transform.array_bounds(h, w, transform))
    dst = np.full((dh, dw), np.nan, "float32")
    reproject(source=arr, destination=dst, src_transform=transform, src_crs=crs,
              dst_transform=dt, dst_crs="EPSG:4326", resampling=Resampling.nearest,
              src_nodata=np.nan, dst_nodata=np.nan)
    south, west = dt.f + dh * dt.e, dt.c
    north, east = dt.f, dt.c + dw * dt.a
    return dst, (south, west, north, east)


def png_b64(arr, norm, cmap):
    import matplotlib.pyplot as plt
    rgba = cmap(norm(arr))
    rgba[..., 3] = np.where(np.isfinite(arr), 0.82, 0.0)
    buf = io.BytesIO(); plt.imsave(buf, rgba, format="png")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def main():
    import rasterio
    from matplotlib import cm, colors
    from pyproj import Transformer
    fwd = Transformer.from_crs("EPSG:4326", "EPSG:32719", always_xy=True)

    wells = json.load(open(DATA / "bsur_wells.json"))
    mon = pd.read_csv(DATA / "bsur_monthly_perwell.csv").sort_values("ym")
    mon["v_oil"] = mon.prod_pet.clip(lower=0) * BO
    mon["v_tot"] = mon.v_oil + mon.prod_agua.clip(lower=0) * BW + mon.prod_gas.clip(lower=0) * 1000 * BG
    g = mon.groupby("idpozo")
    mon["cum_tot"] = g.v_tot.cumsum(); mon["cum_oil"] = g.v_oil.cumsum()

    for idp, w in wells.items():
        xs, ys = fwd.transform([p[0] for p in w["coords"]], [p[1] for p in w["coords"]])
        xs, ys = np.array(xs), np.array(ys)
        w["cx_lon"] = float(np.mean([p[0] for p in w["coords"]]))
        w["cy_lat"] = float(np.mean([p[1] for p in w["coords"]]))
        pts = np.column_stack([xs - xs.mean(), ys - ys.mean()])
        _, _, vt = np.linalg.svd(pts, full_matrices=False)
        w["ang"] = float(np.degrees(np.arctan2(vt[0][1], vt[0][0])))  # azimut lateral (matemático)
        w["_cx"], w["_cy"] = float(xs.mean()), float(ys.mean())

    with h5py.File(TS, "r") as h:
        a = dict(h.attrs)
        dates = [d.decode() for d in h["date"][:]]
        X0, Y0 = float(a["X_FIRST"]), float(a["Y_FIRST"])
        xs_, ys_ = float(a["X_STEP"]), float(a["Y_STEP"])
        allx = np.array([w["_cx"] for w in wells.values()])
        ally = np.array([w["_cy"] for w in wells.values()])
        # ventana al bloque
        c0 = max(int((allx.min() - X0) / xs_) - MARGIN_PX, 0)
        c1 = int((allx.max() - X0) / xs_) + MARGIN_PX
        r0 = max(int((ally.max() - Y0) / ys_) - MARGIN_PX, 0)
        r1 = int((ally.min() - Y0) / ys_) + MARGIN_PX
        sel = pick_quarterly(dates)
        ts = h["timeseries"][:, r0:r1, c0:c1]
    with h5py.File(MASK, "r") as h:
        mask = h["mask"][r0:r1, c0:c1].astype(bool)

    # suavizado temporal Gaussiano (como el slider original)
    t = decimal_years(dates)
    flat = ts.reshape(len(dates), -1)
    rows = []
    for i in sel:
        wts = np.exp(-0.5 * ((t - t[i]) / (SIGMA_DAYS / 365.25)) ** 2); wts /= wts.sum()
        rows.append(wts @ flat)
    stack = np.array(rows, "float32").reshape(len(sel), *ts.shape[1:]) * 1000.0
    stack[:, ~mask] = np.nan
    dates_sel = [dates[i] for i in sel]

    transform = rasterio.transform.Affine(xs_, 0, X0 + c0 * xs_, 0, ys_, Y0 + r0 * ys_)
    crs = rasterio.crs.CRS.from_epsg(int(a["EPSG"]))
    vmax = float(np.nanpercentile(np.abs(stack[np.isfinite(stack)]), 98)) or 10.0
    norm = colors.TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)
    cmap = cm.get_cmap("RdBu")

    frames, bounds = [], None
    for k in range(len(sel)):
        arr, bnds = reproject_4326(stack[k], transform, crs); bounds = bnds
        d = dates_sel[k]
        frames.append({"label": f"{d[:4]}-{d[4:6]}", "png": png_b64(arr, norm, cmap)})

    # voidage acumulado por pozo en cada paso
    ymsel = [f"{d[:4]}-{d[4:6]}" for d in dates_sel]
    cum = mon.groupby(["idpozo", "ym"])[["cum_tot", "cum_oil"]].last()
    ct_max = float(mon.cum_tot.max())
    wlist = []
    for idp, w in wells.items():
        sub = cum.loc[int(idp)] if int(idp) in cum.index.get_level_values(0) else None
        ct, co = [], []
        prev_t = prev_o = 0.0
        for ym in ymsel:
            if sub is not None and ym in sub.index:
                prev_t, prev_o = float(sub.loc[ym, "cum_tot"]), float(sub.loc[ym, "cum_oil"])
            elif sub is not None:
                past = sub[sub.index <= ym]
                if len(past):
                    prev_t, prev_o = float(past.cum_tot.iloc[-1]), float(past.cum_oil.iloc[-1])
            ct.append(round(prev_t, 1)); co.append(round(prev_o, 1))
        wlist.append({"lat": round(w["cy_lat"], 6), "lon": round(w["cx_lon"], 6),
                      "ang": round(w["ang"], 1),
                      "traj": [[round(p[1], 6), round(p[0], 6)] for p in w["coords"]],
                      "ct": ct, "co": co})

    write_html(frames, bounds, vmax, wlist, ct_max)
    print(f"Listo → {OUT}  ({len(frames)} pasos, {len(wlist)} pozos, vmax {vmax:.0f} mm)")


def write_html(frames, bounds, vmax, wells, ct_max):
    s, w, n, e = bounds
    conc = "null"
    if CONC.exists():
        gj = json.load(open(CONC))
        feats = [f for f in gj["features"]
                 if "BANDURRIA" in (json.dumps(f.get("properties", {})).upper())]
        conc = json.dumps({"type": "FeatureCollection", "features": feats}) if feats else "null"
    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<title>Bandurria Sur — deformación + voidage acumulado (slider)</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
 html,body,#map{{height:100%;margin:0}}
 .panel{{position:absolute;bottom:18px;left:50%;transform:translateX(-50%);z-index:1000;
   background:rgba(255,255,255,.94);padding:10px 16px;border-radius:8px;
   font:13px sans-serif;box-shadow:0 1px 6px rgba(0,0,0,.3);width:min(560px,86vw)}}
 #date{{font-weight:bold;color:#222}} input[type=range]{{width:100%}}
 .legend{{position:absolute;top:12px;right:12px;z-index:1000;background:rgba(255,255,255,.93);
   padding:8px 12px;border-radius:6px;font:12px sans-serif}}
 .bar{{height:10px;width:180px;background:linear-gradient(to right,#b2182b,#f7f7f7,#2166ac);
   border:1px solid #999;margin:3px 0}}
 .bl{{display:flex;justify-content:space-between;font-size:11px}}
 .ell{{display:flex;gap:6px;align-items:center;margin-top:6px;font-size:11px;color:#333}}
 .sw{{width:16px;height:9px;border:1px solid #111;border-radius:50%}}
 .sw.oil{{background:rgba(20,20,20,.55);border:none}}
 #play{{cursor:pointer;border:none;background:#334;color:#fff;border-radius:5px;padding:2px 9px;font-size:13px}}
</style></head><body>
<div id="map"></div>
<div class="legend"><b>Deformación acumulada (LOS)</b>
 <div class="bar"></div>
 <div class="bl"><span>−{vmax:.0f} mm</span><span>0</span><span>+{vmax:.0f} mm</span></div>
 <div class="ell"><span class="sw"></span>voidage total acum.</div>
 <div class="ell"><span class="sw oil"></span>parte petróleo</div>
</div>
<div class="panel">
 <div><button id="play">▶</button> &nbsp;<b>Bandurria Sur</b> · <span id="date"></span></div>
 <input type="range" id="sl" min="0" max="{len(frames)-1}" value="{len(frames)-1}" step="1">
 <div style="font-size:11px;color:#666;text-align:center">
   Sentinel-1/SBAS · subsidencia (rojo) vs uplift (azul) · elipse = voidage de reservorio por pozo (anillo total, relleno petróleo)</div>
</div>
<script>
const FR={json.dumps(frames)}, WELLS={json.dumps(wells)}, CTMAX={ct_max}, AMAX=900, ASPECT=3.0;
const B=[[{s},{w}],[{n},{e}]];
const map=L.map('map').fitBounds(B);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
  {{attribution:'Esri World Imagery'}}).addTo(map);
const layers=FR.map(f=>L.imageOverlay('data:image/png;base64,'+f.png,B,{{opacity:0}}).addTo(map));
const CONC={conc};
if(CONC) L.geoJSON(CONC,{{style:{{fill:false,color:'#fff',weight:1.4,opacity:0.8,dashArray:'4 3'}}}}).addTo(map);
// trayectorias (estáticas)
WELLS.forEach(p=>L.polyline(p.traj,{{color:'#222',weight:1,opacity:0.5}}).addTo(map));
const ellGrp=L.layerGroup().addTo(map);
const M_LAT=111320;
function ellipse(lat,lon,angDeg,a_m,fill){{
  if(a_m<25) return null;
  const b_m=a_m/ASPECT, th=angDeg*Math.PI/180, mlon=M_LAT*Math.cos(lat*Math.PI/180);
  const pts=[];
  for(let i=0;i<=28;i++){{const t=2*Math.PI*i/28;
    const dx=(a_m/2)*Math.cos(t), dy=(b_m/2)*Math.sin(t);
    const rx=dx*Math.cos(th)-dy*Math.sin(th), ry=dx*Math.sin(th)+dy*Math.cos(th);
    pts.push([lat+ry/M_LAT, lon+rx/mlon]);}}
  return L.polygon(pts, fill
    ?{{stroke:false,fillColor:'#141414',fillOpacity:0.45}}
    :{{color:'#111',weight:1,fill:false,opacity:0.9}});
}}
function drawEll(i){{
  ellGrp.clearLayers();
  WELLS.forEach(p=>{{
    const at=AMAX*Math.sqrt(Math.max(p.ct[i],0)/CTMAX);
    const ao=AMAX*Math.sqrt(Math.max(p.co[i],0)/CTMAX);
    const e1=ellipse(p.lat,p.lon,p.ang,at,false); if(e1)e1.addTo(ellGrp);
    const e2=ellipse(p.lat,p.lon,p.ang,ao,true); if(e2)e2.addTo(ellGrp);
  }});
}}
const sl=document.getElementById('sl'), dt=document.getElementById('date');
function show(i){{layers.forEach((l,k)=>l.setOpacity(k==i?1:0)); dt.textContent=FR[i].label; drawEll(i);}}
sl.addEventListener('input',ev=>show(+ev.target.value));
// play
let timer=null;
document.getElementById('play').addEventListener('click',function(){{
  if(timer){{clearInterval(timer);timer=null;this.textContent='▶';return;}}
  this.textContent='⏸';
  timer=setInterval(()=>{{let i=(+sl.value+1)%FR.length; sl.value=i; show(i);}},700);
}});
show(FR.length-1);
</script></body></html>"""
    OUT.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
