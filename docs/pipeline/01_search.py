#!/usr/bin/env python
"""Paso 1 — Descubrir la pila Sentinel-1 sobre el AOI (asf_search).

Lista las escenas SLC que intersectan el AOI en la ventana temporal, las agrupa
por track (relativeOrbit) y recomienda el track con más adquisiciones. Con
`--track N` imprime el detalle de ese track (nombres de escena + fechas), que es
lo que consume el paso 2.

    python fase1/01_search.py                 # resumen por track
    python fase1/01_search.py --track 18      # detalle del track elegido
    python fase1/01_search.py --orbit ASCENDING

No descarga nada. Requiere ~/.netrc con credenciales Earthdata.
"""

from __future__ import annotations

import argparse
from collections import defaultdict

import asf_search as asf

import aoi


def search(direction: str | None) -> asf.ASFSearchResults:
    opts = dict(
        platform=asf.PLATFORM.SENTINEL1,
        processingLevel=asf.PRODUCT_TYPE.SLC,
        beamMode=asf.BEAMMODE.IW,
        intersectsWith=aoi.polygon_wkt(),
        start=aoi.START,
        end=aoi.END,
    )
    if direction:
        opts["flightDirection"] = direction
    return asf.search(**opts)


def summarize(results: asf.ASFSearchResults) -> None:
    by_track: dict[tuple, list] = defaultdict(list)
    for r in results:
        p = r.properties
        key = (p["pathNumber"], p["flightDirection"])
        by_track[key].append(p)

    print(f"\n{len(results)} escenas SLC en el AOI ({aoi.START} → {aoi.END})\n")
    print(f"{'track':>6} {'dir':<11} {'escenas':>8}  rango de fechas")
    print("-" * 60)
    best = None
    for (path, direction), scenes in sorted(
        by_track.items(), key=lambda kv: len(kv[1]), reverse=True
    ):
        dates = sorted(s["startTime"][:10] for s in scenes)
        print(f"{path:>6} {direction:<11} {len(scenes):>8}  {dates[0]} … {dates[-1]}")
        if best is None:
            best = (path, direction, len(scenes))
    if best:
        print(
            f"\n→ Recomendado: track {best[0]} ({best[1]}, {best[2]} escenas). "
            f"Detalle: python fase1/01_search.py --track {best[0]}"
        )


def detail(results: asf.ASFSearchResults, track: int) -> None:
    scenes = sorted(
        (r.properties for r in results if r.properties["pathNumber"] == track),
        key=lambda p: p["startTime"],
    )
    if not scenes:
        print(f"Sin escenas para el track {track}.")
        return
    print(f"\nTrack {track} — {len(scenes)} escenas (ordenadas por fecha):\n")
    for p in scenes:
        print(f"  {p['startTime'][:10]}  {p['sceneName']}")
    print(
        "\nFijá este track en fase1/aoi.py (RELATIVE_ORBIT) y pasá a "
        "fase1/02_submit_hyp3.py."
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--track", type=int, help="Detalle de un track (pathNumber).")
    ap.add_argument(
        "--orbit",
        choices=["ASCENDING", "DESCENDING"],
        help="Filtrar por dirección de órbita.",
    )
    args = ap.parse_args()

    results = search(args.orbit)
    if not results:
        print("Sin resultados. Revisá el AOI/fechas en fase1/aoi.py o el ~/.netrc.")
        return

    if args.track:
        detail(results, args.track)
    else:
        summarize(results)


if __name__ == "__main__":
    main()
