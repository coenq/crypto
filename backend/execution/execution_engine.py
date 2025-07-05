from datetime import datetime, timezone
from sqlalchemy import text
import os, sys

# Path fix
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# === Local Imports ===
from backend.risk.risk_manager import check_risk_limits, register_trade


def safe_float(x):
    try:
        return float(x) if x is not None else None
    except:
        return None


class ExecutionEngine:
    FEE_RATE = 0.00075          # Binance fee estimate (adjust if needed)
    POSITION_RISK = 0.10        # 10% of balance per trade
    MIN_PROFIT_PCT = 0.25       # Don't sell unless gain > 0.25%

    def __init__(self, starting_balance=50000, engine=None):
        self.balance = starting_balance
        self.positions = {}         # {symbol: {price, time}}
        self.pnl_log = []           # List of closed trades
        self.engine = engine
        self._create_trades_table()

    def _create_trades_table(self):
        if not self.engine:
            print("[DB] ❌ No DB engine provided.")
            return

        print("[DB] ✅ Ensuring trades table exists...")
        with self.engine.begin() as conn:
            conn.execute(text('''
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ,
                    symbol TEXT,
                    action TEXT,
                    price FLOAT,
                    strategy TEXT,
                    reason TEXT,
                    entry_time TIMESTAMPTZ,
                    entry_price FLOAT,
                    exit_price FLOAT,
                    gross_pnl FLOAT,
                    fees FLOAT,
                    net_pnl FLOAT
                )
            '''))

    def execute_paper_trade(self, signal, price, symbol):
        symbol = symbol.upper()
        timestamp = datetime.now(timezone.utc)
        strategy = signal['strategy']
        action = signal['action'].upper()

        position = self.positions.get(symbol)
        current_position = {
            'entry_price': position['price'],
            'entry_time': position['time']
        } if position else None

        # === RISK CHECK ===
        risk_ok, risk_reason = check_risk_limits(signal, price, current_position, self.balance)
        if not risk_ok:
            print(f"[Risk] 🚫 {symbol} blocked: {risk_reason}")
            return False

        if action == "BUY":
            if symbol not in self.positions:
                self.positions[symbol] = {
                    'price': price,
                    'time': timestamp
                }
                print(f"[BUY] {symbol} at ${price:.2f} | Strategy: {strategy}")
                self._log_trade(timestamp, action, price, strategy, "BUY executed", symbol)
                return True
            else:
                print(f"[Skip] {symbol} BUY ignored — already in position")
                return False

        elif action == "SELL":
            if symbol in self.positions:
                entry_price = position['price']
                entry_time = position['time']
                usd_allocated = self.balance * self.POSITION_RISK
                position_size = usd_allocated / entry_price

                price_move_pct = ((price - entry_price) / entry_price) * 100
                if price_move_pct < self.MIN_PROFIT_PCT:
                    print(f"[Skip] {symbol} SELL skipped — gain only {price_move_pct:.2f}%")
                    return False

                entry_fee = entry_price * position_size * self.FEE_RATE
                exit_fee = price * position_size * self.FEE_RATE
                total_fees = entry_fee + exit_fee

                gross_pnl = (price - entry_price) * position_size
                net_pnl = gross_pnl - total_fees
                pnl_pct = (net_pnl / (entry_price * position_size)) * 100

                self.balance += net_pnl
                self.pnl_log.append({
                    'symbol': symbol,
                    'entry_time': entry_time,
                    'exit_time': timestamp,
                    'entry_price': entry_price,
                    'exit_price': price,
                    'gross_pnl': gross_pnl,
                    'fees': total_fees,
                    'pnl': net_pnl
                })

                print(f"[SELL] {symbol} at ${price:.2f} | Net PnL: ${net_pnl:.2f} ({pnl_pct:.2f}%) | Strategy: {strategy}")
                register_trade(signal, net_pnl)

                self._log_trade(
                    timestamp, action, price, strategy,
                    f"SELL executed | Net PnL: {net_pnl:.2f}", symbol,
                    entry_time, entry_price, price, gross_pnl, total_fees, net_pnl
                )

                del self.positions[symbol]
                return True
            else:
                print(f"[Skip] {symbol} SELL ignored — no open position")
                return False

        else:
            print(f"[Error] {symbol} Unknown action: {action}")
            return False

    def _log_trade(self, timestamp, action, price, strategy, reason,
                   symbol, entry_time=None, entry_price=None,
                   exit_price=None, gross_pnl=None, fees=None, net_pnl=None):
        if not self.engine:
            return

        try:
            with self.engine.begin() as conn:
                conn.execute(text('''
                    INSERT INTO trades (
                        timestamp, symbol, action, price, strategy, reason,
                        entry_time, entry_price, exit_price,
                        gross_pnl, fees, net_pnl
                    ) VALUES (
                        :timestamp, :symbol, :action, :price, :strategy, :reason,
                        :entry_time, :entry_price, :exit_price,
                        :gross_pnl, :fees, :net_pnl
                    )
                '''), {
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'action': action,
                    'price': safe_float(price),
                    'strategy': strategy,
                    'reason': reason,
                    'entry_time': entry_time,
                    'entry_price': safe_float(entry_price),
                    'exit_price': safe_float(exit_price),
                    'gross_pnl': safe_float(gross_pnl),
                    'fees': safe_float(fees),
                    'net_pnl': safe_float(net_pnl)
                })
        except Exception as e:
            print(f"[DB Error] ❌ Trade log failed: {e}")

    def get_balance(self):
        return self.balance

    def get_pnl_log(self):
        return self.pnl_log

    def has_open_position(self, symbol):
        return symbol.upper() in self.positions
