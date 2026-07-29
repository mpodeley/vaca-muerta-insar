#!/usr/bin/env python
"""Pozos de La Calera (Cap IV) → _data/calera_wells_all.json, mismo esquema que
bsur_wells_all.json: {idpozo: {boca:[lon,lat], traj:[[lon,lat],...]|null, has_traj, comp}}.

Filtra por nombre de área en Cap IV y reporta cuántas bocas caen fuera del polígono
LCA de concesiones (sanity geométrico).

    ~/miniforge3/bin/mamba run -n insar python exploraciones/calera/calera_wells.py
"""
from __future__ import annotations
import json
from pathlib import Path

import pandas as pd


_PROJECTS = Path(__file__).resolve().parents[5]  # ~/Projects
HERE = Path(__file__).resolve().parent
DATA = HERE / "_data"
CAPIV = HERE.parent / "escala_pozo" / "_data" / "capitulo_iv_pozos.csv"
CONC = _PROJECTS / "activos/estado-del-sistema/public/data/concesiones_neuquina.geojson"

AREA = "LA CALERA"
CONC_ID = "LCA"
OUT = DATA / "calera_wells_all.json"
TRAJ = HERE.parent / "escala_pozo" / "_data" / "trayectorias_vm.csv"


def parse_geo(g: str):
    """col geojson de Cap IV → (boca [lon,lat] | None, traj [[lon,lat],...] | None)."""
    try:
        gg = json.loads(g)
    except (TypeError, ValueError):
        return None, None
    geoms = gg["geometries"] if gg.get("type") == "GeometryCollection" else [gg]
    boca, traj = None, None
    for sub in geoms:
        if sub.get("type") == "Point" and boca is None:
            boca = [round(c, 6) for c in sub["coordinates"][:2]]
        elif sub.get("type") == "LineString" and traj is None:
            traj = [[round(x, 6), round(y, 6)] for x, y, *_ in sub["coordinates"]]
    if boca is None and traj:
        boca = traj[0]
    return boca, traj


def parse_traj(g: str):
    """col geojson de trayectorias_vm → polilínea [[lon,lat],...] (la rama más larga)."""
    try:
        gg = json.loads(g)
    except (TypeError, ValueError):
        return None
    if gg.get("type") == "LineString":
        lines = [gg["coordinates"]]
    elif gg.get("type") == "MultiLineString":
        lines = gg["coordinates"]
    else:
        return None
    best = max(lines, key=len)
    return [[round(x, 6), round(y, 6)] for x, y, *_ in best] or None


def main() -> None:
    df = pd.read_csv(CAPIV, low_memory=False)
    blk = df[df["area"].astype(str).str.upper().str.strip() == AREA]
    print(f"pozos Cap IV '{AREA}': {len(blk)}")

    tj = pd.read_csv(TRAJ, low_memory=False)
    tj = tj[tj["geojson"].notna()].drop_duplicates("sigla", keep="last")
    trajs = {r["sigla"]: parse_traj(r["geojson"]) for _, r in tj.iterrows()}

    wells = {}
    for _, r in blk.iterrows():
        boca, traj = parse_geo(r.get("geojson"))
        traj = trajs.get(r["sigla"]) or traj
        if boca is None and traj:
            boca = traj[0]
        if boca is None:
            print(f"  sin coordenadas: {r['sigla']} ({r['idpozo']})")
            continue
        comp = None
        for c in ("adjiv_fecha_fin_term", "adjiv_fecha_inicio_term"):
            t = pd.to_datetime(r.get(c), errors="coerce")
            if pd.notna(t):
                comp = f"{t.year:04d}-{t.month:02d}"
                break
        wells[str(int(r["idpozo"]))] = {
            "boca": boca, "traj": traj, "has_traj": traj is not None,
            "comp": comp, "sigla": r["sigla"], "tipo": r.get("tipopozo"),
        }

    # sanity: bocas dentro del polígono de la concesión
    try:
        from shapely.geometry import shape, Point
        gj = json.load(open(CONC))
        poly = shape(next(f["geometry"] for f in gj["features"]
                          if f["properties"].get("id") == CONC_ID))
        fuera = [w["sigla"] for w in wells.values() if not poly.buffer(0.01).contains(Point(w["boca"]))]
        print(f"bocas fuera del polígono {CONC_ID} (+1 km buffer): {len(fuera)} {fuera[:8]}")
    except ImportError:
        print("shapely no disponible: salto sanity geométrico")

    DATA.mkdir(exist_ok=True)
    json.dump(wells, open(OUT, "w"), ensure_ascii=False)
    con_traj = sum(1 for w in wells.values() if w["has_traj"])
    print(f"persistido: {OUT}  ({len(wells)} pozos, {con_traj} con trayectoria)")


if __name__ == "__main__":
    main()
