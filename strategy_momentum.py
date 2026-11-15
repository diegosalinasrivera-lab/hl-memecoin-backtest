"""Variante 'momentum / trend-following' de la estrategia de tablero.

Es la hipótesis contraria a `strategy.py` (odd-one-out / mean-reversion):
en vez de apostar CONTRA la mayoría del tablero, se apuesta A FAVOR.

Reglas:

1. Tablero: igual que la versión original (consenso mínimo configurable
   de monedas del mismo color).

2. Líder (en vez de odd-one-out): de las monedas que van EN EL MISMO
   sentido que el tablero, se opera la más "obediente" (mayor variación
   porcentual en el sentido del tablero) — se sigue al líder del
   movimiento, no al que se le opone.

3. Vela fuerte: en vez de operar en contra en la vela siguiente
   (fade), se opera A FAVOR de la moneda que tuvo el movimiento más
   fuerte (continuación del momentum).

4. Flush: no hay regla de "rebote único" (esa regla es, por diseño,
   contrarian). Tras una vela de flush (caída agregada fuerte) se
   continúa corto en la vela siguiente, sobre la moneda más castigada
   (se sigue la caída en vez de comprar el rebote).

5-7. Pausa de 45 min tras 2 stops, máximo 5 posiciones, stop-loss por
   precio: idénticas a la versión original, implementadas por el mismo
   motor de backtest (`backtest.py`), agnóstico a cómo se generan las
   señales.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from config import STRONG_MOVE_PCT, FLUSH_PCT, MAJORITY_FRACTION, MIN_BOARD_CONSENSUS, MIN_ODD_ONE_OUT_DEVIATION
from strategy import Signal


def generate_signals_momentum(
    board: pd.DataFrame,
    coins: list[str],
    min_board_consensus: float = MIN_BOARD_CONSENSUS,
    min_leader_deviation: float = MIN_ODD_ONE_OUT_DEVIATION,
) -> list[Signal]:
    signals: list[Signal] = []

    n_coins = len(coins)
    majority_n = int(np.ceil(n_coins * MAJORITY_FRACTION))

    pending_flush_continuation = False

    timestamps = board.index
    for i in range(len(timestamps) - 1):
        colors = {c: board[(c, "color")].iloc[i] for c in coins}
        rets = {c: board[(c, "ret")].iloc[i] for c in coins}

        n_green = sum(1 for v in colors.values() if v > 0)
        n_red = n_coins - n_green
        if n_green / n_coins >= min_board_consensus:
            board_bias = "long"
        elif n_red / n_coins >= min_board_consensus:
            board_bias = "short"
        else:
            board_bias = None

        median_ret = float(np.median(list(rets.values())))
        n_strong_up = sum(1 for r in rets.values() if r >= STRONG_MOVE_PCT)
        n_strong_down = sum(1 for r in rets.values() if r <= -STRONG_MOVE_PCT)
        is_flush = median_ret <= -FLUSH_PCT

        next_ts = timestamps[i + 1]
        chosen: Optional[Signal] = None

        if pending_flush_continuation:
            worst_coin = min(rets, key=rets.get)
            chosen = Signal(next_ts, worst_coin, "short", "flush_continuation")
            pending_flush_continuation = False

        elif n_strong_up >= majority_n:
            best_coin = max(rets, key=rets.get)
            chosen = Signal(next_ts, best_coin, "long", "momentum_strong_move")

        elif n_strong_down >= majority_n:
            worst_coin = min(rets, key=rets.get)
            chosen = Signal(next_ts, worst_coin, "short", "momentum_strong_move")

        elif board_bias is not None:
            # líder: moneda a favor del tablero con mayor desvío
            if board_bias == "long":
                candidates = {c: r for c, r in rets.items() if colors[c] > 0}
                if candidates:
                    leader = max(candidates, key=candidates.get)
                    if candidates[leader] >= min_leader_deviation:
                        chosen = Signal(next_ts, leader, "long", "momentum_leader")
            else:
                candidates = {c: r for c, r in rets.items() if colors[c] < 0}
                if candidates:
                    leader = min(candidates, key=candidates.get)
                    if candidates[leader] <= -min_leader_deviation:
                        chosen = Signal(next_ts, leader, "short", "momentum_leader")

        if is_flush:
            pending_flush_continuation = True

        if chosen is not None:
            signals.append(chosen)

    return signals
