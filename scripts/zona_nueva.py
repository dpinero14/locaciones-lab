"""La prueba del clasificador en una zona que no vio: Cutral Có y Plaza Huincul.

El modelo se entrena con las quince ventanas de siempre y se aplica, sin tocar nada, a una ventana nueva que tiene
las dos cosas que hacen falta para medirlo: una ciudad (techos) y chimeneas de quema declaradas (llamas).

    python scripts/zona_nueva.py --bajar    # baja la serie mensual y las bandas infrarrojas de la zona (una hora)
    python scripts/zona_nueva.py            # detecta, describe los focos y mide el modelo
Deja `data/processed/zona_nueva_clasificada.csv`.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from loclab import DATA_PROC, ZONAS, antorchas, escenas, llamas  # noqa: E402

ZONA = "cutral_co_plaza_huincul"
ZONAS[ZONA] = llamas.ZONA_PRUEBA          # solo para esta corrida: no entra en los conteos de los notebooks

if __name__ == "__main__":
    if "--bajar" in sys.argv:
        escenas.bajar_serie(ZONA)
        antorchas.bajar_infrarrojo(ZONA)
    det = antorchas.detectar(ZONA)
    focos = antorchas.resumir(det)
    decl = antorchas.venteos_declarados()
    nada = pd.DataFrame({"lon": [], "lat": [], "veredicto": []})
    nuevo = llamas.etiquetar(llamas.rasgos(focos, det), decl, nada, pd.DataFrame({"zona": [], "foco": []}))
    nuevo["km_ciudad"] = np.min([np.hypot((nuevo.lon - lo) * 87.5, (nuevo.lat - la) * 111) for lo, la in llamas.CENTROS_PRUEBA], axis=0)
    # el modelo: el mismo de siempre, entrenado con las quince ventanas
    base = pd.read_csv(DATA_PROC / "antorchas_clasificadas.csv")
    modelo, med = llamas.entrenar(base)
    con = ~nuevo.borde
    nuevo["p"] = np.nan
    nuevo.loc[con, "p"] = modelo.predict_proba(nuevo.loc[con, llamas.RASGOS].fillna(med))[:, 1]
    llama = con & (nuevo.km_declarado <= llamas.KM_LLAMA)
    techo = con & (nuevo.km_ciudad < llamas.KM_TECHO_ANELO) & (nuevo.km_declarado > llamas.KM_TECHO_LEJOS)
    nuevo["grupo"] = np.where(llama, "llama", np.where(techo, "techo", ""))
    nuevo.to_csv(DATA_PROC / "zona_nueva_clasificada.csv", index=False)
    regla = (nuevo.meses >= antorchas.MESES_MIN) & (nuevo.merge(focos[["foco", "fuera_invierno"]], on="foco").fuera_invierno.values >= antorchas.FUERA_INVIERNO_MIN) \
        & (nuevo.b12_max >= antorchas.B12_SATURA)
    print(f"{ZONA}: {len(det)} detecciones · {len(focos)} focos · {len(nuevo)} en dos escenas o más · {int(nuevo.borde.sum())} pegados al borde")
    print(f"llamas (junto a un punto declarado): {int(llama.sum())} · techos (a menos de 2 km del centro de Cutral Có o Plaza Huincul): {int(techo.sum())}")
    for u in (0.5, llamas.P_LLAMA):
        print(f"  modelo, umbral {u}: reconoce {int((llama & (nuevo.p >= u)).sum())} de {int(llama.sum())} llamas · deja pasar {int((techo & (nuevo.p >= u)).sum())} de {int(techo.sum())} techos")
    print(f"  regla a mano, sin filtro de lugar: reconoce {int((llama & regla).sum())} de {int(llama.sum())} llamas · deja pasar {int((techo & regla).sum())} de {int(techo.sum())} techos")
    otros = con & ~llama & ~techo
    print(f"el resto ({int(otros.sum())} focos sin etiqueta): {int((otros & (nuevo.p >= llamas.P_LLAMA)).sum())} con probabilidad de {llamas.P_LLAMA} o más")
