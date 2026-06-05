# Resultados

Tres formas de mirar el mismo dato: el **mapa de velocidad** (cuánto se mueve cada punto por año), la
**evolución temporal** (cómo se fue moviendo en 7 años), y el **overlay sobre satélite** (dónde,
geográficamente). Área: **~210×210 km** en torno a Añelo; período **2019–2026**.

## Velocidad media de deformación (2019–2026)

<iframe src="../assets/demo_subsidencia.html" width="100%" height="520" style="border:1px solid #ccc;border-radius:6px"></iframe>

*Overlay interactivo sobre imagen satelital. Rojo = subsidencia, azul = uplift (mm/año). Zoom y
arrastre habilitados.*

| Métrica | Valor |
|---|---|
| Área cubierta | ~210×210 km (lon −70.6 a −68.2, lat −39.2 a −37.3) |
| Pixels confiables (coherencia > 0.7) | 4.886.991 (~**74 %** del área) |
| Velocidad mediana | −1.9 mm/año |
| Percentil 1 / 5 | **−12.0** / −5.3 mm/año |
| Percentil 95 / 99 | +0.5 / +2.1 mm/año |
| % con subsidencia < −8 mm/año | 2.0 % (localizado) |

El **74 % de cobertura** confirma que la estepa árida es excelente terreno para InSAR. La señal de
subsidencia es **localizada** (varias cubetas), no un sesgo global.

## Deformación acumulada en el tiempo (slider)

<iframe src="../assets/demo_acumulado_slider.html" width="100%" height="560" style="border:1px solid #ccc;border-radius:6px"></iframe>

*Arrastrá el slider: cada paso es un trimestre (2019→2026) y muestra cuánto se hundió (rojo) o levantó
(azul) cada punto respecto a la primera fecha. Con suavizado temporal para atenuar el ruido
atmosférico de fechas puntuales.*

## La lección metodológica: la atmósfera importa

Un experimento previo con **solo 8 meses sin corrección troposférica** dio un resultado **engañoso**:
una subsidencia "generalizada" de −17 mm/año de mediana que era **artefacto** (retardo atmosférico +
ventana demasiado corta). Al **extender la serie y corregir con ERA5**, el sesgo desaparece y el fondo
queda estable, con señales localizadas reales.

Es un recordatorio de que en InSAR **el preprocesamiento define la conclusión**: sin corrección
atmosférica y con series cortas es fácil "ver" subsidencia donde no la hay.

## Mapa estático (respaldo)

![Heatmap de velocidad](assets/heatmap_subsidencia.png){ loading=lazy }
