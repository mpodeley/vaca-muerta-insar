#!/usr/bin/env python
"""Paso 2 — Encargar interferogramas SBAS a HyP3 (nube gratis de ASF).

Arma una red SBAS conectando cada fecha con las `--neighbors` siguientes, encola
los pares como jobs InSAR (GAMMA) en HyP3, espera a que terminen y descarga los
productos a ./products (ignorado por git).

Por seguridad corre en **dry-run** por defecto: muestra los pares y el costo
estimado en créditos SIN encolar nada. Agregá `--submit` para enviar de verdad.

    python fase1/02_submit_hyp3.py                 # dry-run (revisar pares/créditos)
    python fase1/02_submit_hyp3.py --submit        # encola + espera + descarga

InSAR GAMMA cuesta ~10 créditos/job; HyP3 Basic da 8.000/mes gratis.
Requiere ~/.netrc con credenciales Earthdata y haber fijado el track en aoi.py.
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

import asf_search as asf
import hyp3_sdk as sdk

import aoi

CREDITS_PER_INSAR_JOB = 10  # aprox.; ver https://hyp3-docs.asf.alaska.edu/using/credits/


def list_scenes(track: int | None, frame: int | None) -> list[dict]:
    opts = dict(
        platform=asf.PLATFORM.SENTINEL1,
        processingLevel=asf.PRODUCT_TYPE.SLC,
        beamMode=asf.BEAMMODE.IW,
        intersectsWith=aoi.polygon_wkt(),
        start=aoi.START,
        end=aoi.END,
    )
    if track is not None:
        opts["relativeOrbit"] = track
    if frame is not None:
        opts["frame"] = frame
    results = asf.search(**opts)
    scenes = sorted(
        (r.properties for r in results), key=lambda p: p["startTime"]
    )
    return scenes


def _date8(scene_name: str) -> str:
    """Extrae YYYYMMDD de un sceneName Sentinel-1 (primer token \\d{8}T)."""
    return re.search(r"(\d{8})T", scene_name).group(1)


def existing_pairs() -> set[tuple[str, str]]:
    """Pares (refdate, secdate) ya presentes en products/ (para no reprocesar)."""
    done: set[tuple[str, str]] = set()
    for d in Path(aoi.PRODUCTS_DIR).glob("S1*_*"):
        dates = re.findall(r"(\d{8})T", d.name)
        if len(dates) >= 2:
            done.add((dates[0], dates[1]))
    return done


def sbas_pairs(scenes: list[dict], neighbors: int) -> list[tuple[str, str]]:
    """Conecta cada escena con las `neighbors` siguientes en el tiempo."""
    names = [s["sceneName"] for s in scenes]
    pairs: list[tuple[str, str]] = []
    for i, ref in enumerate(names):
        for sec in names[i + 1 : i + 1 + neighbors]:
            pairs.append((ref, sec))
    return pairs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--track",
        type=int,
        default=aoi.RELATIVE_ORBIT,
        help="relativeOrbit; por defecto el de aoi.RELATIVE_ORBIT.",
    )
    ap.add_argument(
        "--frame",
        type=int,
        default=aoi.FRAME,
        help="frameNumber; por defecto aoi.FRAME (un solo frame = demo limpio).",
    )
    ap.add_argument(
        "--neighbors",
        type=int,
        default=3,
        help="Cuántas fechas siguientes conectar a cada fecha (red SBAS).",
    )
    ap.add_argument(
        "--submit",
        action="store_true",
        help="Encolar de verdad (sin esto = dry-run).",
    )
    args = ap.parse_args()

    if args.track is None:
        sys.exit(
            "Falta el track. Corré fase1/01_search.py y fijá RELATIVE_ORBIT en "
            "fase1/aoi.py, o pasá --track N."
        )

    scenes = list_scenes(args.track, args.frame)
    if getattr(aoi, "MONTHLY", False):
        seen, monthly = set(), []
        for s in scenes:
            ym = s["startTime"][:7]
            if ym not in seen:
                seen.add(ym)
                monthly.append(s)
        print(f"Muestreo mensual: {len(scenes)} → {len(monthly)} escenas (1/mes)")
        scenes = monthly
    if len(scenes) < 2:
        sys.exit(
            f"Solo {len(scenes)} escena(s) en track {args.track} frame {args.frame}; "
            "insuficiente."
        )

    pairs = sbas_pairs(scenes, args.neighbors)
    done = existing_pairs()
    if done:
        before = len(pairs)
        pairs = [p for p in pairs if (_date8(p[0]), _date8(p[1])) not in done]
        print(f"Pares ya en products/: {len(done)} → se saltean {before - len(pairs)}")
    print(
        f"Track {args.track} / frame {args.frame}: {len(scenes)} fechas "
        f"({scenes[0]['startTime'][:10]} → {scenes[-1]['startTime'][:10]})"
    )
    print(f"Red SBAS (neighbors={args.neighbors}): {len(pairs)} pares NUEVOS a encolar")
    print(f"Costo estimado: ~{len(pairs) * CREDITS_PER_INSAR_JOB} créditos "
          f"(de 8.000/mes gratis)\n")

    if not args.submit:
        print("DRY-RUN. Revisá los pares de abajo y reejecutá con --submit.\n")
        for ref, sec in pairs:
            print(f"  {ref[17:25]} – {sec[17:25]}")
        return

    hyp3 = sdk.HyP3()  # usa ~/.netrc
    jobs = sdk.Batch()
    for ref, sec in pairs:
        jobs += hyp3.submit_insar_job(
            ref,
            sec,
            name="vaca-muerta-sbas",
            include_dem=True,
            include_look_vectors=True,
        )
    print(f"Encolados {len(jobs)} jobs (name='vaca-muerta-sbas'). Esperando (puede tardar horas)…")
    jobs = hyp3.watch(jobs, timeout=21600)  # devuelve el Batch ACTUALIZADO; 6 h de margen
    succeeded = jobs.filter_jobs(succeeded=True, running=False, failed=False, pending=False)
    print(f"Listo: {len(succeeded)}/{len(jobs)} SUCCEEDED. Descargando a ./{aoi.PRODUCTS_DIR} …")
    zips = succeeded.download_files(aoi.PRODUCTS_DIR)
    print(f"Descomprimiendo {len(zips)} productos …")
    for z in zips:
        z = Path(z)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(z.parent)
    print("Descarga completa. Pasá a fase1/03_timeseries.sh")


if __name__ == "__main__":
    main()
