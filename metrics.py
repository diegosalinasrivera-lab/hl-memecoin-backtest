"""Cálculo de métricas de performance, desglose mensual/por régimen y
pruebas de sensibilidad (sin la mejor moneda, sin el mejor día)."""
import numpy as np
import pandas as pd

from config import REGIME_BULL_MONTHLY_RET, REGIME_BEAR_MONTHLY_RET


def max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    dd = equity / running_max - 1.0
    return dd.min()


def summary_stats(trades: pd.DataFrame, equity: pd.DataFrame, initial_capital: float) -> dict:
    if equity.empty:
        return {}
    final_equity = equity["equity"].iloc[-1]
    total_return = final_equity / initial_capital - 1.0
    dd = max_drawdown(equity.set_index("ts")["equity"])
    n_trades = len(trades)
    win_rate = (trades["pnl_usd"] > 0).mean() if n_trades else np.nan
    avg_pnl = trades["pnl_usd"].mean() if n_trades else np.nan
    n_stopped = int(trades["stopped_out"].sum()) if n_trades else 0
    return {
        "capital_final": final_equity,
        "retorno_total_pct": total_return * 100,
        "drawdown_maximo_pct": dd * 100,
        "num_trades": n_trades,
        "pct_ganadores": win_rate * 100 if n_trades else np.nan,
        "pnl_promedio_usd": avg_pnl,
        "num_stops": n_stopped,
        "pct_stopped": (n_stopped / n_trades * 100) if n_trades else np.nan,
    }


def monthly_breakdown(trades: pd.DataFrame, equity: pd.DataFrame) -> pd.DataFrame:
    if equity.empty:
        return pd.DataFrame()
    eq = equity.set_index("ts")["equity"]
    monthly_equity = eq.resample("MS").last().ffill()
    monthly_ret = monthly_equity.pct_change()
    monthly_ret.iloc[0] = monthly_equity.iloc[0] / eq.iloc[0] - 1.0

    if not trades.empty:
        t = trades.copy()
        t["month"] = t["exit_ts"].dt.to_period("M").dt.to_timestamp()
        trades_per_month = t.groupby("month").size()
        winrate_per_month = t.groupby("month")["pnl_usd"].apply(lambda s: (s > 0).mean() * 100)
    else:
        trades_per_month = pd.Series(dtype=float)
        winrate_per_month = pd.Series(dtype=float)

    out = pd.DataFrame(
        {
            "equity_fin_mes": monthly_equity,
            "retorno_mes_pct": monthly_ret * 100,
        }
    )
    out["num_trades"] = trades_per_month.reindex(out.index).fillna(0).astype(int)
    out["pct_ganadores"] = winrate_per_month.reindex(out.index)
    return out


def classify_regimes(board: pd.DataFrame, coins: list[str]) -> pd.Series:
    """Clasifica cada mes como alcista / bajista / lateral según el
    retorno mediano del universo de monedas en ese mes."""
    closes = pd.concat({c: board[(c, "close")] for c in coins}, axis=1)
    month_closes = closes.resample("MS").last()
    month_ret = month_closes.pct_change()
    median_ret = month_ret.median(axis=1)

    def label(r):
        if pd.isna(r):
            return "N/D"
        if r >= REGIME_BULL_MONTHLY_RET:
            return "alcista"
        if r <= REGIME_BEAR_MONTHLY_RET:
            return "bajista"
        return "lateral"

    out = median_ret.apply(label)
    out.index = out.index.tz_localize(None)  # para poder cruzar con trades["month"] (tz-naive)
    return out


def regime_breakdown(trades: pd.DataFrame, regimes: pd.Series) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    t = trades.copy()
    t["month"] = t["exit_ts"].dt.to_period("M").dt.to_timestamp()
    t["regimen"] = t["month"].map(regimes)
    grp = t.groupby("regimen")["pnl_usd"].agg(
        pnl_total="sum", num_trades="count", pct_ganadores=lambda s: (s > 0).mean() * 100
    )
    return grp


def robustness_checks(trades: pd.DataFrame, initial_capital: float) -> dict:
    """Recalcula el retorno total (simple, sin compounding por margen fijo
    inicial) excluyendo la mejor moneda y excluyendo el mejor día, para ver
    cuánto depende el resultado de un solo golpe de suerte."""
    if trades.empty:
        return {}

    base_pnl = trades["pnl_usd"].sum()

    by_coin = trades.groupby("coin")["pnl_usd"].sum().sort_values(ascending=False)
    best_coin = by_coin.index[0]
    pnl_wo_best_coin = base_pnl - by_coin.iloc[0]

    t = trades.copy()
    t["day"] = t["exit_ts"].dt.date
    by_day = t.groupby("day")["pnl_usd"].sum().sort_values(ascending=False)
    best_day = by_day.index[0]
    pnl_wo_best_day = base_pnl - by_day.iloc[0]

    return {
        "pnl_total_usd": base_pnl,
        "retorno_total_pct": base_pnl / initial_capital * 100,
        "mejor_moneda": best_coin,
        "pnl_mejor_moneda_usd": by_coin.iloc[0],
        "pnl_sin_mejor_moneda_usd": pnl_wo_best_coin,
        "retorno_sin_mejor_moneda_pct": pnl_wo_best_coin / initial_capital * 100,
        "mejor_dia": str(best_day),
        "pnl_mejor_dia_usd": by_day.iloc[0],
        "pnl_sin_mejor_dia_usd": pnl_wo_best_day,
        "retorno_sin_mejor_dia_pct": pnl_wo_best_day / initial_capital * 100,
    }
