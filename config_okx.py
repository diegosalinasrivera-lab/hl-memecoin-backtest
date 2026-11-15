"""Configuración para la variante con datos de OKX (más historia que
Hyperliquid: OKX sirve velas de 15m desde el listado de cada contrato,
no sólo los últimos ~52 días)."""

# Mapeo moneda pedida -> instId de OKX (perpetuo USDT-margined).
# DOGS, GOAT y MELANIA no tienen contrato USDT-SWAP en OKX -> se
# reemplazan por MEW, SPX y VIRTUAL respectivamente (no se usa VIRTUAL
# en el universo final por cupo de 23, ver EXTRA_COINS_OKX).
REQUESTED_MAP_OKX = {
    "DOGE": "DOGE-USDT-SWAP",
    "PEPE": "PEPE-USDT-SWAP",
    "WIF": "WIF-USDT-SWAP",
    "BOME": "BOME-USDT-SWAP",
    "NEIRO": "NEIRO-USDT-SWAP",
    "TRUMP": "TRUMP-USDT-SWAP",
    "PEOPLE": "PEOPLE-USDT-SWAP",
    "DOGS": None,            # sin contrato USDT-SWAP en OKX
    "BROCCOLI714": None,     # no existe en OKX
    "BANANAS31": None,       # no existe en OKX
}

# Reemplazos de lo que no existe (DOGS) + 13 elegidas originalmente +
# GOAT/MELANIA reemplazadas (tampoco existen en OKX) = 23 en total.
EXTRA_COINS_OKX = [
    "MEW-USDT-SWAP",        # reemplazo de DOGS
    "BONK-USDT-SWAP", "FLOKI-USDT-SWAP", "SHIB-USDT-SWAP", "MEME-USDT-SWAP",
    "POPCAT-USDT-SWAP", "TURBO-USDT-SWAP", "NOT-USDT-SWAP", "BRETT-USDT-SWAP",
    "HMSTR-USDT-SWAP",
    "SPX-USDT-SWAP",         # reemplazo de GOAT
    "MOODENG-USDT-SWAP", "PNUT-USDT-SWAP", "FARTCOIN-USDT-SWAP",
    "ANIME-USDT-SWAP", "PENGU-USDT-SWAP",
]


def build_universe_okx():
    coins = [v for v in REQUESTED_MAP_OKX.values() if v is not None]
    coins += EXTRA_COINS_OKX
    seen = set()
    out = []
    for c in coins:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out[:23]


UNIVERSE_OKX = build_universe_okx()

INTERVAL_OKX = "15m"
# El instrumento listado más tarde entre los 23 (SPX-USDT-SWAP, listado
# 2025-07-17) deja disponibles ~480 días de historia uniforme hasta la
# fecha actual -> se usa una ventana de 365 días (12 meses), dentro del
# rango de 6-12 meses pedido originalmente.
HISTORY_DAYS_OKX = 365
DATA_DIR_OKX = "data_okx"
OUT_DIR_OKX = "output_okx"
