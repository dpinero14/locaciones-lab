"""Las antorchas vistas desde el satélite: la llama de una chimenea de quema en las bandas infrarrojas.

Una llama de gas emite en el infrarrojo de onda corta. En Sentinel-2 eso se ve como un píxel donde la banda
de 2,2 micrones (B12) vale mucho más que la de 1,6 (B11) y que el infrarrojo cercano (B8A), y casi siempre
satura. Es el índice de anomalía térmica de Liu et al. (2021): TAI = (B12 - B11) / B8A.

El camino es el mismo que el de las locaciones: una escena limpia por mes (la misma que ya se bajó para el
color real), los píxeles calientes de cada una, y los que se repiten en el mismo lugar a lo largo de los meses.
Un píxel caliente aislado no es una antorcha: los techos de chapa y los paneles brillan en el infrarrojo
cuando el sol está bajo, en invierno. Por eso la regla pide verla también fuera del invierno.

Los archivos van a `data/raw/<zona>/swir/AAAA-MM.npz` (bandas de 20 m).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import ANELO, DATA_RAW, ZONAS
from .escenas import buscar, leer

# un píxel caliente
TAI_MIN, EXCESO_MIN, B12_MIN = 0.45, 0.05, 0.15
# una antorcha: el mismo lugar (a menos de RADIO_FOCO_PX píxeles de 20 m) en varios meses
RADIO_FOCO_PX = 5
MESES_MIN = 3             # vista en tres escenas mensuales o más
FUERA_INVIERNO_MIN = 3    # de las cuales tres o más de septiembre a abril: un reflejo solo aparece con sol bajo
B12_SATURA = 1.2          # alguna vez la banda de 2,2 micrones satura, como con una llama
KM_ANELO_MIN = 3.0        # el pueblo queda afuera, igual que en el detector de locaciones
INVIERNO = (5, 6, 7, 8)
KM_MISMA = 0.2            # dos focos de ventanas vecinas a menos de 200 m son la misma antorcha

URL_VENTEOS = ("http://datos.energia.gob.ar/dataset/530bb019-32f4-4eaf-b550-1fc05f8b129f/resource/"
               "c3812323-0c38-43b7-8bc6-f05fb5113626/download/produccin-hidrocarburos-puntos-de-venteo-declarados.csv")


def calientes(b12: np.ndarray, b11: np.ndarray, b8a: np.ndarray) -> np.ndarray:
    """Máscara de píxeles calientes a partir de las tres bandas en reflectancia (0 a 1 y más si saturan)."""
    exceso = b12 - b11
    return (exceso / np.maximum(b8a, 0.01) >= TAI_MIN) & (exceso >= EXCESO_MIN) & (b12 >= B12_MIN)


def bajar_infrarrojo(zona: str, raw: Path = DATA_RAW) -> list[str]:
    """Las bandas infrarrojas de la misma escena mensual que ya está bajada en color real. Reanudable."""
    destino = raw / zona / "swir"
    destino.mkdir(parents=True, exist_ok=True)
    bbox = ZONAS[zona]["bbox"]
    hechos, por_anio = [], {}
    for p in sorted((raw / zona).glob("20*.npz")):
        por_anio.setdefault(p.stem[:4], []).append(p)
    for anio, archivos in sorted(por_anio.items()):
        if all((destino / p.name).exists() for p in archivos):
            hechos += [p.stem for p in archivos]
            continue
        por_fecha = {}
        for f in buscar(zona, f"{anio}-01-01", f"{anio}-12-31", nubes_tile_max=101):
            por_fecha.setdefault(f["properties"]["datetime"][:10], f)
        for p in archivos:
            if (destino / p.name).exists():
                hechos.append(p.stem)
                continue
            fecha = str(np.load(p)["fecha"])
            f = por_fecha.get(fecha)
            if f is None:
                print(zona, p.stem, "sin escena para", fecha, flush=True)
                continue
            try:
                b12, tr, crs = leer(f["assets"]["swir22"]["href"], bbox)
                b11, _, _ = leer(f["assets"]["swir16"]["href"], bbox)
                b8a, _, _ = leer(f["assets"]["nir08"]["href"], bbox)
            except Exception as e:  # noqa: BLE001 - el servidor corta a veces: se reintenta en la próxima corrida
                print(zona, p.stem, "error", str(e)[:80], flush=True)
                continue
            np.savez_compressed(destino / p.name, fecha=fecha, b12=b12, b11=b11, b8a=b8a, transform=np.array(tr.to_gdal()), crs=crs)
            print(zona, p.stem, fecha, flush=True)
            hechos.append(p.stem)
    return hechos


def cargar_mes(zona: str, mes: str, raw: Path = DATA_RAW) -> dict:
    """Las tres bandas de un mes en reflectancia, con su transformación."""
    from rasterio.transform import Affine

    e = np.load(raw / zona / "swir" / f"{mes}.npz")
    return {"b12": e["b12"].astype(np.float32) / 10000, "b11": e["b11"].astype(np.float32) / 10000, "b8a": e["b8a"].astype(np.float32) / 10000,
            "transform": Affine.from_gdal(*e["transform"]), "crs": str(e["crs"]), "fecha": str(e["fecha"])}


def detectar(zona: str, raw: Path = DATA_RAW) -> pd.DataFrame:
    """Cada grupo de píxeles calientes de cada escena mensual: mes, posición, tamaño y brillo."""
    from rasterio.transform import Affine
    from rasterio.warp import transform as rtransform
    from scipy import ndimage

    archivos = sorted((raw / zona / "swir").glob("20*.npz"))
    if not archivos:
        raise FileNotFoundError(f"no hay bandas infrarrojas de {zona}: correr scripts/antorchas.py --bajar")
    e0 = np.load(archivos[0])
    tr, crs = Affine.from_gdal(*e0["transform"]), str(e0["crs"])
    h, w = e0["b12"].shape
    filas = []
    for p in archivos:
        e = np.load(p)
        b12, b11, b8a = (e[k][:h, :w].astype(np.float32) / 10000 for k in ("b12", "b11", "b8a"))
        m = calientes(b12, b11, b8a)
        lab, n = ndimage.label(m, structure=np.ones((3, 3)))
        for i in range(1, n + 1):
            g = lab == i
            f, c = ndimage.center_of_mass(g)
            filas.append({"zona": zona, "mes": p.stem, "fila": f, "col": c, "pix": int(g.sum()), "b12": float(b12[g].max()), "b11": float(b11[g].max())})
    d = pd.DataFrame(filas, columns=["zona", "mes", "fila", "col", "pix", "b12", "b11"])
    if d.empty:
        return d.assign(x=[], y=[], lon=[], lat=[], foco=[])
    d["x"], d["y"] = tr * (d.col.values + 0.5, d.fila.values + 0.5)
    d["lon"], d["lat"] = rtransform(crs, "EPSG:4326", d.x.values, d.y.values)
    d["foco"] = agrupar(d.fila.values, d.col.values)
    return d


def agrupar(fila: np.ndarray, col: np.ndarray, radio: float = RADIO_FOCO_PX) -> np.ndarray:
    """Asigna cada detección a un foco: el primero que quedó a menos de `radio` píxeles, o uno nuevo."""
    centros, foco = [], np.empty(len(fila), int)
    for i, (f, c) in enumerate(zip(fila, col)):
        for j, (f0, c0) in enumerate(centros):
            if np.hypot(f - f0, c - c0) < radio:
                foco[i] = j
                break
        else:
            centros.append((f, c))
            foco[i] = len(centros) - 1
    return foco


def resumir(det: pd.DataFrame) -> pd.DataFrame:
    """Una fila por foco: en cuántos meses se lo vio, cuántos fuera del invierno, brillo máximo y posición."""
    d = det.assign(invierno=det.mes.str[5:7].astype(int).isin(INVIERNO))
    f = d.groupby(["zona", "foco"]).agg(meses=("mes", "nunique"), fuera_invierno=("invierno", lambda s: int((~s).sum())), b12=("b12", "max"),
                                        pix=("pix", "median"), lon=("lon", "mean"), lat=("lat", "mean"), x=("x", "mean"), y=("y", "mean"),
                                        primero=("mes", "min"), ultimo=("mes", "max")).reset_index()
    f["km_anelo"] = np.hypot((f.lon - ANELO[0]) * 87.5, (f.lat - ANELO[1]) * 111)
    f["antorcha"] = es_antorcha(f)
    return f


def es_antorcha(f: pd.DataFrame) -> pd.Series:
    """La regla: se repite, también fuera del invierno, satura alguna vez y no está en el pueblo."""
    return (f.meses >= MESES_MIN) & (f.fuera_invierno >= FUERA_INVIERNO_MIN) & (f.b12 >= B12_SATURA) & (f.km_anelo > KM_ANELO_MIN)


def unir(focos: pd.DataFrame) -> pd.DataFrame:
    """Las ventanas vecinas se pisan en el borde: de dos antorchas a menos de 200 m queda la primera."""
    a = focos[focos.antorcha].reset_index(drop=True)
    x, y = a.lon.values * 87.5, a.lat.values * 111
    quedan = []
    for i in range(len(a)):
        if all(np.hypot(x[i] - x[j], y[i] - y[j]) > KM_MISMA for j in quedan):
            quedan.append(i)
    return a.loc[quedan].reset_index(drop=True)


def venteos_declarados(raw: Path = DATA_RAW) -> pd.DataFrame:
    """Los puntos de venteo que las empresas declaran a la Secretaría de Energía (chimeneas y fosas de quema)."""
    import json

    import requests

    p = raw / "venteo_declarado.csv"
    if not p.exists():
        r = requests.get(URL_VENTEOS, timeout=180)
        r.raise_for_status()
        p.write_bytes(r.content)
    v = pd.read_csv(p)
    c = v.geojson.map(lambda s: json.loads(s)["coordinates"])
    return v.assign(lon=c.str[0], lat=c.str[1]).drop(columns="geojson")


def km_al_mas_cercano(lon, lat, lon2, lat2) -> np.ndarray:
    """Distancia en km de cada punto (lon, lat) al más cercano de (lon2, lat2), con la aproximación plana de la zona."""
    a, b = np.asarray(lon2) * 87.5, np.asarray(lat2) * 111
    return np.array([np.hypot(a - x * 87.5, b - y * 111).min() for x, y in zip(lon, lat)])


def aplicar_revision(ant: pd.DataFrame, revision: pd.DataFrame, km: float = 0.1) -> pd.DataFrame:
    """Marca las antorchas revisadas a mano (por posición, a menos de 100 m): galpones, zona urbana o imagen ilegible."""
    ant = ant.copy()
    ant["revision"] = ""
    for r in revision.itertuples():
        d = np.hypot((ant.lon - r.lon) * 87.5, (ant.lat - r.lat) * 111)
        if d.min() <= km:
            ant.loc[d.idxmin(), "revision"] = r.veredicto
    ant["firme"] = ant.revision == ""
    return ant


# ---------------------------------------------------------------- todas las pasadas, no una por mes
NUBES_PASADA_MAX = 0.6      # una pasada con más de 60 % de nubes o sombras en la ventana no se baja
NUBES_SOBRE_MAX = 0.2       # la antorcha "se ve" si en los 200 m de alrededor hay menos de 20 % de nubes o sombras


def bajar_pasadas(zona: str, desde_anio: int = 2025, hasta_anio: int = 2026, raw: Path = DATA_RAW, aviso=None) -> int:
    """Todas las pasadas de Sentinel-2 sobre la zona: de cada una se guardan los píxeles calientes y la máscara de nubes.

    Van a `data/raw/<zona>/pasadas/AAAA-MM-DD.npz`, unos pocos kilobytes cada una. Reanudable.
    """
    from .escenas import SCL_MALAS

    destino = raw / zona / "pasadas"
    destino.mkdir(parents=True, exist_ok=True)
    bbox, nuevas = ZONAS[zona]["bbox"], 0
    for anio in range(hasta_anio, desde_anio - 1, -1):
        por_fecha = {}
        for f in buscar(zona, f"{anio}-01-01", f"{anio}-12-31", nubes_tile_max=101):
            por_fecha.setdefault(f["properties"]["datetime"][:10], f)
        for fecha, f in sorted(por_fecha.items(), reverse=True):
            arch = destino / f"{fecha}.npz"
            if arch.exists():
                continue
            try:
                scl, _, _ = leer(f["assets"]["scl"]["href"], bbox)
                mala = np.isin(scl, SCL_MALAS)
                if mala.mean() > NUBES_PASADA_MAX:
                    np.savez_compressed(arch, fecha=fecha, descartada=True, mala_frac=float(mala.mean()))
                    continue
                b12, tr, crs = leer(f["assets"]["swir22"]["href"], bbox)
                b11, _, _ = leer(f["assets"]["swir16"]["href"], bbox)
                b8a, _, _ = leer(f["assets"]["nir08"]["href"], bbox)
            except Exception as e:  # noqa: BLE001  (un archivo que no responde no corta la bajada)
                if aviso:
                    aviso(f"{zona} {fecha}: {str(e)[:80]}")
                continue
            h, w = min(b12.shape[0], scl.shape[0]), min(b12.shape[1], scl.shape[1])
            a, b, c = (x[:h, :w].astype(np.float32) / 10000 for x in (b12, b11, b8a))
            cal = calientes(a, b, c)
            ys, xs = np.nonzero(cal)
            np.savez_compressed(arch, fecha=fecha, descartada=False, mala_frac=float(mala.mean()), mala=np.packbits(mala[:h, :w]), forma=np.array([h, w]),
                                fila=ys.astype(np.int16), col=xs.astype(np.int16), b12=a[cal], b11=b[cal], b8a=c[cal], transform=np.array(tr.to_gdal()), crs=crs)
            nuevas += 1
    return nuevas


def tiempo_encendida(ant: pd.DataFrame, raw: Path = DATA_RAW) -> pd.DataFrame:
    """En qué fracción de las pasadas sin nubes tenía llama cada antorcha.

    Una pasada cuenta para una antorcha si alrededor suyo (200 m) no hay nubes ni sombras; está encendida si hay
    un píxel caliente a menos de `RADIO_FOCO_PX` píxeles, la misma tolerancia con que se agrupan los focos.
    """
    from rasterio.transform import Affine

    r, filas = RADIO_FOCO_PX, []
    for zona, g in ant.groupby("zona"):
        archivos = sorted((raw / zona / "pasadas").glob("20*.npz"))
        vistas, enc = np.zeros(len(g), int), np.zeros(len(g), int)
        ultima = [""] * len(g)
        for p in archivos:
            e = np.load(p)
            if bool(e["descartada"]):
                continue
            h, w = e["forma"]
            mala = np.unpackbits(e["mala"])[:h * w].reshape(h, w).astype(bool)
            tr = Affine.from_gdal(*e["transform"])
            fc, cc = e["fila"].astype(int), e["col"].astype(int)
            for k, a in enumerate(g.itertuples()):
                c, f = ~tr * (a.x, a.y)
                c, f = int(c), int(f)
                v = mala[max(f - r, 0):f + r + 1, max(c - r, 0):c + r + 1]
                if v.size == 0 or v.mean() > NUBES_SOBRE_MAX:
                    continue
                vistas[k] += 1
                if len(fc) and (np.hypot(fc - f, cc - c) <= r).any():
                    enc[k] += 1
                    ultima[k] = p.stem
        for k, a in enumerate(g.itertuples()):
            filas.append({"zona": zona, "foco": a.foco, "pasadas": len(archivos), "vistas": int(vistas[k]), "encendida": int(enc[k]), "ultima": ultima[k]})
    t = pd.DataFrame(filas)
    t["pct"] = (t.encendida / t.vistas.clip(lower=1) * 100).round(1)
    return t
