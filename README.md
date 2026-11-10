# locaciones-lab

¿Se puede ver la actividad de Vaca Muerta desde el satélite antes de que aparezca en el registro
oficial? Con una imagen gratis de Sentinel-2 por mes desde 2020 sobre cinco áreas de la cuenca
Neuquina y los pozos del Capítulo IV de la Secretaría de Energía. Duodécimo repo de la serie
Sur Analytics.

> Antes de perforar un pozo se desmonta una locación: un rectángulo de 100 a 200 metros en el monte.
> El satélite la ve casi un año antes de que el pozo registre su primer barril. Y cuando ve una
> locación nueva sin pozo al lado, en 3 de cada 4 casos llega un pozo, casi siempre en dos meses.

![Cuando el satélite ve una locación sin pozo, llega un pozo](docs/figures/prueba_hacia_atras.png)

## De dónde sale

En la cuenca Pérmica de Estados Unidos hay empresas que venden la actividad petrolera vista desde el
satélite: detectan la locación en construcción meses antes del permiso de perforación. Este repo hace
la misma pregunta para Vaca Muerta con datos abiertos: imágenes de 10 metros de Copernicus y el padrón
público de pozos, y la responde con una prueba hacia atrás, no con un ejemplo.

## Qué hace

| Notebook | Qué hace |
|---|---|
| `01_la_locacion_se_ve` | Verifica que cada locación se ve en Sentinel-2 y que el pozo del padrón cae encima. Sigue el contraste de cada una de las locaciones de cinco áreas contra el monte que la rodea, en 82 escenas mensuales, y fecha su construcción. Mide cuánto antes aparece que el inicio de perforación y que la primera producción. |
| `02_el_detector_a_ciegas` | Busca locaciones sin mirar el padrón, en toda la serie, con el contraste local de cada píxel. Clasifica qué es locación y qué es camino, planta, pueblo o barda, con 48 detecciones etiquetadas a mano. Prueba hacia atrás: en el mes en que el satélite vio la obra, ¿había un pozo perforado al lado? Si no, ¿llegó uno después? Y verifica las locaciones del último año que todavía no tienen pozo registrado. |

Las funciones están en `src/loclab/`: `escenas.py` busca y baja la serie mensual del STAC público
de Sentinel-2 y elige la escena limpia de cada mes; `padron.py` lee los pozos, sus fechas y las
locaciones multipozo; `senal.py` mide el contraste de una locación y fecha su construcción;
`ciego.py` es el detector a ciegas, la regla de clasificación y la prueba hacia atrás;
`figuras.py`, las figuras.

## Qué encontramos

**La locación se ve, y el pozo cae encima.** A 10 metros, cada locación es un rectángulo claro sobre
el monte oscuro. Las coordenadas del Capítulo IV son de boca de pozo y caen sobre la locación; en
Loma Campana, 710 de 770 pozos tienen otro a menos de 30 metros: son las locaciones multipozo.

![Antes y después en Loma Campana](docs/figures/antes_despues.png)

**El satélite ve 167 de 177 locaciones nuevas, casi un año antes de la producción.** En las cinco áreas,
de 2020 a 2026, siguiendo el contraste de cada locación contra el monte vecino mes a mes:

| | Mediana |
|---|---|
| Locaciones nuevas detectadas | 167 de 177 (94 %), 725 pozos |
| Adelanto sobre el inicio de perforación | 2,3 meses (la ve antes en el 85 %) |
| Adelanto sobre la primera producción | 9,5 meses |
| Falsas alarmas en el monte | 2 a 9 % según la zona |

El satélite no adelanta mucho la perforación, porque el operador desmonta la locación poco antes de
traer el equipo. Lo que adelanta es la producción.

![La locación aparece de golpe](docs/figures/series_locaciones.png)

![El adelanto](docs/figures/adelanto.png)

**A ciegas, y con la prueba hacia atrás.** Sin mirar el padrón, el detector encuentra 422 obras nuevas
en las cuatro ventanas; 186 se clasifican como locación con una regla de tamaño y fuerza del salto
(recall 81 %, precisión 94 % en 48 detecciones etiquetadas, dejando una afuera; la forma no separa: un
cruce de caminos es tan compacto como una locación). Después, para cada una, en el mes en que se vio:

| Lo que vio el satélite, sin pozo perforado al lado | Recibió un pozo después |
|---|---|
| Locaciones vistas hace al menos 12 meses | 73 % (98 de 135) |
| Resto de las detecciones (caminos, plantas, pueblo) | 12 % (22 de 185) |
| Puntos al azar en las mismas zonas | 1 % (23 de 2.313) |

La espera mediana entre la locación visible y el inicio de perforación es de 1,9 meses.

**Lo que el satélite ve y el padrón todavía no.** 28 locaciones vistas desde julio de 2025 no tienen
hoy ningún pozo registrado a menos de 150 metros. El padrón carga los pozos nuevos con unos seis
meses de demora: en las cuatro ventanas registra entre 20 y 48 pozos por trimestre de inicio de
perforación hasta el primero de 2026, y 8 en el segundo. Mirando cada una en la escena de septiembre y octubre
de 2026:

| Estado en octubre de 2026 | Locaciones |
|---|---|
| Con equipos trabajando | 12 |
| Locación construida, sin equipo todavía | 8 |
| Instalación o locación con actividad | 2 |
| Dudosa | 1 |
| Falsa (pueblo, valle, barda) | 5 |

Veintidós obras reales sin pozo en ningún registro público. La confirmación por el padrón llega a
comienzos de 2027. Las coordenadas no se publican.

**CBERS-4A no cubre Vaca Muerta.** El catálogo abierto del INPE no tiene ninguna escena CBERS-4A sobre
Neuquén entre 2019 y 2026. Para la cuenca, el satélite es Sentinel-2.

## El tablero

<https://dpinero14.github.io/locaciones-lab/tablero/>

El detector corrido sobre quince ventanas de la cuenca (`scripts/detectar.py`), en un mapa: mes a mes,
cada locación aparece cuando el satélite la ve y el pozo del padrón cuando llega. Suma los gasoductos
troncales y las plantas compresoras de ENARGAS, la ruta de la arena de
[arena-lab](https://github.com/dpinero14/arena-lab), un mapa de calor de producción contra exploración y
dos pestañas:

- **Demanda:** pozos fracturados, etapas, arena, agua, camiones y equipos por año desde 2019, del
  Adjunto IV de fracturas, con la proyección de 2027 a partir de las locaciones que ya se ven.
- **Finanzas:** la producción nueva por operadora con la curva tipo de la cuenca, y la facturación y las
  regalías al precio que elija quien lo mira.

Es la versión pública: las locaciones que todavía no tienen pozo registrado no se publican, entran solo
como conteo por ventana.

## Limitaciones

- **Cuatro ventanas, cinco áreas.** Loma Campana, La Amarga Chica, Bajada del Palo, Bandurria y Fortín
  de Piedra: el corazón de la actividad, no toda la cuenca.
- **Una escena por mes.** El satélite pasa cada 5 días; la serie mensual alcanza para fechar locaciones
  pero no para ver el equipo de perforación llegar y irse.
- **La ampliación de un pad viejo** también se enciende: es actividad real, pero no es una locación
  nueva. En el notebook 01, una de cada cinco locaciones viejas "se construye" en la serie.
- **La regla de clasificación** está ajustada con 48 etiquetas hechas por una persona. Es poco; una
  muestra mayor y etiquetada por otro la haría más confiable.
- **El padrón como verdad** tiene su propio atraso y sus errores. Un pozo a menos de 150 m de la
  detección cuenta como acierto aunque sea de otra locación vecina.
- **El cerca de Añelo** es difícil: el pueblo crece y confunde al detector; la regla lo excluye.

## Cómo correrlo

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m ipykernel install --user --name locaciones-lab --display-name "locaciones-lab"
.venv\Scripts\python.exe scripts/download_data.py --series
.venv\Scripts\python.exe -m pytest -q tests
.venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute --inplace notebooks/01_la_locacion_se_ve.ipynb
.venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute --inplace notebooks/02_el_detector_a_ciegas.ipynb
```

La serie de Sentinel-2 son unas 80 escenas por zona recortadas a la ventana, unos 3 GB y 40 minutos
por zona. En Linux, en lugar de `.venv\Scripts\python.exe`, `.venv/bin/python`.

## Datos y licencias

- Copernicus Sentinel-2 L2A (ESA), por el catálogo STAC público de Element84 en AWS:
  <https://earth-search.aws.element84.com/v1>. Datos libres y abiertos de Copernicus.
- Secretaría de Energía, Capítulo IV: shapefile de pozos y producción de pozos no convencionales,
  CC BY 4.0: <http://datos.energia.gob.ar/dataset/c846e79c-026c-4040-897f-1ad3543b407c>
- `data/etiquetas_muestra.csv`: 48 detecciones etiquetadas a mano, sin coordenadas.
- `data/verificacion_visual_2026-10.csv`: la verificación visual de las 28 locaciones sin pozo, sin
  coordenadas.

Código con licencia MIT.

## Autor

Diego Piñero · Sur Analytics
