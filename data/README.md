# Datos

`data/raw` y `data/processed` no se versionan. `python scripts/download_data.py --series` baja todo.

| Archivo | Fuente | Licencia | Qué es |
|---|---|---|---|
| `raw/<zona>/AAAA-MM.npz` | Copernicus Sentinel-2 L2A vía el STAC de Element84 | datos libres de Copernicus | Una escena limpia por mes (menos del 3 % de nube sobre la ventana, medido con la banda SCL), bandas roja, verde y azul a 10 m recortadas a la ventana, con su transformación |
| `raw/pozos_shp/` | Secretaría de Energía, Capítulo IV, shapefile de pozos | CC BY 4.0 | Boca de cada pozo, operador y fechas de perforación y terminación |
| `raw/produccion_no_convencional.csv` | Secretaría de Energía, Capítulo IV | CC BY 4.0 | Producción mensual de los pozos no convencionales: de ahí sale el primer mes con producción |
| `etiquetas_muestra.csv` | propio | MIT | 48 detecciones etiquetadas a mano (locación, camino, planta, urbano, natural) con sus rasgos, sin coordenadas |
| `verificacion_visual_2026-10.csv` | propio | MIT | Lo que se ve en septiembre-octubre de 2026 en las 28 locaciones sin pozo registrado, sin coordenadas |

Descarga verificada el 15 de octubre de 2026.
