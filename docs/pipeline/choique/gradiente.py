#!/usr/bin/env python
"""Bajo del Choique — detección de discontinuidades del campo de velocidad InSAR.

Del campo de velocidad LOS (MintPy) deriva:
  1. |∇v| en mm/año/km (suavizado robusto: mediana 3x3 + gaussiana σ=1.5 px)
  2. curvatura (laplaciano) — flexura = banda de un signo; falla = dipolo ± apretado
  3. lineamientos candidatos: |∇v| ≥ percentil --pctl → cierre morfológico →
     componentes elongadas (≥ --min-px px, elongación ≥ 3) → esqueleto → polilíneas

Salidas: choique_gradiente.png (4 paneles + rosa de azimuts) y _data/grad_candidates.geojson
(con azimut, |∇v| mediano, largo km por lineamiento).

Por defecto lee ./mintpy_int80 (40 m). Con --src se puede apuntar a otra corrida
MintPy (p.ej. el 80 m de t18_f1050 para un screening previo):

    ~/miniforge3/bin/mamba run -n insar python exploraciones/choique/gradiente.py
    ... gradiente.py --src ../../t18_f1050 --suffix _80m
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

import h5py
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from pyproj import Transformer
from scipy import ndimage
from skimage.measure import label, regionprops
from skimage.morphology import closing, skeletonize

HERE = Path(__file__).resolve().parent
DATA = HERE / "_data"
WELLS = DATA / "choique_wells_all.json"
SEGEMAR = HERE.parent / "calera" / "_data" / "fallas_segemar.geojson"
SEAMS = DATA / "burst_seams.geojson"   # costuras de empalme (burst_seams.py)
# bloque LCA + margen (idéntico al subset de mintpy_calera.cfg)
LON0, LAT0, LON1, LAT1 = -69.51, -37.84, -69.05, -37.42
BLOQUE_ID = "BCLI"
CONC = Path("/var/home/matias/Projects/estado-del-sistema/public/data/concesiones_neuquina.geojson")


def load_velocity(src: Path):
    """velocity.h5 + maskTempCoh.h5 (MintPy geocodificado UTM) → recorte al bloque."""
    with h5py.File(src / "velocity.h5") as f:
        at = dict(f.attrs)
        vel = f["velocity"][:] * 1000.0  # m/yr → mm/yr
    with h5py.File(src / "maskTempCoh.h5") as f:
        mask = f["mask"][:].astype(bool)
    epsg = at.get("EPSG", "32719")
    epsg = epsg.decode() if isinstance(epsg, bytes) else str(int(float(epsg)))
    x0, y0 = float(at["X_FIRST"]), float(at["Y_FIRST"])
    dx, dy = float(at["X_STEP"]), float(at["Y_STEP"])
    tr = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    xs, ys = tr.transform([LON0, LON1, LON0, LON1], [LAT0, LAT1, LAT1, LAT0])
    c0 = max(int((min(xs) - x0) / dx), 0); c1 = min(int((max(xs) - x0) / dx) + 1, vel.shape[1])
    r0 = max(int((max(ys) - y0) / dy), 0); r1 = min(int((min(ys) - y0) / dy) + 1, vel.shape[0])
    v = np.where(mask[r0:r1, c0:c1], vel[r0:r1, c0:c1], np.nan)
    grid = dict(epsg=epsg, x0=x0 + c0 * dx, y0=y0 + r0 * dy, dx=dx, dy=dy)
    print(f"recorte {v.shape} px  paso {abs(dx):.0f} m  válidos {np.isfinite(v).mean()*100:.0f}%")
    return v, grid


def smooth_robust(v, sigma=1.5):
    """mediana 3x3 (NaN-aware) + gaussiana con normalización por pesos (respeta NaN)."""
    med = ndimage.generic_filter(v, np.nanmedian, size=3, mode="nearest")
    w = np.isfinite(med).astype(float)
    f = np.where(np.isfinite(med), med, 0.0)
    num = ndimage.gaussian_filter(f, sigma)
    den = ndimage.gaussian_filter(w, sigma)
    out = np.where(den > 0.3, num / np.maximum(den, 1e-9), np.nan)
    return np.where(np.isfinite(v), out, np.nan)


def skeleton_paths(sk):
    """esqueleto binario → lista de caminos [ (fila, col), ... ] ordenados por vecindad."""
    paths = []
    lab, n = ndimage.label(sk, structure=np.ones((3, 3)))
    for i in range(1, n + 1):
        pix = set(map(tuple, np.argwhere(lab == i)))
        if len(pix) < 2:
            continue
        nbr = {p: [q for q in pix if q != p and abs(q[0]-p[0]) <= 1 and abs(q[1]-p[1]) <= 1]
               for p in pix}
        ends = [p for p, ns in nbr.items() if len(ns) == 1]
        start = ends[0] if ends else next(iter(pix))
        path, seen, cur = [start], {start}, start
        while True:
            nxt = [q for q in nbr[cur] if q not in seen]
            if not nxt:
                break
            cur = nxt[0]
            path.append(cur); seen.add(cur)
        paths.append(path)
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=str(HERE / "mintpy_int80"))
    ap.add_argument("--suffix", default="")
    ap.add_argument("--pctl", type=float, default=96.0)
    ap.add_argument("--min-px", type=int, default=10)
    ap.add_argument("--min-elong", type=float, default=3.0)
    ap.add_argument("--min-km", type=float, default=0.8,
                    help="largo mínimo del lineamiento [km] (tras encadenar)")
    ap.add_argument("--gap-km", type=float, default=3.5,
                    help="encadenar segmentos colineales separados hasta este gap")
    ap.add_argument("--az-tol", type=float, default=25.0,
                    help="tolerancia de azimut para encadenar [deg]")
    ap.add_argument("--buffer-km", type=float, default=2.5,
                    help="candidatos con centroide a menos de esto del bloque")
    args = ap.parse_args()

    v, g = load_velocity(Path(args.src))
    step_m = abs(g["dx"])
    vs = smooth_robust(v)

    gy, gx = np.gradient(vs, step_m, step_m)          # mm/yr por m
    grad = np.hypot(gx, gy) * 1000.0                  # mm/yr por km
    # curvatura sobre un campo extra-suavizado: el laplaciano amplifica la alta frecuencia
    vs_c = smooth_robust(vs, sigma=3.0)
    curv = ndimage.laplace(np.nan_to_num(vs_c)) / step_m**2 * 1e6  # mm/yr/km²
    curv[~np.isfinite(vs_c)] = np.nan

    thr = np.nanpercentile(grad, args.pctl)
    binm = np.nan_to_num(grad) >= thr
    binm[:5, :] = binm[-5:, :] = False   # bordes del subset: gradiente espurio
    binm[:, :5] = binm[:, -5:] = False
    binm = closing(binm, footprint=np.ones((5, 5)))  # 5x5: une segmentos vecinos del mismo lineamiento
    lab = label(binm, connectivity=2)
    keep = np.zeros_like(binm)
    cands = []
    for rp in regionprops(lab):
        elong = rp.axis_major_length / max(rp.axis_minor_length, 1e-6)
        if rp.num_pixels >= args.min_px and elong >= args.min_elong:
            keep |= lab == rp.label
    sk = skeletonize(keep)

    tr_inv = Transformer.from_crs(f"EPSG:{g['epsg']}", "EPSG:4326", always_xy=True)

    def rc2ll(path):
        xs = [g["x0"] + (c + 0.5) * g["dx"] for _, c in path]
        ys = [g["y0"] + (r + 0.5) * g["dy"] for r, _ in path]
        lons, lats = tr_inv.transform(xs, ys)
        return list(zip(lons, lats)), np.array(xs), np.array(ys)

    # polígono del bloque (para retener solo candidatos en el bloque + buffer)
    from shapely.geometry import shape, Point
    gj_blk = json.load(open(CONC))
    poly_blk = shape(next(f["geometry"] for f in gj_blk["features"]
                          if f["properties"].get("id") == BLOQUE_ID))
    tr_deg = args.buffer_km / 111.0   # buffer aproximado en grados
    poly_buf = poly_blk.buffer(tr_deg)

    def azim(xs, ys):
        dxy = np.column_stack([xs - xs.mean(), ys - ys.mean()])
        _, _, vt = np.linalg.svd(dxy, full_matrices=False)
        return (np.degrees(np.arctan2(vt[0][0], vt[0][1])) + 360) % 180  # geográfico 0-180

    def az_diff(a, b):
        d = abs(a - b) % 180
        return min(d, 180 - d)

    # segmentos crudos en UTM (se descartan migas < 0.25 km)
    segs = []
    for path in skeleton_paths(sk):
        ll, xs, ys = rc2ll(path)
        L = np.hypot(np.diff(xs), np.diff(ys)).sum() / 1000.0
        if L < 0.25:
            continue
        segs.append(dict(xs=np.asarray(xs), ys=np.asarray(ys), path=list(path)))

    # ENCADENAMIENTO: une segmentos colineales (mismo rumbo ± az-tol) con extremos
    # a < gap-km — un lineamiento largo suele salir fragmentado del esqueleto
    def try_merge(a, b):
        if az_diff(azim(a["xs"], a["ys"]), azim(b["xs"], b["ys"])) > args.az_tol:
            return None
        ends_a = [(a["xs"][0], a["ys"][0], 0), (a["xs"][-1], a["ys"][-1], -1)]
        ends_b = [(b["xs"][0], b["ys"][0], 0), (b["xs"][-1], b["ys"][-1], -1)]
        best = min(((np.hypot(xa - xb, ya - yb), ia, ib)
                    for xa, ya, ia in ends_a for xb, yb, ib in ends_b),
                   key=lambda t: t[0])
        d, ia, ib = best
        if d > args.gap_km * 1000:
            return None
        # el puente también tiene que ser colineal (no unir paralelas desplazadas)
        xa, ya, _ = ends_a[0 if ia == 0 else 1]; xb, yb, _ = ends_b[0 if ib == 0 else 1]
        az_bridge = (np.degrees(np.arctan2(xb - xa, yb - ya)) + 360) % 180
        if az_diff(az_bridge, azim(a["xs"], a["ys"])) > args.az_tol + 10:
            return None
        xs_a = a["xs"] if ia == -1 else a["xs"][::-1]
        ys_a = a["ys"] if ia == -1 else a["ys"][::-1]
        xs_b = b["xs"] if ib == 0 else b["xs"][::-1]
        ys_b = b["ys"] if ib == 0 else b["ys"][::-1]
        return dict(xs=np.concatenate([xs_a, xs_b]), ys=np.concatenate([ys_a, ys_b]),
                    path=a["path"] + b["path"])

    merged = True
    while merged:
        merged = False
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                m = try_merge(segs[i], segs[j])
                if m is not None:
                    segs[i] = m
                    del segs[j]
                    merged = True
                    break
            if merged:
                break

    # costuras de empalme del producto multi-burst: un "lineamiento" que corre
    # SOBRE una costura y con su mismo rumbo es artefacto de mosaico, no geología
    seam_lines = []
    if SEAMS.exists():
        from shapely.geometry import LineString
        tr_fw2 = Transformer.from_crs("EPSG:4326", f"EPSG:{g['epsg']}", always_xy=True)
        for f in json.load(open(SEAMS))["features"]:
            cc = f["geometry"]["coordinates"]
            xs2, ys2 = tr_fw2.transform([p[0] for p in cc], [p[1] for p in cc])
            ln = LineString(zip(xs2, ys2))
            xy = np.array(ln.coords)
            az_s = (np.degrees(np.arctan2(xy[-1, 0] - xy[0, 0], xy[-1, 1] - xy[0, 1])) + 360) % 180
            seam_lines.append((ln, az_s))
        print(f"costuras cargadas: {len(seam_lines)}")

    def es_costura(xs, ys, az):
        from shapely.geometry import Point as ShPoint
        for ln, az_s in seam_lines:
            if az_diff(az, az_s) > 12:
                continue
            dmed = np.median([ln.distance(ShPoint(x, y)) for x, y in zip(xs[::3], ys[::3])])
            if dmed < 2500:   # la costura real cae en el borde del solape (~2 km de la línea media)
                return True
        return False

    tr_ll = Transformer.from_crs(f"EPSG:{g['epsg']}", "EPSG:4326", always_xy=True)
    feats = []
    for s in sorted(segs, key=lambda s: -len(s["xs"])):
        xs, ys = s["xs"], s["ys"]
        seg = np.hypot(np.diff(xs), np.diff(ys)).sum() / 1000.0  # km
        if seg < args.min_km:
            continue
        lons, lats = tr_ll.transform(xs, ys)
        lon_c, lat_c = float(np.mean(lons)), float(np.mean(lats))
        if not poly_buf.contains(Point(lon_c, lat_c)):
            continue
        az = azim(xs, ys)
        if es_costura(xs, ys, az):
            print(f"  descartado por costura de empalme: {seg:.1f} km az {az:.0f}°")
            continue
        gmed = float(np.nanmedian([grad[r, c] for r, c in s["path"]]))
        feats.append({"type": "Feature",
                      "geometry": {"type": "LineString",
                                   "coordinates": [[round(x, 6), round(y, 6)]
                                                   for x, y in zip(lons, lats)]},
                      "properties": {"id": len(feats) + 1, "azimut_deg": round(az, 1),
                                     "grad_mmyr_km": round(gmed, 2), "largo_km": round(seg, 2)}})
    out_gj = DATA / f"grad_candidates{args.suffix}.geojson"
    json.dump({"type": "FeatureCollection", "features": feats}, open(out_gj, "w"))
    print(f"lineamientos candidatos: {len(feats)} → {out_gj}")
    for f in feats:
        p = f["properties"]
        print(f"  #{p['id']}: {p['largo_km']:.1f} km  az {p['azimut_deg']:.0f}°  "
              f"|∇v| {p['grad_mmyr_km']:.1f} mm/año/km")

    # ---------- figura ----------
    ext = [g["x0"], g["x0"] + v.shape[1] * g["dx"], g["y0"] + v.shape[0] * g["dy"], g["y0"]]
    tr_fw = Transformer.from_crs("EPSG:4326", f"EPSG:{g['epsg']}", always_xy=True)

    wells = json.load(open(WELLS)) if WELLS.exists() else {}
    lat_xy = []
    for w in wells.values():
        pts = w["traj"] if w["has_traj"] else [w["boca"]]
        xs, ys = tr_fw.transform([p[0] for p in pts], [p[1] for p in pts])
        lat_xy.append((xs, ys))

    conc_xy = []
    gj = json.load(open(CONC))
    geom = next(f["geometry"] for f in gj["features"] if f["properties"].get("id") == BLOQUE_ID)
    rings = geom["coordinates"] if geom["type"] == "Polygon" else [r for p in geom["coordinates"] for r in p]
    for ring in rings:
        xs, ys = tr_fw.transform([p[0] for p in ring], [p[1] for p in ring])
        conc_xy.append((xs, ys))

    seg_xy = []
    if SEGEMAR.exists():
        for f in json.load(open(SEGEMAR))["features"]:
            geo = f["geometry"]
            lines = ([geo["coordinates"]] if geo["type"] == "LineString"
                     else geo["coordinates"] if geo["type"] == "MultiLineString" else [])
            for ln in lines:
                xs, ys = tr_fw.transform([p[0] for p in ln], [p[1] for p in ln])
                seg_xy.append((xs, ys, f["properties"].get("capa", "")))

    def deco(ax):
        for xs, ys in conc_xy:
            ax.plot(xs, ys, "k--", lw=1.0, alpha=0.8)
        ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
        ax.set_xticks([]); ax.set_yticks([]); ax.set_aspect("equal")

    fig, axs = plt.subplots(1, 4, figsize=(21, 6.2),
                            gridspec_kw=dict(width_ratios=[1, 1, 1, 0.62]))
    vmax = np.nanpercentile(np.abs(vs), 99)
    im0 = axs[0].imshow(vs, extent=ext, cmap="RdBu", norm=TwoSlopeNorm(0, -vmax, vmax))
    for xs, ys in lat_xy:
        axs[0].plot(xs, ys, "-", color="0.25", lw=0.4, alpha=0.55)
    deco(axs[0]); axs[0].set_title("Velocidad LOS suavizada [mm/año] + laterales")
    plt.colorbar(im0, ax=axs[0], shrink=0.8)

    im1 = axs[1].imshow(grad, extent=ext, cmap="magma",
                        vmin=0, vmax=np.nanpercentile(grad, 99.5))
    deco(axs[1]); axs[1].set_title("|∇v| [mm/año/km]")
    plt.colorbar(im1, ax=axs[1], shrink=0.8)

    cmax = np.nanpercentile(np.abs(curv), 98)
    im2 = axs[2].imshow(curv, extent=ext, cmap="PuOr", norm=TwoSlopeNorm(0, -cmax, cmax))
    for f in feats:
        cc = f["geometry"]["coordinates"]
        xs, ys = tr_fw.transform([p[0] for p in cc], [p[1] for p in cc])
        for a in (axs[1], axs[2]):
            a.plot(xs, ys, "-", color="#00c2a0", lw=1.6)
        xm, ym = np.mean(xs), np.mean(ys)
        axs[2].annotate(str(f["properties"]["id"]), (xm, ym), color="#007a63",
                        fontsize=9, fontweight="bold")
    for xs, ys, capa in seg_xy:
        axs[2].plot(xs, ys, "-", color="#c51b8a", lw=1.4, alpha=0.9)
    deco(axs[2]); axs[2].set_title("Curvatura [mm/año/km²] + lineamientos (verde) + SEGEMAR (rosa)")
    plt.colorbar(im2, ax=axs[2], shrink=0.8)

    axr = plt.subplot(1, 4, 4, projection="polar")
    azs = [np.radians(f["properties"]["azimut_deg"]) for f in feats]
    lens = [f["properties"]["largo_km"] for f in feats]
    if azs:
        azs = azs + [a + np.pi for a in azs]  # simetría 180°
        lens = lens + lens
        axr.bar(azs, lens, width=np.radians(10), color="#00c2a0", alpha=0.8)
    axr.set_theta_zero_location("N"); axr.set_theta_direction(-1)
    axr.set_title("Rosa de azimuts\n(largo km)", fontsize=10)

    fig.suptitle(f"Bajo del Choique — discontinuidades del campo de velocidad "
                 f"(paso {step_m:.0f} m, umbral p{args.pctl:.0f} = {thr:.1f} mm/año/km)",
                 fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out_png = HERE / f"choique_gradiente{args.suffix}.png"
    fig.savefig(out_png, dpi=140)
    print("guardado:", out_png)


if __name__ == "__main__":
    main()
