#!/usr/bin/env python
"""Costuras de empalme del producto multi-burst (bordes entre bursts consecutivos
y entre subswaths). Se calculan como la línea media del solape entre footprints
de bursts vecinos → _data/burst_seams.geojson. gradiente.py las usa para
descartar lineamientos que las siguen (artefactos, no geología).

    ~/miniforge3/bin/mamba run -n insar python exploraciones/calera/burst_seams.py
"""
from __future__ import annotations
import json
from pathlib import Path

import asf_search as asf
import numpy as np
from shapely.geometry import shape, mapping, LineString
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
BURSTS = [
    "018_038423_IW2", "018_038424_IW2", "018_038425_IW2",


]
OUT = HERE / "_data" / "burst_seams.geojson"


def midline(inter):
    """línea media del polígono de solape: eje mayor por PCA de su contorno."""
    xy = np.array(inter.exterior.coords)
    c = xy.mean(axis=0)
    d = xy - c
    _, _, vt = np.linalg.svd(d, full_matrices=False)
    t = d @ vt[0]
    a, b = c + vt[0] * t.min(), c + vt[0] * t.max()
    return LineString([tuple(a), tuple(b)])


def main() -> None:
    geoms = {}
    r = asf.search(platform=asf.PLATFORM.SENTINEL1, processingLevel="BURST", beamMode="IW",
                   polarization="VV", fullBurstID=BURSTS,
                   start="2025-01-01", end="2025-02-01")
    for x in r:
        bid = x.properties["burst"]["fullBurstID"]
        if bid not in geoms and x.geometry:
            geoms[bid] = shape(x.geometry)
    print(f"footprints: {len(geoms)}/{len(BURSTS)}")

    feats = []
    ids = sorted(geoms)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            inter = geoms[ids[i]].intersection(geoms[ids[j]])
            if inter.is_empty or inter.area < 1e-4:   # ~>1 km² de solape
                continue
            if inter.geom_type != "Polygon":
                inter = max(inter.geoms, key=lambda g: g.area)
            ml = midline(inter)
            xy = np.array(ml.coords)
            clat = np.cos(np.radians(xy[:, 1].mean()))
            az = (np.degrees(np.arctan2((xy[-1, 0] - xy[0, 0]) * clat,
                                        xy[-1, 1] - xy[0, 1])) + 360) % 180
            feats.append({"type": "Feature", "geometry": mapping(ml),
                          "properties": {"a": ids[i], "b": ids[j], "az_aprox": round(az, 1)}})
            print(f"  costura {ids[i]} ∩ {ids[j]}: az ≈ {az:.0f}°")

    OUT.parent.mkdir(exist_ok=True)
    json.dump({"type": "FeatureCollection", "features": feats}, open(OUT, "w"))
    print(f"persistido: {OUT} ({len(feats)} costuras)")


if __name__ == "__main__":
    main()
