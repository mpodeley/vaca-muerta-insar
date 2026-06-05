# ¿Se puede ver subsidencia en Vaca Muerta desde el espacio?

Este sitio documenta un **experimento técnico**: medir la **deformación del suelo**
(hundimiento o *subsidencia*, y levantamiento o *uplift*, de milímetros a centímetros por año)
en la cuenca Neuquina / Vaca Muerta usando **únicamente datos satelitales públicos y gratuitos**
(Sentinel-1, radar de apertura sintética).

La pregunta no es comercial sino metodológica:

> **¿Se observa bien la subsidencia con InSAR satelital en esta zona, y los datos dicen algo?**

![Mapa de velocidad de deformación, ~210×210 km en torno a Añelo](assets/heatmap_subsidencia.png){ loading=lazy }

*Velocidad media de deformación 2019–2026 (mm/año) sobre ~210×210 km. Rojo = subsidencia, azul =
uplift. Fondo amplio estable con varias cubetas de subsidencia localizadas. Sentinel-1/SBAS (track 18
ascendente), corregido por atmósfera (ERA5).*

## Respuesta corta

**Sí.** Con datos gratuitos se obtiene un mapa de velocidad **creíble** sobre un área grande: el fondo
es mayormente estable y aparecen **varias zonas localizadas de subsidencia** de hasta ~12 mm/año,
coherentes con lo publicado para la cuenca (Brunori et al. 2022, −8 a −10 mm/año). Y sí, **los datos
dicen algo**: hay zonas que **se hunden de forma sostenida** a lo largo de **7 años** —la principal
acumuló ~82 mm— ver [Interpretación](interpretacion.md).

## Qué vas a encontrar acá

- **[Método paso a paso](metodo.md)** — cómo se hizo, de la descarga de imágenes al mapa final, todo
  reproducible y con las fuentes.
- **[Resultados](resultados.md)** — tres visualizaciones interactivas: un mapa de velocidad sobre
  satélite, un *slider* temporal de deformación acumulada (2019→2026), y un heatmap.
- **[Interpretación](interpretacion.md)** — qué muestran los datos, la hipótesis del valle del río y
  el uso de agua, y los *caveats* (qué NO se puede afirmar).
- **[Próximos pasos](proximos-pasos.md)** y **[Referencias](referencias.md)**.

!!! note "Honestidad metodológica"
    InSAR mide **correlación espacio-temporal**, no causalidad. Este es un piloto de viabilidad con
    datos gratuitos sobre ~7 años y **una sola línea de vista** (track ascendente); no reemplaza un
    estudio con validación de campo (GNSS) ni distingue por sí solo el mecanismo de la deformación.
