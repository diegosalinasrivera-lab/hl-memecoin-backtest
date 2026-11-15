"""Descarga de velas de 15 minutos desde la API pública de Hyperliquid.

No requiere cuenta ni API key. Endpoint: POST https://api.hyperliquid.xyz/info
con {"type": "candleSnapshot", "req": {...}}. Devuelve como máximo ~5000
velas por request, así que se pagina hacia atrás en el tiempo.
"""
import json
import os
import time
import urllib.request
import urllib.error

import pandas as pd

from config import DATA_DIR, INTERVAL, HISTORY_DAYS, UNIVERSE

API_URL = "https://api.hyperliquid.xyz/info"
MAX_CANDLES_PER_REQ = 5000
INTERVAL_MS = {"15m": 15 * 60 * 1000}[INTERVAL]


def _post(payload, retries=5, timeout=20):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        API_URL, data=body, headers={"Content-Type": "application/json"}
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            wait = min(2 ** attempt, 20)
            print(f"  ! error de red ({e}), reintento en {wait}s...")
            time.sleep(wait)
    raise RuntimeError(f"No se pudo contactar la API tras {retries} intentos")


def fetch_coin_candles(coin: str, days: int = HISTORY_DAYS) -> pd.DataFrame:
    """Descarga `days` días de velas de 15m para `coin`, paginando hacia atrás."""
    now_ms = int(time.time() * 1000)
    target_start = now_ms - days * 24 * 3600 * 1000

    all_rows = []
    end_ms = now_ms
    seen_min_t = None

    while True:
        start_ms = max(target_start, end_ms - MAX_CANDLES_PER_REQ * INTERVAL_MS)
        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": coin,
                "interval": INTERVAL,
                "startTime": start_ms,
                "endTime": end_ms,
            },
        }
        batch = _post(payload)
        if not batch:
            break

        all_rows.extend(batch)
        min_t = min(c["t"] for c in batch)

        if seen_min_t is not None and min_t >= seen_min_t:
            break  # no avanzamos más (llegamos al listado del activo)
        seen_min_t = min_t

        if min_t <= target_start:
            break

        end_ms = min_t - 1
        time.sleep(0.15)  # ser amable con la API pública

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows).drop_duplicates(subset="t").sort_values("t")
    df = df.rename(
        columns={
            "t": "open_time",
            "T": "close_time",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
            "n": "n_trades",
        }
    )
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df[["open_time", "open", "high", "low", "close", "volume", "n_trades"]]
    df = df[df["open_time"] >= pd.Timestamp(target_start, unit="ms", tz="UTC")]
    return df.reset_index(drop=True)


def load_or_fetch(coin: str, days: int = HISTORY_DAYS, force: bool = False) -> pd.DataFrame:
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"{coin}_{INTERVAL}.csv")
    if not force and os.path.exists(path):
        df = pd.read_csv(path, parse_dates=["open_time"])
        df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
        return df
    df = fetch_coin_candles(coin, days=days)
    if not df.empty:
        df.to_csv(path, index=False)
    return df


def fetch_universe(coins=None, days: int = HISTORY_DAYS, force: bool = False):
    coins = coins or UNIVERSE
    data = {}
    skipped = []
    for coin in coins:
        print(f"Descargando {coin} ...")
        try:
            df = load_or_fetch(coin, days=days, force=force)
        except Exception as e:
            print(f"  ! fallo definitivo para {coin}: {e}")
            df = pd.DataFrame()
        if df.empty or len(df) < 100:
            print(f"  -> {coin}: histórico insuficiente ({len(df)} velas), se excluye.")
            skipped.append(coin)
            continue
        print(f"  -> {coin}: {len(df)} velas, desde {df['open_time'].min()} hasta {df['open_time'].max()}")
        data[coin] = df
    return data, skipped


if __name__ == "__main__":
    data, skipped = fetch_universe()
    print(f"\nTotal monedas con datos: {len(data)}")
    print(f"Excluidas por falta de historial: {skipped}")
