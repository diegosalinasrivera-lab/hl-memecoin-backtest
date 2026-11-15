# Backtest "tablero / odd-one-out" — memecoins — Hyperliquid 15m

Backtest de simulación (NO dinero real) de la estrategia descrita por el
usuario, sobre velas de 15 minutos de 23 memecoins, usando la **API pública
de Hyperliquid** (sin cuenta, sin API key).

## ⚠️ Cambios respecto al pedido original (y por qué)

1. **Fuente de datos: Hyperliquid, no Binance.** El usuario pidió
   explícitamente no usar Binance. Se migró todo a la API pública de
   Hyperliquid (`https://api.hyperliquid.xyz/info`).

2. **Ventana de historia: ~52 días, no 6-12 meses.** El endpoint
   `candleSnapshot` de Hyperliquid, para velas de 15 minutos, **sólo sirve
   los últimos ~5000 registros (~52 días) sin importar qué `startTime` se
   pida** — se verificó pidiendo rangos de 270 y 400 días y paginando hacia
   atrás: la API simplemente no devuelve nada más viejo, en ningún activo
   probado (DOGE, BTC, etc.). No es un límite de nuestro código, es un
   límite real de los datos servidos por Hyperliquid para ese timeframe.
   El usuario confirmó seguir adelante con el máximo real disponible
   (~52 días, del **2026-09-24 al 2026-11-15**) en vez de buscar otra
   fuente o cambiar de timeframe.

3. **BROCCOLI714 y BANANAS31 no existen en Hyperliquid** (son listados
   exclusivos de Binance Alpha/Futures). **DOGS (`kDOGS`) existe en el
   universo de Hyperliquid pero no tiene velas recientes** (mercado sin
   actividad reciente). Las tres se excluyeron y se reemplazaron por otras
   memecoins líquidas para completar 23 monedas: **TURBO, ANIME, MELANIA**
   (sumadas a las 13 elegidas originalmente). Ver `config.py` →
   `REQUESTED_MAP` / `EXTRA_COINS` para el detalle completo del mapeo.

## Universo final (23 monedas, ticker real en Hyperliquid)

DOGE, kPEPE (PEPE), WIF, BOME, kNEIRO (NEIRO), TRUMP, PEOPLE, kBONK (BONK),
kFLOKI (FLOKI), kSHIB (SHIB), MEME, POPCAT, TURBO, NOT, BRETT, HMSTR, GOAT,
MOODENG, PNUT, FARTCOIN, ANIME, MELANIA, PENGU.

## Interpretación de las reglas de la estrategia

El enunciado original es una descripción discrecional/manual de trading;
para poder backtestearlo se tradujo a reglas mecánicas exactas (ver
`strategy.py` para el detalle completo, código y comentarios):

- **Tablero**: en cada vela de 15m, si la mayoría de las 23 monedas cerró
  roja → sesgo corto; si la mayoría cerró verde → sesgo largo.
- **Odd one out**: de las monedas que van contra el tablero, se opera la
  más "desobediente" (mayor variación % en sentido contrario).
- **Vela fuerte en contra**: si la mayoría de las monedas sube (o baja)
  ≥1.5% en una sola vela de 15m, en la vela siguiente se opera en contra
  de la más extrema, ignorando la señal normal de odd-one-out.
- **Flush + rebote único**: si el retorno mediano de las monedas en una
  vela es ≤ -2% ("flush"), la vela siguiente se opera **siempre long**
  (un solo rebote, sobre la moneda más castigada), y la vela subsiguiente
  se fuerza **short** (se vende el rebote) antes de volver a la lógica
  normal.
- **Pausa de 45 min**: tras 2 stops seguidos, no se abren posiciones
  nuevas durante 3 velas (45 min).
- **Máximo 5 posiciones abiertas simultáneas.**
- **Stop-loss**: 0.5%-1% de precio por posición (caso base: 0.75%,
  chequeado contra el high/low de la vela siguiente a la entrada).
- **Duración de cada operación**: 1 vela (se entra al cierre de la vela
  señal, se sale al cierre de la vela siguiente, o antes si se dispara el
  stop intravela). No hay en el enunciado una regla de "cuánto se
  mantiene" la posición más allá del esquema de reacción vela-a-vela, así
  que se asumió el horizonte más consistente con el resto de las reglas
  (reaccionar cada 15 min).
- **Tamaño de posición**: capital_actual / 5 como margen por slot
  (recalculado dinámicamente con el equity vigente, no fijo al capital
  inicial) — notional = margen × leverage.
- **Costos**: 0.035% de comisión taker + 0.03% de slippage, por lado
  (entrada y salida) → 0.13% de costo de ida y vuelta antes de leverage.
  El costo se multiplica por el leverage (porque se aplica sobre el
  notional, no sobre el margen).
- **Capital inicial**: 146 USD.

## Resultado del backtest

**La estrategia, tal como está especificada, pierde la enorme mayoría del
capital en los tres escenarios de apalancamiento, en la ventana de datos
disponible (~52 días, 2026-09-24 a 2026-11-15):**

| Leverage | Capital final | Retorno total | Drawdown máx | # Trades | % Ganadores | % Stopped |
|---|---|---|---|---|---|---|
| 3x  | $5.35  | -96.3%  | -96.3%  | 4207 | 33.4% | 11.9% |
| 5x  | $0.58  | -99.6%  | -99.6%  | 4207 | 33.4% | 11.9% |
| 25x | ~$0.00 | -100.0% | -100.0% | 4207 | 33.4% | 11.9% |

(stop-loss base 0.75%; ver `output/summary_by_leverage.csv` para el detalle
exacto y `output/robustness_*.csv` para sin-mejor-moneda / sin-mejor-día)

### Por qué pierde tanto

- La regla de "odd one out" genera señal en **prácticamente cada vela**
  (4487 de 4542 señales totales son odd-one-out puro) → la estrategia
  entra y sale de posiciones casi 4200 veces en 52 días (~80/día). Con un
  win rate real de ~33%, la expectativa neta por operación ya es negativa
  **antes** de costos, y el costo de ida y vuelta (0.13% × leverage) sobre
  cada una de esas ~4200 operaciones termina de destruir el capital. A
  mayor leverage, el costo fijo en % también escala, por eso 25x es
  prácticamente ruina garantizada y 3x "sólo" pierde el 96%.
- El universo entero de memecoins cayó en la ventana analizada (régimen
  "bajista" en los dos meses completos cubiertos — ver
  `output/regime_*.csv`), lo que además sesga mal a una estrategia que
  gran parte del tiempo está comprando el "odd one out" verde contra un
  tablero rojo (comprando rebotes en tendencia bajista).
- La prueba de robustez confirma que el resultado **no** depende de un
  golpe de suerte puntual: quitando la mejor moneda o el mejor día
  individual, el retorno total apenas cambia (sigue siendo fuertemente
  negativo) — la pérdida está distribuida en miles de trades, no
  concentrada.

### Sensibilidad de stop-loss (leverage 5x)

| Stop-loss | Capital final | Retorno | # Trades | % Stopped |
|---|---|---|---|---|
| 0.5% | $1.35 | -99.1% | 3833 | 21.2% |
| 1.0% | $0.32 | -99.8% | 4408 | 7.3% |

Un stop más ajustado (0.5%) corta pérdidas antes pero igual no evita el
resultado catastrófico, porque el problema de fondo es la frecuencia de
operación y el costo de transacción, no el tamaño del stop.

## Cómo correrlo

```bash
pip install pandas numpy matplotlib
python3 main.py
```

Los datos se cachean en `data/*.csv` (no se vuelven a descargar si ya
existen). Los resultados (trades, curvas de equity, desgloses mensuales,
por régimen, y robustez, para cada leverage) quedan en `output/`.

## Limitaciones / honestidad de los resultados

- **Ventana corta (~52 días)**: no hay 6-12 meses de velas de 15m
  disponibles vía la API pública de Hyperliquid para este timeframe; el
  usuario confirmó avanzar con el máximo real. Con 52 días, sólo se cubren
  2 meses completos de régimen "bajista" — no hay datos de régimen
  alcista o lateral en esta ventana, así que esas filas no existen en el
  desglose por régimen.
- **Interpretación de reglas**: el enunciado es discrecional (lenguaje de
  trading manual); las reglas mecánicas usadas son una traducción
  razonable pero no la única posible — otra interpretación (p. ej. otro
  umbral de "vela fuerte", otra duración de la operación, o permitir
  pirámidar posiciones) podría dar resultados distintos.
- **Esto es sólo una simulación histórica**, no una recomendación de
  trading ni garantía de resultados futuros. No se operó ni se va a
  operar con dinero real.
