"""AOI y config — track 18 ASCENDENTE, frame 1050 (área ampliada oeste+norte, 2019–2026).

A diferencia del track 112 descendente (fase1/, solo 2019–2020), el track 18 ascendente
tiene cobertura CONTINUA 2019→2026 y se extiende al oeste (lon −71) y norte (lat −37.1).
Muestreo ~mensual para mantener el cómputo/créditos acotados.
"""

from __future__ import annotations

# --- Bounding box ampliado (lon/lat): oeste + norte + sur sobre el frame 1050 ---
WEST = -70.6
SOUTH = -39.2
EAST = -68.2
NORTH = -37.3

# --- Referencia (lat, lon) ---
ANELO = (-38.35, -68.79)

# --- Ventana temporal: serie larga hasta el presente ---
START = "2019-01-01"
END = "2026-06-30"

# --- Track / frame (ASCENDENTE) ---
RELATIVE_ORBIT: int | None = 18
FRAME: int | None = 1050

# Muestreo ~mensual (1 escena por mes) para acotar jobs/créditos en la serie larga.
MONTHLY = True

PRODUCTS_DIR = "products"


def polygon_wkt() -> str:
    return (
        f"POLYGON(({WEST} {SOUTH},{EAST} {SOUTH},"
        f"{EAST} {NORTH},{WEST} {NORTH},{WEST} {SOUTH}))"
    )


def center_lonlat() -> tuple[float, float]:
    return ((WEST + EAST) / 2.0, (SOUTH + NORTH) / 2.0)
