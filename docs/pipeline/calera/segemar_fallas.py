#!/usr/bin/env python
"""Estructuras mapeadas SEGEMAR (SIGAM) para la región La Calera / Bajo del Choique.

Baja por WFS (geoserver217) las capas de fallas 1:250.000, pliegues 1:250.000 y
estructuras 1:2.500.000, recortadas a un bbox regional, y persiste un único
GeoJSON con la propiedad extra `capa`. Reporta qué cae dentro de cada bloque.

Nota: el WFS del endpoint principal (/geoserver) está deshabilitado; el que
funciona es /geoserver217 (el que referencia el GeoNetwork del SIGAM).

    ~/miniforge3/bin/mamba run -n insar python exploraciones/calera/segemar_fallas.py
"""
from __future__ import annotations
import json
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
OUT = HERE / "_data" / "fallas_segemar.geojson"
WFS = "https://sigam.segemar.gov.ar/geoserver217/wfs"
BBOX = "-70.0,-39.0,-68.3,-37.0"  # lon1,lat1,lon2,lat2 (región ampliada)
CAPAS = ["e250K.Fallas", "e250K.Pliegues", "e2.5M.Estructuras"]
BLOQUES = {
    "LA CALERA": (-69.16, -38.47, -68.89, -38.16),
    "BAJO DEL CHOIQUE": (-69.51, -37.84, -69.05, -37.42),
}


def coords_flat(geom):
    pts = []
    def walk(x):
        if isinstance(x[0], (int, float)):
            pts.append(x)
        else:
            for y in x:
                walk(y)
    walk(geom["coordinates"])
    return pts


def main() -> None:
    feats = []
    for capa in CAPAS:
        r = requests.get(WFS, params={
            "request": "GetFeature", "service": "WFS", "version": "1.0.0",
            "typename": f"sigam:{capa}", "outputFormat": "json", "bbox": BBOX,
        }, timeout=120)
        r.raise_for_status()
        fs = r.json().get("features", [])
        print(f"{capa}: {len(fs)} features en la región")
        for f in fs:
            f["properties"]["capa"] = capa
            feats.append(f)

    for nombre, (w, s, e, n) in BLOQUES.items():
        dentro = []
        for f in feats:
            pts = coords_flat(f["geometry"])
            if any(w <= x <= e and s <= y <= n for x, y in (p[:2] for p in pts)):
                dentro.append(f["properties"])
        print(f"\n{nombre}: {len(dentro)} estructuras tocan el bloque")
        for p in dentro:
            print(f"   {p['capa']}: {p.get('tipo')} ({p.get('certidumbre')})")

    OUT.parent.mkdir(exist_ok=True)
    json.dump({"type": "FeatureCollection", "features": feats}, open(OUT, "w"))
    print(f"\npersistido: {OUT}  ({len(feats)} features)")


if __name__ == "__main__":
    main()
