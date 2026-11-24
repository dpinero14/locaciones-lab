"""Cotizaciones para la cinta del tablero de minería: cobre, oro, un fondo de litio y las dueñas de los proyectos que cotizan.

Es el mismo script del tablero de Vaca Muerta con otra lista. Baja un año de cierres diarios de cada una y escribe un
JSON chico con el último precio, la variación del día, del mes y del año, y la serie para dibujar. No es tiempo real.
Cada acción va en la moneda de su plaza principal. El carbonato de litio no tiene una cotización abierta con historia:
como referencia del sector se usa el fondo cotizado LIT (Global X Lithium & Battery Tech).

Fuente: el servicio de gráficos de Yahoo Finance, que no es una API oficial y puede dejar de responder. Si falla una
cotización, se conserva la que ya estaba en el archivo de salida.

Uso: python scripts/cotizaciones_mineria.py [SALIDA.json ...]      (por defecto docs/tablero/mineria/data/cotizaciones.json)
"""
import datetime as dt
import json
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDAS = [Path(a) for a in sys.argv[1:]] or [RAIZ / "docs" / "tablero" / "mineria" / "data" / "cotizaciones.json"]
ITEMS = [
    {"id": "cobre", "simbolo": "HG=F", "nombre": "Cobre", "unidad": "US$/lb", "tipo": "metal"},
    {"id": "oro", "simbolo": "GC=F", "nombre": "Oro", "unidad": "US$/oz", "tipo": "metal"},
    {"id": "LIT", "simbolo": "LIT", "nombre": "Fondo de litio y baterías", "corto": "Fondo LIT", "unidad": "US$", "tipo": "fondo", "plaza": "Nueva York"},
    {"id": "RIO", "simbolo": "RIO", "nombre": "Rio Tinto", "unidad": "US$", "tipo": "accion", "plaza": "Nueva York"},
    {"id": "Ganfeng", "simbolo": "1772.HK", "nombre": "Ganfeng", "unidad": "HK$", "tipo": "accion", "plaza": "Hong Kong"},
    {"id": "LAR", "simbolo": "LAR", "nombre": "Lithium Argentina", "unidad": "US$", "tipo": "accion", "plaza": "Nueva York"},
    {"id": "POSCO", "simbolo": "PKX", "nombre": "POSCO", "unidad": "US$", "tipo": "accion", "plaza": "Nueva York"},
    {"id": "Zijin", "simbolo": "2899.HK", "nombre": "Zijin", "unidad": "HK$", "tipo": "accion", "plaza": "Hong Kong"},
    {"id": "Eramet", "simbolo": "ERA.PA", "nombre": "Eramet", "unidad": "€", "tipo": "accion", "plaza": "París"},
    {"id": "Galan", "simbolo": "GLN.AX", "nombre": "Galan", "unidad": "A$", "tipo": "accion", "plaza": "Sídney"},
    {"id": "Lundin", "simbolo": "LUN.TO", "nombre": "Lundin Mining", "unidad": "C$", "tipo": "accion", "plaza": "Toronto"},
    {"id": "McEwen", "simbolo": "MUX", "nombre": "McEwen", "unidad": "US$", "tipo": "accion", "plaza": "Nueva York"},
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
        print(f"{it['nombre'][:18]:18s} {items[-1]['fecha']} {items[-1]['ultimo']:8.2f} · día {items[-1]['var_dia']:+.1%} · mes {items[-1]['var_mes']:+.1%} · año {items[-1]['var_anio']:+.1%}")
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
