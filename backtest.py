"""Motor de simulación: toma las señales generadas por `strategy.py` y las
ejecuta con gestión de riesgo (tamaño de posición, stop-loss, máximo de
posiciones abiertas, pausa tras 2 stops seguidos, apalancamiento, comisiones
y slippage). Cada operación dura 1 vela de 15 min como máximo (se cierra al
close de la vela siguiente a la entrada, salvo que el stop se dispare antes
usando el high/low de esa vela)."""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from config import (
    MAX_OPEN_POSITIONS,
    PAUSE_BARS_AFTER_2_STOPS,
    ROUND_TRIP_COST_PCT,
    INITIAL_CAPITAL,
)
from strategy import Signal


@dataclass
class Trade:
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    coin: str
    side: str
    reason: str
    entry_price: float
    exit_price: float
    leverage: int
    stop_loss_pct: float
    margin: float
    pnl_usd: float
    pnl_pct_on_margin: float
    stopped_out: bool


def _bar_hit_stop(side: str, entry_price: float, stop_pct: float, high: float, low: float) -> bool:
    if side == "long":
        return low <= entry_price * (1 - stop_pct)
    else:
        return high >= entry_price * (1 + stop_pct)


def run_backtest(
    board: pd.DataFrame,
    signals: list[Signal],
    leverage: int,
    stop_loss_pct: float,
    initial_capital: float = INITIAL_CAPITAL,
    max_positions: int = MAX_OPEN_POSITIONS,
    round_trip_cost_pct: float = ROUND_TRIP_COST_PCT,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ejecuta el backtest para una combinación de leverage/stop dados.

    Devuelve (trades_df, equity_df).
    """
    signals_by_ts: dict[pd.Timestamp, list[Signal]] = {}
    for s in signals:
        signals_by_ts.setdefault(s.ts, []).append(s)

    timestamps = list(board.index)
    ts_to_idx = {ts: i for i, ts in enumerate(timestamps)}

    equity = initial_capital
    equity_curve = []  # (ts, equity)

    open_positions = []   # lista de dicts: coin, side, entry_price, entry_ts, exit_idx, margin, lev, stop_pct
    trades: list[Trade] = []

    consecutive_stops = 0
    pause_until_idx = -1

    for i, ts in enumerate(timestamps):
        # 1) liquidar posiciones que vencen en esta vela (abiertas en la vela anterior)
        still_open = []
        realized_pnl_this_bar = 0.0
        for pos in open_positions:
            if pos["exit_idx"] != i:
                still_open.append(pos)
                continue
            coin = pos["coin"]
            side = pos["side"]
            entry_price = pos["entry_price"]
            stop_pct = pos["stop_pct"]
            high = board[(coin, "high")].iloc[i]
            low = board[(coin, "low")].iloc[i]
            close = board[(coin, "close")].iloc[i]

            stopped = _bar_hit_stop(side, entry_price, stop_pct, high, low)
            if stopped:
                exit_price = (
                    entry_price * (1 - stop_pct) if side == "long" else entry_price * (1 + stop_pct)
                )
            else:
                exit_price = close

            raw_ret = (exit_price / entry_price - 1.0) if side == "long" else (entry_price / exit_price - 1.0)
            gross_pnl_pct = raw_ret * pos["leverage"]
            net_pnl_pct = gross_pnl_pct - round_trip_cost_pct * pos["leverage"]
            pnl_usd = pos["margin"] * net_pnl_pct

            trades.append(
                Trade(
                    entry_ts=pos["entry_ts"],
                    exit_ts=ts,
                    coin=coin,
                    side=side,
                    reason=pos["reason"],
                    entry_price=entry_price,
                    exit_price=exit_price,
                    leverage=pos["leverage"],
                    stop_loss_pct=stop_pct,
                    margin=pos["margin"],
                    pnl_usd=pnl_usd,
                    pnl_pct_on_margin=net_pnl_pct,
                    stopped_out=stopped,
                )
            )
            realized_pnl_this_bar += pnl_usd

            if stopped:
                consecutive_stops += 1
                if consecutive_stops >= 2:
                    pause_until_idx = i + PAUSE_BARS_AFTER_2_STOPS
            else:
                consecutive_stops = 0

        open_positions = still_open
        equity += realized_pnl_this_bar

        # 2) abrir nuevas posiciones señaladas para esta vela (si hay cupo y no estamos en pausa)
        todays_signals = signals_by_ts.get(ts, [])
        in_pause = i <= pause_until_idx
        if not in_pause:
            for sig in todays_signals:
                if len(open_positions) >= max_positions:
                    break
                if i + 1 >= len(timestamps):
                    continue  # no hay vela siguiente para salir
                if sig.coin not in board.columns.get_level_values(0):
                    continue
                entry_price = board[(sig.coin, "close")].iloc[i]
                margin = equity / max_positions  # tamaño por slot, basado en equity actual
                if margin <= 0:
                    continue
                open_positions.append(
                    {
                        "coin": sig.coin,
                        "side": sig.side,
                        "entry_price": entry_price,
                        "entry_ts": ts,
                        "exit_idx": i + 1,
                        "margin": margin,
                        "leverage": leverage,
                        "stop_pct": stop_loss_pct,
                        "reason": sig.reason,
                    }
                )

        equity_curve.append((ts, equity))

        if equity <= 0:
            # cuenta liquidada: dejamos de operar
            open_positions = []
            equity_curve.append((timestamps[-1], 0.0))
            break

    equity_df = pd.DataFrame(equity_curve, columns=["ts", "equity"]).drop_duplicates("ts", keep="last")
    trades_df = pd.DataFrame(
        [
            {
                "entry_ts": t.entry_ts,
                "exit_ts": t.exit_ts,
                "coin": t.coin,
                "side": t.side,
                "reason": t.reason,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "leverage": t.leverage,
                "stop_loss_pct": t.stop_loss_pct,
                "margin": t.margin,
                "pnl_usd": t.pnl_usd,
                "pnl_pct_on_margin": t.pnl_pct_on_margin,
                "stopped_out": t.stopped_out,
            }
            for t in trades
        ]
    )
    return trades_df, equity_df
