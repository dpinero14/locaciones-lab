"""Cuánto tiempo está encendida cada antorcha, con todas las pasadas de Sentinel-2 y no una por mes.

    python scripts/pasadas.py --bajar    # baja las pasadas de 2025 y 2026 de cada zona (reanudable, varias horas)
    python scripts/pasadas.py            # calcula con lo que haya bajado
Deja `data/processed/antorchas_pasadas.csv`: por antorcha firme, en cuántas pasadas sin nubes se la pudo ver y en cuántas tenía llama.
"""

import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from loclab import DATA_PROC, DATA_RAW, antorchas  # noqa: E402

if __name__ == "__main__":
    ant = pd.read_csv(DATA_PROC / "antorchas.csv")
    ant = ant[ant.firme]
    if "--bajar" in sys.argv:
        for z in sorted(ant.zona.unique()):
            print(z, antorchas.bajar_pasadas(z, aviso=print), "pasadas nuevas", flush=True)
    t = antorchas.tiempo_encendida(ant)
    t.to_csv(DATA_PROC / "antorchas_pasadas.csv", index=False)
    fechas = sorted(p.stem for z in ant.zona.unique() for p in (DATA_RAW / z / "pasadas").glob("20*.npz"))
    print(f"{len(t)} antorchas · pasadas del {fechas[0]} al {fechas[-1]} · mediana de {int(t.vistas.median())} pasadas sin nubes por antorcha")
    print(f"con llama en el {t.pct.median():.0f} % de las pasadas (la mitad entre {t.pct.quantile(.25):.0f} % y {t.pct.quantile(.75):.0f} %)")
    print(f"más del 75 % del tiempo: {int((t.pct > 75).sum())} · nunca en el período: {int((t.encendida == 0).sum())} · más de la mitad: {int((t.pct > 50).sum())}")
