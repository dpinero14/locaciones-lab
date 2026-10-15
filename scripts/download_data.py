"""Baja todo lo que usa el repo.

    python scripts/download_data.py                 # padrón y producción (un par de minutos)
    python scripts/download_data.py --series        # además, la serie mensual de Sentinel-2 de las cuatro zonas

La serie son unas 80 escenas por zona, recortadas a la ventana: unos 40 minutos por zona y 1 GB en total.
Reanudable: lo que ya está en data/raw no se vuelve a pedir.
"""

import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from loclab import DATA_RAW, ZONAS  # noqa: E402
from loclab.escenas import bajar_serie  # noqa: E402
from loclab.padron import URLS  # noqa: E402


def bajar(url: str, destino: Path) -> None:
    if destino.exists() and destino.stat().st_size > 0:
        print("  ya existe:", destino.name)
        return
    print("  bajando", destino.name, flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "locaciones-lab/0.1 (+https://github.com/dpinero14)"})
    with urllib.request.urlopen(req) as r, open(destino, "wb") as f:  # noqa: S310
        while chunk := r.read(1 << 20):
            f.write(chunk)


def main() -> None:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    print("Secretaría de Energía: pozos (shapefile) y producción no convencional")
    for nombre, url in URLS.items():
        bajar(url, DATA_RAW / nombre)
    carpeta = DATA_RAW / "pozos_shp"
    if not carpeta.exists():
        zipfile.ZipFile(DATA_RAW / "pozos_shp.zip").extractall(carpeta)
    if "--series" in sys.argv:
        for zona in ZONAS:
            print("Sentinel-2:", zona)
            bajar_serie(zona)
    print("listo")


if __name__ == "__main__":
    main()
