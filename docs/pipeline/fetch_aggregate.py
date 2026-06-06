#!/usr/bin/env python
"""Baja Cap IV producción-por-pozo 2019-2026 (streaming) y PERSISTE el agregado por idpozo
(prod + inyección) en _data/pozos_agg.csv, para que el análisis no re-baje 2.3 GB.

    ~/miniforge3/bin/mamba run -n insar python exploraciones/escala_pozo/fetch_aggregate.py
"""
from __future__ import annotations
import csv, json
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
DATA = HERE / "_data"
PROD_URLS = json.load(open(DATA / "prod_urls.json"))
HDRS = {"User-Agent": "Mozilla/5.0"}
csv.field_size_limit(1 << 24)
FLD = ["prod_pet", "prod_gas", "prod_agua", "iny_agua", "iny_gas", "iny_co2"]


def main() -> None:
    acc: dict = {}
    for y in sorted(PROD_URLS):
        n = 0
        with requests.get(PROD_URLS[y]["url"], headers=HDRS, stream=True, timeout=900) as r:
            r.raise_for_status()
            lines = (ln for ln in r.iter_lines(decode_unicode=True) if ln)
            for row in csv.DictReader(lines):
                if (row.get("cuenca") or "").strip().upper() != "NEUQUINA":
                    continue
                try:
                    idp = int(row["idpozo"])
                except (ValueError, KeyError, TypeError):
                    continue
                d = acc.setdefault(idp, {k: 0.0 for k in FLD} | {"nm": 0})
                for k in FLD:
                    v = row.get(k)
                    if v:
                        try:
                            d[k] += float(v)
                        except ValueError:
                            pass
                d["nm"] += 1
                d["conc"] = (row.get("areapermisoconcesion") or "").strip()
                d["rec"] = (row.get("tipo_de_recurso") or "").strip()
                d["tipopozo"] = (row.get("tipopozo") or "").strip()
                d["tipoext"] = (row.get("tipoextraccion") or "").strip()
                n += 1
        print(f"  {y}: {n:,} filas  (pozos acum={len(acc):,})", flush=True)

    out = DATA / "pozos_agg.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["idpozo", *FLD, "nm", "conc", "rec", "tipopozo", "tipoext"])
        for idp, d in acc.items():
            w.writerow([idp, *[round(d[k], 3) for k in FLD], d["nm"],
                        d.get("conc", ""), d.get("rec", ""), d.get("tipopozo", ""),
                        d.get("tipoext", "")])
    print(f"\npersistido: {out}  ({len(acc):,} pozos)")


if __name__ == "__main__":
    main()
