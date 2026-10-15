"""La serie mensual de Sentinel-2: una escena limpia por mes sobre cada ventana, recortada y guardada.

El catálogo es el STAC público de Element84 (Sentinel-2 L2A en AWS, sin cuenta). Las nubes que informa
el STAC son las del tile entero (110 x 110 km): una escena con 60 % de nubes puede estar limpia sobre la
ventana. Por eso se lee la banda de clasificación de escena (SCL, 20 m) sobre la ventana y se acepta la
escena si menos del 3 % de los píxeles son nube, sombra, cirro, nieve o sin dato.

Las bandas RGB a 10 m se guardan como `data/raw/<zona>/AAAA-MM.npz` con la transformación de la
banda de 10 m. (Guardar la transformación de una banda de 20 m con píxeles de 10 m corre todo el
mapa al doble: se ve como que no hay señal. Pasó.)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import requests

from . import DATA_RAW, ZONAS

STAC = "https://earth-search.aws.element84.com/v1/search"
SCL_MALAS = (0, 3, 8, 9, 10, 11)   # sin dato, sombra de nube, nube media, nube alta, cirro, nieve
ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", AWS_NO_SIGN_REQUEST="YES", GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="5")


def buscar(zona: str, desde: str, hasta: str, nubes_tile_max: float = 60.0) -> list[dict]:
    """Escenas Sentinel-2 L2A del tile de la zona entre dos fechas (aaaa-mm-dd)."""
    z = ZONAS[zona]
    body = {"collections": ["sentinel-2-l2a"], "bbox": list(z["bbox"]), "datetime": f"{desde}T00:00:00Z/{hasta}T23:59:59Z", "limit": 200,
            "query": {"eo:cloud_cover": {"lt": nubes_tile_max}}}
    items, url = [], STAC
    while True:
        r = requests.post(url, json=body, timeout=180)
        r.raise_for_status()
        d = r.json()
        items += [f for f in d.get("features", []) if f["properties"].get("grid:code") == z["tile"]]
        nxt = next((l_ for l_ in d.get("links", []) if l_.get("rel") == "next"), None)
        if not nxt:
            break
        url, body = nxt.get("href", url), nxt.get("body", body)
    return items


def leer(href: str, bbox: tuple) -> tuple[np.ndarray, object, str]:
    """Recorte de una banda (COG remoto) sobre un bbox lon/lat: arreglo, transformación y CRS."""
    import rasterio
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds

    with rasterio.Env(**ENV):
        with rasterio.open(href) as src:
            izq, abajo, der, arriba = transform_bounds("EPSG:4326", src.crs, *bbox)
            w = from_bounds(izq, abajo, der, arriba, transform=src.transform)
            return src.read(1, window=w, boundless=True, fill_value=0), src.window_transform(w), str(src.crs)


def fraccion_mala(scl: np.ndarray) -> float:
    """Fracción de píxeles inservibles en la banda SCL."""
    return float(np.isin(scl, SCL_MALAS).mean())


def bajar_mes(zona: str, items: list[dict], destino: Path, max_malas: float = 0.03, probar: int = 6) -> dict | None:
    """Prueba las escenas del mes de menos a más nubes y guarda la primera limpia sobre la ventana."""
    bbox = ZONAS[zona]["bbox"]
    for f in sorted(items, key=lambda f: f["properties"].get("eo:cloud_cover", 100))[:probar]:
        try:
            scl, _, _ = leer(f["assets"]["scl"]["href"], bbox)
        except Exception:  # noqa: BLE001 - el servidor corta a veces: probar la siguiente
            continue
        malas = fraccion_mala(scl)
        if malas >= max_malas:
            continue
        r, tr, crs = leer(f["assets"]["red"]["href"], bbox)
        g, _, _ = leer(f["assets"]["green"]["href"], bbox)
        b, _, _ = leer(f["assets"]["blue"]["href"], bbox)
        destino.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(destino, fecha=f["properties"]["datetime"][:10], escena=f["id"], red=r, green=g, blue=b, transform=np.array(tr.to_gdal()), crs=crs)
        return {"fecha": f["properties"]["datetime"][:10], "escena": f["id"], "malas": malas}
    return None


def bajar_serie(zona: str, desde_anio: int = 2020, hasta_anio: int = 2026, raw: Path = DATA_RAW) -> list[str]:
    """Una escena limpia por mes. Reanudable: lo que ya está en disco no se vuelve a pedir."""
    hechos = []
    for anio in range(desde_anio, hasta_anio + 1):
        por_mes: dict[str, list] = {}
        for f in buscar(zona, f"{anio}-01-01", f"{anio}-12-31"):
            por_mes.setdefault(f["properties"]["datetime"][:7], []).append(f)
        for mes, fs in sorted(por_mes.items()):
            destino = raw / zona / f"{mes}.npz"
            if destino.exists():
                hechos.append(mes)
                continue
            info = bajar_mes(zona, fs, destino)
            print(zona, mes, info["fecha"] if info else "sin escena limpia", flush=True)
            if info:
                hechos.append(mes)
    return hechos


def cargar_serie(zona: str, raw: Path = DATA_RAW, factor: int = 1) -> dict:
    """La serie de brillo (media de RGB en reflectancia) de una zona, opcionalmente agregada en bloques de factor x factor."""
    from rasterio.transform import Affine

    archivos = sorted((raw / zona).glob("20*.npz"))
    if not archivos:
        raise FileNotFoundError(f"no hay escenas de {zona} en {raw / zona}: correr scripts/download_series.py")
    e0 = np.load(archivos[0])
    h0, w0 = e0["red"].shape
    h, w = h0 // factor, w0 // factor
    serie = []
    for p in archivos:
        e = np.load(p)
        br = sum(e[k][:h0, :w0].astype(np.float32) for k in ("red", "green", "blue")) / 30000.0
        if factor > 1:
            br = br[:h * factor, :w * factor].reshape(h, factor, w, factor).mean(axis=(1, 3))
        serie.append(br)
    return {"meses": [p.stem for p in archivos], "brillo": np.stack(serie), "transform": Affine.from_gdal(*e0["transform"]) * Affine.scale(factor),
            "crs": str(e0["crs"]), "archivos": archivos}


def rgb(archivo: Path, ganancia: float = 3.0) -> np.ndarray:
    """La escena en color para mostrar."""
    e = np.load(archivo)
    return np.clip(np.dstack([e[k].astype(float) / 10000 for k in ("red", "green", "blue")]) * ganancia, 0, 1)
