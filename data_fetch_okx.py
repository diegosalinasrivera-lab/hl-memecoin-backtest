"""Descarga de velas de 15 minutos desde la API pública de OKX
(https://www.okx.com/api/v5/market/history-candles), sin cuenta ni API
key. A diferencia de Hyperliquid, este endpoint sirve velas desde el
listado del contrato, así que permite cubrir 6-12 meses de historia.
"""
import json
import os
import time
import urllib.request
import urllib.error

import pandas as pd

from config_okx import DATA_DIR_OKX, INTERVAL_OKX, HISTORY_DAYS_OKX, UNIVERSE_OKX

API_URL = "https://www.okx.com/api/v5/market/history-candles"
MAX_CANDLES_PER_REQ = 300
INTERVAL_MS = {"15m": 15 * 60 * 1000}[INTERVAL_OKX]

# User-Agent explícito tipo curl: el cliente real de estas requests es un
# script de línea de comandos, no un navegador; con el User-Agent por
# defecto de urllib el WAF de OKX devuelve 403.
HEADERS = {"User-Agent": "curl/8.5.0", "Accept": "*/*"}


def _get(url, retries=6, timeout=20):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            wait = min(2 ** attempt, 20)
            print(f"  ! error de red ({e}), reintento en {wait}s...")
            time.sleep(wait)
    raise RuntimeError(f"No se pudo contactar la API tras {retries} intentos")


def fetch_coin_candles(inst_id: str, days: int = HISTORY_DAYS_OKX) -> pd.DataFrame:
    """Descarga `days` días de velas de 15m para `inst_id`, paginando hacia
    atrás con el parámetro `after`."""
    now_ms = int(time.time() * 1000)
    target_start = now_ms - days * 24 * 3600 * 1000

    all_rows = []
    after = None

    while True:
        url = f"{API_URL}?instId={inst_id}&bar={INTERVAL_OKX}&limit={MAX_CANDLES_PER_REQ}"
        if after is not None:
            url += f"&after={after}"
        resp = _get(url)
        if resp.get("code") != "0":
            print(f"  ! respuesta con error para {inst_id}: {resp.get('msg')}")
            break
        batch = resp.get("data", [])
        if not batch:
            break

        all_rows.extend(batch)
        min_ts = min(int(c[0]) for c in batch)

        if min_ts <= target_start:
            break
        after = min_ts
        time.sleep(0.2)  # ser amable con la API pública

    if not all_rows:
        return pd.DataFrame()

    # formato OKX: [ts, open, high, low, close, vol, volCcy, volCcyQuote, confirm]
    df = pd.DataFrame(
        all_rows,
        columns=["open_time", "open", "high", "low", "close", "vol", "volCcy", "volCcyQuote", "confirm"],
    )
    df = df.drop_duplicates(subset="open_time")
    for col in ("open", "high", "low", "close", "vol"):
        df[col] = df[col].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"].astype(float), unit="ms", utc=True)
    df = df.sort_values("open_time")
    df = df[["open_time", "open", "high", "low", "close", "vol"]].rename(columns={"vol": "volume"})
    df = df[df["open_time"] >= pd.Timestamp(target_start, unit="ms", tz="UTC")]
    return df.reset_index(drop=True)


def load_or_fetch(inst_id: str, days: int = HISTORY_DAYS_OKX, force: bool = False) -> pd.DataFrame:
    os.makedirs(DATA_DIR_OKX, exist_ok=True)
    safe_name = inst_id.replace("-", "_")
    path = os.path.join(DATA_DIR_OKX, f"{safe_name}_{INTERVAL_OKX}.csv")
    if not force and os.path.exists(path):
        df = pd.read_csv(path, parse_dates=["open_time"])
        df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
        return df
    df = fetch_coin_candles(inst_id, days=days)
    if not df.empty:
        df.to_csv(path, index=False)
    return df


def fetch_universe(insts=None, days: int = HISTORY_DAYS_OKX, force: bool = False):
    insts = insts or UNIVERSE_OKX
    data = {}
    skipped = []
    for inst_id in insts:
        coin = inst_id.replace("-USDT-SWAP", "")
        print(f"Descargando {inst_id} ...")
        try:
            df = load_or_fetch(inst_id, days=days, force=force)
        except Exception as e:
            print(f"  ! fallo definitivo para {inst_id}: {e}")
            df = pd.DataFrame()
        if df.empty or len(df) < 1000:
            print(f"  -> {inst_id}: histórico insuficiente ({len(df)} velas), se excluye.")
            skipped.append(inst_id)
            continue
        print(f"  -> {inst_id}: {len(df)} velas, desde {df['open_time'].min()} hasta {df['open_time'].max()}")
        data[coin] = df
    return data, skipped


if __name__ == "__main__":
    data, skipped = fetch_universe()
    print(f"\nTotal monedas con datos: {len(data)}")
    print(f"Excluidas por falta de historial: {skipped}")
