#!/usr/bin/env python
"""Espera a que terminen los jobs HyP3 'bsur-int{tag}' y descarga+descomprime a products_int{tag}/.

    python watch_download.py --tag 40
    python watch_download.py --tag 20
"""
from __future__ import annotations
import argparse, zipfile
from pathlib import Path
import hyp3_sdk as sdk

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)         # 40 | 20
    ap.add_argument("--no-wait", action="store_true")
    args = ap.parse_args()

    hyp3 = sdk.HyP3()
    jobs = hyp3.find_jobs(name=f"bsur-int{args.tag}")
    print(f"jobs bsur-int{args.tag}: {len(jobs)}")
    if not args.no_wait:
        jobs = hyp3.watch(jobs, timeout=36000)      # 10 h margen
    ok = jobs.filter_jobs(succeeded=True, running=False, failed=False, pending=False)
    fail = jobs.filter_jobs(succeeded=False, running=False, failed=True, pending=False)
    print(f"SUCCEEDED {len(ok)} | FAILED {len(fail)}")
    out = HERE / f"products_int{args.tag}"
    out.mkdir(exist_ok=True)
    zips = ok.download_files(out)
    print(f"descargados {len(zips)} → {out}, descomprimiendo…")
    for z in zips:
        z = Path(z)
        try:
            with zipfile.ZipFile(z) as zf:
                zf.extractall(z.parent)
        except zipfile.BadZipFile:
            print("  zip malo:", z.name)
    print("listo.")


if __name__ == "__main__":
    main()
