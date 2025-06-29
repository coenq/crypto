import json
import threading
import time
from datetime import datetime, timedelta, timezone
from binance import ThreadedWebsocketManager  

import pandas as pd
import talib
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import create_engine, text
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from strategies.rsi_strategy import evaluate_rsi
from strategies.ema_crossover import evaluate_ema_crossover
from strategies.macd_strategy import evaluate_macd
from backend.ml.ml_strategy import evaluate_ml_strategy  # <-- make sure this path is correct

from strategies.bb_strategy import evaluate_bollinger
from backend.ml.lgbm_model_trainer import train_lightgbm
from backend.execution.execution_engine import ExecutionEngine

# Config
DB_PARAMS = {
    'dbname': 'postgres',
    'user': 'postgres.ahrkjfvcriprqucdfcvs',
    'password': 'Hajara-2006#',
    'host': 'aws-0-eu-west-2.pooler.supabase.com',
    'port': '5432'
}
SYMBOL = "btcusdt"
INTERVAL = "1m"
STARTING_BALANCE = 50000
lstm_active = False
bot_start_time = datetime.now(timezone.utc)

# SQLAlchemy engine
DB_URI = f"postgresql+psycopg2://{DB_PARAMS['user']}:{DB_PARAMS['password']}@{DB_PARAMS['host']}:{DB_PARAMS['port']}/{DB_PARAMS['dbname']}"
engine = create_engine(DB_URI)

execution_engine = ExecutionEngine(starting_balance=STARTING_BALANCE,engine=engine)

# === Market Data Collector ===
def store_to_db(candle):
    with engine.begin() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS market_data (
                timestamp TIMESTAMPTZ PRIMARY KEY,
                open FLOAT, high FLOAT, low FLOAT, close FLOAT, volume FLOAT
            )
        '''))
        conn.execute(text('''
            INSERT INTO market_data (timestamp, open, high, low, close, volume)
            VALUES (:timestamp, :open, :high, :low, :close, :volume)
            ON CONFLICT (timestamp) DO NOTHING
        '''), {
            'timestamp': datetime.fromtimestamp(candle['t'] / 1000, tz=timezone.utc),
            'open': float(candle['o']),
            'high': float(candle['h']),
            'low': float(candle['l']),
            'close': float(candle['c']),
            'volume': float(candle['v'])
        })
    print(f"[Info] Storing candle @ {datetime.fromtimestamp(candle['t'] / 1000, tz=timezone.utc).isoformat()}")


# === REST Polling ===
def fetch_latest_candle():
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": SYMBOL.upper(),
        "interval": INTERVAL,
        "limit": 2
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    latest = data[-2]  # previous closed candle
    return {
        't': latest[0],
        'o': float(latest[1]),
        'h': float(latest[2]),
        'l': float(latest[3]),
        'c': float(latest[4]),
        'v': float(latest[5])
    }

# === Feature Engineering ===
def load_features():
    df = pd.read_sql("SELECT * FROM market_data ORDER BY timestamp DESC LIMIT 100", engine)
    print(f"[Debug] Loaded {len(df)} rows from market_data")

    if df.empty:
        return df

    df.sort_values('timestamp', inplace=True)
    df['rsi'] = talib.RSI(df['close'], timeperiod=14)
    df['ema_fast'] = talib.EMA(df['close'], timeperiod=9)
    df['ema_slow'] = talib.EMA(df['close'], timeperiod=21)
    macd, macdsignal, _ = talib.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
    df['macd'] = macd
    df['macd_signal'] = macdsignal
    upper, middle, lower = talib.BBANDS(df['close'], timeperiod=20)
    df['bb_upper'] = upper
    df['bb_lower'] = lower
    return df

# === Strategy Engine ===
def log_signal_to_db(signal, price, executed=False):
    try:
        with engine.begin() as conn:
            conn.execute(text('''
                CREATE TABLE IF NOT EXISTS strategy_signals (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ,
                    strategy TEXT,
                    action TEXT,
                    price FLOAT,
                    reason TEXT,
                    executed BOOLEAN DEFAULT FALSE
                )
            '''))
            conn.execute(text('''
                INSERT INTO strategy_signals (timestamp, strategy, action, price, reason, executed)
                VALUES (:timestamp, :strategy, :action, :price, :reason, :executed)
            '''), {
                'timestamp': datetime.now(timezone.utc),
                'strategy': signal['strategy'],
                'action': signal['action'],
                'price': price,
                'reason': signal['reason'],
                'executed': True
            })
        print(f"[DB Insert] ✅ Logged signal to DB: {signal} | Executed: {executed}")
    except Exception as e:
        print(f"[DB Error] ❌ Failed to log signal: {e}")

       


def evaluate_all_strategies(row, full_df):
    strategy_functions = [
        ("RSI", lambda row, df: evaluate_rsi(row)),
        ("EMA Crossover", lambda row, df: evaluate_ema_crossover(row)),
        ("MACD", lambda row, df: evaluate_macd(row)),
        ("Bollinger Bands", lambda row, df: evaluate_bollinger(row)),
        ("ML Strategy", lambda row, df: evaluate_ml_strategy())  # independent of row
    ]

    votes = {"BUY": 0, "SELL": 0}
    signals = []

    for name, strategy_func in strategy_functions:
        try:
            signal = strategy_func(row, full_df)
            if signal and signal["action"].upper() in votes:
                action = signal["action"].upper()
                votes[action] += 1
                signals.append({
                    "strategy": name,
                    "action": action,
                    "reason": signal.get("reason", "")
                })
                print(f"[Signal] {name} voted {action} - {signal.get('reason')}")
            else:
                print(f"[No Signal] {name} returned None")
        except Exception as e:
            print(f"[Error] {name} failed: {e}")

    print(f"[Votes] BUY={votes['BUY']}, SELL={votes['SELL']}")

    if votes["BUY"] >= 2:
        return {
            "action": "BUY",
            "strategy": "cumulative_vote",
            "reason": f"Consensus from {[s['strategy'] for s in signals if s['action'] == 'BUY']}"
        }
    elif votes["SELL"] >= 2:
        return {
            "action": "SELL",
            "strategy": "cumulative_vote",
            "reason": f"Consensus from {[s['strategy'] for s in signals if s['action'] == 'SELL']}"
        }
    else:
        print("[Consensus] ❌ No strong consensus for action")
        return None

# === Scheduler Tasks ===
def log_pnl():
    pnl_log = execution_engine.get_pnl_log()
    if pnl_log:
        print("\n--- PnL Summary ---")
        for trade in pnl_log:
            print(f"Entry: {trade['entry_time']} | Exit: {trade['exit_time']} | PnL: {trade['pnl']:.2f}")
        print(f"[Balance] ${execution_engine.get_balance():.2f}")
        print("-------------------\n")

def activate_lightgbm():
    global lstm_active
    train_lightgbm()
    lstm_active = True
    print("[Lightgbm] ✅ Model trained. ML strategy now active.")

# === Main Polling Loop ===
def handle_socket_message(msg):
    try:
        if msg['e'] != 'kline' or not msg['k']['x']:
            return  # only use closed candles

        kline = msg['k']
        candle = {
            't': int(kline['t']),
            'o': float(kline['o']),
            'h': float(kline['h']),
            'l': float(kline['l']),
            'c': float(kline['c']),
            'v': float(kline['v']),
        }

        store_to_db(candle)
        df = load_features()

        if df.empty or len(df) < 30:
            print(f"[Info] Waiting for more data... ({len(df)} rows)")
            return

        row = df.iloc[-1]
        print(f"[Latest Row] {row.to_dict()}")

        signal = evaluate_all_strategies(row, df)

        if signal:
            # Execute trade and only log if executed
            executed = execution_engine.execute_paper_trade(signal, row['close'])
            if executed:
                log_signal_to_db(signal, row['close'], executed=True)

    


    except Exception as e:
        print(f"[WebSocket Error] {e}")


# === Run Everything ===
if __name__ == '__main__':
    # Start WebSocket manager
    print("[WebSocket] Starting Binance WebSocket stream...")
    twm = ThreadedWebsocketManager()
    twm.start()
    twm.start_kline_socket(callback=handle_socket_message, symbol=SYMBOL, interval=INTERVAL)

    # Start background jobs
    scheduler = BackgroundScheduler()
    scheduler.add_job(log_pnl, 'interval', minutes=1)

    # 🕛 Nightly retraining at midnight UTC
    scheduler.add_job(activate_lightgbm, 'cron', hour=0, minute=0)
    scheduler.start()

    print("[Bot Started] ✅ Paper trading active. ML strategy retrains nightly at 00:00 UTC...\n")

    while True:
        time.sleep(1)
