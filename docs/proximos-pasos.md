# Próximos pasos

El piloto responde la pregunta de viabilidad. Para convertirlo en algo robusto:

## Mejorar la medición

- **Descomposición vertical / este-oeste.** Ya tenemos el track **ascendente** (18, este sitio) y un
  track **descendente** (112) procesado para 2019–2020. Combinando ambas líneas de vista se puede
  **separar** el movimiento vertical del horizontal — el paso natural siguiente.
- **Extender más el histórico.** Sentinel-1 tiene datos desde ~2015; sumar 2015–2018 daría aún más
  robustez. (Este experimento ya cubre 2019–2026.)
- **GNSS de calibración.** No hay estaciones continuas cercanas; instalar una o dos daría **verdad de
  campo** y ataría el InSAR a un marco absoluto.

## Confirmar la interpretación

- **Sentinel-2 (NDVI).** ✓ Hecho — la subsidencia fuerte **no** coincide con parcelas regadas (NDVI 0,11
  vs 0,12 de la zona estable; ver [Interpretación](interpretacion.md)). Descarta el riego superficial.
- **Cruzar con hidrología.** Decisivo pero **bloqueado por disponibilidad de datos**: no hay serie
  piezométrica pública del valle de Añelo (los repositorios abiertos —SNIH/BDHI, AIC, Datos Abiertos
  Neuquén— solo tienen agua de superficie). Requiere **datos institucionales** (DPRH Neuquén / AIC, por
  pedido) o piezómetros de campo para superponer la freática con la serie de subsidencia.
- **Geología (SEGEMAR).** Distinguir compactación de aluvión de subsidencia por bombeo.

## Contexto y comunicación

- **Polígonos oficiales de concesiones** (`energia.gob.ar`) para ubicar la señal respecto a la
  actividad — *no se incluyeron coordenadas de yacimientos acá porque las aproximadas eran imprecisas*.
- **Alta resolución dirigida** (SAR comercial: ICEYE/Capella/Umbra) solo sobre los *hotspots*
  detectados, si se quisiera detalle a escala de instalación.

## Limitaciones actuales (honestas)

- Una sola línea de vista (ascendente): no se separa vertical de horizontal.
- Muestreo ~mensual (se pierde algo de detalle sub-mensual / estacional fino).
- Sin validación de campo (GNSS).
- Zonas de baja coherencia (agua, regadío denso, pads activos) quedan sin dato.
