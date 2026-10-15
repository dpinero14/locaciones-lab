"""El detector a ciegas: busca en la serie mensual cada parche de meseta que se aclara de golpe y queda claro. No mira el padrón.

1. Brillo a 20 m (bloques de 2 x 2), dividido por la mediana de la escena y restado el promedio del
   vecindario de 1 km. Sin ese contraste local el monte que cambia de tono con la estación y la sequía
   da cientos de falsos positivos (con el brillo crudo: 727 detecciones y 5 % de acierto en una zona).
2. Por píxel, el escalón más grande: media de los 4 meses siguientes menos media de los 12 anteriores.
3. Candidato: escalón > umbral, sin verde en ninguna fecha (valle, chacras) y oscuro antes del escalón.
4. Parches conexos de 0,4 a 8 ha, compactos, con el mismo mes de escalón (± 2) en la mayoría del parche.
5. Clasificación: locación si el parche tiene al menos 1 ha, un escalón de al menos 0,55 y está a más
   de 3 km del centro de Añelo. Ajustada con 48 detecciones etiquetadas a mano (recall 81 %,
   precisión 94 % dejando una afuera). La forma (relleno, elongación) no separa: un cruce de caminos es
   tan compacto como una locación.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import ndimage

ANTES, DESPUES = 12, 4
REGLA = {"area_min_ha": 1.0, "escalon_min": 0.55, "km_anelo_min": 3.0}


def contraste_local(brillo: np.ndarray, vecindario: int = 51) -> np.ndarray:
    """Cada mes, el brillo relativo a la mediana de la escena menos el promedio de su vecindario."""
    out = np.empty_like(brillo)
    for t, b in enumerate(brillo):
        b = b / np.median(b)
        out[t] = b - ndimage.uniform_filter(b, size=vecindario)
    return out


def escalones(c: np.ndarray, antes: int = ANTES, despues: int = DESPUES) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Para cada píxel: tamaño del mayor escalón, mes del escalón y nivel antes del escalón."""
    T, h, w = c.shape
    cs = np.concatenate([np.zeros((1, h, w), np.float32), np.cumsum(c, axis=0, dtype=np.float32)])
    mejor, mes, base = np.full((h, w), -9.0, np.float32), np.zeros((h, w), int), np.zeros((h, w), np.float32)
    for t in range(antes, T - despues + 1):
        a = (cs[t] - cs[t - antes]) / antes
        d = (cs[t + despues] - cs[t]) / despues - a
        m = d > mejor
        mejor[m], mes[m], base[m] = d[m], t, a[m]
    return mejor, mes, base


def detectar(brillo: np.ndarray, verde: np.ndarray, umbral: float = 0.35, ha_por_pixel: float = 0.04) -> pd.DataFrame:
    """Parches de construcción nueva: fila, columna (en la grilla de brillo), área, mes del escalón y forma."""
    c = contraste_local(brillo)
    mejor, mes, base = escalones(c)
    monte = np.median(base[~verde])
    cand = ndimage.binary_opening((mejor > umbral) & (~verde) & (base < monte + 0.10))
    lab, _ = ndimage.label(cand)
    T = len(brillo)
    dets = []
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        m = lab[sl] == i
        area = m.sum() * ha_por_pixel
        relleno = m.sum() / m.size
        if not (0.4 <= area <= 8) or relleno < 0.45:
            continue
        t_med = int(np.median(mes[sl][m]))
        if np.mean(np.abs(mes[sl][m] - t_med) <= 2) < 0.6:
            continue
        rr, cc = np.nonzero(m)
        dets.append({"fila": sl[0].start + rr.mean(), "col": sl[1].start + cc.mean(), "area_ha": area, "t": t_med, "escalon": float(np.median(mejor[sl][m])),
                     "relleno": float(relleno), "brillo_despues": float(np.median(c[min(T - 1, t_med + DESPUES)][sl][m]))})
    return pd.DataFrame(dets)


def es_locacion(d: pd.DataFrame, km_anelo: pd.Series, regla: dict = REGLA) -> pd.Series:
    """La regla de clasificación: tamaño, salto fuerte y lejos del pueblo."""
    return (d.area_ha >= regla["area_min_ha"]) & (d.escalon >= regla["escalon_min"]) & (km_anelo > regla["km_anelo_min"])


def estado_al_verla(x: float, y: float, mes: pd.Timestamp, px: np.ndarray, py: np.ndarray, perforacion: np.ndarray, radio_m: float = 150.0) -> tuple[str, float]:
    """Cuando el satélite vio la obra: ¿ya había un pozo perforado a menos de radio_m? ¿llegó después, a los cuántos meses?

    Devuelve ('sin_pozo' | 'pozo_sin_fecha' | 'ya_perforado' | 'llego_despues', meses de espera).
    """
    cerca = np.hypot(px - x, py - y) < radio_m
    if not cerca.any():
        return "sin_pozo", np.nan
    f = pd.to_datetime(perforacion[cerca])
    if f.isna().all():
        return "pozo_sin_fecha", np.nan
    if (f <= mes).any():
        return "ya_perforado", np.nan
    return "llego_despues", (f.min() - mes).days / 30.4
