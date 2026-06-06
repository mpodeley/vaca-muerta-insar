#!/usr/bin/env python
"""Baja los SLC IW (full) mensuales track 18 sobre Bandurria Sur, 2022-2026, para el stack PS
(ISCE2 topsStack + MiaplPy). Usa ~/.netrc (Earthdata). ~4 GB/escena.

    python download_slc.py            # lista (dry)
    python download_slc.py --download
"""
from __future__ import annotations
import argparse
from pathlib import Path
import asf_search as asf

HERE = Path(__file__).resolve().parent
SLC_DIR = HERE / "slc"
START, END = "2022-01-01", "2026-07-01"


def monthly_slcs():
    r = asf.search(platform=asf.PLATFORM.SENTINEL1, processingLevel=asf.PRODUCT_TYPE.SLC,
                   beamMode=asf.BEAMMODE.IW, relativeOrbit=18, polarization="VV+VH",
                   start=START, end=END, intersectsWith="POINT(-68.77 -38.27)")
    by = {}
    for p in sorted(r, key=lambda x: x.properties["startTime"]):
        ym = p.properties["startTime"][:7]
        by.setdefault(ym, p)   # 1ª escena del mes
    return list(by.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    args = ap.parse_args()
    scenes = monthly_slcs()
    print(f"SLC mensuales: {len(scenes)} ({scenes[0].properties['startTime'][:10]}…"
          f"{scenes[-1].properties['startTime'][:10]})")
    tot = sum(s.properties.get("bytes", 0) for s in scenes) / 1e9
    print(f"tamaño total ~{tot:.0f} GB")
    if not args.download:
        for s in scenes[:5]:
            print("  ", s.properties["sceneName"])
        print("  …  (--download para bajar)")
        return
    SLC_DIR.mkdir(exist_ok=True)
    session = asf.ASFSession()  # usa ~/.netrc
    res = asf.ASFSearchResults(scenes)
    res.download(path=str(SLC_DIR), session=session, processes=4)
    print(f"descargados a {SLC_DIR}")


if __name__ == "__main__":
    main()
