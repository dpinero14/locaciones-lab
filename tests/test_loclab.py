import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from loclab import ciego, senal  # noqa: E402
from loclab.escenas import fraccion_mala  # noqa: E402


def _escena_sintetica(T=40, h=200, w=200, t_obra=20, seed=0):
    """Monte con ruido y estación; en t_obra aparece una locación de 10 x 10 píxeles (1 ha a 10 m) mucho más clara."""
    rng = np.random.default_rng(seed)
    estacion = 0.02 * np.sin(np.arange(T) / 12 * 2 * np.pi)
    b = 0.2 + estacion[:, None, None] + rng.normal(0, 0.004, (T, h, w)).astype(np.float32)
    b[t_obra:, 95:105, 95:105] += 0.12
    return b.astype(np.float32)


def test_contraste_y_mes_de_construccion():
    b = _escena_sintetica()
    s = senal.contraste(b, 100, 100)
    assert s is not None and s[25] - s[5] > 0.08
    assert senal.mes_construccion(s) == 20
    # un punto de monte no se "construye"
    assert senal.mes_construccion(senal.contraste(b, 40, 40)) is None
    # en el borde no hay anillo
    assert senal.contraste(b, 5, 5) is None


def test_detector_a_ciegas_encuentra_la_obra_y_no_el_monte():
    b = _escena_sintetica(h=300, w=300)
    b[20:, 140:160, 140:160] += 0.15   # una locación grande, 20 x 20 píxeles de 10 m = 4 ha
    br = b.reshape(len(b), 150, 2, 150, 2).mean(axis=(2, 4))   # a 20 m, como el detector
    verde = np.zeros((150, 150), bool)
    d = ciego.detectar(br, verde)
    assert len(d) >= 1
    mejor = d.sort_values("area_ha").iloc[-1]
    assert abs(mejor.col - 75) < 3 and abs(mejor.fila - 75) < 3
    assert abs(mejor.t - 20) <= 1


def test_regla_de_locacion():
    d = pd.DataFrame({"area_ha": [2.0, 0.6, 2.0], "escalon": [0.8, 0.8, 0.8]})
    assert ciego.es_locacion(d, pd.Series([10.0, 10.0, 1.0])).tolist() == [True, False, False]


def test_estado_al_verla():
    px, py = np.array([0.0, 1000.0]), np.array([0.0, 0.0])
    perf = np.array(["2024-05-01", "2023-01-01"], dtype="datetime64[ns]")
    assert ciego.estado_al_verla(0, 0, pd.Timestamp("2024-03-15"), px, py, perf)[0] == "llego_despues"
    assert ciego.estado_al_verla(0, 0, pd.Timestamp("2024-06-15"), px, py, perf)[0] == "ya_perforado"
    assert ciego.estado_al_verla(500, 0, pd.Timestamp("2024-03-15"), px, py, perf)[0] == "sin_pozo"


def test_scl():
    assert fraccion_mala(np.array([4, 5, 8, 0])) == 0.5
