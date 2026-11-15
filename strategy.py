"""Lógica de la estrategia 'tablero / odd-one-out' sobre velas de 15 min.

Reglas implementadas (interpretación del enunciado, documentada en el README):

1. Tablero: en cada vela cerrada, si la mayoría de las monedas cerró roja
   (close < open) -> sesgo CORTO del tablero; si la mayoría cerró verde
   -> sesgo LARGO.

2. Odd one out: de las monedas que van en contra del tablero (verdes en
   tablero rojo, o rojas en tablero verde), se opera la más "desobediente"
   (mayor variación porcentual en sentido contrario al tablero). Esa
   moneda es la candidata de entrada: si el tablero es verde y ella cerró
   roja -> short; si el tablero es rojo y ella cerró verde -> long.

3. Vela fuerte en contra del tablero: si la MAYORÍA de las monedas tuvo
   una vela con variación >= STRONG_MOVE_PCT en una sola vela (hacia
   arriba o hacia abajo), en la vela SIGUIENTE se fuerza una señal de
   contrarian sobre el tablero completo (si fue fuerte al alza -> short;
   si fue fuerte a la baja -> long), reemplazando a la señal normal de
   odd-one-out para ese tick.

4. Flush + rebote único: una vela de "flush" es una vela con caída
   agregada (retorno mediano de la mayoría) <= -FLUSH_PCT. Tras un flush,
   la vela siguiente se opera SIEMPRE long (el rebote), una sola vez;
   la vela subsiguiente a ese rebote vuelve al sesgo corto (se fuerza
   short en esa vela, ignorando el cálculo normal del tablero, para
   representar la vuelta a vender el rebote).

5. Pausa de 45 min (3 velas de 15m) tras 2 stops seguidos: no se abren
   posiciones nuevas durante esas 3 velas.

6. Máximo 5 posiciones abiertas simultáneas.

7. Cada posición lleva un stop-loss fijo en % de precio (configurable,
   0.5%-1%), chequeado contra el high/low de la vela siguiente a la
   entrada. Cada operación dura exactamente 1 vela (se entra al cierre
   de la vela señal y se sale al cierre de la vela siguiente, o antes si
   se dispara el stop intravela).
"""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from config import (
    STRONG_MOVE_PCT,
    FLUSH_PCT,
    MAJORITY_FRACTION,
    MIN_BOARD_CONSENSUS,
    MIN_ODD_ONE_OUT_DEVIATION,
)


@dataclass
class Signal:
    ts: pd.Timestamp
    coin: str
    side: str          # "long" | "short"
    reason: str         # "odd_one_out" | "fade_strong_move" | "flush_bounce" | "flush_resume_short"


def build_board_frame(panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Combina los closes/returns de todas las monedas en un panel alineado
    por timestamp (open_time). Devuelve un DataFrame con MultiIndex de
    columnas (coin, field)."""
    frames = []
    for coin, df in panel.items():
        d = df.set_index("open_time")[["open", "high", "low", "close"]].copy()
        d["ret"] = d["close"] / d["open"] - 1.0
        d["color"] = np.where(d["ret"] >= 0, 1, -1)  # 1 verde, -1 roja
        d.columns = pd.MultiIndex.from_product([[coin], d.columns])
        frames.append(d)
    board = pd.concat(frames, axis=1, join="inner").sort_index()
    return board


def generate_signals(board: pd.DataFrame, coins: list[str]) -> list[Signal]:
    """Recorre el panel vela por vela y genera las señales de entrada según
    las reglas 1-4 descritas arriba. No aplica todavía gestión de riesgo
    (eso lo hace el motor de backtest)."""
    signals: list[Signal] = []

    n_coins = len(coins)
    majority_n = int(np.ceil(n_coins * MAJORITY_FRACTION))

    pending_bounce = False      # próxima vela debe ser rebote largo forzado
    pending_short_resume = False  # vela después del rebote: forzar short

    timestamps = board.index
    for i in range(len(timestamps) - 1):
        ts = timestamps[i]
        colors = {c: board[(c, "color")].iloc[i] for c in coins}
        rets = {c: board[(c, "ret")].iloc[i] for c in coins}

        n_green = sum(1 for v in colors.values() if v > 0)
        n_red = n_coins - n_green
        # ajuste v2: el sesgo de tablero sólo cuenta si hay consenso fuerte
        # (>=MIN_BOARD_CONSENSUS de las monedas del mismo color), no con
        # una simple mayoría de 1 voto.
        if n_green / n_coins >= MIN_BOARD_CONSENSUS:
            board_bias = "long"
        elif n_red / n_coins >= MIN_BOARD_CONSENSUS:
            board_bias = "short"
        else:
            board_bias = None

        median_ret = float(np.median(list(rets.values())))
        n_strong_up = sum(1 for r in rets.values() if r >= STRONG_MOVE_PCT)
        n_strong_down = sum(1 for r in rets.values() if r <= -STRONG_MOVE_PCT)
        is_flush = median_ret <= -FLUSH_PCT

        next_ts = timestamps[i + 1]
        chosen: Optional[Signal] = None

        # Prioridad de reglas: rebote forzado > resume-short forzado >
        # fade de vela fuerte > odd-one-out normal.
        if pending_bounce:
            # el rebote se opera sobre la moneda más castigada (mayor caída)
            worst_coin = min(rets, key=rets.get)
            chosen = Signal(next_ts, worst_coin, "long", "flush_bounce")
            pending_bounce = False
            pending_short_resume = True

        elif pending_short_resume:
            best_coin = max(rets, key=rets.get)
            chosen = Signal(next_ts, best_coin, "short", "flush_resume_short")
            pending_short_resume = False

        elif n_strong_up >= majority_n:
            best_coin = max(rets, key=rets.get)
            chosen = Signal(next_ts, best_coin, "short", "fade_strong_move")

        elif n_strong_down >= majority_n:
            worst_coin = min(rets, key=rets.get)
            chosen = Signal(next_ts, worst_coin, "long", "fade_strong_move")

        elif board_bias is not None:
            # odd one out: moneda en contra del tablero con mayor desvío,
            # pero sólo si ese desvío es >= MIN_ODD_ONE_OUT_DEVIATION
            # (ajuste v2: filtra ruido de baja magnitud que antes
            # generaba señal en casi cada vela).
            if board_bias == "long":
                candidates = {c: r for c, r in rets.items() if colors[c] < 0}
                if candidates:
                    odd_coin = min(candidates, key=candidates.get)
                    if candidates[odd_coin] <= -MIN_ODD_ONE_OUT_DEVIATION:
                        chosen = Signal(next_ts, odd_coin, "short", "odd_one_out")
            else:
                candidates = {c: r for c, r in rets.items() if colors[c] > 0}
                if candidates:
                    odd_coin = max(candidates, key=candidates.get)
                    if candidates[odd_coin] >= MIN_ODD_ONE_OUT_DEVIATION:
                        chosen = Signal(next_ts, odd_coin, "long", "odd_one_out")

        if is_flush:
            pending_bounce = True
            pending_short_resume = False

        if chosen is not None:
            signals.append(chosen)

    return signals
