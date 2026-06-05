# Sismicidad

Una capa más para el contexto: **¿hay actividad sísmica en la zona, y cómo se relaciona con la
deformación y la actividad?**

## El antecedente: sismicidad inducida

La cuenca Neuquina tiene **sismicidad inducida documentada**. La zona de **Sauzal Bonito** (al
noroeste de Añelo) **no registraba sismos antes de ~2015** y desde entonces concentra eventos
asociados temporalmente al desarrollo no convencional. El mayor evento conocido fue un **ML 4.9 / Mw 5
el 7 de marzo de 2019**, somero, cerca de Añelo [Brunori 2022]. Estudios recientes estiman que
**~0.5 % de las operaciones de fractura** se asocian estadísticamente a sismos detectables [Schultz 2024].

## Mapa: deformación + sismos + concesiones

<iframe src="../assets/demo_sismicidad.html" width="100%" height="540" style="border:1px solid #ccc;border-radius:6px"></iframe>

*Catálogo USGS 2015–2026. Amarillo = sismos **corticales** (< 30 km, candidatos a inducidos); gris =
**profundos** (subducción, no relacionados). Tamaño ∝ magnitud. Fondo = velocidad InSAR. Click en un
sismo para ver fecha/magnitud/profundidad.*

De los 11 sismos del catálogo en el área, **8 son corticales** (< 30 km) — los relevantes para
sismicidad inducida — y se dispersan al **oeste y suroeste de Añelo**, hacia Sauzal Bonito. Los 3
restantes son profundos (> 180 km, subducción de la placa de Nazca) y no tienen relación con la
actividad de superficie. El mayor cortical es el **M5.0 de 2019**.

!!! warning "Caveats (importantes)"
    - **Catálogo incompleto.** USGS solo cataloga eventos de **M ≳ 3.4**. Los **micro-sismos inducidos
      (< M3)** que detectan las redes sísmicas locales **no aparecen** acá — son la mayoría de la
      sismicidad inducida real.
    - **Ubicación aproximada.** Las localizaciones globales del USGS tienen **±10–30 km** de error; las
      redes locales relocalizan los eventos mucho mejor (el M5 de 2019 se modela cerca de Sauzal Bonito,
      a pocos km de profundidad).
    - **Correlación temporal, no causalidad.** La asociación entre actividad y sismicidad es estadística
      y temporal; **no es una prueba de causa**. Atribuir cada sismo requiere datos locales (red sísmica,
      presiones de inyección).

## Por qué importa juntar las dos capas

La deformación (InSAR) y la sismicidad son **dos síntomas del mismo proceso** —cambios de presión en el
subsuelo por inyección/extracción—. Monitorear ambas a la vez (más datos de inyección) es lo que
permitiría pasar de *correlación* a *gestión de riesgo* con base empírica. Las fuentes para profundizar
están en [Referencias](referencias.md); una red GNSS + catálogo sísmico local serían los próximos
insumos ([próximos pasos](proximos-pasos.md)).
