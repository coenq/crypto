from datetime import datetime, timezone
from sqlalchemy import text
import os, sys

# Adjust path for relative imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from backend.risk.risk_manager import check_risk_limits, register_trade


def safe_float(x):
    try:
        return float(x) if x is not None else None
    except:
        return None


class ExecutionEngine:
    def __init__(self, starting_balance=50000, engine=None):
        self.balance = starting_balance
        self.position = None
        self.entry_time = None
        self.pnl_log = []
        self.engine = engine
        self._create_trades_table()

    def _create_trades_table(self):
        if self.engine:
            print("[DB] ✅ Creating trades table if not exists...")
            with self.engine.begin() as conn:
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS trades (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMPTZ,
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
        else:
            print("[DB] ❌ No database engine provided.")

    def execute_paper_trade(self, signal, price):
        action = signal['action']
        strategy = signal['strategy']
        timestamp = datetime.now(timezone.utc)

        current_position = {
            'entry_price': self.position,
            'entry_time': self.entry_time
        } if self.position else None

        # ✅ Risk Check
        risk_ok, risk_reason = check_risk_limits(signal, price, current_position, self.balance)
        if not risk_ok:
            print(f"[Risk] 🚫 Trade blocked: {risk_reason}")
            self._log_trade(timestamp, action, price, strategy, f"Blocked by risk: {risk_reason}")
            return False

        # ✅ BUY
        if action.upper() == 'BUY':
            if self.position is None:
                self.position = price
                self.entry_time = timestamp
                print(f"[BUY] at ${price:.2f} | Strategy: {strategy}")
                self._log_trade(timestamp, action, price, strategy, "BUY executed")
                return True
            else:
                reason = "Already in position, ignoring BUY"
                print(f"[Info] {reason}")
                self._log_trade(timestamp, action, price, strategy, reason)
                return False

        # ✅ SELL
        elif action.upper() == 'SELL':
            if self.position is not None:
                fee_rate = 0.00075
                usd_to_use = self.balance * 0.1
                position_size = usd_to_use / self.position
                signal['position_size'] = position_size

                price_increase_pct = ((price - self.position) / self.position) * 100
                if price_increase_pct < 0.45:
                    reason = f"Trade skipped: price only up {price_increase_pct:.2f}% (min required: 1%)"
                    print(f"[🕒] {reason}")
                    self._log_trade(timestamp, action, price, strategy, reason)
                    return False

                entry_fee = position_size * self.position * fee_rate
                exit_fee = position_size * price * fee_rate
                total_fees = entry_fee + exit_fee

                gross_pnl = (price - self.position) * position_size
                net_pnl = gross_pnl - total_fees
                pnl_pct = (net_pnl / (self.position * position_size)) * 100

                self.balance += net_pnl

                self.pnl_log.append({
                    'entry_time': self.entry_time,
                    'exit_time': timestamp,
                    'entry_price': self.position,
                    'exit_price': price,
                    'gross_pnl': gross_pnl,
                    'fees': total_fees,
                    'pnl': net_pnl
                })

                print(f"[SELL] at ${price:.2f} | Size: {position_size:.6f} | Gross: {gross_pnl:.2f} | Fees: {total_fees:.4f} | Net PnL: {net_pnl:.2f} ({pnl_pct:.2f}%) | Strategy: {strategy}")

                register_trade(signal, net_pnl)

                self._log_trade(
                    timestamp, action, price, strategy, f"SELL executed | Net PnL: {net_pnl:.2f}",
                    entry_time=self.entry_time,
                    entry_price=self.position,
                    exit_price=price,
                    gross_pnl=gross_pnl,
                    fees=total_fees,
                    net_pnl=net_pnl
                )

                self.position = None
                self.entry_time = None
                return True
            else:
                reason = "No open position, ignoring SELL"
                print(f"[Info] {reason}")
                self._log_trade(timestamp, action, price, strategy, reason)
                return False

        # ❌ Invalid action
        reason = "Unknown action type"
        print(f"[Error] {reason}")
        self._log_trade(timestamp, action, price, strategy, reason)
        return False

    def _log_trade(self, timestamp, action, price, strategy, reason,
                   entry_time=None, entry_price=None, exit_price=None,
                   gross_pnl=None, fees=None, net_pnl=None):
        if self.engine:
            try:
                with self.engine.begin() as conn:
                    conn.execute(text('''
                        INSERT INTO trades (
                            timestamp, action, price, strategy, reason,
                            entry_time, entry_price, exit_price,
                            gross_pnl, fees, net_pnl
                        ) VALUES (
                            :timestamp, :action, :price, :strategy, :reason,
                            :entry_time, :entry_price, :exit_price,
                            :gross_pnl, :fees, :net_pnl
                        )
                    '''), {
                        'timestamp': timestamp,
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
                print(f"[DB Error] ❌ Failed to log trade: {e}")

    def get_balance(self):
        return self.balance

    def get_pnl_log(self):
        return self.pnl_log
