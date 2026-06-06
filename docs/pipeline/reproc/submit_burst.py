#!/usr/bin/env python
"""Reproceso fino Bandurria Sur — encarga interferogramas multi-burst a HyP3 a 40 m (10x2)
o 20 m (5x1). Cubre el bloque con los 2 bursts IW2 (018_038424 + 018_038425), track 18 ASC.

Red SBAS mensual neighbors=3, ventana pilot 2022-2026. Dry-run por defecto (cuenta pares,
no gasta créditos). --submit para encolar de verdad.

    python submit_burst.py --looks 10x2            # dry-run 40 m
    python submit_burst.py --looks 10x2 --submit   # encola 40 m
    python submit_burst.py --looks 5x1  --submit   # encola 20 m
"""
from __future__ import annotations
import argparse, json
from collections import defaultdict
from pathlib import Path

import asf_search as asf
import hyp3_sdk as sdk

HERE = Path(__file__).resolve().parent
BURSTS = ["018_038424_IW2", "018_038425_IW2"]
START, END = "2022-01-01", "2026-07-01"
NEIGHBORS = 3


def monthly_dates() -> dict:
    """date(YYYYMMDD) -> {fullBurstID: sceneName} para fechas con LOS DOS bursts; 1/mes."""
    per_date: dict = defaultdict(dict)
    r = asf.search(platform=asf.PLATFORM.SENTINEL1, processingLevel="BURST", beamMode="IW",
                   relativeOrbit=18, polarization="VV", start=START, end=END,
                   intersectsWith="POINT(-68.77 -38.27)")
    for p in r:
        bid = p.properties["burst"]["fullBurstID"]
        if bid in BURSTS:
            d = p.properties["startTime"][:10].replace("-", "")
            per_date[d][bid] = p.properties["sceneName"]
    both = {d: v for d, v in per_date.items() if len(v) == 2}
    # 1 fecha por mes
    seen, monthly = set(), {}
    for d in sorted(both):
        ym = d[:6]
        if ym not in seen:
            seen.add(ym); monthly[d] = both[d]
    return monthly


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--looks", choices=["20x4", "10x2", "5x1"], required=True)
    ap.add_argument("--neighbors", type=int, default=NEIGHBORS)
    ap.add_argument("--submit", action="store_true")
    args = ap.parse_args()

    md = monthly_dates()
    dates = sorted(md)
    print(f"Fechas mensuales con ambos bursts: {len(dates)} ({dates[0]}…{dates[-1]})")
    pairs = [(dates[i], dates[j]) for i in range(len(dates))
             for j in range(i + 1, min(i + 1 + args.neighbors, len(dates)))]
    print(f"Red SBAS neighbors={args.neighbors}: {len(pairs)} pares  | looks {args.looks}")
    print(f"Costo aprox: {len(pairs)} jobs multi-burst (≈1–2 créditos c/u)\n")

    tag = {"20x4": "80", "10x2": "40", "5x1": "20"}[args.looks]
    if not args.submit:
        print("DRY-RUN. Revisá y reejecutá con --submit.")
        for a, b in pairs[:6]:
            print(f"  {a} – {b}")
        print("  …")
        return

    hyp3 = sdk.HyP3()
    jobs = sdk.Batch()
    for a, b in pairs:
        ref = [md[a][bid] for bid in BURSTS]
        sec = [md[b][bid] for bid in BURSTS]
        jobs += hyp3.submit_insar_isce_multi_burst_job(
            reference=ref, secondary=sec, looks=args.looks,
            apply_water_mask=False, name=f"bsur-int{tag}")
    print(f"Encolados {len(jobs)} jobs name='bsur-int{tag}'.")
    json.dump([j.to_dict() for j in jobs], open(HERE / f"jobs_int{tag}.json", "w"))
    print(f"IDs guardados en jobs_int{tag}.json. Seguí con watch_download.py --tag {tag}")


if __name__ == "__main__":
    main()
