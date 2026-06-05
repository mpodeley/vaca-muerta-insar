# Referencias

## InSAR en la cuenca Neuquina / casos análogos

- **[Brunori 2022]** Brunori et al. (2022), *Scientific Reports* — cuenca Neuquina: subsidencia −8 a
  −10 mm/año con Sentinel-1/SBAS (2017–2020). [doi:10.1038/s41598-022-23160-6](https://www.nature.com/articles/s41598-022-23160-6)
- **[Cigna 2021]** Cigna, Esquivel Ramírez & Tapete (2021), *Remote Sensing* 13(23):4800 — validación de
  Sentinel-1 PSI/SBAS contra GNSS. [mdpi.com](https://www.mdpi.com/2072-4292/13/23/4800)

## Subsidencia por extracción de agua subterránea (InSAR)

- **[Fenhe 2025]** Land subsidence in the Fenhe River Basin (China), Sentinel-1: hasta 81 mm/año,
  ciclos estacionales sincrónicos con el nivel freático. [Springer](https://link.springer.com/article/10.1007/s11069-025-07582-9)
- **[Ardabil 2022]** Land subsidence by groundwater withdrawal, Ardabil Plain (Irán), Sentinel-1.
  [Scientific Reports](https://www.nature.com/articles/s41598-022-17438-y)
- **[Aguascalientes 2021]** Structurally-controlled subsidence by groundwater exploitation,
  Aguascalientes Valley (México). [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0034425720306271)

## Sismicidad inducida

- **[Schultz 2024]** Schultz et al. (2024), *Seismica* — "Chasing the ghost of fracking in the Vaca
  Muerta"; ~0.5 % de operaciones asociadas a sismos. [seismica.library.mcgill.ca](https://seismica.library.mcgill.ca/article/view/1435)
- **[Sagripanti 2018]** Sagripanti et al. (2018), *J. South American Earth Sciences* — sismicidad
  intraplaca con red local, eventos cerca de Añelo posiblemente antropogénicos.
- **Catálogo sísmico:** **ISC** FDSN event service (isc.ac.uk), que agrega los reportes de **INPRES**
  (inpres.gob.ar, autor "SJA"); baja a ~M1.8. El **Observatorio de Sismicidad Inducida** (red local)
  registra el detalle fino (600+ temblores). **USGS** (earthquake.usgs.gov) solo capta M≳3.4.

## Software y procesamiento

- **[Yunjun 2019]** Yunjun, Fattahi & Amelung (2019), *Computers & Geosciences* — **MintPy**, software de
  series de tiempo InSAR. [doi:10.1016/j.cageo.2019.104331](https://doi.org/10.1016/j.cageo.2019.104331)
- **[Morishita 2020]** Morishita et al. (2020), *Remote Sensing* 12(3):424 — **LiCSBAS** (open-source).
  [mdpi.com](https://www.mdpi.com/2072-4292/12/3/424)
- **ASF HyP3** — procesamiento Sentinel-1 InSAR on-demand en la nube. [hyp3-docs.asf.alaska.edu](https://hyp3-docs.asf.alaska.edu)
- **PyAPS / ERA5** — corrección troposférica con reanálisis ECMWF. [Copernicus CDS](https://cds.climate.copernicus.eu)

## Datos satelitales

- **Sentinel-1** (ESA Copernicus), distribuido por **Alaska Satellite Facility (ASF)**.
- **Sentinel-2** (óptico, NDVI) — uso de suelo / riego.

## Producción y concesiones

- **Producción por área** (gas/petróleo/agua, Capítulo IV) y **polígonos de concesiones** de la cuenca
  Neuquina: datos públicos de la Secretaría de Energía / provincia de Neuquén
  (`energianeuquen.gob.ar`), vía el proyecto [estado-del-sistema](https://github.com/mpodeley/estado-del-sistema).

## Fuentes hídricas y geológicas (Argentina) para cruzar

- **AIC** — Autoridad Interjurisdiccional de las Cuencas de los ríos Limay, Neuquén y Negro.
- **DPRH Neuquén** (Dirección Provincial de Recursos Hídricos) / **DPA Río Negro** (Departamento
  Provincial de Aguas) — niveles freáticos, consorcios de riego.
- **energianeuquen.gob.ar** — datos de niveles de acuíferos en pozos de hidrocarburos.
- **SEGEMAR** — cartografía geológica (aluvión vs roca).
- **ERA5-Land / SMAP** — humedad de suelo (test de estacionalidad).

---

!!! note
    Las referencias de la cuenca Neuquina y de software fueron verificadas; las de casos análogos de
    subsidencia por agua subterránea provienen de literatura revisada por pares localizada para este
    informe. Cualquier afirmación de **causalidad** requiere el cruce con datos hidrológicos
    ([próximos pasos](proximos-pasos.md)).
