#!/usr/bin/env python
"""Stream Cap IV producción 2019-2026 y persiste la serie MENSUAL POR POZO para los
115 pozos de Bandurria Sur con trayectoria. Filtra por idpozo (set chico) en el stream,
así no guarda los 2.3 GB crudos.

    ~/miniforge3/bin/mamba run -n insar python exploraciones/escala_pozo/fetch_bsur_monthly.py
"""
from __future__ import annotations
import csv, json
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
DATA = HERE / "_data"
PROD_URLS = json.load(open(DATA / "prod_urls.json"))
WELLS = set(int(k) for k in json.load(open(DATA / "bsur_wells_all.json")))
HDRS = {"User-Agent": "Mozilla/5.0"}
csv.field_size_limit(1 << 24)
FLD = ["prod_pet", "prod_gas", "prod_agua", "iny_agua"]


def ym(row) -> str:
    a = (row.get("anio") or "").strip()
    m = (row.get("mes") or "").strip()
    if a and m:
        return f"{int(a):04d}-{int(m):02d}"
    return ""


def main() -> None:
    # acc[(idpozo, ym)] = {fld: val}
    acc: dict = {}
    for y in sorted(PROD_URLS):
        n = hit = 0
        with requests.get(PROD_URLS[y]["url"], headers=HDRS, stream=True, timeout=1800) as r:
            r.raise_for_status()
            lines = (ln for ln in r.iter_lines(decode_unicode=True) if ln)
            for row in csv.DictReader(lines):
                n += 1
                try:
                    idp = int(row["idpozo"])
                except (ValueError, KeyError, TypeError):
                    continue
                if idp not in WELLS:
                    continue
                key = (idp, ym(row))
                d = acc.setdefault(key, {k: 0.0 for k in FLD})
                for k in FLD:
                    v = row.get(k)
                    if v:
                        try:
                            d[k] += float(v)
                        except ValueError:
                            pass
                hit += 1
        print(f"  {y}: {n:,} filas  (registros Bandurria Sur acum={hit:,} este año)", flush=True)

    out = DATA / "bsur_monthly_perwell_all.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["idpozo", "ym", *FLD])
        for (idp, m), d in sorted(acc.items()):
            if not m:
                continue
            w.writerow([idp, m, *[round(d[k], 3) for k in FLD]])
    print(f"\npersistido: {out}  ({len(acc):,} filas pozo-mes)")


if __name__ == "__main__":
    main()
