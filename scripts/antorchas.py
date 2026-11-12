"""Las antorchas de todas las zonas con bandas infrarrojas bajadas.

Deja en `data/processed/`:
  antorchas_detecciones.csv   cada grupo de píxeles calientes de cada mes, con su foco
  antorchas_focos.csv         una fila por foco, con la regla aplicada
  antorchas.csv               las antorchas (sin repetir entre ventanas vecinas), con la revisión a mano y la
                              distancia al punto de venteo declarado más cercano

    python scripts/antorchas.py --bajar   # baja las bandas infrarrojas de la escena mensual de cada zona
    python scripts/antorchas.py           # detecta con lo que haya bajado
"""

import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from loclab import DATA_PROC, DATA_RAW, ZONAS, antorchas  # noqa: E402

if __name__ == "__main__":
    zonas = sorted(z for z in ZONAS if (DATA_RAW / z).exists())
    if "--bajar" in sys.argv:
        for z in zonas:
            antorchas.bajar_infrarrojo(z)
    zonas = [z for z in zonas if list((DATA_RAW / z / "swir").glob("20*.npz"))]
    det = pd.concat([antorchas.detectar(z) for z in zonas], ignore_index=True)
    focos = antorchas.resumir(det)
    ant = antorchas.unir(focos)
    ant = antorchas.aplicar_revision(ant, pd.read_csv(RAIZ / "data" / "antorchas_revision.csv"))
    decl = antorchas.venteos_declarados()
    ant["km_declarado"] = antorchas.km_al_mas_cercano(ant.lon, ant.lat, decl.lon, decl.lat)
    DATA_PROC.mkdir(parents=True, exist_ok=True)
    det.to_csv(DATA_PROC / "antorchas_detecciones.csv", index=False)
    focos.to_csv(DATA_PROC / "antorchas_focos.csv", index=False)
    ant.to_csv(DATA_PROC / "antorchas.csv", index=False)
    f = ant[ant.firme]
    print(f"{len(zonas)} zonas · {len(det)} detecciones · {len(focos)} focos · {int((focos.meses >= antorchas.MESES_MIN).sum())} en tres meses o más")
    print(f"{int(focos.antorcha.sum())} pasan la regla · {len(ant)} sin repetir entre ventanas · {len(f)} firmes tras la revisión a mano")
    print(f"con punto de venteo declarado a menos de 150 m: {int((f.km_declarado <= 0.15).sum())} · a menos de 500 m: {int((f.km_declarado <= 0.5).sum())} · sin ninguno a menos de 500 m: {int((f.km_declarado > 0.5).sum())}")
