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
