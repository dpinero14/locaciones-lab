"""Los equipos de perforación con radar: detector a ciegas sobre Sentinel-1 y validación contra el padrón.

    python scripts/radar.py --bajar                 # baja las pasadas que falten (reanudable; horas: ~30 MB por pasada)
    python scripts/radar.py [--detectar]            # detecta (o usa lo detectado), aplica la regla, arma campañas y valida
Ventanas de validación (desde 2023): VALIDACION. El resto, desde agosto de 2025 (revisita de 6 días).
Deja en `data/processed/`: radar_eventos.csv (todo lo que se encendió), radar_equipos.csv (los que pasan la regla, con lo
que dice el padrón debajo), radar_campanias.csv (una fila por locación y campaña) y radar_recall.csv.
"""

import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from loclab import DATA_PROC, DATA_RAW, ZONAS, padron, radar  # noqa: E402

VALIDACION = {"loma_campana_este": "2023-01-01", "norte_lac_bdp_bandurria": "2023-01-01", "norte_este": "2023-01-01"}
AJUSTE = "loma_campana_este"     # la regla (VH, base) se eligió mirando solo esta ventana; las otras dos son la prueba

if __name__ == "__main__":
    zonas = [z for z in ZONAS if (DATA_RAW / z / "radar").exists() or "--bajar" in sys.argv]
    if "--bajar" in sys.argv:
        for z in ZONAS:
            n = radar.bajar(z, desde=VALIDACION.get(z, "2025-08-01"))
            print(z, n, "pasadas nuevas", flush=True)
    todos, eqs, recs = [], [], []
    POZOS, OBRAS = padron.pozos(), radar.obras_s2()
    for z in zonas:
        fe = radar.fechas(z)
        if len(fe) < 10:
            continue
        cache = DATA_PROC / f"radar_eventos_{z}.csv"
        if cache.exists() and "--detectar" not in sys.argv:
            e = pd.read_csv(cache, parse_dates=["llegada", "salida", "ultima_pasada"])
        else:
            e = radar.eventos(z)
            e.to_csv(cache, index=False)
        todos.append(e)
        eq = radar.lugar(radar.equipos(e), POZOS, OBRAS)
        eq = eq[eq.sobre_locacion].reset_index(drop=True)
        if z in VALIDACION:
            r, eq = radar.validar(eq, radar.fases(z), fe.min(), fe.max())
            recs.append(r)
        eqs.append(eq)
        print(f"{z}: {len(fe)} pasadas del {fe.min():%Y-%m-%d} al {fe.max():%Y-%m-%d} · {len(e)} objetos · {len(eq)} equipos", flush=True)
    e, eq = pd.concat(todos), pd.concat(eqs)
    c = radar.campanias(eq)
    e.to_csv(DATA_PROC / "radar_eventos.csv", index=False)
    eq.to_csv(DATA_PROC / "radar_equipos.csv", index=False)
    c.to_csv(DATA_PROC / "radar_campanias.csv", index=False)
    r = pd.concat(recs)
    r.to_csv(DATA_PROC / "radar_recall.csv", index=False)
    for nombre, zs in (("ajuste", [AJUSTE]), ("prueba", [z for z in VALIDACION if z != AJUSTE])):
        rr, ee = r[r.zona.isin(zs)], eq[eq.zona.isin(zs) & eq.tipo.notna()]
        print(f"\n[{nombre}] locaciones perforadas dentro del período: {len(rr)} · con un equipo encima mientras se perforaba: {int(rr.visto.sum())} ({rr.visto.mean() * 100:.0f} %)")
        print(f"  llegada del equipo menos inicio de perforación: mediana {rr.llegada.median():.0f} días · salida menos fin: {rr.salida.median():.0f} días")
        print(f"  equipos terminados antes del corte: {len(ee)} · qué hay debajo: " + " · ".join(f"{k} {v}" for k, v in ee.tipo.value_counts().items()))
    print(f"\ncampañas: {len(c)} · activas en la última pasada: {int(c.activa.sum())}")

    # figuras: brillo por fase y conteo mensual en las ventanas de validación; un caso
    import numpy as np  # noqa: E402
    from loclab import FIGURES, figuras  # noqa: E402
    Ls = {z: radar.fases(z) for z in VALIDACION}
    s = pd.concat([radar.brillo_por_fase(z, Ls[z]) for z in VALIDACION])
    s.to_csv(DATA_PROC / "radar_brillo_fases.csv", index=False)
    figuras.radar_fases(s, FIGURES / "radar_fases.png")
    print("pasadas con más de 5 dB, por fase:", (s.groupby("fase").vv_max.apply(lambda x: (x > 5).mean() * 100)).round(0).to_dict())
    cv = c[c.zona.isin(VALIDACION)]
    t = sum(radar.conteo_mensual(cv[cv.zona == z], Ls[z], "2023-02", "2026-10").set_index("mes") for z in VALIDACION).reset_index()
    t.to_csv(DATA_PROC / "radar_conteo_mensual.csv", index=False)
    figuras.radar_conteo(t, FIGURES / "radar_conteo.png", corte="2026-03-01")
    hasta = t[t.mes < "2026-03"]
    print(f"conteo mensual 2023-02 a 2026-02: radar {hasta.radar.mean():.1f} equipos por mes, padrón {hasta.padron.mean():.1f} locaciones · correlación {np.corrcoef(hasta.radar, hasta.padron)[0, 1]:.2f}")
    # el caso: una locación de 4 pozos perforada en 2025 con revisita de 6 días
    z, loc = "norte_lac_bdp_bandurria", 98
    l = Ls[z][Ls[z]["loc"] == loc].iloc[0]
    T = np.load(DATA_RAW / z / "radar" / "transform.npy")
    col, fil = int(round((l.x - T[2]) / T[0])), int(round((l.y - T[5]) / T[4]))
    se = s[(s.zona == z) & (s["loc"] == loc)][["fecha", "vv_max"]]
    fs = {pd.Timestamp(p.stem): p for p in (DATA_RAW / z / "radar").glob("20*.npz")}
    ser = pd.DataFrame([(d, np.load(p)["vv"][fil - 6:fil + 7, col - 6:col + 7].max() / 5 - 25) for d, p in sorted(fs.items())
                        if l.perf_ini - pd.Timedelta(days=30) <= d <= l.perf_fin + pd.Timedelta(days=30)], columns=["fecha", "vv_max"])
    elegidas = [ser[ser.fecha < l.perf_ini - pd.Timedelta(days=5)].fecha.iloc[-1], ser[(ser.fecha > l.perf_ini) & (ser.fecha < l.perf_fin)].sort_values("vv_max").fecha.iloc[-1],
                ser[(ser.fecha > l.perf_fin + pd.Timedelta(days=10)) & (ser.vv_max < -3)].fecha.iloc[0]]
    rec = [np.load(fs[d])["vv"][fil - 45:fil + 45, col - 45:col + 45] / 5 - 25 for d in elegidas]
    figuras.radar_caso(rec, [f"Antes · {elegidas[0]:%d/%m/%Y}", f"Con el equipo · {elegidas[1]:%d/%m/%Y}", f"Después · {elegidas[2]:%d/%m/%Y}"],
                       ser, (l.perf_ini, l.perf_fin), FIGURES / "radar_caso.png", f"El equipo llega y se va: una locación de {l.pozos} pozos, {l.perf_ini:%m/%Y} a {l.perf_fin:%m/%Y}")
