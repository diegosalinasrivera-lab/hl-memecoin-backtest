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

## Resultado del backtest — v1 (sin filtros)

**La estrategia, tal como está especificada literalmente (sin filtro de
magnitud), pierde la enorme mayoría del capital en los tres escenarios de
apalancamiento, en la ventana de datos disponible (~52 días, 2026-09-24 a
2026-11-15):**

| Leverage | Capital final | Retorno total | Drawdown máx | # Trades | % Ganadores | % Stopped |
|---|---|---|---|---|---|---|
| 3x  | $5.35  | -96.3%  | -96.3%  | 4207 | 33.4% | 11.9% |
| 5x  | $0.58  | -99.6%  | -99.6%  | 4207 | 33.4% | 11.9% |
| 25x | ~$0.00 | -100.0% | -100.0% | 4207 | 33.4% | 11.9% |

### Por qué perdía tanto

- La regla de "odd one out" generaba señal en **prácticamente cada vela**
  (4487 de 4542 señales totales eran odd-one-out puro) → la estrategia
  entraba y salía de posiciones casi 4200 veces en 52 días (~80/día). Con
  un win rate real de ~33%, la expectativa neta por operación ya era
  negativa **antes** de costos, y el costo de ida y vuelta (0.13% ×
  leverage) sobre cada una de esas ~4200 operaciones terminaba de destruir
  el capital.
- El universo entero de memecoins cayó en la ventana analizada (régimen
  "bajista" en los dos meses completos cubiertos), lo que además sesgaba
  mal a una estrategia que gran parte del tiempo compra el "odd one out"
  verde contra un tablero rojo (comprando rebotes en tendencia bajista).
- La prueba de robustez confirmó que el resultado no dependía de un golpe
  de suerte puntual: sin la mejor moneda o el mejor día, el retorno apenas
  cambiaba — la pérdida estaba distribuida en miles de trades.

### Sensibilidad de stop-loss v1 (leverage 5x)

| Stop-loss | Capital final | Retorno | # Trades | % Stopped |
|---|---|---|---|---|
| 0.5% | $1.35 | -99.1% | 3833 | 21.2% |
| 1.0% | $0.32 | -99.8% | 4408 | 7.3% |

## Ajuste v2: filtros anti-sobre-trading

Para no "operar prácticamente cada vela", se agregaron dos filtros
(`config.py` → `MIN_BOARD_CONSENSUS`, `MIN_ODD_ONE_OUT_DEVIATION`,
aplicados en `strategy.py`):

- **Consenso de tablero mínimo 65%** (antes: simple mayoría >50%): el
  sesgo del tablero sólo cuenta si al menos 65% de las 23 monedas
  cerraron del mismo color en esa vela.
- **Desvío mínimo del odd-one-out: 0.6%**: la moneda candidata sólo se
  opera si se movió al menos 0.6% en contra del tablero (antes: se
  operaba cualquier desvío, sin importar cuán chico).

### Resultado v2

| Leverage | Capital final | Retorno total | Drawdown máx | # Trades | % Ganadores | % Stopped |
|---|---|---|---|---|---|---|
| 3x  | $93.08 | -36.2% | -36.5% | 537 | 31.5% | 24.8% |
| 5x  | $68.50 | -53.1% | -53.4% | 537 | 31.5% | 24.8% |
| 25x | $2.43  | -98.3% | -98.4% | 537 | 31.5% | 24.8% |

Los filtros bajaron los trades de 4207 a 537 (-87%), y el resultado dejó
de ser una ruina total: 3x pasó de -96% a -36%. **Pero la estrategia
sigue perdiendo dinero en los tres escenarios.** El win rate real
(~31%) sigue por debajo del punto de equilibrio que necesita el payoff de
este setup (stop 0.75%, 1 vela de duración); los filtros redujeron el
sangrado por costos de transacción, pero no cambian el problema de fondo:
**en esta muestra (100% bajista), comprar el "odd one out" contra la
tendencia dominante no tiene edge positivo**, aunque ahora pierde menos y
más despacio. La prueba de robustez (sin mejor moneda / sin mejor día,
`output/robustness_*.csv`) confirma que tampoco este resultado depende de
un golpe de suerte puntual.

### Sensibilidad de stop-loss v2 (leverage 5x)

| Stop-loss | Capital final | Retorno | # Trades | % Stopped |
|---|---|---|---|---|
| 0.5% | $73.65 | -49.6% | 500 | 38.4% |
| 1.0% | $59.84 | -59.0% | 544 | 17.3% |

### Próximos pasos posibles (no implementados todavía)

- Probar la estrategia sobre un período con régimen alcista o lateral
  (requiere otra fuente de datos con más historia, ver limitaciones).
- Exigir confirmación de reversión (p. ej. que la vela siguiente a la
  señal también vaya en el sentido de la operación) antes de entrar.
- Ampliar la duración de la posición más allá de 1 vela, o usar un
  take-profit en vez de salir siempre al cierre de la vela siguiente.

## Barrido de sensibilidad de los filtros v2 (`sweep_filters.py`)

Para no quedarnos con un solo par de umbrales elegido a mano, se corrió
un grid completo de 7×6 = 42 combinaciones de `MIN_BOARD_CONSENSUS`
(50%-80%) × `MIN_ODD_ONE_OUT_DEVIATION` (0%-2.0%), con leverage 5x fijo,
sobre los mismos datos de Hyperliquid (~52 días). Resultado completo en
`output/sweep_filters.csv`.

**Ninguna de las 42 combinaciones dio retorno positivo.** La mejor fue
consenso=50% + desvío mínimo=2.0%: -10.5% de retorno (72 trades, 36% de
ganadores) — la pérdida más chica de todo el grid, pero sigue siendo
pérdida. En el otro extremo, sin filtro de desvío (0%) cualquier nivel de
consenso vuelve a perder 93-100%, confirmando que el filtro de magnitud
es el que más aporta.

**Conclusión del barrido**: esto no es un problema de calibración de
parámetros. Ajustar los umbrales reduce cuánto se pierde (de -96% a
-10.5% en el mejor caso), pero no revierte el signo — la premisa de
comprar/vender el "odd one out" contra el tablero no tiene edge positivo
en esta muestra, sin importar qué tan selectivos sean los filtros.
Además, elegir la "mejor" combinación mirando el mismo tramo de datos
que se usa para evaluarla es sobreajuste (overfitting): no hay garantía
de que esos umbrales sigan siendo los mejores fuera de esta muestra.

**⚠️ Esto NO es una base para operar con dinero real.** El usuario
planteó usar esta estrategia con capital real; dado que ninguna
configuración probada hasta ahora es rentable (ni siquiera ajustando los
parámetros a medida sobre los propios datos de prueba), la recomendación
explícita fue no avanzar a ejecución real todavía. Antes de considerar
capital real haría falta: (1) validar out-of-sample con datos que el
barrido nunca vio, (2) paper trading en vivo por varias semanas, y (3)
sólo entonces capital chico y leverage bajo — nunca 25x sobre $146 en
memecoins con un win rate real de ~31-36%.

## Resultado con 12 meses reales (OKX) — confirmación final

Con la fuente de datos OKX (`main_okx.py`, `config_okx.py`), se corrió el
mismo motor de estrategia (filtros v2 con los umbrales por defecto:
consenso 65%, desvío mínimo 0.6%) sobre **12 meses completos y reales**
(35039 velas de 15m, 2025-11-15 a 2026-11-15), con régimen de mercado
mixto: **9 meses bajistas, 3 alcistas**, ningún mes lateral puro.

| Leverage | Capital final | Retorno total | Drawdown máx | # Trades | % Ganadores | % Stopped |
|---|---|---|---|---|---|---|
| 3x  | $3.74  | -97.4%  | -97.4%  | 4723 | 36.2% | 36.5% |
| 5x  | $0.30  | -99.8%  | -99.8%  | 4723 | 36.2% | 36.5% |
| 25x | ~$0.00 | -100.0% | -100.0% | 4723 | 36.2% | 36.5% |

### Desglose por régimen (leverage 3x)

| Régimen | PnL total | # Trades | % Ganadores |
|---|---|---|---|
| Alcista | -$6.61  | 1172 | 37.5% |
| Bajista | -$121.68 | 3328 | 35.9% |
| N/D (primer mes, sin baseline) | -$13.97 | 223 | 34.1% |

**Esto descarta la hipótesis de que el resultado negativo con Hyperliquid
era sólo producto de una muestra 100% bajista.** Con un año completo y
régimen mixto (9 bajista / 3 alcista), **la estrategia pierde dinero en
ambos regímenes** — mucho menos en el alcista (-$6.6 vs -$121.7), pero
sigue siendo negativa incluso ahí. La prueba de robustez (sin mejor
moneda / sin mejor día, ver `output_okx/robustness_*.csv`) confirma de
nuevo que no es un resultado dependiente de un golpe de suerte puntual:
quitando a TURBO (la moneda más rentable) o el mejor día individual, el
retorno total empeora.

**Conclusión general del proyecto**: la premisa de "tablero / odd one
out" tal como fue especificada —comprar o vender la moneda que se mueve
contra la mayoría— no tiene edge positivo en memecoins perpetuos de 15m,
ni en la muestra corta bajista de Hyperliquid, ni en los 12 meses de
régimen mixto de OKX, ni ajustando los filtros de selectividad (barrido
de 42 combinaciones, 0 rentables). **No es una base para operar con
dinero real** bajo ninguna de las configuraciones probadas.

## Variante momentum (trend-following) — también probada, también pierde

Ante la pregunta de si una hipótesis distinta (ir A FAVOR del tablero en
vez de en contra) podría ser rentable, se implementó `strategy_momentum.py`
/ `main_momentum.py`: mismo motor de backtest y gestión de riesgo, misma
ventana de 12 meses de OKX, pero en vez de operar el "odd one out"
(moneda que va contra la mayoría) se opera el "líder" (moneda que va más
a favor de la mayoría), y en vez de "fade" de vela fuerte se sigue la
continuación del movimiento.

| Leverage | Momentum | Mean-reversion (original) |
|---|---|---|
| 3x  | **-99.9998%** | -97.4% |
| 5x  | **-100.0%**   | -99.8% |
| 25x | **-100.0%**   | -100.0% |

**Momentum es peor, no mejor.** El filtro de "líder" (moneda a favor del
tablero) se cumple con mucha más frecuencia que el de "odd one out"
(moneda en contra, por definición más rara), generando 16.565 trades
(vs. 4.723 del original) con el mismo ~36% de aciertos — más del triple
de operaciones al mismo costo por operación, ruina total garantizada en
los tres leverages. Ni siquiera en los meses alcistas da positivo: a 3x
el PnL en régimen alcista es -$0.45 sobre 4054 trades, prácticamente
plano pero nunca ganador.

**Conclusión general (actualizada)**: ni la hipótesis de mean-reversion
("apostar contra el que se desvía") ni la de momentum ("apostar con el
líder del movimiento") tienen edge positivo en este universo de
memecoins perpetuos de 15m, en ninguna de las ventanas de datos
probadas (52 días Hyperliquid, 12 meses OKX), con ningún apalancamiento,
y ajustando filtros de selectividad no cambia el signo del resultado.
Buscar la rentabilidad probando más activos sobre la misma mecánica no
es un camino razonable: con suficientes intentos, algún activo mostrará
un resultado positivo por puro azar (comparaciones múltiples), sin que
eso implique una ventaja real. Si se quiere seguir explorando, el
siguiente paso razonable sería una lógica distinta (basada en
liquidez, funding rate, correlación con BTC, o un horizonte de holding
más largo), no repetir este mecanismo sobre más tickers.

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
