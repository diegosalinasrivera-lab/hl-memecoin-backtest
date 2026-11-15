"""Configuración central del backtest."""

# --- Universo de monedas --------------------------------------------------
# Las 10 pedidas por el usuario, mapeadas al ticker real en Hyperliquid.
# BROCCOLI714 y BANANAS31 son listados exclusivos de Binance (Alpha/Futures)
# y NO existen en Hyperliquid -> se excluyen y se reemplazan por otras
# memecoins líquidas para completar el universo de 23.
REQUESTED_MAP = {
    "DOGE": "DOGE",
    "PEPE": "kPEPE",
    "WIF": "WIF",
    "BOME": "BOME",
    "NEIRO": "kNEIRO",
    "TRUMP": "TRUMP",
    "PEOPLE": "PEOPLE",
    "DOGS": None,           # kDOGS existe en Hyperliquid pero sin velas recientes (mercado inactivo)
    "BROCCOLI714": None,    # no existe en Hyperliquid
    "BANANAS31": None,      # no existe en Hyperliquid
}

# 13 (+2 de reemplazo por las que no existen) memecoins líquidas elegidas.
# kDOGS, MEW y CHILLGUY están en el universo de Hyperliquid pero sin velas
# recientes disponibles (mercado sin actividad) -> se reemplazan por
# TURBO, ANIME y MELANIA, que sí tienen historial completo.
EXTRA_COINS = [
    "kBONK", "kFLOKI", "kSHIB", "MEME", "POPCAT", "TURBO", "NOT",
    "BRETT", "HMSTR", "GOAT", "MOODENG", "PNUT", "FARTCOIN",
    "ANIME", "MELANIA", "PENGU",
]

def build_universe():
    coins = [v for v in REQUESTED_MAP.values() if v is not None]
    coins += EXTRA_COINS
    # dedupe conservando orden
    seen = set()
    out = []
    for c in coins:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out[:23]

UNIVERSE = build_universe()

# --- Datos -----------------------------------------------------------------
# La API pública de Hyperliquid (candleSnapshot) sólo sirve ~5000 velas
# de 15m hacia atrás (~52 días) sin importar el startTime solicitado: no
# hay forma de pedir 6-12 meses de velas de 15m por esta vía. Se usa el
# máximo real disponible.
INTERVAL = "15m"
HISTORY_DAYS = 55
DATA_DIR = "data"

# --- Estrategia --------------------------------------------------------------
STRONG_MOVE_PCT = 0.015      # 1.5% en una sola vela de 15m = "sube/baja fuerte"
FLUSH_PCT = 0.02             # 2% de caída agregada de la mayoría = "flush"
MAJORITY_FRACTION = 0.5      # fracción de monedas para definir sesgo de tablero

PAUSE_BARS_AFTER_2_STOPS = 3   # 45 min / 15 min = 3 velas
MAX_OPEN_POSITIONS = 5
STOP_LOSS_PCTS = [0.005, 0.01]   # 0.5% y 1% (se corre el promedio como caso base, y ambos como sensibilidad)
DEFAULT_STOP_LOSS_PCT = 0.0075   # punto medio usado como caso "base"

LEVERAGES = [3, 5, 25]

INITIAL_CAPITAL = 146.0

# --- Costos realistas (Hyperliquid perps) -----------------------------------
TAKER_FEE_PCT = 0.00035     # 0.035% por lado (fee taker típico de Hyperliquid)
SLIPPAGE_PCT = 0.0003       # 0.03% de slippage estimado por lado
ROUND_TRIP_COST_PCT = 2 * (TAKER_FEE_PCT + SLIPPAGE_PCT)  # entrada + salida

# --- Régimen de mercado ------------------------------------------------------
REGIME_BULL_MONTHLY_RET = 0.05     # retorno mediano mensual del universo > +5% -> alcista
REGIME_BEAR_MONTHLY_RET = -0.05    # < -5% -> bajista
