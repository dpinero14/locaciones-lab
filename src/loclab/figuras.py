"""Las figuras de locaciones-lab, con la paleta de la serie."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BG, INK, MUTED, RULE = "#0e1b25", "#f2f2f2", "#8fa3b0", "#22333f"
AMBAR, AZUL, ROJO, VERDE, CIAN, GRIS = "#f2b134", "#3b8ed0", "#e05a4e", "#4caf50", "#2ec5e6", "#6b8799"
FUENTE = "locaciones-lab · Copernicus Sentinel-2 L2A (ESA), una escena limpia por mes · pozos y fechas: Secretaría de Energía, Capítulo IV"


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    return plt


def _style(ax, grid="y"):
    ax.set_facecolor(BG)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=9.5, length=0)
    if grid:
        ax.grid(axis=grid, color=RULE, linewidth=0.8, zorder=0)


def _titles(fig, titulo, subtitulo, fuente=FUENTE, x=0.03):
    fig.text(x, 0.955, titulo, color=INK, fontsize=15, fontweight="bold")
    fig.text(x, 0.915, subtitulo, color=MUTED, fontsize=10)
    fig.text(x, 0.015, fuente, color=MUTED, fontsize=8)


def _save(fig, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=BG, dpi=110)
    _plt().close(fig)
    return path


def antes_despues(img0, img1, f0, f1, pozos: pd.DataFrame, path, recorte=None) -> Path:
    """Dos fechas lado a lado con los pozos: verde los que ya producían, rojo los que vinieron después."""
    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(15, 8), facecolor=BG)
    for ax, img, f in zip(axes, (img0, img1), (f0, f1)):
        r0, r1, c0, c1 = recorte or (0, img.shape[0], 0, img.shape[1])
        ax.imshow(img[r0:r1, c0:c1])
        sub = pozos[(pozos.fila.between(r0, r1)) & (pozos.col.between(c0, c1))]
        ya = sub.produccion <= f
        ax.scatter(sub.col[ya] - c0, sub.fila[ya] - r0, s=26, facecolors="none", edgecolors=VERDE, linewidths=1.0)
        ax.scatter(sub.col[~ya] - c0, sub.fila[~ya] - r0, s=26, facecolors="none", edgecolors=ROJO, linewidths=1.0)
        ax.set_title(f"{f:%d/%m/%Y} · en producción {int(ya.sum())} (verde) · todavía no {int((~ya).sum())} (rojo)", color=INK, fontsize=10.5, loc="left")
        ax.axis("off")
    _titles(fig, "Cada locación es un rectángulo claro de 100 a 200 metros", "Sentinel-2 a 10 m · los círculos son las bocas de pozo del padrón, en el lugar exacto de cada locación")
    fig.subplots_adjust(top=0.87, bottom=0.04, left=0.01, right=0.99, wspace=0.03)
    return _save(fig, path)


def series_locaciones(fechas, ejemplos: pd.DataFrame, path) -> Path:
    """Contraste de varias locaciones mes a mes, con el mes detectado y el inicio de perforación."""
    plt = _plt()
    fig, ax = plt.subplots(figsize=(13, 6.5), facecolor=BG)
    _style(ax, grid=None)
    for k, (_, e) in enumerate(ejemplos.iterrows()):
        s = np.asarray(e.serie)
        ax.plot(getattr(e, "fechas", fechas), s - np.median(s[:6]) + k * 0.12, color=CIAN, lw=1.4)
        ax.plot(e.detectada, k * 0.12 + 0.09, "o", color=AMBAR, ms=8)
        ax.plot(e.perforacion, k * 0.12 + 0.09, "v", color=ROJO, ms=8)
    ax.set_yticks([])
    ax.plot([], [], "o", color=AMBAR, label="el satélite ve la locación")
    ax.plot([], [], "v", color=ROJO, label="inicio de perforación (padrón)")
    ax.legend(loc="lower right", frameon=False, labelcolor=INK, fontsize=10)
    _titles(fig, "La locación aparece de golpe, y la perforación llega después", "contraste de cada locación contra el monte que la rodea, mes a mes, 2020-2026")
    fig.subplots_adjust(top=0.86, bottom=0.08, left=0.03, right=0.98)
    return _save(fig, path)


def adelanto(perf: pd.Series, prod: pd.Series, n_det: int, n_tot: int, falsas: float, path) -> Path:
    """Histogramas del adelanto sobre la perforación y sobre la primera producción."""
    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.2), facecolor=BG)
    for ax, v, c, cm, rot, bins in ((axes[0], perf, AMBAR, CIAN, "inicio de perforación", np.arange(-12, 30, 1)), (axes[1], prod, CIAN, AMBAR, "primera producción", np.arange(-6, 40, 1))):
        _style(ax)
        ax.hist(v, bins=bins, color=c, zorder=3)
        ax.axvline(0, color=INK, lw=1)
        ax.axvline(v.median(), color=cm, lw=1.5, ls="--")
        ax.text(v.median() + 0.5, ax.get_ylim()[1] * 0.92, f"mediana {v.median():.1f} meses".replace(".", ","), color=cm, fontsize=12)
        ax.set_xlabel(f"meses entre la locación visible y la {rot}", color=MUTED)
        ax.set_title(f"antes de la {rot}", color=INK, fontsize=11, loc="left")
    _titles(fig, f"El satélite ve {n_det} de {n_tot} locaciones nuevas antes de que el padrón las registre",
            f"cinco áreas de Vaca Muerta, 2020-2026 · falsas alarmas en el monte {100 * falsas:.0f} %")
    fig.subplots_adjust(top=0.82, bottom=0.13, left=0.04, right=0.98, wspace=0.12)
    return _save(fig, path)


def prueba_hacia_atras(tabla: pd.DataFrame, path) -> Path:
    """Qué fracción recibió un pozo: locaciones vistas sin pozo, resto de las detecciones, puntos al azar."""
    plt = _plt()
    fig, ax = plt.subplots(figsize=(11, 5.6), facecolor=BG)
    _style(ax, grid="x")
    colores = [AMBAR, GRIS, MUTED]
    y = np.arange(len(tabla))
    ax.barh(y, tabla.porcentaje, color=colores[:len(tabla)], height=0.55, zorder=3)
    for yy, (_, r) in zip(y, tabla.iterrows()):
        ax.text(r.porcentaje + 1.5, yy, f"{r.porcentaje:.0f} %  ({r.detalle})", color=INK, fontsize=11.5, va="center")
    ax.set_yticks(y)
    ax.set_yticklabels(tabla.grupo, color=INK, fontsize=11)
    ax.set_xlim(0, 100)
    ax.invert_yaxis()
    ax.set_xlabel("recibieron un pozo después de que el satélite las vio", color=MUTED)
    _titles(fig, "Cuando el satélite ve una locación sin pozo, en 3 de cada 4 casos llega un pozo",
            "prueba hacia atrás 2021-2026: en el mes en que se vio la obra no había pozo perforado a menos de 150 m; ¿llegó uno después?")
    fig.subplots_adjust(top=0.8, bottom=0.14, left=0.3, right=0.96)
    return _save(fig, path)


def lamina(recortes: list, titulos: list[str], path, columnas: int = 8, titulo: str = "", subtitulo: str = "") -> Path:
    """Una grilla de recortes de imagen con su título."""
    plt = _plt()
    filas = int(np.ceil(len(recortes) / columnas))
    fig, axes = plt.subplots(filas, columnas, figsize=(2.4 * columnas, 2.6 * filas + 1.2), facecolor=BG)
    for ax in np.ravel(axes):
        ax.axis("off")
    for ax, im, t in zip(np.ravel(axes), recortes, titulos):
        ax.imshow(im)
        ax.set_title(t, color=INK, fontsize=8.5)
    if titulo:
        _titles(fig, titulo, subtitulo)
    fig.subplots_adjust(top=0.9 if titulo else 0.98, bottom=0.04, left=0.01, right=0.99, hspace=0.25, wspace=0.05)
    return _save(fig, path)


FUENTE_ANT = "locaciones-lab · Copernicus Sentinel-2 L2A (ESA), bandas infrarrojas de 20 m, una escena por mes · puntos de venteo declarados: Secretaría de Energía"


def antorchas_invierno(focos: pd.DataFrame, det: pd.DataFrame, path) -> Path:
    """Los reflejos se delatan por el calendario: qué parte de las veces que se vio cada foco fue en invierno."""
    plt = _plt()
    inv = det.assign(inv=det.mes.str[5:7].astype(int).between(5, 8)).groupby(["zona", "foco"]).inv.mean().rename("parte_invierno").reset_index()
    f = focos[focos.meses >= 3].merge(inv, on=["zona", "foco"])
    fig, ax = plt.subplots(figsize=(11, 5.6), facecolor=BG)
    _style(ax)
    cortes = np.linspace(0, 1, 11)
    a, b = f[f.antorcha].parte_invierno * 100, f[~f.antorcha].parte_invierno * 100
    ax.hist([a, b], bins=cortes * 100, stacked=True, color=[CIAN, GRIS], label=[f"pasan la regla ({len(a)})", f"descartados ({len(b)})"], zorder=3, rwidth=0.9)
    ax.axvline(33.3, color=MUTED, linewidth=1, linestyle=(0, (4, 4)), zorder=2)
    ax.text(35, ax.get_ylim()[1] * 0.97, "si el foco se viera parejo todo el año,\nun tercio de las veces caería de mayo a agosto", color=MUTED, fontsize=9.5, va="top")
    ax.set_xlabel("de las veces que se vio el foco, porcentaje entre mayo y agosto", color=MUTED)
    ax.set_ylabel("focos vistos en tres meses o más", color=MUTED)
    ax.legend(frameon=False, labelcolor=INK, fontsize=10.5, loc="upper left", bbox_to_anchor=(0.0, 1.0))
    _titles(fig, "Una llama se ve todo el año; un techo que refleja, casi solo en invierno",
            "con el sol bajo, la chapa y los paneles brillan en el infrarrojo y pasan por píxeles calientes", FUENTE_ANT)
    fig.subplots_adjust(top=0.82, bottom=0.14, left=0.08, right=0.97)
    return _save(fig, path)


def antorchas_mapa(ant: pd.DataFrame, pozos: pd.DataFrame, zonas: dict, path, km_declarado: float = 0.5) -> Path:
    """Las antorchas de las ventanas sobre los pozos del padrón: llenas las que tienen un punto de venteo declarado cerca."""
    plt = _plt()
    fig, ax = plt.subplots(figsize=(12.5, 9), facecolor=BG)
    ax.set_facecolor(BG)
    ax.scatter(pozos.lon, pozos.lat, s=1.2, color="#2c3e4b", linewidths=0, zorder=1)
    for z in zonas.values():
        x0, y0, x1, y1 = z["bbox"]
        ax.plot([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0], color=RULE, linewidth=1, zorder=2)
    con = ant.km_declarado <= km_declarado
    s = 30 + ant.meses * 6
    ax.scatter(ant.lon[con], ant.lat[con], s=s[con], color=CIAN, alpha=0.85, linewidths=0, zorder=4, label=f"con punto de venteo declarado a menos de {int(km_declarado * 1000)} m ({int(con.sum())})")
    ax.scatter(ant.lon[~con], ant.lat[~con], s=s[~con], facecolors="none", edgecolors=CIAN, linewidths=1.6, zorder=4, label=f"sin punto declarado cerca ({int((~con).sum())})")
    ax.set_xlim(-69.45, -68.12)
    ax.set_ylim(-38.90, -37.93)
    ax.set_aspect(111 / 87.5)
    ax.axis("off")
    ax.legend(frameon=False, labelcolor=INK, fontsize=11, loc="lower left", markerscale=0.8)
    _titles(fig, f"{len(ant)} antorchas en quince ventanas de la cuenca",
            "el tamaño es en cuántas escenas mensuales de 2020 a 2026 se la vio encendida · en gris, los pozos del padrón", FUENTE_ANT)
    fig.subplots_adjust(top=0.9, bottom=0.04, left=0.01, right=0.99)
    return _save(fig, path)


def antorchas_por_anio(tabla: pd.DataFrame, path) -> Path:
    """Antorchas vistas encendidas al menos una vez en las escenas de cada año."""
    plt = _plt()
    fig, ax = plt.subplots(figsize=(10, 5.2), facecolor=BG)
    _style(ax)
    ax.bar(tabla.anio.astype(str), tabla.antorchas, color=CIAN, width=0.62, zorder=3)
    for x, v in zip(tabla.anio.astype(str), tabla.antorchas):
        ax.text(x, v + 1, str(int(v)), color=INK, ha="center", fontsize=12, fontweight="bold")
    ax.set_ylabel("antorchas vistas encendidas en el año", color=MUTED)
    _titles(fig, "Las antorchas encendidas crecen de 2020 a 2025, a la par de la actividad",
            "una antorcha cuenta en el año si alguna de sus escenas mensuales la muestra con llama · 2026 hasta octubre", FUENTE_ANT)
    fig.subplots_adjust(top=0.82, bottom=0.1, left=0.08, right=0.97)
    return _save(fig, path)


def antorchas_recortes(arriba: list, abajo: list, titulos: list[str], meses: list[str], path) -> Path:
    """Las antorchas más constantes: arriba el color real a 10 m, abajo las bandas infrarrojas a 20 m de la misma escena."""
    plt = _plt()
    n = len(arriba)
    fig, axes = plt.subplots(2, n, figsize=(2.6 * n, 6.9), facecolor=BG)
    for j in range(n):
        axes[0, j].imshow(arriba[j])
        axes[0, j].set_title(titulos[j], color=INK, fontsize=9.5)
        axes[1, j].imshow(abajo[j])
        axes[1, j].set_title(f"infrarrojo, {meses[j]}", color=MUTED, fontsize=9)
    for ax in np.ravel(axes):
        ax.axis("off")
    _titles(fig, "Cada antorcha está sobre una instalación", "recortes de 800 m · arriba el color real, abajo las bandas infrarrojas (B12, B11, B8A) de la misma escena: la llama es el punto claro", FUENTE_ANT)
    fig.subplots_adjust(top=0.84, bottom=0.05, left=0.01, right=0.99, hspace=0.16, wspace=0.04)
    return _save(fig, path)
