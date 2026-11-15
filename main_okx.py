"""Orquestador del backtest usando datos de OKX (más historia que
Hyperliquid). Reutiliza el mismo motor de estrategia/backtest; sólo
cambia la fuente de datos y la ventana de tiempo."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from config import (
    LEVERAGES,
    DEFAULT_STOP_LOSS_PCT,
    STOP_LOSS_PCTS,
    INITIAL_CAPITAL,
)
from config_okx import UNIVERSE_OKX, OUT_DIR_OKX
from data_fetch_okx import fetch_universe
from strategy import build_board_frame, generate_signals
from backtest import run_backtest
from metrics import (
    summary_stats,
    monthly_breakdown,
    classify_regimes,
    regime_breakdown,
    robustness_checks,
)

OUT_DIR = OUT_DIR_OKX


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("Cargando datos de OKX (cache local si ya existe)...")
    panel, skipped = fetch_universe(UNIVERSE_OKX)
    coins = list(panel.keys())
    print(f"Universo final: {len(coins)} monedas. Excluidas: {skipped}")

    board = build_board_frame(panel)
    print(f"Panel combinado: {len(board)} velas desde {board.index.min()} hasta {board.index.max()}")

    print("Generando señales de la estrategia (con filtros v2)...")
    signals = generate_signals(board, coins)
    print(f"Total señales generadas: {len(signals)}")
    reasons = pd.Series([s.reason for s in signals]).value_counts()
    print(reasons)

    regimes = classify_regimes(board, coins)
    print("\nRégimen de mercado por mes (retorno mediano del universo):")
    print(regimes)
    print(regimes.value_counts())

    all_summaries = []

    for lev in LEVERAGES:
        print(f"\n=== Apalancamiento {lev}x (stop {DEFAULT_STOP_LOSS_PCT*100:.2f}%) ===")
        trades, equity = run_backtest(
            board, signals, leverage=lev, stop_loss_pct=DEFAULT_STOP_LOSS_PCT,
            initial_capital=INITIAL_CAPITAL,
        )
        trades.to_csv(f"{OUT_DIR}/trades_{lev}x.csv", index=False)
        equity.to_csv(f"{OUT_DIR}/equity_{lev}x.csv", index=False)

        stats = summary_stats(trades, equity, INITIAL_CAPITAL)
        stats["leverage"] = lev
        all_summaries.append(stats)
        print(stats)

        mb = monthly_breakdown(trades, equity)
        mb.to_csv(f"{OUT_DIR}/monthly_{lev}x.csv")
        print("\nDesglose mensual:")
        print(mb)

        rb = regime_breakdown(trades, regimes)
        rb.to_csv(f"{OUT_DIR}/regime_{lev}x.csv")
        print("\nDesglose por régimen:")
        print(rb)

        rc = robustness_checks(trades, INITIAL_CAPITAL)
        pd.Series(rc).to_csv(f"{OUT_DIR}/robustness_{lev}x.csv")
        print("\nPruebas de robustez (sin mejor moneda / sin mejor día):")
        print(rc)

        if not equity.empty:
            plt.figure(figsize=(10, 5))
            plt.plot(equity["ts"], equity["equity"])
            plt.title(f"Curva de capital (OKX) - leverage {lev}x (capital inicial ${INITIAL_CAPITAL})")
            plt.xlabel("Fecha")
            plt.ylabel("Equity (USD)")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(f"{OUT_DIR}/equity_curve_{lev}x.png", dpi=130)
            plt.close()

    print("\n=== Sensibilidad de stop-loss (leverage 5x) ===")
    for sl in STOP_LOSS_PCTS:
        trades, equity = run_backtest(
            board, signals, leverage=5, stop_loss_pct=sl, initial_capital=INITIAL_CAPITAL
        )
        stats = summary_stats(trades, equity, INITIAL_CAPITAL)
        stats["stop_loss_pct"] = sl
        print(stats)

    summary_df = pd.DataFrame(all_summaries)
    summary_df.to_csv(f"{OUT_DIR}/summary_by_leverage.csv", index=False)
    print("\n=== Resumen final por apalancamiento ===")
    print(summary_df)

    plt.figure(figsize=(10, 5))
    for lev in LEVERAGES:
        eq = pd.read_csv(f"{OUT_DIR}/equity_{lev}x.csv", parse_dates=["ts"])
        plt.plot(eq["ts"], eq["equity"], label=f"{lev}x")
    plt.title(f"Curvas de capital por apalancamiento (OKX, capital inicial ${INITIAL_CAPITAL})")
    plt.xlabel("Fecha")
    plt.ylabel("Equity (USD)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{OUT_DIR}/equity_curve_comparativa.png", dpi=130)
    plt.close()

    print(f"\nListo. Resultados en ./{OUT_DIR}/")


if __name__ == "__main__":
    main()
