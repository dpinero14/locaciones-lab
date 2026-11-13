"""El clasificador llama / techo sobre los focos de `scripts/antorchas.py`.

Deja en `data/processed/`:
  antorchas_rasgos.csv        los dieciocho rasgos de cada foco (tarda unos diez minutos; se reutiliza si ya está)
  antorchas_clasificadas.csv  lo mismo con las etiquetas y la probabilidad de llama
  antorchas_temporales.csv    las llamas cortas que la regla descarta y el modelo reconoce
Uso: python scripts/clasificar.py [--rasgos]     (--rasgos los vuelve a calcular)
"""
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from loclab import DATA_PROC, antorchas, llamas  # noqa: E402

focos = pd.read_csv(DATA_PROC / "antorchas_focos.csv")
det = pd.read_csv(DATA_PROC / "antorchas_detecciones.csv")
ant = pd.read_csv(DATA_PROC / "antorchas.csv")
rev = pd.read_csv(RAIZ / "data" / "antorchas_revision.csv")
ruta = DATA_PROC / "antorchas_rasgos.csv"
if "--rasgos" in sys.argv or not ruta.exists():
    llamas.rasgos(focos, det, aviso=lambda s: print(s, flush=True)).to_csv(ruta, index=False)
t = llamas.etiquetar(pd.read_csv(ruta), antorchas.venteos_declarados(), rev, ant[ant.firme])
t, peso = llamas.clasificar(t)
t.to_csv(DATA_PROC / "antorchas_clasificadas.csv", index=False)
tmp = llamas.temporales(t)
tmp.to_csv(DATA_PROC / "antorchas_temporales.csv", index=False)

e = t[t.etiqueta.notna()]
regla = llamas.regla_sin_lugar(t, focos)
ok = t.p >= 0.5
print(f"{len(t)} focos en dos escenas o más · {int(t.borde.sum())} pegados al borde, sin rasgos")
print(f"entrenamiento: {int((e.etiqueta == 1).sum())} llamas junto a un punto declarado · {int((e.etiqueta == 0).sum())} techos del casco de Añelo")
for nombre, cual in (("clasificador", ok), ("regla a mano, sin el filtro de Añelo", regla)):
    print(f"  {nombre}: reconoce {int((cual & (t.etiqueta == 1)).sum())} de {int((t.etiqueta == 1).sum())} llamas · deja pasar {int((cual & (t.etiqueta == 0)).sum())} de {int((t.etiqueta == 0).sum())} techos")
techos = t[t.revision.isin(llamas.VEREDICTOS_TECHO) & ~t.borde]
sin_decl = t[t.firme & (t.km_declarado > 0.5) & ~t.borde]
print(f"prueba, sin haberlos visto: rechaza {int((techos.p < 0.5).sum())} de {len(techos)} techos descartados a mano (la regla, {int((~regla[techos.index]).sum())}) · "
      f"acepta {int((sin_decl.p >= 0.5).sum())} de {len(sin_decl)} antorchas firmes sin punto declarado")
print(f"con probabilidad {llamas.P_LLAMA} o más: {int(((t.p >= llamas.P_LLAMA) & (t.etiqueta == 0)).sum())} techos de Añelo · "
      f"{int(((t.p >= llamas.P_LLAMA) & (t.etiqueta == 1)).sum())} de {int((t.etiqueta == 1).sum())} llamas · {len(tmp)} llamas cortas fuera de la regla")
print("lo que más pesa:", ", ".join(f"{k} {v:.2f}" for k, v in peso.head(6).items()))
