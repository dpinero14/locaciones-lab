"""Los pozos del Capítulo IV: dónde están, cuándo se empezaron a perforar y cuándo produjeron por primera vez.

- El shapefile de pozos de la Secretaría de Energía trae la boca de pozo y las fechas de perforación
  (FECHA_INIC, FECHA_FIN_) y de terminación. Está al día para los pozos fracturados, pero carga los
  pozos nuevos con unos seis meses de demora.
- La producción de pozos no convencionales da el primer mes con producción de cada pozo.
- Una locación es un grupo de pozos a menos de 30 m entre sí (los pads multipozo de Vaca Muerta).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import DATA_RAW

ENERGIA = "http://datos.energia.gob.ar/dataset/c846e79c-026c-4040-897f-1ad3543b407c/resource"
URLS = {
    "pozos_shp.zip": f"{ENERGIA}/3fcda0c5-68aa-4f33-bbe2-0180e6dbeebe/download/shapefile-de-pozos.zip",
    "produccion_no_convencional.csv": f"{ENERGIA}/b5b58cdc-9e07-41f9-b392-fb9ec68b0725/download/produccin-de-pozos-de-gas-y-petrleo-no-convencional.csv",
}


def pozos(raw: Path = DATA_RAW) -> pd.DataFrame:
    """Todos los pozos del shapefile con lon, lat y fecha de inicio de perforación."""
    import geopandas as gpd

    shp = next((raw / "pozos_shp").glob("*.shp"))
    g = gpd.read_file(shp)
    g = g[g.geometry.notna()].copy()
    df = pd.DataFrame({"idpozo": g.IDENTIFICA.values, "sigla": g.SIGLA.values, "empresa": g.EMPRESA.values, "lon": g.geometry.x.values, "lat": g.geometry.y.values,
                       "perforacion": pd.to_datetime(g.FECHA_INIC, errors="coerce").values, "tipo_recurso": g.TIPO_RECUR.values})
    return df


def primera_produccion(raw: Path = DATA_RAW) -> pd.Series:
    """Primer mes con producción de cada pozo no convencional."""
    p = pd.read_csv(raw / "produccion_no_convencional.csv", usecols=["idpozo", "anio", "mes"])
    p = p.sort_values(["anio", "mes"]).drop_duplicates("idpozo")
    return pd.Series(pd.to_datetime(dict(year=p.anio, month=p.mes, day=1)).values, index=p.idpozo.values, name="produccion")


def en_ventana(df: pd.DataFrame, transform, crs: str, alto: int, ancho: int) -> pd.DataFrame:
    """Agrega columna y fila de cada pozo en la grilla de la escena y se queda con los de adentro."""
    from rasterio.warp import transform as rtransform

    xs, ys = rtransform("EPSG:4326", crs, df.lon.values, df.lat.values)
    col, fila = ~transform * (np.array(xs), np.array(ys))
    out = df.assign(col=col, fila=fila)
    return out[(out.col >= 0) & (out.col <= ancho - 1) & (out.fila >= 0) & (out.fila <= alto - 1)].copy()


def locaciones(df: pd.DataFrame, metros_por_pixel: float, radio_m: float = 30.0) -> pd.DataFrame:
    """Agrupa pozos a menos de radio_m en locaciones. Fecha de la locación: el primer pozo perforado y el primero en producir."""
    from scipy.cluster.hierarchy import fcluster, linkage

    if len(df) < 2:
        return pd.DataFrame(columns=["loc", "col", "fila", "pozos", "perforacion", "produccion"])
    z = linkage(np.column_stack([df.col * metros_por_pixel, df.fila * metros_por_pixel]), method="single")
    d = df.assign(loc=fcluster(z, t=radio_m, criterion="distance"))
    agg = {"col": ("col", "mean"), "fila": ("fila", "mean"), "pozos": ("idpozo", "size"), "perforacion": ("perforacion", "min")}
    if "produccion" in d:
        agg["produccion"] = ("produccion", "min")
    return d.groupby("loc").agg(**agg).reset_index()
