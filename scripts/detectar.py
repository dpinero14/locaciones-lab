"""Corre el detector a ciegas sobre todas las zonas con serie bajada y deja `data/processed/detecciones.csv`:
cada obra con su mes, área, si es locación, su estado contra el padrón (sin pozo / llegó después / ya perforado)
y la espera hasta la perforación. Es lo que usa el notebook 02 y la maqueta del mapa.

    python scripts/detectar.py            # todas las zonas con escenas
    python scripts/detectar.py norte_este # una zona
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from loclab import ANELO, CRS_METRICO, DATA_PROC, DATA_RAW, ZONAS, ciego, escenas, padron  # noqa: E402


def detectar_zona(zona: str) -> pd.DataFrame:
    from rasterio.warp import transform as rtransform

    S = escenas.cargar_serie(zona, factor=2)
    verde = np.zeros(S["brillo"].shape[1:], bool)
    h2, w2 = verde.shape
    for p in S["archivos"]:
        e = np.load(p)
        g, r = (e[k][:2 * h2, :2 * w2].astype(np.float32).reshape(h2, 2, w2, 2).mean(axis=(1, 3)) for k in ("green", "red"))
        verde |= g > r * 1.02
    d = ciego.detectar(S["brillo"], verde)
    if d.empty:
        return d
    x, y = S["transform"] * (d.col.values + 0.5, d.fila.values + 0.5)
    d["lon"], d["lat"] = rtransform(S["crs"], "EPSG:4326", x, y)
    d["mes"] = pd.to_datetime([S["meses"][t] + "-15" for t in d.t])
    d["zona"] = zona
    d["km_anelo"] = np.hypot((d.lon - ANELO[0]) * 87.3, (d.lat - ANELO[1]) * 111)
    d["es_locacion"] = ciego.es_locacion(d, d.km_anelo)
    return d


def main() -> None:
    from pyproj import Transformer

    zonas = sys.argv[1:] or [z for z in ZONAS if any((DATA_RAW / z).glob("20*.npz"))]
    partes = []
    for z in zonas:
        n = len(list((DATA_RAW / z).glob("20*.npz")))
        if n < 30:
            print(f"{z}: solo {n} escenas, se salta")
            continue
        d = detectar_zona(z)
        print(f"{z}: {n} escenas · {len(d)} detecciones · {int(d.es_locacion.sum()) if len(d) else 0} locaciones", flush=True)
        partes.append(d)
    D = pd.concat(partes, ignore_index=True)
    P = padron.pozos()
    tf = Transformer.from_crs("EPSG:4326", CRS_METRICO, always_xy=True)
    px, py = tf.transform(P.lon.values, P.lat.values)
    dx, dy = tf.transform(D.lon.values, D.lat.values)
    est = [ciego.estado_al_verla(x, y, m, px, py, P.perforacion.values) for x, y, m in zip(dx, dy, D.mes)]
    D["estado"], D["espera_meses"] = [e[0] for e in est], [round(e[1], 1) if e[1] == e[1] else np.nan for e in est]
    dist = np.array([np.min(np.hypot(px - x, py - y)) for x, y in zip(dx, dy)])
    D["pozo_a_m"] = dist.round(0)
    idx = [int(np.argmin(np.hypot(px - x, py - y))) for x, y in zip(dx, dy)]
    D["perforacion_cercana"] = pd.to_datetime(P.perforacion.values[idx])
    D.loc[D.estado == "sin_pozo", "perforacion_cercana"] = pd.NaT
    DATA_PROC.mkdir(parents=True, exist_ok=True)
    D.to_csv(DATA_PROC / "detecciones.csv", index=False)
    L = D[D.es_locacion]
    print(f"\ntotal: {len(D)} detecciones, {len(L)} locaciones · {D.zona.nunique()} zonas")
    print("estado de las locaciones:", L.estado.value_counts().to_dict())
    print("guardado en", DATA_PROC / "detecciones.csv")


if __name__ == "__main__":
    main()
