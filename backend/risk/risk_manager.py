# backend/risk/risk_manager.py

from datetime import datetime, timezone

# === More Lenient Risk Parameters ===
MAX_TRADES_PER_DAY = 30            # Allow up to 1000 trades per day
MAX_DRAWDOWN_PCT = 0.30              # Allow 30% max drawdown
STOP_LOSS_PCT = 0.05                 # 5% SL
TAKE_PROFIT_PCT = 0.04              # 4% TP
FIXED_RISK_PCT = 1.0                # Use 5% capital per trade
DAILY_LOSS_LIMIT = 0.3               # Allow 30% daily capital loss

# Track trade history per day
trade_log = []


def check_risk_limits(signal, price, current_position, balance):
    global trade_log

    now = datetime.now(timezone.utc)
    today = now.date()
    trade_log = [t for t in trade_log if t['timestamp'].date() == today]

    # === Limit number of trades per day ===
    if len(trade_log) >= MAX_TRADES_PER_DAY:
        return False, f"Max trades ({MAX_TRADES_PER_DAY}) reached for today"

    # === Simulate position sizing ===
    usd_risk = max(balance * FIXED_RISK_PCT, 100)  # at least $100
    position_size = usd_risk / price
    signal['position_size'] = position_size

    # === Drawdown Check ===
    net_pnl_today = sum(t['net_pnl'] for t in trade_log)
    if net_pnl_today < -balance * MAX_DRAWDOWN_PCT:
        return False, f"Daily drawdown limit exceeded ({net_pnl_today:.2f})"

    return True, "Pass"


def register_trade(signal, net_pnl):
    trade_log.append({
        'timestamp': datetime.now(timezone.utc),
        'action': signal['action'],
        'strategy': signal.get('strategy', 'N/A'),
        'net_pnl': net_pnl
    })
