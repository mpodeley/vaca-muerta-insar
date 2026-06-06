# Bandurria Sur en el tiempo

La página de [Análisis por pozo](pozos.md) cruza la deformación con la producción **acumulada** de
toda la ventana InSAR. Acá hacemos el zoom temporal sobre **un solo bloque** —**Bandurria Sur**, el de
subsidencia más fuerte de la escena (núcleo de *shale oil* de Añelo)— para **ver crecer** el cuenco a la
par de la producción, pozo por pozo. Todo con **datos públicos** (Capítulo IV de la Secretaría de
Energía + trayectorias de pozo de Vaca Muerta).

## Voidage por pozo vs subsidencia, cuadro a cuadro

Seis instantáneas entre 2019 y 2026. En cada panel:

- **Fondo:** desplazamiento LOS **acumulado** a esa fecha (azul = estable/uplift, rojo = subsidencia),
  con la misma escala de color en todos los paneles (referencia ene-2019).
- **Líneas:** las **115 trayectorias horizontales** del bloque.
- **Elipse** (orientada a lo largo del lateral de cada pozo): **anillo negro** = voidage de reservorio
  **total** acumulado hasta esa fecha; **relleno** = la parte que es **petróleo** (Np·Bo). Ambos en la
  **misma escala volumétrica** (rm³), así el anillo visible alrededor del relleno es el aporte de
  **agua + gas** de reservorio.

![Bandurria Sur — voidage por pozo (elipse) vs subsidencia InSAR, 6 timesteps + panel temporal](assets/bsur_timesteps.png){ loading=lazy }

La película es contundente: en 2019–2020 casi no hay producción (elipses mínimas) y el terreno está
plano. A medida que entran pozos y el voidage crece, **el cuenco rojo se forma y se profundiza justo
donde se concentran las elipses más grandes** (racimo del sureste), llegando a **≈ −118 mm** acumulados.
La subsidencia es **focalizada en el racimo denso**, no bajo los pocos pozos aislados del noroeste.

## El acople en números (panel inferior)

El panel de abajo descompone el **voidage acumulado del bloque** (áreas apiladas, en Mm³ de reservorio)
y lo superpone con la **subsidencia mediana sobre los pozos** (línea roja, eje derecho):

| Componente (acum. 2026) | Mm³ reservorio |
|---|---|
| Petróleo (Np·Bo) | **13.5** |
| Agua (Wp·Bw) | 3.96 |
| Gas (Gp·Bg) | 5.95 |
| **Voidage bruto** | **23.4** |
| Subsidencia mediana de los pozos | **−85 mm** |

El petróleo es la mayor componente del voidage, y la curva de subsidencia **se despega justo cuando
despega el voidage** (~2022) — el mismo acople producción↔compactación de la página por pozo, ahora
resuelto en el tiempo y sobre un bloque concreto.

!!! warning "Caveats"
    - **El "voidage neto" del panel ≈ al bruto** porque los **inyectores de Bandurria Sur no tienen
      trayectoria** y quedan fuera de este set de 115 productores: el neto graficado **no** resta la
      inyección de agua del bloque (que existe, en pozos inyectores aparte). Es voidage de **producción**,
      no balance de bloque.
    - **FVF aproximados** (Bo≈1.4, Bw≈1.03, Bg≈0.0035 rm³/sm³): valen para comparación relativa, no como
      balance volumétrico exacto.
    - **Correlación, no causalidad**; el voidage es colineal con la producción.
    - La elipse codifica **volumen** (tamaño) y **orientación** (azimut del lateral por PCA); no es el
      radio de drenaje físico.

*Datos: Capítulo IV (producción mensual por pozo, trayectorias) de la Secretaría de Energía; serie
temporal InSAR de este trabajo. Reproducible con `pipeline/fetch_bsur_monthly.py` (serie mensual por
pozo) y `pipeline/bsur_timesteps.py` (figura).*
