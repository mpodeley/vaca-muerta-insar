# Método paso a paso

Todo el procesamiento usa **software libre** y **datos gratuitos**. El pipeline está pensado para
correr en una máquina local (Linux, ~96 GB RAM). Los scripts están en
[`docs/pipeline/`](https://github.com/mpodeley/vaca-muerta-insar/tree/main/docs/pipeline).

## Qué es InSAR (en una línea)

El **InSAR** (interferometría radar de apertura sintética) compara la **fase** de dos imágenes de radar
tomadas en fechas distintas desde la misma órbita: el desfasaje revela cuánto se movió el suelo en la
**línea de vista** del satélite (LOS), con precisión de **milímetros**. Apilando decenas de imágenes
(*time-series* SBAS) se separa la deformación del ruido. Es la técnica madura y de referencia para
subsidencia fina [Morishita 2020].

## 0. Datos y herramientas

| Pieza | Qué | Fuente |
|---|---|---|
| Imágenes | **Sentinel-1** SLC, banda C, ~revisita 6–12 d | ESA Copernicus / ASF |
| Interferogramas | **ASF HyP3** (procesamiento en la nube, gratis) | [hyp3-docs.asf.alaska.edu](https://hyp3-docs.asf.alaska.edu) |
| Serie de tiempo | **MintPy** (SBAS) | [Yunjun et al. 2019] |
| Atmósfera | **ERA5** (ECMWF) vía PyAPS | Copernicus CDS |
| Búsqueda | `asf_search` | ASF |

## 1. Área y track

Se acota a un solo *frame* Sentinel-1 sobre el clúster productivo en torno a **Añelo**
(núcleo de Vaca Muerta). Con `asf_search` se eligió el **track 112 descendente, frame 722**, que cubre
el área con buena densidad temporal. Ventana **2019–2020** (51 fechas), para acercarse al período del
estudio de referencia [Brunori 2022]. → `01_search.py`, `aoi.py`.

## 2. Interferogramas en la nube (HyP3)

Se arma una **red SBAS** (*Small BAseline Subset*): cada fecha se conecta con las 3 siguientes
(baselines temporales cortos = mejor coherencia). Los **147 pares** resultantes se encargan a **HyP3**,
que genera los interferogramas gratis en la nube de ASF (~10 créditos por par, de 8.000/mes gratuitos).
→ `02_submit_hyp3.py`.

## 3. Serie de tiempo con MintPy

Con los productos descargados, **MintPy** invierte la red SBAS a una serie de tiempo de desplazamiento
y una **velocidad media** (mm/año). Pasos clave (config en `vacamuerta.cfg`):

1. **Carga** del stack (147 interferogramas, 51 fechas).
2. **Red por coherencia**: se descartan pares de baja coherencia.
3. **Punto de referencia** automático en zona de máxima coherencia.
4. **Inversión SBAS** → serie de tiempo.
5. **Corrección troposférica con ERA5** (PyAPS): quita el retardo atmosférico, el principal ruido en
   InSAR. *Este paso fue decisivo* (ver [Resultados](resultados.md)).
6. **Deramp** + **corrección de error de DEM** + **velocidad**.

→ `03_timeseries.sh`, `vacamuerta.cfg`.

## 4. Máscara de calidad

Se conservan solo los pixels con **coherencia temporal > 0.7** (~40 % del área). El resto —agua del
embalse, vegetación de regadío, pads activos— se descarta por poco confiable. La zona árida/semiárida
favorece coherencias altas (medidas: 0.79–0.85), lo que confirma empíricamente que es buen terreno
para InSAR.

## 5. Visualización

- `04_export_visual.py` → GeoTIFF de velocidad + overlay sobre satélite (folium) + heatmap.
- `05_timeseries_slider.py` → *slider* temporal de deformación acumulada (Leaflet + Plotly), con
  suavizado temporal Gaussiano para atenuar el ruido atmosférico residual de fechas puntuales.
- `point_timeseries.py` → series temporales por zona (para la [interpretación](interpretacion.md)).

!!! warning "Nota técnica (reproducibilidad)"
    Con MintPy 1.6.2 + numpy 2.x hay un bug en la inversión pixel-a-pixel
    (`setting an array element with a sequence`). Se corrige con un patch de una línea
    (`np.asarray(x).item()`) en `ifgram_inversion.py` y `dem_error.py`. Alternativa: `numpy<2`.

## Reproducir

```bash
mamba env create -f pipeline/environment.yml && mamba activate insar
# credenciales: cuenta NASA Earthdata (~/.netrc) + token CDS (~/.cdsapirc)
python pipeline/01_search.py            # elegir track/frame
python pipeline/02_submit_hyp3.py --submit
bash   pipeline/03_timeseries.sh        # → velocity.h5
python pipeline/04_export_visual.py
python pipeline/05_timeseries_slider.py
```
