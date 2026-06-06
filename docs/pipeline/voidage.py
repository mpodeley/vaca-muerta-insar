#!/usr/bin/env python
"""Voidage de reservorio por pozo, SEPARADO POR RESERVORIO/PROFUNDIDAD, + agua de fractura aparte.

Hallazgo que motiva la separación: los horizontales a Vaca Muerta son profundos y tight (radio de
drenaje chico → compactación localizada → subsidencia), mientras los sumideros/convencionales son
someros y permeables (drenaje amplio → señal difusa). Además el agua de fractura inyectada (Adjunto IV)
es comparable al voidage de petróleo y NO vuelve toda como flowback → el balance volumétrico de
voidage casi se cancela, pero igual hay subsidencia ⇒ el driver es la DEPLECIÓN DE PRESIÓN
(mejor proxied por la producción de líquido del VM), no el balance de volumen.

FVF aproximados (configurables): Bo=1.4, Bw=1.03, Bg=0.0035 rm³/sm³.
Unidades Cap IV: prod_pet/agua, iny_agua/co2 en m³; prod_gas/iny_gas en MILES de m³ (→ ×1000).

    ~/miniforge3/bin/mamba run -n insar python exploraciones/escala_pozo/voidage.py
"""
from __future__ import annotations
import csv
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "_data"
CSV_IN = HERE / "pozos_inyeccion.csv"
CSV_OUT = HERE / "pozos_voidage.csv"
POZOS_MASTER = DATA / "capitulo_iv_pozos.csv"
FRAC = DATA / "fractura_adjiv.csv"
csv.field_size_limit(1 << 24)

BO, BW, BG = 1.4, 1.03, 0.0035


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    meta = {}
    with open(POZOS_MASTER, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if (r.get("cuenca") or "").strip().upper() != "NEUQUINA":
                continue
            try:
                idp = int(r["idpozo"]); prof = float(r.get("profundidad") or 0)
            except (ValueError, TypeError):
                continue
            meta[idp] = ((r.get("formacion") or "").strip().upper(),
                         (r.get("tipo_recurso") or "").strip().upper(),
                         (r.get("subclasificacion") or "").strip().upper(),
                         prof if 50 < prof < 8000 else np.nan)
    df["formacion"] = df.idpozo.map(lambda i: meta.get(i, ("", "", "", np.nan))[0])
    df["tipo_rec"] = df.idpozo.map(lambda i: meta.get(i, ("", "", "", np.nan))[1])
    df["subclas"] = df.idpozo.map(lambda i: meta.get(i, ("", "", "", np.nan))[2])
    df["prof"] = df.idpozo.map(lambda i: meta.get(i, ("", "", "", np.nan))[3])
    # agua de fractura por pozo (Adjunto IV), SEPARADA (no se netea)
    fr = pd.read_csv(FRAC, encoding="utf-8-sig")
    fr.columns = [c.strip() for c in fr.columns]
    fw = (pd.to_numeric(fr["agua_inyectada_m3"], errors="coerce")
          .groupby(fr["idpozo"]).sum())
    df["frac_agua"] = df.idpozo.map(fw).fillna(0.0)
    df["is_vm"] = df.formacion.str.contains("VACA MUERTA") | (df.tipo_rec == "NO CONVENCIONAL")
    df["is_iny"] = df.subclas.str.contains("INYECTOR") | (df.iny_agua > df.prod_pet + df.prod_gas)
    return df


def compute(df: pd.DataFrame) -> pd.DataFrame:
    Np = df.prod_pet.clip(lower=0); Wp = df.prod_agua.clip(lower=0)
    Gp = df.prod_gas.clip(lower=0) * 1000.0
    Wi = df.iny_agua.clip(lower=0); Gi = df.iny_gas.clip(lower=0) * 1000.0
    # voidage VOLUMÉTRICO neto (todos los fluidos) — el que NO predice bien
    df["voidage_prod"] = Np * BO + Wp * BW + Gp * BG
    df["voidage_inj"] = Wi * BW + Gi * BG
    df["voidage_net"] = df.voidage_prod - df.voidage_inj
    # extracción de LÍQUIDO del VM profundo (proxy de depleción de presión) — el que SÍ predice
    liq = Np * BO + Wp * BW
    df["extr_vm_liq"] = np.where(df.is_vm, liq, 0.0)
    df["frac_agua_rm3"] = df.frac_agua * BW
    return df


def main() -> None:
    from scipy.stats import spearmanr
    df = compute(enrich(pd.read_csv(CSV_IN)))
    df.to_csv(CSV_OUT, index=False)

    conv = df[~df.is_vm & ~df.is_iny]
    print(f"VM/no-conv: {int(df.is_vm.sum())} (prof~{df[df.is_vm].prof.median():.0f} m, "
          f"vel_med {df[df.is_vm].vel.median():+.1f})   "
          f"convencional: {len(conv)} (prof~{conv.prof.median():.0f} m, vel_med {conv.vel.median():+.1f})   "
          f"inyectores: {int(df.is_iny.sum())}")

    def r(d, col):
        d = d[d[col] > 0]
        return (len(d), *spearmanr(d[col], d.vel)) if len(d) > 20 else (len(d), np.nan, 1)

    print("\n=== Spearman vel vs variable, por grupo ===")
    for nm, sub in [("VM/no-conv", df[df.is_vm]), ("convencional", conv), ("TODOS", df)]:
        for col in ["prod_pet", "prod_gas", "voidage_prod", "extr_vm_liq"]:
            n, rho, p = r(sub, col)
            print(f"  {nm:13s} {col:14s} n={n:5d}  rho={rho:+.3f}  p={p:.1e}")
        print()

    fa = df[df.frac_agua > 0]
    print(f"agua de fractura: {fa.frac_agua.sum():.3e} m³ en {len(fa)} pozos  "
          f"(= {100*fa.frac_agua_rm3.sum()/(df.prod_pet.sum()*BO):.0f}% del voidage de petróleo)")
    print("  → si se neteara, el voidage volumétrico casi se cancela; por eso se reporta APARTE.")


if __name__ == "__main__":
    main()
