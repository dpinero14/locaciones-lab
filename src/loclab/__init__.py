"""locaciones-lab: la actividad de Vaca Muerta vista desde el satélite, antes que en el padrón.

Una escena limpia de Sentinel-2 por mes desde 2020 sobre cinco áreas de la cuenca Neuquina, y los
pozos del Capítulo IV de la Secretaría de Energía con sus fechas de perforación y de producción.
Primero se verifica que cada locación se ve y se fecha; después se buscan a ciegas, sin el padrón,
y se mide cuántas recibieron un pozo.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_PROC = REPO_ROOT / "data" / "processed"
DOCS = REPO_ROOT / "docs"
FIGURES = DOCS / "figures"

# Ventanas de estudio (lon/lat WGS84) y el tile de Sentinel-2 que las cubre entero.
ZONAS = {
    "loma_campana_oeste": {"bbox": (-68.85, -38.40, -68.70, -38.28), "tile": "MGRS-19HET", "nombre": "Loma Campana oeste y Añelo"},
    "norte_lac_bdp_bandurria": {"bbox": (-68.75, -38.28, -68.52, -38.13), "tile": "MGRS-19HET", "nombre": "La Amarga Chica, Bajada del Palo y Bandurria"},
    "loma_campana_este": {"bbox": (-68.70, -38.42, -68.52, -38.28), "tile": "MGRS-19HET", "nombre": "Loma Campana este"},
    "fortin_de_piedra": {"bbox": (-69.15, -38.57, -68.95, -38.43), "tile": "MGRS-19HDT", "nombre": "Fortín de Piedra"},
    # segunda tanda (20/10/2026): el resto de la actividad no convencional desde 2021
    "norte_este": {"bbox": (-68.60, -38.26, -68.40, -38.10), "tile": "MGRS-19HET", "nombre": "Bajada del Palo este (YPF, Vista)"},
    "norte_norte": {"bbox": (-68.78, -38.13, -68.58, -37.97), "tile": "MGRS-19HET", "nombre": "Bandurria norte y Aguada Federal (Vista, Pampa)"},
    "norte_noreste": {"bbox": (-68.60, -38.10, -68.40, -37.97), "tile": "MGRS-19HET", "nombre": "Parva Negra y El Mangrullo (Pampa, YPF)"},
    "aguada_pichana_oeste": {"bbox": (-69.20, -38.40, -69.00, -38.25), "tile": "MGRS-19HDT", "nombre": "Aguada Pichana oeste (Total, Pluspetrol)"},
    "aguada_pichana_este": {"bbox": (-69.00, -38.40, -68.86, -38.25), "tile": "MGRS-19HET", "nombre": "Aguada Pichana este (Pluspetrol, YPF)"},
    "sierras_blancas": {"bbox": (-68.58, -38.55, -68.25, -38.41), "tile": "MGRS-19HET", "nombre": "Sierras Blancas y Cruz de Lorena (Shell, YPF, Phoenix)"},
    "loma_la_lata_sur": {"bbox": (-68.75, -38.85, -68.60, -38.70), "tile": "MGRS-19HET", "nombre": "Loma La Lata sur (YPF, Tecpetrol)"},
    "aguada_del_chanar": {"bbox": (-68.57, -38.67, -68.44, -38.58), "tile": "MGRS-19HET", "nombre": "Aguada del Chañar (PAE)"},
    "rincon_del_mangrullo": {"bbox": (-69.40, -38.62, -69.22, -38.46), "tile": "MGRS-19HDT", "nombre": "Rincón del Mangrullo (PAE, YPF, Pampa)"},
    "ypf_sur_este": {"bbox": (-68.30, -38.78, -68.18, -38.68), "tile": "MGRS-19HET", "nombre": "Loma Campana sur este (YPF)"},
    "aguada_pichana_norte": {"bbox": (-69.19, -38.21, -69.00, -38.13), "tile": "MGRS-19HDT", "nombre": "Aguada Pichana norte (YPF, Pampa)"},
}
ANELO = (-68.789, -38.352)   # plaza de Añelo, el centro del pueblo
CRS_METRICO = "EPSG:32719"   # UTM 19 sur, el de los tiles

__all__ = ["REPO_ROOT", "DATA_RAW", "DATA_PROC", "DOCS", "FIGURES", "ZONAS", "ANELO", "CRS_METRICO"]
