# ¿Se puede ver subsidencia en Vaca Muerta desde el espacio?

Este sitio documenta un **experimento técnico**: medir la **deformación del suelo**
(hundimiento o *subsidencia*, y levantamiento o *uplift*, de milímetros a centímetros por año)
en la cuenca Neuquina / Vaca Muerta usando **únicamente datos satelitales públicos y gratuitos**
(Sentinel-1, radar de apertura sintética).

La pregunta no es comercial sino metodológica:

> **¿Se observa bien la subsidencia con InSAR satelital en esta zona, y los datos dicen algo?**

![Mapa de velocidad de deformación sobre el clúster productivo de Añelo](assets/heatmap_subsidencia.png){ loading=lazy }

*Velocidad media de deformación 2019–2020 (mm/año). Rojo = subsidencia, azul = uplift. Fondo
estable (~0) con señales localizadas. Sentinel-1/SBAS, corregido por atmósfera (ERA5).*

## Respuesta corta

**Sí.** Con datos gratuitos se obtiene un mapa de velocidad **creíble**: el fondo es estable
(mediana ≈ 0 mm/año) y aparecen **zonas localizadas de subsidencia y uplift** de varios mm/año,
coherentes con lo publicado para la cuenca (Brunori et al. 2022, –8 a –10 mm/año). Y sí, **los datos
dicen algo**: hay una zona que **se hunde de forma sostenida (~15 mm/año)** a lo largo del valle —
ver [Interpretación](interpretacion.md).

## Qué vas a encontrar acá

- **[Método paso a paso](metodo.md)** — cómo se hizo, de la descarga de imágenes al mapa final, todo
  reproducible y con las fuentes.
- **[Resultados](resultados.md)** — tres visualizaciones interactivas: un mapa de velocidad sobre
  satélite, un *slider* temporal de deformación acumulada, y un heatmap.
- **[Interpretación](interpretacion.md)** — qué muestran los datos, la hipótesis del valle del río y
  el uso de agua, y los *caveats* (qué NO se puede afirmar).
- **[Próximos pasos](proximos-pasos.md)** y **[Referencias](referencias.md)**.

!!! note "Honestidad metodológica"
    InSAR mide **correlación espacio-temporal**, no causalidad. Este es un piloto de viabilidad con
    datos gratuitos sobre ~20 meses; no reemplaza un estudio con validación de campo (GNSS) ni
    distingue por sí solo el mecanismo de la deformación.
