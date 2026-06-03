"""Área de interés (AOI) y constantes compartidas de la demo Fase 1.

AOI mínimo centrado en Añelo (núcleo de Vaca Muerta). Las coordenadas vienen de
`docs/Fase-1-guia.md` §3 y del caso de negocio (Brunori et al. 2022). Son
aproximadas: refinalas al activo concreto antes de gastar cómputo.
"""

from __future__ import annotations

# --- Bounding box (lon/lat) sobre el CLÚSTER DE MÁXIMA PRODUCCIÓN -----------
# Núcleo "zona caliente" de Vaca Muerta en torno a Añelo, dentro de la huella
# del frame 722 (verificado), así que NO requiere reprocesar.
WEST = -69.10
SOUTH = -38.65
EAST = -68.40
NORTH = -38.05

# --- Puntos de referencia (lat, lon) ---------------------------------------
# Solo Añelo (pueblo, coordenada confiable) como orientación. NO marcamos los
# bloques/yacimientos: las coords aproximadas estaban mal; los polígonos exactos
# vienen de las concesiones oficiales (energia.gob.ar) y se cargarán para el pitch.
ANELO = (-38.35, -68.79)

# --- Ventana temporal de referencia ----------------------------------------
# Brunori et al. 2022 detectó -8 a -10 mm/año con Sentinel-1/SBAS en 2017-2020.
# Ventana 2019–2020 (~2 años) para una velocidad lineal robusta, acercándose al
# período de Brunori et al. 2022 (2017-2020).
START = "2019-01-01"
END = "2020-12-31"

# Track Sentinel-1 y frame (fijados con 01_search.py sobre el AOI de Añelo).
# Track 112 DESCENDING, frame 722 cubre Añelo (verificado, 21 escenas en 2019).
# None en RELATIVE_ORBIT = que 01_search.py recomiende; None en FRAME = no filtrar.
RELATIVE_ORBIT: int | None = 112
FRAME: int | None = 722

# Directorio local donde se descargan los productos HyP3 (ignorado por git).
PRODUCTS_DIR = "products"


def polygon_wkt() -> str:
    """AOI como POLYGON WKT (lon lat), formato que espera asf_search."""
    return (
        f"POLYGON(({WEST} {SOUTH},{EAST} {SOUTH},"
        f"{EAST} {NORTH},{WEST} {NORTH},{WEST} {SOUTH}))"
    )


def center_lonlat() -> tuple[float, float]:
    """Centro del AOI como (lon, lat)."""
    return ((WEST + EAST) / 2.0, (SOUTH + NORTH) / 2.0)
