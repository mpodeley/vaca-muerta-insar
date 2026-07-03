#!/usr/bin/env python
"""Bajo del Choique – La Invernada 80 m — encarga interferogramas multi-burst a HyP3
(ISCE2, looks 20x4). El bloque BCLI cae FUERA del footprint de t18_f1050 (frame 1050
termina en lat ≈ −37.84), así que se procesa un stack propio: rectángulo 3x2 de bursts
del track 18 ASC (038428/038429/038430 × IW2/IW3).

La validación de jobs cross-subswath (IW2+IW3 juntos) es server-side: correr --smoke
antes del batch. Si HyP3 lo rechaza → contingencia: dos strips (IW2 y IW3) y mosaico.

Red SBAS mensual neighbors=3, ventana 2020-2026. Dry-run por defecto.

    python submit_burst.py                    # dry-run
    python submit_burst.py --smoke --submit   # 1 job de prueba (valida cross-subswath)
    python submit_burst.py --submit           # batch completo
"""
from __future__ import annotations
import argparse, json
from collections import defaultdict
from pathlib import Path

import asf_search as asf
import hyp3_sdk as sdk

HERE = Path(__file__).resolve().parent
BURSTS = [
    "018_038428_IW2", "018_038428_IW3",
    "018_038429_IW2", "018_038429_IW3",
    "018_038430_IW2", "018_038430_IW3",
]
START, END = "2020-01-01", "2026-08-01"
NEIGHBORS = 3
NAME, TAG = "choique-int80", "80"
LOOKS = "20x4"
# bloque BCLI + margen ~4 km (subset MintPy: -37.84:-37.42,-69.51:-69.05)
BLOQUE = (-69.51, -37.84, -69.05, -37.42)


def search_bursts():
    return asf.search(platform=asf.PLATFORM.SENTINEL1, processingLevel="BURST",
                      beamMode="IW", polarization="VV", fullBurstID=BURSTS,
                      start=START, end=END)


def monthly_dates(results) -> dict:
    """date(YYYYMMDD) -> {fullBurstID: sceneName} para fechas con TODOS los bursts; 1/mes."""
    per_date: dict = defaultdict(dict)
    for p in results:
        bid = p.properties["burst"]["fullBurstID"]
        d = p.properties["startTime"][:10].replace("-", "")
        per_date[d][bid] = p.properties["sceneName"]
    full = {d: v for d, v in per_date.items() if len(v) == len(BURSTS)}
    seen, monthly = set(), {}
    for d in sorted(full):
        ym = d[:6]
        if ym not in seen:
            seen.add(ym); monthly[d] = full[d]
    return monthly


def print_footprints(results) -> None:
    """bbox por burst + cobertura del bloque (los footprints reales son paralelogramos)."""
    boxes: dict = {}
    for p in results:
        bid = p.properties["burst"]["fullBurstID"]
        if bid in boxes or not p.geometry:
            continue
        cc = p.geometry["coordinates"][0]
        lons = [c[0] for c in cc]; lats = [c[1] for c in cc]
        boxes[bid] = (min(lons), min(lats), max(lons), max(lats))
    print("footprints (bbox) por burst:")
    for b in BURSTS:
        f = boxes.get(b)
        print(f"  {b}: lon {f[0]:.2f}..{f[2]:.2f}  lat {f[1]:.2f}..{f[3]:.2f}" if f else f"  {b}: SIN ESCENAS")
    if len(boxes) == len(BURSTS):
        u = (min(b[0] for b in boxes.values()), min(b[1] for b in boxes.values()),
             max(b[2] for b in boxes.values()), max(b[3] for b in boxes.values()))
        ok = u[0] <= BLOQUE[0] and u[1] <= BLOQUE[1] and u[2] >= BLOQUE[2] and u[3] >= BLOQUE[3]
        print(f"unión: lon {u[0]:.2f}..{u[2]:.2f}  lat {u[1]:.2f}..{u[3]:.2f}  "
              f"⊇ bloque+margen {BLOQUE}? -> {'SÍ' if ok else 'NO (revisar bursts)'}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--looks", default=LOOKS, choices=["20x4", "10x2", "5x1"])
    ap.add_argument("--neighbors", type=int, default=NEIGHBORS)
    ap.add_argument("--smoke", action="store_true", help="encolar solo el primer par")
    ap.add_argument("--submit", action="store_true")
    args = ap.parse_args()

    results = search_bursts()
    md = monthly_dates(results)
    dates = sorted(md)
    print(f"Fechas mensuales con los {len(BURSTS)} bursts: {len(dates)} ({dates[0]}…{dates[-1]})")
    ym = lambda d: int(d[:4]) * 12 + int(d[4:6])
    gaps = [(a, b) for a, b in zip(dates, dates[1:]) if ym(b) - ym(a) > 2]
    if gaps:
        print(f"  huecos >2 meses: {gaps}")
    pairs = [(dates[i], dates[j]) for i in range(len(dates))
             for j in range(i + 1, min(i + 1 + args.neighbors, len(dates)))]
    if args.smoke:
        pairs = pairs[:1]
    print(f"Red SBAS neighbors={args.neighbors}: {len(pairs)} pares  | looks {args.looks}")

    if not args.submit:
        print_footprints(results)
        print("\nDRY-RUN. Revisá y reejecutá con --submit (o --smoke --submit para 1 job).")
        for a, b in pairs[:6]:
            print(f"  {a} – {b}")
        if len(pairs) > 6:
            print("  …")
        return

    hyp3 = sdk.HyP3()
    jobs = sdk.Batch()
    for a, b in pairs:
        ref = [md[a][bid] for bid in BURSTS]
        sec = [md[b][bid] for bid in BURSTS]
        jobs += hyp3.submit_insar_isce_multi_burst_job(
            reference=ref, secondary=sec, looks=args.looks,
            apply_water_mask=False, name=NAME)
    print(f"Encolados {len(jobs)} jobs name='{NAME}'.")
    suffix = "_smoke" if args.smoke else ""
    json.dump([j.to_dict() for j in jobs], open(HERE / f"jobs_int{TAG}{suffix}.json", "w"))
    print(f"IDs guardados en jobs_int{TAG}{suffix}.json. Seguí con watch_download.py --tag {TAG}")


if __name__ == "__main__":
    main()
