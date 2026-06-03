# Próximos pasos

El piloto responde la pregunta de viabilidad. Para convertirlo en algo robusto:

## Mejorar la medición

- **Track ascendente.** Sumar la órbita ascendente permite **descomponer** la deformación LOS en
  componentes **vertical y este-oeste** (hoy solo tenemos una línea de vista).
- **Extender el histórico.** Sentinel-1 tiene datos desde ~2015; más años = velocidad más robusta y
  detección de cambios de tendencia.
- **GNSS de calibración.** No hay estaciones continuas cercanas; instalar una o dos daría **verdad de
  campo** y ataría el InSAR a un marco absoluto.

## Confirmar la interpretación

- **Cruzar con hidrología.** Superponer la serie de subsidencia con **niveles freáticos** (AIC / DPRH)
  y con **humedad de suelo** (ERA5-Land/SMAP) para separar extracción de agua vs artefacto estacional.
- **Sentinel-2 (NDVI).** Verificar si la subsidencia coincide con **parcelas bajo riego**.
- **Geología (SEGEMAR).** Distinguir compactación de aluvión de subsidencia por bombeo.

## Contexto y comunicación

- **Polígonos oficiales de concesiones** (`energia.gob.ar`) para ubicar la señal respecto a la
  actividad — *no se incluyeron coordenadas de yacimientos acá porque las aproximadas eran imprecisas*.
- **Alta resolución dirigida** (SAR comercial: ICEYE/Capella/Umbra) solo sobre los *hotspots*
  detectados, si se quisiera detalle a escala de instalación.

## Limitaciones actuales (honestas)

- Una sola línea de vista (no se separa vertical de horizontal).
- ~20 meses de datos (tendencia corta).
- Sin validación de campo (GNSS).
- Zonas de baja coherencia (agua, regadío denso, pads activos) quedan sin dato.
