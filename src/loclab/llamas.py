"""El clasificador: separar una llama de un techo que refleja, sin regla escrita a mano.

La regla de `antorchas.py` (tres meses fuera del invierno, que sature, lejos de Añelo) deja pasar galpones y pierde las
quemas cortas. Acá se describe cada foco con dieciocho rasgos sacados de las 82 escenas mensuales y se entrena un
bosque aleatorio con verdad que no depende de quien mira:

  llama  un foco a menos de 150 m de un punto de venteo declarado ante la Secretaría de Energía
  techo  un foco dentro del casco de Añelo y lejos de cualquier punto declarado

La revisión a mano (`data/antorchas_revision.csv`) no se usa para entrenar: queda como prueba.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import ANELO, DATA_RAW
from . import antorchas as A

MESES_MIN = 2            # se describe todo foco visto en dos escenas mensuales o más
MEDIA_VENTANA = 7        # recorte de 15 x 15 píxeles de 20 m (300 m) alrededor del foco
KM_LLAMA = 0.15          # etiqueta "llama": a menos de 150 m de un punto declarado
KM_TECHO_ANELO = 2.0     # etiqueta "techo": a menos de 2 km del centro de Añelo...
KM_TECHO_LEJOS = 0.3     # ...y a más de 300 m de cualquier punto declarado
P_LLAMA = 0.7            # desde esta probabilidad no pasó ningún techo de Añelo en la validación cruzada
VEREDICTOS_TECHO = ("galpon", "zona urbana", "base de servicios", "techos de planta")
# la ventana que el modelo no vio: una ciudad petrolera con chimeneas declaradas alrededor (scripts/zona_nueva.py)
ZONA_PRUEBA = {"bbox": (-69.33, -39.00, -69.12, -38.87), "tile": "MGRS-19HDS", "nombre": "Cutral Có y Plaza Huincul"}
CENTROS_PRUEBA = ((-69.230, -38.940), (-69.200, -38.930))      # las plazas de Cutral Có y de Plaza Huincul

RASGOS = ["frac_invierno", "frac_meses", "b12_mediana", "b12_max", "exceso_mediana", "cociente_b12_b11", "pix_mediana", "pix_max",
          "deriva_m", "apagado_b12", "apagado_rel", "variacion_b12", "salto", "alargada", "tai_max", "visible_claro",
          "visible_oscuro", "visible_textura"]


def alargada(mascara: np.ndarray) -> float:
    """Cuán estirada es una mancha: 1 si es redonda (una llama), más si es una tira (el techo de un galpón)."""
    yy, xx = np.nonzero(mascara)
    if len(yy) < 3:
        return 1.0
    ev = np.sort(np.linalg.eigvalsh(np.cov(np.vstack([yy, xx])) + np.eye(2) * 0.08))
    return float(np.sqrt(ev[1] / ev[0]))


def rasgos(focos: pd.DataFrame, det: pd.DataFrame, raw: Path = DATA_RAW, aviso=None) -> pd.DataFrame:
    """Una fila por foco con cómo se comporta el lugar en todas las escenas mensuales.

    Cuándo aparece (invierno o todo el año), cuánto brilla y de qué tamaño es la mancha, cuánto se mueve de un mes a
    otro, cómo se ve el lugar cuando no hay píxel caliente y cómo se ve en la foto común. Los focos pegados al borde
    de su ventana quedan sin recorte (`borde`) y sin rasgos de imagen.
    """
    focos = focos[focos.meses >= MESES_MIN]
    R, filas = MEDIA_VENTANA, []
    for zona, g in focos.groupby("zona"):
        meses = sorted(p.stem for p in (raw / zona / "swir").glob("20*.npz"))
        n, lado = len(g), 2 * R + 1
        b12 = np.full((n, len(meses), lado, lado), np.nan, np.float32)
        b11, b8a = b12.copy(), b12.copy()
        lum = np.full((n, len(meses), 2 * lado, 2 * lado), np.nan, np.float32)      # la misma ventana en color real, a 10 m
        pos = None
        for j, mes in enumerate(meses):
            m = A.cargar_mes(zona, mes, raw)
            e = np.load(raw / zona / f"{mes}.npz")
            v = (0.30 * e["red"].astype(np.float32) + 0.59 * e["green"] + 0.11 * e["blue"]) / 10000
            if pos is None:
                c, f = ~m["transform"] * (g.x.values, g.y.values)
                pos = np.round(f).astype(int), np.round(c).astype(int)
            h, w = m["b12"].shape
            for k in range(n):
                f0, c0 = pos[0][k], pos[1][k]
                if f0 - R < 0 or c0 - R < 0 or f0 + R + 1 > h or c0 + R + 1 > w:
                    continue
                sl = (slice(f0 - R, f0 + R + 1), slice(c0 - R, c0 + R + 1))
                b12[k, j], b11[k, j], b8a[k, j] = m["b12"][sl], m["b11"][sl], m["b8a"][sl]
                lum[k, j] = v[2 * (f0 - R):2 * (f0 + R + 1), 2 * (c0 - R):2 * (c0 + R + 1)]
        invierno = np.isin([int(x[5:]) for x in meses], A.INVIERNO)
        for k, a in enumerate(g.itertuples()):
            d = det[(det.zona == zona) & (det.foco == a.foco)]
            visto = np.isin(meses, d.mes.values)
            fila = {"zona": zona, "foco": a.foco, "lon": a.lon, "lat": a.lat, "x": a.x, "y": a.y, "meses": a.meses,
                    "borde": bool(np.isnan(b12[k]).all()),
                    "frac_invierno": float(invierno[visto].mean()), "frac_meses": float(visto.mean()),
                    "b12_mediana": float(d.b12.median()), "b12_max": float(d.b12.max()),
                    "exceso_mediana": float((d.b12 - d.b11).median()),
                    "cociente_b12_b11": float((d.b12 / d.b11.clip(lower=0.01)).median()),
                    "pix_mediana": float(d.pix.median()), "pix_max": float(d.pix.max()),
                    "deriva_m": float(np.hypot(d.fila - d.fila.mean(), d.col - d.col.mean()).mean() * 20)}
            if not fila["borde"]:
                centro = b12[k][:, R - 1:R + 2, R - 1:R + 2].max(axis=(1, 2))       # el píxel más brillante del lugar, mes a mes
                marco = np.concatenate([b12[k][:, :2].reshape(len(meses), -1), b12[k][:, -2:].reshape(len(meses), -1)], axis=1)
                anillo = np.nanmedian(marco, axis=1)
                apag = ~visto
                if apag.any():
                    fila["apagado_b12"] = float(np.median(centro[apag]))
                    fila["apagado_rel"] = float(np.median(centro[apag] / np.maximum(anillo[apag], 0.01)))
                    fila["salto"] = float(np.median(centro[visto]) / max(np.median(centro[apag]), 0.01))
                fila["variacion_b12"] = float(np.std(centro) / max(np.median(centro), 0.01))
                jm = meses.index(d.sort_values("pix").mes.iloc[-1])                 # el mes de mancha más grande
                fila["alargada"] = alargada(A.calientes(b12[k, jm], b11[k, jm], b8a[k, jm]))
                tai = (b12[k, jm] - b11[k, jm]) / np.maximum(b8a[k, jm], 0.01)
                fila["tai_max"] = float(np.nanmax(tai[R - 2:R + 3, R - 2:R + 3]))
                lc = lum[k][:, 2 * R - 3:2 * R + 5, 2 * R - 3:2 * R + 5]
                fondo = np.maximum(np.nanmedian(lum[k].reshape(len(meses), -1), axis=1), 0.01)
                fila["visible_claro"] = float(np.median(lc.max(axis=(1, 2)) / fondo))
                fila["visible_oscuro"] = float(np.median(lc.min(axis=(1, 2)) / fondo))
                fila["visible_textura"] = float(np.median(lc.reshape(len(meses), -1).std(axis=1) / fondo))
            filas.append(fila)
        if aviso:
            aviso(f"{zona}: {n} focos")
    return pd.DataFrame(filas).reindex(columns=["zona", "foco", "lon", "lat", "x", "y", "meses", "borde"] + RASGOS)


def etiquetar(t: pd.DataFrame, declarados: pd.DataFrame, revision: pd.DataFrame, firmes: pd.DataFrame) -> pd.DataFrame:
    """Agrega las distancias, la revisión a mano, cuáles son antorchas firmes y la `etiqueta` de entrenamiento.

    `etiqueta` vale 1 (llama), 0 (techo) o queda vacía. Lo revisado a mano nunca lleva etiqueta: es la prueba.
    """
    t = t.copy()
    t["km_declarado"] = A.km_al_mas_cercano(t.lon, t.lat, declarados.lon, declarados.lat)
    t["km_anelo"] = np.hypot((t.lon - ANELO[0]) * 87.5, (t.lat - ANELO[1]) * 111)
    t["revision"] = ""
    for r in revision.itertuples():
        d = np.hypot((t.lon - r.lon) * 87.5, (t.lat - r.lat) * 111)
        t.loc[d <= 0.1, "revision"] = r.veredicto          # el mismo lugar puede estar en dos ventanas vecinas
    clave = set(zip(firmes.zona, firmes.foco))
    t["firme"] = [(z, f) in clave for z, f in zip(t.zona, t.foco)]
    t["etiqueta"] = np.nan
    libre = (t.revision == "") & ~t.borde
    t.loc[libre & (t.km_declarado <= KM_LLAMA), "etiqueta"] = 1.0
    t.loc[libre & (t.km_anelo < KM_TECHO_ANELO) & (t.km_declarado > KM_TECHO_LEJOS), "etiqueta"] = 0.0
    t["celda"] = (t.x // 1000).astype(int).astype(str) + "_" + (t.y // 1000).astype(int).astype(str)
    return t


def _bosque(semilla: int, arboles: int = 300):
    from sklearn.ensemble import RandomForestClassifier
    return RandomForestClassifier(n_estimators=arboles, min_samples_leaf=2, class_weight="balanced", random_state=semilla, n_jobs=-1)


def _matriz(t: pd.DataFrame, medianas: pd.Series) -> pd.DataFrame:
    return t[RASGOS].fillna(medianas)


def clasificar(t: pd.DataFrame, repeticiones: int = 10) -> tuple[pd.DataFrame, pd.Series]:
    """Probabilidad de llama para cada foco, y cuánto pesa cada rasgo.

    Los focos con etiqueta reciben la probabilidad de la validación cruzada (nunca la de un modelo que los vio): cinco
    partes armadas por celdas de 1 km, para que el mismo lugar no caiga a la vez en entrenamiento y prueba, repetido
    varias veces. El resto recibe la del modelo entrenado con todas las etiquetas.
    """
    from sklearn.model_selection import StratifiedGroupKFold
    t = t.copy()
    e = t[t.etiqueta.notna()]
    med = e[RASGOS].median()
    X, y = _matriz(e, med), e.etiqueta.astype(int)
    fuera = np.zeros(len(e))
    for s in range(repeticiones):
        for tr, te in StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=s).split(X, y, e.celda):
            fuera[te] += _bosque(s).fit(X.iloc[tr], y.iloc[tr]).predict_proba(X.iloc[te])[:, 1] / repeticiones
    final, _ = entrenar(t)
    con = ~t.borde
    t["p"] = np.nan
    t.loc[con, "p"] = final.predict_proba(_matriz(t[con], med))[:, 1]
    t.loc[e.index, "p"] = fuera
    return t, pd.Series(final.feature_importances_, RASGOS).sort_values(ascending=False)


def entrenar(t: pd.DataFrame):
    """El modelo entrenado con todos los focos etiquetados de `t`, y las medianas con que se rellenan los rasgos que falten."""
    e = t[t.etiqueta.notna()]
    med = e[RASGOS].median()
    return _bosque(0, 600).fit(_matriz(e, med), e.etiqueta.astype(int)), med


def regla_sin_lugar(t: pd.DataFrame, focos: pd.DataFrame) -> pd.Series:
    """La regla de `antorchas.es_antorcha` sin el filtro de distancia a Añelo, para compararla en igualdad con el modelo."""
    fi = t.merge(focos[["zona", "foco", "fuera_invierno"]], on=["zona", "foco"], how="left").fuera_invierno.values
    return (t.meses >= A.MESES_MIN) & (fi >= A.FUERA_INVIERNO_MIN) & (t.b12_max >= A.B12_SATURA)


def temporales(t: pd.DataFrame, p_min: float = P_LLAMA) -> pd.DataFrame:
    """Las llamas cortas que la regla descarta: el modelo las ve como llama, no son antorchas firmes ni están en Añelo.

    Dos focos de ventanas vecinas a menos de 200 m son la misma; se queda la de mayor probabilidad.
    """
    fir = t[t.firme]
    lejos = np.array([np.hypot((fir.lon - r.lon) * 87.5, (fir.lat - r.lat) * 111).min() > A.KM_MISMA for r in t.itertuples()])
    c = t[~t.firme & (t.revision == "") & (t.p >= p_min) & lejos & (t.km_anelo > A.KM_ANELO_MIN)].sort_values("p", ascending=False)
    quedan = []
    for i, r in c.iterrows():
        if all(np.hypot((r.lon - c.loc[j, "lon"]) * 87.5, (r.lat - c.loc[j, "lat"]) * 111) > A.KM_MISMA for j in quedan):
            quedan.append(i)
    return c.loc[quedan].reset_index(drop=True)
