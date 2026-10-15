"""La señal de una locación: contraste contra el monte que la rodea, mes a mes, y el mes en que aparece.

Contraste = brillo medio en 70 x 70 m sobre la locación menos el brillo del anillo de 150 a 300 m. Comparar
contra el vecino saca la estación, la iluminación y la sequía, que mueven toda la escena junta.
Fecha de construcción: primer mes en que el contraste supera la línea de base (mediana de los primeros
seis meses de la serie) en más de `umbral` y se mantiene dos meses seguidos.
"""

from __future__ import annotations

import numpy as np


def contraste(brillo: np.ndarray, col: float, fila: float, r_centro: int = 3, r_anillo: tuple[int, int] = (15, 30)) -> np.ndarray | None:
    """Serie de contraste de un punto (píxeles de 10 m). None si el anillo no entra en la escena."""
    _, h, w = brillo.shape
    c, r = int(round(col)), int(round(fila))
    ro = r_anillo[1]
    if not (ro <= c < w - ro and ro <= r < h - ro):
        return None
    centro = brillo[:, r - r_centro:r + r_centro + 1, c - r_centro:c + r_centro + 1].mean(axis=(1, 2))
    sub = brillo[:, r - ro:r + ro + 1, c - ro:c + ro + 1]
    d = np.hypot(*np.mgrid[-ro:ro + 1, -ro:ro + 1])
    anillo = sub[:, (d >= r_anillo[0]) & (d <= ro)].mean(axis=1)
    return centro - anillo


def mes_construccion(serie: np.ndarray, umbral: float = 0.03, base: int = 6) -> int | None:
    """Índice del primer mes que supera la base + umbral dos meses seguidos; None si nunca."""
    if serie is None or len(serie) <= base + 1:
        return None
    alto = serie > np.median(serie[:base]) + umbral
    for i in range(base, len(serie) - 1):
        if alto[i] and alto[i + 1]:
            return i
    return None
