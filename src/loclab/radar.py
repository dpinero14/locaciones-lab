"""Los equipos de perforación vistos con radar (Sentinel-1).

Un equipo de perforación es una torre de metal de ~40 m: en el radar, que ve de día, de noche y con nubes, es
un punto muy brillante sobre una locación que antes era oscura, y además despolariza (brilla en VH, no solo en
VV). Se busca a ciegas, sin el padrón: puntos que se encienden sobre su brillo de siempre, seguidos de pasada en
pasada. El padrón (fechas de inicio y fin de perforación de cada pozo) se usa solo para medir.

- Datos: Sentinel-1 RTC (corregido por terreno) de Microsoft Planetary Computer, procesado por Catalyst, licencia
  CC BY 4.0. Órbita relativa 18 ascendente: una geometría fija, cada 12 días y cada 6 desde 2025.
- Se guarda en una grilla fija de 10 m (UTM 19 sur) por ventana: `data/raw/<zona>/radar/AAAA-MM-DD.npz`, VV y VH
  en dB cuantizados a uint8 (dB = q / 5 - 25; 0 = sin dato).
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from . import ANELO, CRS_METRICO, DATA_PROC, DATA_RAW, ZONAS

API = "https://planetarycomputer.microsoft.com/api/stac/v1"
TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-1-rtc"
ORBITA = 18
U_DB = 5.0          # un punto encendido: VV por encima de esto (dB, ya quitado el suelo mojado o seco de la escena)
D_DB = 6.0          # ... y por encima de su mediana de siempre
AREA_MAX = 60       # píxeles: más grande que esto no es un equipo
ENLACE_M = 60       # dos detecciones a menos de esto, en pasadas distintas, son el mismo objeto
HUECO_DIAS = 40     # sin verlo más que esto, el objeto se fue
MIN_PASADAS = 3
VH_MIN = -4.0       # la torre despolariza: VH máximo por encima de esto
BASE_MAX = -5.0     # el lugar casi siempre es oscuro (una locación, no una planta ni una playa)
KM_LOC = 0.15       # un equipo a menos de 150 m del centro de los pozos es de esa locación
CAMPANIA_DIAS = 60  # dos eventos en el mismo lugar separados por menos que esto son la misma campaña
KM_OBRA = 0.20      # ... o a menos de 200 m de una locación que vio Sentinel-2 (puede no tener pozo todavía)
KM_ANELO = 3.0      # el pueblo, las bases y las playas de Añelo brillan siempre: afuera, como en el detector de locaciones
CONTRASTE_MIN = 1.5  # sin padrón ni Sentinel-2: la locación nueva se ve clara contra el monte en la última imagen óptica
VERDE_MAX = 0.80     # ... y no es una chacra (verde sobre rojo)
DIAS_MAX = 240      # el 95 % de las perforaciones dura menos de 180 días; con la terminación pegada, hasta ~220: más es una instalación

_tok = {"t": None, "hasta": 0.0}


def _token() -> str:
    import requests

    if time.time() > _tok["hasta"]:
        _tok["t"] = requests.get(TOKEN, timeout=60).json()["token"]
        _tok["hasta"] = time.time() + 40 * 60
    return _tok["t"]


def grilla(zona: str):
    """La grilla fija de 10 m de la ventana: (transform, ancho, alto)."""
    from rasterio.transform import from_origin
    from rasterio.warp import transform_bounds

    x0, y0, x1, y1 = transform_bounds("EPSG:4326", CRS_METRICO, *ZONAS[zona]["bbox"])
    x0, y1 = np.floor(x0 / 10) * 10, np.ceil(y1 / 10) * 10
    return from_origin(x0, y1, 10, 10), int(np.ceil((x1 - x0) / 10)), int(np.ceil((y1 - y0) / 10))


def escenas(zona: str, desde: str, hasta: str) -> list[dict]:
    import requests

    body = {"collections": ["sentinel-1-rtc"], "bbox": list(ZONAS[zona]["bbox"]), "datetime": f"{desde}/{hasta}", "limit": 500,
            "query": {"sat:relative_orbit": {"eq": ORBITA}, "sat:orbit_state": {"eq": "ascending"}}}
    out = []
    while True:
        r = requests.post(f"{API}/search", json=body, timeout=120).json()
        out += r["features"]
        nx = [l for l in r.get("links", []) if l["rel"] == "next"]
        if not nx:
            return out
        body = nx[0]["body"]


def _cuantizar(lin: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        db = 10 * np.log10(np.clip(lin, 1e-4, None))
    q = np.clip(np.round((db + 25) * 5), 1, 255).astype(np.uint8)
    q[~np.isfinite(lin) | (lin <= 0)] = 0
    return q


def _bajar_una(f: dict, destino: Path, T, ancho: int, alto: int) -> str:
    import rasterio
    from rasterio.vrt import WarpedVRT
    from rasterio.warp import Resampling

    fecha = f["properties"]["datetime"][:10]
    dest = destino / f"{fecha}.npz"
    if dest.exists():
        return "ya"
    bandas = {}
    for b in ("vv", "vh"):
        for intento in range(4):
            try:
                with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="4"):
                    with rasterio.open(f["assets"][b]["href"] + "?" + _token()) as src:
                        with WarpedVRT(src, crs=CRS_METRICO, transform=T, width=ancho, height=alto, resampling=Resampling.bilinear, nodata=0) as v:
                            bandas[b] = _cuantizar(v.read(1).astype(np.float32))
                break
            except Exception as e:  # noqa: BLE001
                if intento == 3:
                    return f"error {e}"
                time.sleep(10)
    if (bandas["vv"] > 0).mean() < 0.5:      # el mismo día suele haber dos cuadros: se queda el que cubre la ventana
        return "fuera de la franja"
    np.savez_compressed(dest, vv=bandas["vv"], vh=bandas["vh"])
    return "ok"


def bajar(zona: str, desde: str = "2025-08-01", hasta: str = "2026-12-31", raw: Path = DATA_RAW, hilos: int = 4, aviso=None) -> int:
    """Baja las pasadas que falten de la ventana (reanudable). ~30 MB por pasada; el límite es el ancho de banda."""
    T, ancho, alto = grilla(zona)
    destino = raw / zona / "radar"
    destino.mkdir(parents=True, exist_ok=True)
    np.save(destino / "transform.npy", np.array(T)[:6])
    fs = escenas(zona, desde, hasta)
    n = 0
    with ThreadPoolExecutor(hilos) as ex:
        for f, est in zip(fs, ex.map(lambda f: _bajar_una(f, destino, T, ancho, alto), fs)):
            n += est == "ok"
            if aviso:
                aviso(zona, f["properties"]["datetime"][:10], est)
    return n


def fases(zona: str, raw: Path = DATA_RAW) -> pd.DataFrame:
    """Las locaciones del padrón con su perforación [primer inicio, último fin] y su terminación, en metros UTM."""
    import geopandas as gpd
    from rasterio.warp import transform as rtransform
    from scipy.cluster.hierarchy import fcluster, linkage

    g = gpd.read_file(next((raw / "pozos_shp").glob("*.shp")))
    g = g[g.geometry.notna()]
    x0, y0, x1, y1 = ZONAS[zona]["bbox"]
    w = g[g.geometry.x.between(x0, x1) & g.geometry.y.between(y0, y1)].copy()
    for c in ["FECHA_INIC", "FECHA_FIN_", "ASFECHA_IN", "FECHA_F_01"]:
        w[c] = pd.to_datetime(w[c], errors="coerce")
    w["x"], w["y"] = rtransform("EPSG:4326", CRS_METRICO, w.geometry.x.values, w.geometry.y.values)
    w["loc"] = fcluster(linkage(w[["x", "y"]].values, method="single"), t=30, criterion="distance")
    return w.groupby("loc").agg(x=("x", "mean"), y=("y", "mean"), lon=("geometry", lambda s: s.x.mean()), lat=("geometry", lambda s: s.y.mean()),
                                pozos=("SIGLA", "size"), empresa=("EMPRESA", "first"),
                                perf_ini=("FECHA_INIC", "min"), perf_fin=("FECHA_FIN_", "max"),
                                term_ini=("ASFECHA_IN", "min"), term_fin=("FECHA_F_01", "max")).reset_index().assign(zona=zona)


def fechas(zona: str, raw: Path = DATA_RAW) -> pd.DatetimeIndex:
    return pd.to_datetime(sorted(p.stem for p in (raw / zona / "radar").glob("20*.npz")))


def eventos(zona: str, raw: Path = DATA_RAW, desde: str | None = None) -> pd.DataFrame:
    """Detector a ciegas: puntos que se encienden, seguidos de pasada en pasada. Un evento por objeto seguido."""
    from rasterio.warp import transform as rtransform
    from scipy import ndimage

    carpeta = raw / zona / "radar"
    fs = sorted(carpeta.glob("20*.npz"))
    if desde:
        fs = [f for f in fs if f.stem >= desde]
    fe = pd.to_datetime([f.stem for f in fs])
    vv_q = np.stack([np.load(f)["vv"] for f in fs])
    vh = np.stack([np.load(f)["vh"] for f in fs])                      # uint8: se pasa a dB solo al medir
    vv = vv_q.astype(np.float32) / 5 - 25
    vv[vv_q == 0] = np.nan
    del vv_q
    fondo = np.nanmedian(vv.reshape(len(vv), -1), axis=1)
    vv -= (fondo - np.nanmedian(fondo))[:, None, None]       # suelo mojado o seco: toda la escena sube o baja
    base = np.nanmedian(vv, axis=0)                           # cómo se ve cada píxel casi siempre
    T = np.load(carpeta / "transform.npy")
    dets = []
    for i in range(len(vv)):
        m = (vv[i] > U_DB) & (vv[i] - base > D_DB)
        m = ndimage.binary_dilation(m, iterations=1) & (vv[i] > U_DB - 4)
        lab, n = ndimage.label(m)
        if n == 0:
            continue
        idx = np.arange(1, n + 1)
        area = ndimage.sum(m, lab, idx)
        cy, cx = np.array(ndimage.center_of_mass(m, lab, idx)).reshape(-1, 2).T
        vmax, hmax = ndimage.maximum(vv[i], lab, idx), np.asarray(ndimage.maximum(vh[i], lab, idx)) / 5 - 25
        for a, y, x, v, h in zip(area, cy, cx, vmax, hmax):
            if a <= AREA_MAX:
                dets.append((i, T[2] + (x + 0.5) * T[0], T[5] + (y + 0.5) * T[4], a, v, h))   # centro del píxel
    objetos, vivos = [], []
    for i in sorted({d[0] for d in dets}):
        f = fe[i]
        vivos = [o for o in vivos if (f - o["salida"]).days <= HUECO_DIAS]
        for _, x, y, a, v, h in (d for d in dets if d[0] == i):
            cand = [o for o in vivos if o["i"] != i and np.hypot(o["x"] - x, o["y"] - y) < ENLACE_M]
            if cand:
                o = min(cand, key=lambda o: np.hypot(o["x"] - x, o["y"] - y))
                k = o["pasadas"]
                o.update(x=(o["x"] * k + x) / (k + 1), y=(o["y"] * k + y) / (k + 1), pasadas=k + 1, salida=f, i=i,
                         vv=max(o["vv"], v), vh=max(o["vh"], h), area=max(o["area"], a))
            else:
                o = dict(x=x, y=y, pasadas=1, llegada=f, salida=f, i=i, vv=v, vh=h, area=a)
                objetos.append(o)
                vivos.append(o)
    e = pd.DataFrame(objetos, columns=["x", "y", "pasadas", "llegada", "salida", "i", "vv", "vh", "area"]).drop(columns="i")
    e["posibles"] = [int(((fe >= a) & (fe <= b)).sum()) for a, b in zip(e.llegada, e.salida)]
    e["dias"] = (e.salida - e.llegada).dt.days
    b0 = np.nan_to_num(base, nan=-25)
    c = np.clip(np.floor((e.x - T[2]) / T[0]).astype(int), 0, base.shape[1] - 1)
    r = np.clip(np.floor((e.y - T[5]) / T[4]).astype(int), 0, base.shape[0] - 1)
    e["base"] = ndimage.maximum_filter(b0, size=5)[r, c]
    # percentil 90 del brillo de siempre en ~600 m alrededor; se calcula en bloques de 50 m para que sea rápido
    h5, w5 = b0.shape[0] // 5 * 5, b0.shape[1] // 5 * 5
    chico = b0[:h5, :w5].reshape(h5 // 5, 5, w5 // 5, 5).max(axis=(1, 3))
    p90 = ndimage.percentile_filter(chico, 90, size=13)
    e["entorno"] = p90[np.clip(r // 5, 0, p90.shape[0] - 1), np.clip(c // 5, 0, p90.shape[1] - 1)]
    e["lon"], e["lat"] = rtransform(CRS_METRICO, "EPSG:4326", e.x.values, e.y.values)
    e["zona"] = zona
    e["ultima_pasada"] = fe.max()
    return e


def equipos(e: pd.DataFrame) -> pd.DataFrame:
    """La regla: visto en 3+ pasadas, despolariza (VH alto) y el lugar casi siempre es oscuro."""
    return e[(e.pasadas >= MIN_PASADAS) & (e.vh > VH_MIN) & (e.base < BASE_MAX)].reset_index(drop=True)


def _km(lon, lat, lon2, lat2):
    lon2, lat2 = np.asarray(lon2), np.asarray(lat2)
    return np.array([np.hypot((lon2 - x) * 87.5, (lat2 - y) * 111).min() if len(lon2) else np.inf for x, y in zip(lon, lat)])


def lugar(eq: pd.DataFrame, pozos: pd.DataFrame, obras: pd.DataFrame | None = None) -> pd.DataFrame:
    """Dónde cayó cada equipo: distancia al pozo del padrón más cercano, a la locación de Sentinel-2 más cercana y a Añelo.
    `sobre_locacion` es la condición para contarlo."""
    eq = eq.copy()
    eq["km_pozo"] = _km(eq.lon, eq.lat, pozos.lon, pozos.lat)
    eq["km_obra"] = _km(eq.lon, eq.lat, obras.lon, obras.lat) if obras is not None else np.inf
    eq["km_anelo"] = np.hypot((eq.lon - ANELO[0]) * 87.5, (eq.lat - ANELO[1]) * 111)
    eq["contraste"], eq["verde"] = contraste_optico(eq)
    eq["lugar"] = np.select([eq.km_pozo < KM_LOC, eq.km_obra < KM_OBRA, (eq.contraste >= CONTRASTE_MIN) & (eq.verde <= VERDE_MAX)],
                            ["pozo del padrón", "locación de Sentinel-2", "locación nueva (óptico)"], "ninguno")
    eq["sobre_locacion"] = (eq.km_anelo > KM_ANELO) & (eq.lugar != "ninguno")
    return eq


def contraste_optico(eq: pd.DataFrame, raw: Path = DATA_RAW) -> tuple[np.ndarray, np.ndarray]:
    """En la última escena Sentinel-2 de la ventana: cuánto más clara es la caja de 130 m (percentil 75) que su entorno de
    600 m (mediana), y la relación verde/rojo (las chacras dan más de 0,8)."""
    from rasterio.transform import Affine
    from rasterio.warp import transform as rtransform

    con, ver = np.full(len(eq), np.nan), np.full(len(eq), np.nan)
    for z, g in eq.groupby("zona"):
        fs = sorted((raw / z).glob("20*.npz"))
        if not fs:
            continue
        d = np.load(fs[-1])
        br = sum(d[b].astype(np.float32) for b in ("red", "green", "blue")) / 30000
        vr = d["green"].astype(np.float32) / np.maximum(d["red"].astype(np.float32), 1)
        x, y = rtransform("EPSG:4326", CRS_METRICO, g.lon.values, g.lat.values)
        c, r = ~Affine.from_gdal(*d["transform"]) * (np.array(x), np.array(y))
        for k, cc, rr in zip(g.index, c.astype(int), r.astype(int)):
            if 30 <= rr < br.shape[0] - 30 and 30 <= cc < br.shape[1] - 30:
                j = eq.index.get_loc(k)
                con[j] = np.percentile(br[rr - 6:rr + 7, cc - 6:cc + 7], 75) / np.median(br[rr - 30:rr + 31, cc - 30:cc + 31])
                ver[j] = vr[rr - 6:rr + 7, cc - 6:cc + 7].mean()
    return con, ver


def obras_s2(proc: Path = DATA_PROC) -> pd.DataFrame:
    """Las locaciones que vio el detector a ciegas de Sentinel-2 (con o sin pozo)."""
    d = pd.read_csv(proc / "detecciones.csv")
    return d[d.es_locacion][["lon", "lat"]]


def campanias(eq: pd.DataFrame) -> pd.DataFrame:
    """Junta los eventos del mismo lugar (a < 150 m) separados por menos de CAMPANIA_DIAS: una campaña por locación."""
    out = []
    for zona, g in eq.sort_values("llegada").groupby("zona"):
        abiertas = []
        for r in g.itertuples():
            c = next((c for c in abiertas if np.hypot(c["x"] - r.x, c["y"] - r.y) < KM_LOC * 1000 and (r.llegada - c["salida"]).days < CAMPANIA_DIAS), None)
            if c:
                c.update(salida=max(c["salida"], r.salida), pasadas=c["pasadas"] + r.pasadas, vv=max(c["vv"], r.vv), vh=max(c["vh"], r.vh), eventos=c["eventos"] + 1)
            else:
                c = dict(zona=zona, x=r.x, y=r.y, lon=r.lon, lat=r.lat, llegada=r.llegada, salida=r.salida, pasadas=r.pasadas, vv=r.vv, vh=r.vh,
                         eventos=1, ultima_pasada=r.ultima_pasada)
                abiertas.append(c)
                out.append(c)
    c = pd.DataFrame(out)
    if len(c):
        c["dias"] = (c.salida - c.llegada).dt.days
        c["activa"] = c.salida >= c.ultima_pasada - pd.Timedelta(days=HUECO_DIAS // 2)
        c = c[c.dias <= DIAS_MAX]
        # las ventanas se pisan en los bordes: el mismo equipo visto desde dos ventanas cuenta una vez
        c = c.sort_values(["pasadas", "dias"], ascending=False).reset_index(drop=True)
        fuera = set()
        for i in range(len(c)):
            if i in fuera:
                continue
            d = np.hypot((c.lon - c.lon[i]) * 87.5, (c.lat - c.lat[i]) * 111)
            mismo = (d < KM_LOC) & (c.llegada <= c.salida[i]) & (c.salida >= c.llegada[i]) & (c.index != i) & (c.zona != c.zona[i])
            fuera |= set(c.index[mismo])
        c = c.drop(index=list(fuera)).sort_values(["zona", "llegada"]).reset_index(drop=True)
    return c


def validar(eq: pd.DataFrame, L: pd.DataFrame, f0, f1, corte: str = "2026-03-01") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Contra el padrón. Recall: locaciones perforadas enteras dentro del período con un equipo encima mientras se
    perforaba. Qué hay debajo de cada equipo: perforación, terminación, locación vieja o nada del padrón (hasta `corte`,
    porque el padrón carga los pozos con ~6 meses de demora)."""
    dist = np.hypot(eq.x.values[:, None] - L.x.values[None], eq.y.values[:, None] - L.y.values[None]) / 1000
    rec = []
    P = L[(L.perf_ini >= f0 + pd.Timedelta(days=30)) & (L.perf_fin <= f1)]
    for l in P.itertuples():
        j = L.index.get_loc(l.Index)
        cerca = eq[(dist[:, j] < KM_LOC) & (eq.salida >= l.perf_ini) & (eq.llegada <= l.perf_fin)]
        rec.append(dict(zona=l.zona, loc=l.loc, pozos=l.pozos, dias=(l.perf_fin - l.perf_ini).days, visto=len(cerca) > 0,
                        llegada=(cerca.llegada.min() - l.perf_ini).days if len(cerca) else np.nan,
                        salida=(cerca.salida.max() - l.perf_fin).days if len(cerca) else np.nan))
    tipos = []
    m = pd.Timedelta(days=30)
    for k, ev in enumerate(eq.itertuples()):
        tipo = None
        if ev.salida <= pd.Timestamp(corte):
            tipo = "nada en el padrón"
            for jj in np.where(dist[k] < KM_LOC)[0]:
                l = L.iloc[jj]
                if pd.notna(l.perf_ini) and ev.llegada <= l.perf_fin + m and ev.salida >= l.perf_ini - m:
                    tipo = "perforación"
                    break
                if pd.notna(l.term_ini) and ev.llegada <= l.term_fin + m and ev.salida >= l.term_ini - m:
                    tipo = "terminación"
            if tipo == "nada en el padrón" and (dist[k] < KM_LOC).any():
                tipo = "locación vieja"
        tipos.append(tipo)
    return pd.DataFrame(rec), eq.assign(tipo=tipos)


def brillo_por_fase(zona: str, L: pd.DataFrame, raw: Path = DATA_RAW, radio: int = 6, margen: int = 15) -> pd.DataFrame:
    """El VV máximo sobre cada locación del padrón en cada pasada, con la fase en que estaba según el padrón:
    antes (más de 120 días antes de perforar), perforación, espera (entre perforación y terminación), terminación y
    producción (90 días después de terminar)."""
    yy, xx = np.mgrid[-radio:radio + 1, -radio:radio + 1]
    disco = (yy ** 2 + xx ** 2) <= radio ** 2
    T = np.load(raw / zona / "radar" / "transform.npy")
    cols = np.floor((L.x.values - T[2]) / T[0]).astype(int)
    fils = np.floor((L.y.values - T[5]) / T[4]).astype(int)
    filas = []
    for f in sorted((raw / zona / "radar").glob("20*.npz")):
        vv = np.load(f)["vv"]
        fecha = pd.Timestamp(f.stem)
        for k, (c, r) in enumerate(zip(cols, fils)):
            if radio <= r < vv.shape[0] - radio and radio <= c < vv.shape[1] - radio:
                a = vv[r - radio:r + radio + 1, c - radio:c + radio + 1][disco]
                if (a > 0).all():
                    filas.append((k, fecha, a.max() / 5 - 25))
    s = pd.DataFrame(filas, columns=["k", "fecha", "vv_max"])
    s = s.join(L[["loc", "perf_ini", "perf_fin", "term_ini", "term_fin"]].reset_index(drop=True), on="k")
    m = pd.Timedelta(days=margen)
    fase = np.full(len(s), None, dtype=object)
    fase[s.fecha < s.perf_ini - pd.Timedelta(days=120)] = "antes"
    fase[(s.fecha >= s.perf_ini + m) & (s.fecha <= s.perf_fin - m)] = "perforación"
    fase[(s.fecha > s.perf_fin + m) & (s.fecha < s.term_ini - m)] = "espera"
    fase[(s.fecha >= s.term_ini + m) & (s.fecha <= s.term_fin - m)] = "terminación"
    fase[s.fecha > s.term_fin + pd.Timedelta(days=90)] = "producción"
    return s.assign(fase=fase, zona=zona).dropna(subset=["fase"])


def conteo_mensual(c: pd.DataFrame, L: pd.DataFrame, desde: str, hasta: str) -> pd.DataFrame:
    """Por mes: campañas del radar con el equipo presente algún día del mes, y locaciones del padrón que se estaban
    perforando algún día del mes."""
    meses = pd.period_range(desde, hasta, freq="M")
    out = []
    for p in meses:
        a, b = p.start_time, p.end_time
        out.append((p.strftime("%Y-%m"), int(((c.llegada <= b) & (c.salida >= a)).sum()), int(((L.perf_ini <= b) & (L.perf_fin >= a)).sum())))
    return pd.DataFrame(out, columns=["mes", "radar", "padron"])
