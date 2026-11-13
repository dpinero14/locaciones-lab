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


def test_pixel_caliente_y_regla_de_antorcha():
    from loclab import antorchas

    # una llama: la banda de 2,2 micrones satura y supera por mucho a la de 1,6; el suelo y un techo claro, no
    b12 = np.array([[1.50, 0.30, 0.55]], np.float32)
    b11 = np.array([[0.60, 0.33, 0.52]], np.float32)
    b8a = np.array([[0.30, 0.28, 0.50]], np.float32)
    assert antorchas.calientes(b12, b11, b8a).tolist() == [[True, False, False]]
    # dos detecciones a tres píxeles son el mismo foco; a veinte, otro
    assert antorchas.agrupar(np.array([10.0, 12.0, 30.0]), np.array([10.0, 12.0, 10.0])).tolist() == [0, 0, 1]
    # la regla: una llama de todo el año pasa; un reflejo que solo aparece en invierno, uno que no satura y uno en el pueblo, no
    f = pd.DataFrame({"meses": [20, 9, 12, 15], "fuera_invierno": [14, 1, 8, 10], "b12": [1.5, 1.5, 0.8, 1.5], "km_anelo": [12.0, 9.0, 7.0, 1.5]})
    assert antorchas.es_antorcha(f).tolist() == [True, False, False, False]


def test_antorchas_vecinas_y_revision():
    from loclab import antorchas

    f = pd.DataFrame({"antorcha": [True, True, True, False], "lon": [-68.6000, -68.6010, -68.5000, -68.4000], "lat": [-38.3000, -38.3000, -38.3000, -38.3000]})
    u = antorchas.unir(f)   # la segunda está a menos de 100 m de la primera: es la misma; la cuarta no pasó la regla
    assert u.lon.round(3).tolist() == [-68.6, -68.5]
    r = antorchas.aplicar_revision(u, pd.DataFrame({"lon": [-68.5001], "lat": [-38.3], "veredicto": ["galpon"]}))
    assert r.firme.tolist() == [True, False] and r.revision.tolist() == ["", "galpon"]
    assert antorchas.km_al_mas_cercano([-68.6], [-38.3], [-68.6, -68.0], [-38.31, -38.3]).round(2).tolist() == [1.11]


def test_llamas_forma_y_etiquetas():
    from loclab import ANELO, llamas

    redonda = np.zeros((15, 15), bool); redonda[6:9, 6:9] = True
    tira = np.zeros((15, 15), bool); tira[7, 3:12] = True
    assert llamas.alargada(redonda) < 1.2 and llamas.alargada(tira) > 3 and llamas.alargada(np.zeros((15, 15), bool)) == 1.0
    # cuatro focos: junto a un punto declarado, en el casco de Añelo, junto a un punto declarado pero revisado a mano, y en el medio del campo
    t = pd.DataFrame({"zona": ["a"] * 4, "foco": [0, 1, 2, 3], "lon": [-68.5, ANELO[0] + 0.005, -68.3, -68.9], "lat": [-38.3, ANELO[1], -38.3, -38.6],
                      "x": [1000.0, 2500.0, 9000.0, 20000.0], "y": [5000.0, 5000.0, 7000.0, 9000.0], "borde": [False] * 4})
    decl = pd.DataFrame({"lon": [-68.5, -68.3], "lat": [-38.3005, -38.3]})
    rev = pd.DataFrame({"lon": [-68.3], "lat": [-38.3], "veredicto": ["galpon"]})
    e = llamas.etiquetar(t, decl, rev, pd.DataFrame({"zona": ["a"], "foco": [0]}))
    assert e.etiqueta.fillna(-1).tolist() == [1.0, 0.0, -1.0, -1.0]      # lo revisado a mano no entrena: es la prueba
    assert e.firme.tolist() == [True, False, False, False] and e.revision.tolist() == ["", "", "galpon", ""]
    assert e.y.tolist() == [5000.0, 5000.0, 7000.0, 9000.0] and e.celda.tolist() == ["1_5", "2_5", "9_7", "20_9"]


def test_tiempo_encendida(tmp_path):
    from loclab import antorchas

    # tres pasadas sobre una antorcha en el píxel (10, 10): con llama, sin llama, y tapada por nubes (no cuenta)
    d = tmp_path / "z" / "pasadas"
    d.mkdir(parents=True)
    tr = np.array([500000.0, 20.0, 0.0, 5800000.0, 0.0, -20.0])
    limpia, nube = np.zeros((30, 30), bool), np.ones((30, 30), bool)
    comun = dict(descartada=False, mala_frac=0.0, forma=np.array([30, 30]), transform=tr, crs="EPSG:32719")
    np.savez(d / "2025-01-01.npz", fecha="2025-01-01", mala=np.packbits(limpia), fila=np.array([11], np.int16), col=np.array([10], np.int16), **comun)
    np.savez(d / "2025-01-06.npz", fecha="2025-01-06", mala=np.packbits(limpia), fila=np.array([], np.int16), col=np.array([], np.int16), **comun)
    np.savez(d / "2025-01-11.npz", fecha="2025-01-11", mala=np.packbits(nube), fila=np.array([10], np.int16), col=np.array([10], np.int16), **comun)
    np.savez(d / "2025-01-16.npz", fecha="2025-01-16", descartada=True, mala_frac=0.9)
    ant = pd.DataFrame({"zona": ["z"], "foco": [0], "x": [500000.0 + 10.5 * 20], "y": [5800000.0 - 10.5 * 20]})
    t = antorchas.tiempo_encendida(ant, tmp_path)
    assert t[["pasadas", "vistas", "encendida", "ultima", "pct"]].iloc[0].tolist() == [4, 2, 1, "2025-01-01", 50.0]
