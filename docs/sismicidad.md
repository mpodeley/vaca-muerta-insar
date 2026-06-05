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

*Catálogo **ISC** (que agrega los reportes de **INPRES**, la red argentina), 2015–2026. Amarillo =
sismos **corticales** (< 30 km, candidatos a inducidos); gris = **profundos** (subducción, no
relacionados). Tamaño ∝ magnitud. Fondo = velocidad InSAR. Click en un sismo para ver
fecha/magnitud/profundidad.*

Usando ISC/INPRES —mucho más completo que el catálogo global, **baja hasta ~M1.8**— aparecen **70
eventos**, de los cuales **67 son corticales** (< 30 km, casi todos < 15 km). Se concentran al **oeste y
suroeste de Añelo**, en la zona de **Sauzal Bonito**, justo donde la literatura ubica la sismicidad
inducida. El mayor cortical es el **M4.8 del 7-mar-2019** —el mismo evento que Brunori (2022) reporta
como **Mw 5**; los catálogos dan magnitudes algo distintas para un mismo sismo según el método de
cálculo—. Y hay un dato llamativo: **41 de los 70 sismos ocurrieron en 2023** — un enjambre marcado.

!!! warning "Caveats (importantes)"
    - **El aumento es en parte detección.** La red sísmica local recién **densifica desde ~2018**, así
      que parte del "aumento" de sismos es mejor capacidad de detección, no solo más actividad. Separar
      ambos efectos requiere el análisis cuidadoso que hacen los estudios especializados [Schultz 2024].
    - **Sigue habiendo un piso de magnitud.** Aun ISC/INPRES pierde los micro-sismos más chicos que sí
      registran las redes densas locales del *Observatorio de Sismicidad Inducida* (600+ temblores).
    - **Correlación temporal, no causalidad.** La asociación actividad↔sismicidad es estadística y
      temporal; **no es una prueba de causa**. Atribuir cada sismo requiere datos locales (red sísmica,
      presiones de inyección).

## Por qué importa juntar las dos capas

La deformación (InSAR) y la sismicidad son **dos síntomas del mismo proceso** —cambios de presión en el
subsuelo por inyección/extracción—. Monitorear ambas a la vez (más datos de inyección) es lo que
permitiría pasar de *correlación* a *gestión de riesgo* con base empírica. Las fuentes para profundizar
están en [Referencias](referencias.md); una red GNSS + catálogo sísmico local serían los próximos
insumos ([próximos pasos](proximos-pasos.md)).
