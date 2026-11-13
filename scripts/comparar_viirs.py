"""Las antorchas contra un registro independiente: VIIRS Nightfire, el satélite nocturno con que se mide la quema de gas del mundo.

El registro (Zhizhin, Ghosh, Gleason, Elvidge y Bazilian, 2026, DOI 10.5281/zenodo.23091822, licencia CC BY-NC 4.0) trae
una fila por sitio de quema y por año, de 2012 a 2025, con las noches despejadas, las detecciones y el volumen quemado.
No se redistribuye: el script lo baja a `data/raw/viirs/`.

    python scripts/comparar_viirs.py
Deja `data/processed/antorchas_viirs.csv` (una fila por antorcha con su sitio VIIRS más cercano) y
`data/processed/viirs_ventanas.csv` (los sitios VIIRS de las quince ventanas, con la antorcha o el foco más cercano).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from loclab import DATA_PROC, DATA_RAW, FIGURES, ZONAS, figuras  # noqa: E402

URL = "https://zenodo.org/records/23091822/files/{}?download=1"
KM = 0.5                # un sitio VIIRS y una antorcha a menos de 500 m son el mismo lugar (el píxel de VIIRS mide 750 m)
DESDE = 2020            # la serie de Sentinel-2 arranca en 2020


def bajar(nombre: str) -> Path:
    destino = DATA_RAW / "viirs" / nombre
    if not destino.exists():
        destino.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(URL.format(nombre), timeout=600)
        r.raise_for_status()
        destino.write_bytes(r.content)
    return destino


def km_al_mas_cercano(lon, lat, lon2, lat2):
    d = [np.hypot((lon2 - x) * 87.5, (lat2 - y) * 111) for x, y in zip(lon, lat)]
    return np.array([v.min() for v in d]), np.array([int(v.argmin()) for v in d])


if __name__ == "__main__":
    v = pd.read_csv(bajar("annual_flare_site_records.csv"))
    pais = pd.read_csv(bajar("annual_country.csv"))
    arg = v[v.country_iso == "ARG"]
    s = arg.groupby("flare_id").agg(lat=("lat", "first"), lon=("lon", "first"), clase=("upstream_class", "first")).reset_index()
    dentro = np.zeros(len(s), bool)
    for z in ZONAS.values():
        x0, y0, x1, y1 = z["bbox"]
        dentro |= s.lon.between(x0, x1).values & s.lat.between(y0, y1).values
    s = s[dentro].reset_index(drop=True)
    rec = arg[arg.flare_id.isin(s.flare_id) & (arg.year >= DESDE)]
    act = rec.groupby("flare_id").agg(anios_activos=("n_det", lambda x: int((x > 0).sum())), detecciones=("n_det", "sum"), despejadas=("n_clear", "sum"), bcm=("bcm", "sum"))
    s = s.merge(act, on="flare_id")
    activos = s[s.anios_activos > 0].reset_index(drop=True)

    ant = pd.read_csv(DATA_PROC / "antorchas.csv")
    ant = ant[ant.firme].reset_index(drop=True)
    ant["km_viirs"], i = km_al_mas_cercano(ant.lon, ant.lat, s.lon.values, s.lat.values)
    ant["flare_id"] = s.flare_id.values[i]
    ant = ant.merge(s[["flare_id", "clase", "detecciones", "despejadas", "bcm"]], on="flare_id", how="left")
    ant.loc[ant.km_viirs > KM, ["flare_id", "clase", "detecciones", "despejadas", "bcm"]] = np.nan
    pas = DATA_PROC / "antorchas_pasadas.csv"
    if pas.exists():
        ant = ant.merge(pd.read_csv(pas)[["zona", "foco", "vistas", "encendida", "pct"]], on=["zona", "foco"], how="left")
        r25 = arg[arg.year == 2025].set_index("flare_id")
        ant["viirs_2025_pct"] = [r25.n_det.get(f, np.nan) / max(r25.n_clear.get(f, np.nan), 1) * 100 if isinstance(f, str) else np.nan for f in ant.flare_id]
    ant.to_csv(DATA_PROC / "antorchas_viirs.csv", index=False)

    activos["km_antorcha"], _ = km_al_mas_cercano(activos.lon, activos.lat, ant.lon.values, ant.lat.values)
    tmp_p = DATA_PROC / "antorchas_temporales.csv"
    tmp = pd.read_csv(tmp_p) if tmp_p.exists() else pd.DataFrame({"lon": [], "lat": []})
    if len(tmp):
        activos["km_temporal"], _ = km_al_mas_cercano(activos.lon, activos.lat, tmp.lon.values, tmp.lat.values)
        tmp["km_viirs"], _ = km_al_mas_cercano(tmp.lon, tmp.lat, s.lon.values, s.lat.values)
    cl_p = DATA_PROC / "antorchas_clasificadas.csv"
    if cl_p.exists():
        cl = pd.read_csv(cl_p)
        d, j = km_al_mas_cercano(activos.lon, activos.lat, cl.lon.values, cl.lat.values)
        activos["km_foco"], activos["foco_meses"], activos["foco_p"] = d, cl.meses.values[j], cl.p.values[j]
    activos.to_csv(DATA_PROC / "viirs_ventanas.csv", index=False)

    con = ant[ant.km_viirs <= KM]
    print(f"sitios VIIRS de Argentina: {arg.flare_id.nunique()} · dentro de las quince ventanas: {len(s)} · con alguna detección desde {DESDE}: {len(activos)}")
    print(f"antorchas firmes con un sitio VIIRS a menos de {int(KM * 1000)} m: {len(con)} de {len(ant)} · distancia mediana {con.km_viirs.median() * 1000:.0f} m")
    if len(tmp):
        print(f"quemas temporales con un sitio VIIRS a menos de {int(KM * 1000)} m: {int((tmp.km_viirs <= KM).sum())} de {len(tmp)}")
    sin = activos[(activos.km_antorcha > KM) & (activos.get("km_temporal", 9) > KM)]
    print(f"sitios VIIRS activos con una antorcha o una quema temporal nuestra a menos de {int(KM * 1000)} m: {len(activos) - len(sin)} de {len(activos)}")
    if "km_foco" in sin:
        cerca = sin[sin.km_foco <= KM]
        print(f"  de los {len(sin)} que faltan: {len(cerca)} tienen un foco nuestro que no pasó la regla ni el umbral · {len(sin) - len(cerca)} no tienen ningún foco de dos meses o más")
        print(f"  volumen 2020-2025 de los que faltan: {sin.bcm.sum():.3f} de {activos.bcm.sum():.3f} mil millones de m3 ({sin.bcm.sum() / activos.bcm.sum() * 100:.0f} %)")
    faltan = ant[ant.km_viirs > KM]
    print(f"antorchas nuestras sin sitio VIIRS: {len(faltan)} · mediana de {int(faltan.meses.median())} escenas con llama (las que sí tienen: {int(con.meses.median())})")
    por_anio = rec.groupby("year").bcm.sum()
    pa = pais[pais.country_iso == "ARG"].set_index("year").bcm
    print("volumen quemado según VIIRS, mil millones de m3 por año:")
    print("  ", " · ".join(f"{a}: ventanas {por_anio[a]:.2f}, país {pa[a]:.2f}" for a in range(DESDE, 2026)))
    det = pd.read_csv(DATA_PROC / "antorchas_detecciones.csv").merge(ant[["zona", "foco"]], on=["zona", "foco"])
    vistas = det.assign(anio=det.mes.str[:4].astype(int)).groupby("anio").apply(lambda g: g[["zona", "foco"]].drop_duplicates().shape[0])
    tabla = pd.DataFrame({"anio": range(DESDE, 2026)})
    tabla["antorchas"], tabla["bcm"] = tabla.anio.map(vistas).values, tabla.anio.map(por_anio).values
    figuras.antorchas_contra_viirs(tabla, FIGURES / "antorchas_viirs.png")
    print("  antorchas vistas encendidas:", " · ".join(f"{r.anio}: {int(r.antorchas)}" for r in tabla.itertuples()))
    if "pct" in ant:
        c = ant.dropna(subset=["pct", "viirs_2025_pct"])
        print(f"fracción del tiempo con llama, de día (Sentinel-2, 2025-2026) contra de noche (VIIRS, 2025): correlación {np.corrcoef(c.pct, c.viirs_2025_pct)[0, 1]:.2f} en {len(c)} antorchas")
