# backend/risk/risk_manager.py

from datetime import datetime, timezone
from collections import defaultdict

# === Risk Parameters ===
MAX_TRADES_PER_DAY = 30           # Max 30 trades per symbol per day
MAX_DRAWDOWN_PCT = 0.30           # Max 30% daily drawdown
STOP_LOSS_PCT = 0.05              # 5% SL
TAKE_PROFIT_PCT = 0.04            # 4% TP
FIXED_RISK_PCT = 0.01             # 1% of balance per trade
DAILY_LOSS_LIMIT = 0.3            # Max 30% capital loss per day

# === Trade Log (per-symbol, per-day) ===
trade_logs = defaultdict(list)


def check_risk_limits(signal, price, current_position, balance):
    now = datetime.now(timezone.utc)
    today = now.date()
    symbol = signal.get("symbol", "").upper()

    # Clean old logs for today
    trade_logs[symbol] = [t for t in trade_logs[symbol] if t["timestamp"].date() == today]

    # === Max Trades Per Day ===
    if len(trade_logs[symbol]) >= MAX_TRADES_PER_DAY:
        return False, f"Max trades ({MAX_TRADES_PER_DAY}) reached for {symbol} today"

    # === Position Sizing ===
    usd_risk = max(balance * FIXED_RISK_PCT, 50)  # Minimum $50 trade
    position_size = usd_risk / price
    signal["position_size"] = position_size

    # === SL/TP Enforcement ===
    if signal["action"].upper() == "SELL" and current_position:
        entry_price = current_position["entry_price"]
        if entry_price:
            change_pct = (price - entry_price) / entry_price

            if change_pct <= -STOP_LOSS_PCT:
                return True, f"Forced SELL by Stop Loss ({change_pct:.2%})"

            if change_pct >= TAKE_PROFIT_PCT:
                return True, f"Forced SELL by Take Profit ({change_pct:.2%})"

            if change_pct < 0.0025:  # 0.45%
                return False, f"Gain {change_pct:.2%} below threshold (0.45%)"

    # === Daily Drawdown ===
    net_pnl_today = sum(t["net_pnl"] for t in trade_logs[symbol])
    if net_pnl_today < -balance * MAX_DRAWDOWN_PCT:
        return False, f"Daily drawdown exceeded for {symbol} ({net_pnl_today:.2f})"

    return True, "Pass"


def register_trade(signal, net_pnl):
    now = datetime.now(timezone.utc)
    symbol = signal.get("symbol", "").upper()

    trade_logs[symbol].append({
        "timestamp": now,
        "action": signal.get("action", "N/A"),
        "strategy": signal.get("strategy", "N/A"),
        "net_pnl": net_pnl
    })
