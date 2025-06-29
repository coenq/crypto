# backtester.py
"""
Run backtest on historical market_data using your strategies.
Outputs:
- PnL & trade log to backtest_results.csv
- Summary metrics: Sharpe, drawdown
"""

import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import os
import sys
from sqlalchemy import create_engine, text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from strategies.rsi_strategy import evaluate_rsi
from strategies.ema_crossover import evaluate_ema_crossover
from strategies.macd_strategy import evaluate_macd
from strategies.bb_strategy import evaluate_bollinger

# === DB CONFIG ===
DB_PARAMS = {
    'dbname': 'postgres',
    'user': 'postgres.ahrkjfvcriprqucdfcvs',
    'password': 'Hajara-2006#',
    'host': 'aws-0-eu-west-2.pooler.supabase.com',
    'port': '5432'
}
DB_URI = f"postgresql+psycopg2://{DB_PARAMS['user']}:{DB_PARAMS['password']}@{DB_PARAMS['host']}:{DB_PARAMS['port']}/{DB_PARAMS['dbname']}"
engine = create_engine(DB_URI)

STRATEGIES = {
    'rsi': evaluate_rsi,
    'ema': evaluate_ema_crossover,
    'macd': evaluate_macd,
    'bb': evaluate_bollinger
}

USE_STRATEGY = 'rsi'  # options: 'rsi', 'ema', 'macd', 'bb', 'all'
TRADE_SIZE = 1
STARTING_BALANCE = 1000

# === Load historical market data ===
def load_data():
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM market_data ORDER BY timestamp", conn)
    df.set_index('timestamp', inplace=True)
    return df

# === Feature Engineering ===
def add_indicators(df):
    import talib
    df['rsi'] = talib.RSI(df['close'], timeperiod=14)
    df['ema_fast'] = talib.EMA(df['close'], timeperiod=9)
    df['ema_slow'] = talib.EMA(df['close'], timeperiod=21)
    macd, macdsignal, _ = talib.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
    df['macd'] = macd
    df['macd_signal'] = macdsignal
    upper, middle, lower = talib.BBANDS(df['close'], timeperiod=20)
    df['bb_upper'] = upper
    df['bb_lower'] = lower
    return df.dropna()

# === Backtest Logic ===
def run_backtest(df):
    position = None
    trades = []
    equity = []
    balance = STARTING_BALANCE

    for i in range(1, len(df)):
        row = df.iloc[i]

        # Select strategy
        if USE_STRATEGY == 'all':
            signal = None
            for func in STRATEGIES.values():
                signal = func(row)
                if signal:
                    break
        else:
            signal = STRATEGIES[USE_STRATEGY](row)

        price = row['close']

        if signal:
            action = signal['action']
            if action == 'BUY' and position is None:
                position = {
                    'entry_price': price,
                    'entry_time': row.name
                }
            elif action == 'SELL' and position:
                pnl = price - position['entry_price']
                trades.append({
                    'entry_time': position['entry_time'],
                    'exit_time': row.name,
                    'entry_price': position['entry_price'],
                    'exit_price': price,
                    'pnl': pnl * TRADE_SIZE
                })
                balance += pnl * TRADE_SIZE
                position = None

        # Add equity (mark-to-market if in position)
        if position:
            unrealized = (price - position['entry_price']) * TRADE_SIZE
            equity.append(balance + unrealized)
        else:
            equity.append(balance)

    return trades, equity

# === Metrics ===
def summarize(trades, equity):
    pnl = [t['pnl'] for t in trades]
    equity = np.array(equity)
    returns = np.diff(equity) / equity[:-1]

    sharpe = np.mean(returns) / (np.std(returns) + 1e-6) * np.sqrt(252 * 24 * 60)  # annualized for minute data
    drawdown = np.max(np.maximum.accumulate(equity) - equity)

    print(f"\nBacktest Summary:")
    print(f"Trades: {len(trades)}")
    print(f"Total PnL: {sum(pnl):.2f} USDT")
    print(f"Sharpe Ratio: {sharpe:.2f}")
    print(f"Max Drawdown: {drawdown:.2f}")

    return pd.DataFrame(trades), equity

# === Save Results ===
def save_results(trade_df, equity):
    trade_df.to_csv("backtest_results.csv", index=False)
    plt.figure(figsize=(10, 5))
    plt.plot(equity)
    plt.title("Equity Curve")
    plt.xlabel("Steps")
    plt.ylabel("Balance")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("backtest_equity.png")
    plt.show()

# === Main ===
if __name__ == '__main__':
    df = load_data()
    df = add_indicators(df)
    print(f"Loaded {len(df)} rows of historical data.")

    trades, equity = run_backtest(df)
    trade_df, eq_curve = summarize(trades, equity)
    save_results(trade_df, eq_curve)
