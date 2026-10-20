"""Baja la serie mensual de Sentinel-2 de una zona.    python scripts/download_zona.py <zona>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from loclab.escenas import bajar_serie  # noqa: E402

bajar_serie(sys.argv[1])
print("listo", sys.argv[1])
