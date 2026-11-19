"""Cotizaciones para la cinta del tablero: el Brent y las acciones de energía argentinas que cotizan en Nueva York.

Baja un año de cierres diarios de cada una y escribe un JSON chico con el último precio, la variación del día, del mes
y del año, y la serie para dibujar. No es tiempo real: son los últimos datos disponibles, con la demora de la fuente.
Solo usa la biblioteca estándar, para que corra igual en la PC y en la tarea diaria de GitHub.

Fuente: el servicio de gráficos de Yahoo Finance, que no es una API oficial y puede dejar de responder. Si falla una
cotización, se conserva la que ya estaba en el archivo de salida.

Uso: python scripts/cotizaciones.py [SALIDA.json ...]      (por defecto docs/tablero/data/cotizaciones.json)
"""
import datetime as dt
import json
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDAS = [Path(a) for a in sys.argv[1:]] or [RAIZ / "docs" / "tablero" / "data" / "cotizaciones.json"]
ITEMS = [
    {"id": "brent", "simbolo": "BZ=F", "nombre": "Brent", "unidad": "US$/bbl", "tipo": "petroleo"},
    {"id": "YPF", "simbolo": "YPF", "nombre": "YPF", "unidad": "US$", "tipo": "accion"},
    {"id": "Vista", "simbolo": "VIST", "nombre": "Vista", "unidad": "US$", "tipo": "accion"},
    {"id": "Pampa", "simbolo": "PAM", "nombre": "Pampa", "unidad": "US$", "tipo": "accion"},
    {"id": "TGS", "simbolo": "TGS", "nombre": "TGS", "unidad": "US$", "tipo": "accion"},
]
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}?range=1y&interval=1d"


def bajar(simbolo):
    req = urllib.request.Request(URL.format(urllib.request.quote(simbolo)), headers={"User-Agent": "Mozilla/5.0"})
    r = json.load(urllib.request.urlopen(req, timeout=30))["chart"]["result"][0]
    pares = [(dt.datetime.fromtimestamp(t, dt.timezone.utc).date(), c) for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c is not None]
    assert len(pares) > 100, f"{simbolo}: serie corta ({len(pares)})"
    return pares


def variacion(pares, dias):
    """Contra el último cierre de hace `dias` días corridos o antes."""
    hoy, ult = pares[-1]
    antes = [c for f, c in pares if f <= hoy - dt.timedelta(days=dias)]
    return round(ult / antes[-1] - 1, 4) if antes else None


previo = {}
if SALIDAS[0].exists():
    try:
        previo = {x["id"]: x for x in json.load(open(SALIDAS[0], encoding="utf-8"))["items"]}
    except Exception:
        previo = {}

items, fallas = [], []
for it in ITEMS:
    try:
        p = bajar(it["simbolo"])
        serie = p[::-1][::3][::-1]                       # un cierre de cada tres, terminando en el último
        items.append(dict(it, fecha=p[-1][0].isoformat(), ultimo=round(p[-1][1], 2), var_dia=round(p[-1][1] / p[-2][1] - 1, 4),
                          var_mes=variacion(p, 30), var_anio=round(p[-1][1] / p[0][1] - 1, 4),
                          maximo_anio=round(max(c for _, c in p), 2), minimo_anio=round(min(c for _, c in p), 2),
                          desde=serie[0][0].isoformat(), serie=[round(c, 2) for _, c in serie]))
        print(f"{it['nombre']:6s} {items[-1]['fecha']} {items[-1]['ultimo']:8.2f} · día {items[-1]['var_dia']:+.1%} · mes {items[-1]['var_mes']:+.1%} · año {items[-1]['var_anio']:+.1%}")
    except Exception as e:                               # una falla no tira las demás: queda la cotización anterior
        fallas.append(it["id"])
        print(f"{it['nombre']}: no se pudo bajar ({type(e).__name__}: {e})")
        if it["id"] in previo:
            items.append(previo[it["id"]])
    time.sleep(1)

if not items:
    sys.exit("no se bajó ninguna cotización y no había archivo anterior: no se escribe nada")
salida = {"actualizado": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "fuente": "Yahoo Finance, último dato disponible con demora", "items": items}
for s in SALIDAS:
    s.parent.mkdir(parents=True, exist_ok=True)
    json.dump(salida, open(s, "w", encoding="utf-8"), ensure_ascii=False)
    print("escrito:", s)
if fallas:
    print("con fallas:", fallas)
