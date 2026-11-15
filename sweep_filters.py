"""Barrido de sensibilidad de los dos filtros anti-sobre-trading del
ajuste v2 (MIN_BOARD_CONSENSUS, MIN_ODD_ONE_OUT_DEVIATION), sobre los
datos de Hyperliquid (~52 días) ya descargados. Objetivo: ver si existe
alguna combinación de umbrales que vuelva la estrategia rentable, o al
menos identificar la mejor de un grid razonable, antes de repetir el
análisis con la ventana más larga de OKX.
"""
import itertools

import pandas as pd

from config import UNIVERSE, INITIAL_CAPITAL, DEFAULT_STOP_LOSS_PCT
from data_fetch import fetch_universe
from strategy import build_board_frame, generate_signals
from backtest import run_backtest
from metrics import summary_stats

LEVERAGE = 5  # leverage de referencia para el barrido (caso intermedio)

CONSENSUS_GRID = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
DEVIATION_GRID = [0.000, 0.003, 0.006, 0.010, 0.015, 0.020]


def main():
    print("Cargando datos (cache local)...")
    panel, skipped = fetch_universe(UNIVERSE)
    coins = list(panel.keys())
    board = build_board_frame(panel)
    print(f"Universo: {len(coins)} monedas. Panel: {len(board)} velas.")

    rows = []
    total = len(CONSENSUS_GRID) * len(DEVIATION_GRID)
    done = 0
    for consensus, deviation in itertools.product(CONSENSUS_GRID, DEVIATION_GRID):
        signals = generate_signals(
            board, coins,
            min_board_consensus=consensus,
            min_odd_one_out_deviation=deviation,
        )
        trades, equity = run_backtest(
            board, signals, leverage=LEVERAGE, stop_loss_pct=DEFAULT_STOP_LOSS_PCT,
            initial_capital=INITIAL_CAPITAL,
        )
        stats = summary_stats(trades, equity, INITIAL_CAPITAL)
        stats["min_board_consensus"] = consensus
        stats["min_odd_one_out_deviation"] = deviation
        rows.append(stats)
        done += 1
        print(f"[{done}/{total}] consensus={consensus:.2f} deviation={deviation:.3f} "
              f"-> retorno={stats.get('retorno_total_pct', float('nan')):.1f}% "
              f"trades={stats.get('num_trades', 0)} "
              f"win%={stats.get('pct_ganadores', float('nan')):.1f}")

    df = pd.DataFrame(rows)
    df = df.sort_values("retorno_total_pct", ascending=False)
    df.to_csv("output/sweep_filters.csv", index=False)

    print(f"\n=== Top 10 combinaciones (leverage {LEVERAGE}x) ===")
    cols = [
        "min_board_consensus", "min_odd_one_out_deviation", "retorno_total_pct",
        "drawdown_maximo_pct", "num_trades", "pct_ganadores", "num_stops",
    ]
    print(df[cols].head(10).to_string(index=False))

    print(f"\n=== Peores 5 combinaciones ===")
    print(df[cols].tail(5).to_string(index=False))

    n_profitable = (df["retorno_total_pct"] > 0).sum()
    print(f"\nCombinaciones con retorno positivo: {n_profitable} de {len(df)}")


if __name__ == "__main__":
    main()
