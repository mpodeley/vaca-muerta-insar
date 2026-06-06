#!/usr/bin/env python
"""Tres mecanismos geomecánicos compitiendo en la deformación (escala pozo):
  (1) depleción → compactación → subsidencia  (proxy: extracción de líquido VM)
  (2) agua de fractura → SIGNO ABIERTO: hinchamiento (heave) vs water-weakening (compactación)
  (3) inyección activa de agua → inflación poroelástica → uplift  (sumideros, clase aparte)

A.0  velocidad por pozo VM = MEDIA a lo largo del lateral (no en la boca), usando trayectorias_vm.
A    regresión múltiple vel ~ z(log extr_vm_liq) + z(log frac_agua) entre productores VM → signo de β2.
     + correlación parcial de rango, métrica de ratio, e inyección↔vel entre sumideros.
B    campos de densidad (extracción VM / agua fractura / inyección) vs subsidencia, corr. gridded.

    ~/miniforge3/bin/mamba run -n insar python exploraciones/escala_pozo/geomecanica.py
"""
from __future__ import annotations
import csv, json
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = HERE / "_data"
VEL_TIF = ROOT / "t18_f1050" / "_velocity_wgs84.tif"
CSV = HERE / "pozos_voidage.csv"
TRAJ = DATA / "trayectorias_vm.csv"
LON0, LON1, LAT0, LAT1 = -70.6, -68.2, -39.2, -37.3
csv.field_size_limit(1 << 24)


# ----------------------------------------------------------------- A.0 laterales
def lateral_vertices() -> dict:
    out = {}
    with open(TRAJ, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            gj = r.get("geojson")
            if not gj:
                continue
            try:
                idp = int(r["idpo"]); g = json.loads(gj); c = g["coordinates"]
                pts = ([p for ln in c for p in ln] if g["type"] == "MultiLineString"
                       else c if g["type"] == "LineString" else [c])
            except Exception:
                continue
            if pts:
                out[idp] = np.asarray(pts, float)
    return out


def vel_best(df, lat):
    """vel media sobre el lateral (VM con trayectoria), si no la boca de pozo."""
    import rasterio
    vbest = df.vel.astype(float).copy()
    with rasterio.open(VEL_TIF) as src:
        for i, idp in enumerate(df.idpozo):
            arr = lat.get(int(idp))
            if arr is None:
                continue
            sub = arr[:: max(1, len(arr) // 200)]
            vals = np.array([v[0] for v in src.sample([(x, y) for x, y in sub])], float)
            vals = vals[np.isfinite(vals) & (vals != 0)]
            if len(vals) >= 3:
                vbest.iat[i] = float(np.mean(vals))
    return vbest


# ----------------------------------------------------------------- stats helpers
def ols(y, X):
    """OLS con intercepto; devuelve betas, errores estándar, t y p (aprox normal)."""
    from scipy.stats import t as tdist
    Xc = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(Xc, y, rcond=None)
    resid = y - Xc @ beta
    n, k = Xc.shape
    s2 = resid @ resid / (n - k)
    cov = s2 * np.linalg.inv(Xc.T @ Xc)
    se = np.sqrt(np.diag(cov))
    tval = beta / se
    p = 2 * tdist.sf(np.abs(tval), n - k)
    return beta, se, tval, p, n


def partial_spearman(d, a, b, ctrl):
    """corr parcial de rango entre a y b controlando ctrl (residuos de rangos)."""
    from scipy.stats import rankdata, pearsonr
    ra, rb, rc = rankdata(d[a]), rankdata(d[b]), rankdata(d[ctrl])
    def resid(y, x):
        x1 = np.column_stack([np.ones(len(x)), x])
        bb, *_ = np.linalg.lstsq(x1, y, rcond=None)
        return y - x1 @ bb
    return pearsonr(resid(ra, rc), resid(rb, rc))


def main():
    from scipy.stats import spearmanr, mannwhitneyu
    df = pd.read_csv(CSV)
    df = df[df.lon.between(LON0, LON1) & df.lat.between(LAT0, LAT1)].copy()
    print("A.0  velocidad a lo largo del lateral (VM con trayectoria) ...", flush=True)
    df["vel"] = vel_best(df, lateral_vertices())

    vm = df[df.is_vm & (df.prod_pet > 0) & (df.frac_agua > 0) & (df.extr_vm_liq > 0)].copy()
    print(f"\n=== (A) Regresión múltiple entre productores VM (n={len(vm)}) ===")
    lx = np.log10(vm.extr_vm_liq); lf = np.log10(vm.frac_agua)
    z = lambda v: (v - v.mean()) / v.std()
    X = np.column_stack([z(lx), z(lf)])
    beta, se, tval, p, n = ols(vm.vel.values, X)
    print(f"  vel ~ b0 + b1·z(log extracción_VM) + b2·z(log agua_fractura)   (n={n})")
    print(f"  b1 (extracción) = {beta[1]:+.3f} ± {se[1]:.3f}  p={p[1]:.1e}   "
          f"[<0 ⇒ depleción→subsidencia]")
    print(f"  b2 (agua fract.) = {beta[2]:+.3f} ± {se[2]:.3f}  p={p[2]:.1e}   "
          f"[>0 ⇒ hinchamiento/heave ; <0 ⇒ ablandamiento→compactación]")
    rpf, ppf = partial_spearman(vm, "frac_agua", "vel", "extr_vm_liq")
    rpe, ppe = partial_spearman(vm, "extr_vm_liq", "vel", "frac_agua")
    print(f"  parcial Spearman vel↔agua_fractura | extracción = {rpf:+.3f} (p={ppf:.1e})")
    print(f"  parcial Spearman vel↔extracción | agua_fractura = {rpe:+.3f} (p={ppe:.1e})")

    print("\n=== (A) Ratio agua_fractura / extracción (hidratación vs depleción) ===")
    vm["ratio"] = vm.frac_agua / vm.extr_vm_liq
    rr, pr = spearmanr(vm.ratio, vm.vel)
    print(f"  vel ↔ ratio  Spearman={rr:+.3f} (p={pr:.1e})  "
          f"[>0 ⇒ más agua/menos extracción → menos subsidencia/uplift]")

    print("\n=== (3) Inyección → uplift (sumideros) ===")
    inj = df[df.is_iny].copy(); pro = df[df.es_productor] if "es_productor" in df else df[~df.is_iny]
    print(f"  inyectores n={len(inj)} vel_med={inj.vel.median():+.2f} | "
          f"productores vel_med={pro.vel.median():+.2f}  "
          f"MWU(iny>prod) p={mannwhitneyu(inj.vel,pro.vel,alternative='greater').pvalue:.1e}")
    d = inj[inj.iny_agua > 0]
    if len(d) > 20:
        ri, pi = spearmanr(d.iny_agua, d.vel)
        print(f"  entre inyectores: vel ↔ iny_agua Spearman={ri:+.3f} (p={pi:.1e})  "
              f"[>0 ⇒ más inyección → más uplift]")
        for q in (0.5, 0.8, 0.95):
            thr = d.iny_agua.quantile(q)
            up = (d[d.iny_agua >= thr].vel > 0).mean() * 100
            print(f"    inyectores top-{int((1-q)*100)}% por iny_agua: {up:.0f}% en uplift")

    df.to_csv(HERE / "pozos_geomec.csv", index=False)
    make_fields(df)


# ----------------------------------------------------------------- B campos
def make_fields(df, ncell=240):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import colors
    from scipy.ndimage import gaussian_filter
    from scipy.stats import spearmanr
    import sys
    sys.path.insert(0, str(HERE))
    from pozos_visuals import velocity_grid

    xe = np.linspace(LON0, LON1, ncell + 1); ye = np.linspace(LAT0, LAT1, ncell + 1)
    latm = (LAT0 + LAT1) / 2
    area = (xe[1]-xe[0])*111.32*np.cos(np.radians(latm)) * (ye[1]-ye[0])*110.57

    def field(sub, col, sigma=1.0):
        H, _, _ = np.histogram2d(sub.lat, sub.lon, bins=[ye, xe], weights=sub[col])
        cnt, _, _ = np.histogram2d(sub.lat, sub.lon, bins=[ye, xe])
        return gaussian_filter(H/area, sigma), cnt
    f_extr, c_extr = field(df[df.is_vm], "extr_vm_liq", 0.8)
    f_frac, c_frac = field(df[df.is_vm & (df.frac_agua > 0)], "frac_agua", 0.8)
    f_inj, c_inj = field(df[df.iny_agua > 0], "iny_agua", 1.2)
    velg = velocity_grid(ncell)

    def gcorr(f, c):
        m = (c > 0) & np.isfinite(velg)
        return spearmanr(f[m], velg[m])[0], int(m.sum())
    re_, ne = gcorr(f_extr, c_extr); rf, nf = gcorr(f_frac, c_frac); ri, ni = gcorr(f_inj, c_inj)
    print(f"\n=== (B) corr gridded campo↔velocidad ===")
    print(f"  extracción VM ↔ vel = {re_:+.2f} (n={ne})   [subsidencia]")
    print(f"  agua fractura ↔ vel = {rf:+.2f} (n={nf})   [signo = mecanismo]")
    print(f"  inyección     ↔ vel = {ri:+.2f} (n={ni})   [>0 ⇒ uplift]")

    ext = [LON0, LON1, LAT0, LAT1]
    fig, ax = plt.subplots(1, 4, figsize=(20, 5.2))
    for a, (f, ttl, rr) in zip(ax[:3], [(f_extr, "Extracción VM (depleción)", re_),
                                        (f_frac, "Agua de fractura", rf),
                                        (f_inj, "Inyección de agua", ri)]):
        pos = np.where(f > 0, f, np.nan)
        a.imshow(pos, extent=ext, origin="lower", cmap="inferno",
                 norm=colors.LogNorm(vmin=np.nanpercentile(pos, 70), vmax=np.nanpercentile(pos, 99.5)))
        a.set_title(f"{ttl}\n(ρ vs vel = {rr:+.2f})"); a.set_xlabel("Lon")
    vmax = float(np.nanpercentile(np.abs(velg), 98)) or 10
    ax[3].imshow(velg, extent=ext, origin="lower", cmap="RdBu",
                 norm=colors.TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax))
    ax[3].set_title("Subsidencia (vel LOS)\nrojo=subsidencia, azul=uplift"); ax[3].set_xlabel("Lon")
    ax[0].set_ylabel("Lat")
    fig.suptitle("Tres mecanismos vs subsidencia: extracción (compacta) · fractura · inyección", fontsize=13)
    fig.tight_layout(); fig.savefig(HERE / "geomecanica_campos.png", dpi=115); plt.close(fig)
    print("→ geomecanica_campos.png")


if __name__ == "__main__":
    main()
