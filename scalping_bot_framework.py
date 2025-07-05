import os, sys, time
from datetime import datetime, timezone
import pandas as pd
import talib
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import create_engine, text
from binance import ThreadedWebsocketManager

# === Path Fixes ===
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# === Local Imports ===
from strategies.rsi_strategy import evaluate_rsi
from strategies.ema_crossover import evaluate_ema_crossover
from strategies.macd_strategy import evaluate_macd
from strategies.bb_strategy import evaluate_bollinger
from backend.ml.ml_strategy import evaluate_ml_strategy
from backend.ml.lgbm_model_trainer import train_lightgbm
from backend.execution.execution_engine import ExecutionEngine

# === CONFIG ===
DB_PARAMS = {
    'dbname': 'postgres',
    'user': 'postgres.ahrkjfvcriprqucdfcvs',
    'password': 'Hajara-2006#',
    'host': 'aws-0-eu-west-2.pooler.supabase.com',
    'port': '5432'
}
SYMBOLS = ["btcusdt", "ethusdt", "bnbusdt", "solusdt", "xrpusdt"]
INTERVAL = "1m"
STARTING_BALANCE = 50000
lstm_active = False

# === DB Setup ===
DB_URI = f"postgresql+psycopg2://{DB_PARAMS['user']}:{DB_PARAMS['password']}@{DB_PARAMS['host']}:{DB_PARAMS['port']}/{DB_PARAMS['dbname']}"
engine = create_engine(DB_URI)

# === Execution Engine ===
execution_engine = ExecutionEngine(starting_balance=STARTING_BALANCE, engine=engine)

# === Store OHLCV ===
def store_to_db(symbol, candle):
    with engine.begin() as conn:
        conn.execute(text(f'''
            CREATE TABLE IF NOT EXISTS market_data (
                symbol TEXT NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL,
                open FLOAT, high FLOAT, low FLOAT, close FLOAT, volume FLOAT,
                PRIMARY KEY (symbol, timestamp)
            )
        '''))
        conn.execute(text(f'''
            INSERT INTO market_data (symbol, timestamp, open, high, low, close, volume)
            VALUES (:symbol, :timestamp, :open, :high, :low, :close, :volume)
            ON CONFLICT (symbol, timestamp) DO NOTHING
        '''), {
            'symbol': symbol,
            'timestamp': datetime.fromtimestamp(candle['t'] / 1000, tz=timezone.utc),
            'open': float(candle['o']),
            'high': float(candle['h']),
            'low': float(candle['l']),
            'close': float(candle['c']),
            'volume': float(candle['v'])
        })

# === Load Features ===
def load_features(symbol):
    query = '''
        SELECT * FROM market_data
        WHERE symbol = %s
        ORDER BY timestamp DESC
        LIMIT 100
    '''
    df = pd.read_sql(query, engine, params=(symbol,))
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

# === Log Executed Signal Only ===
def log_signal_to_db(signal, price, symbol, executed=True):
    try:
        with engine.begin() as conn:
            conn.execute(text('''
                CREATE TABLE IF NOT EXISTS strategy_signals (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ,
                    symbol TEXT,
                    strategy TEXT,
                    action TEXT,
                    price FLOAT,
                    reason TEXT,
                    executed BOOLEAN DEFAULT TRUE
                )
            '''))
            conn.execute(text('''
                INSERT INTO strategy_signals (timestamp, symbol, strategy, action, price, reason, executed)
                VALUES (:timestamp, :symbol, :strategy, :action, :price, :reason, :executed)
            '''), {
                'timestamp': datetime.now(timezone.utc),
                'symbol': symbol,
                'strategy': signal['strategy'],
                'action': signal['action'],
                'price': price,
                'reason': signal['reason'],
                'executed': executed
            })
    except Exception as e:
        print(f"[DB Error] ❌ Failed to log signal for {symbol}: {e}")

# === Strategy Voting ===
def evaluate_all_strategies(row, full_df):
    strategy_functions = [
        ("RSI", lambda r, df: evaluate_rsi(r, df)),
        ("EMA Crossover", lambda r, df: evaluate_ema_crossover(r)),
        ("MACD", lambda r, df: evaluate_macd(r)),
        ("Bollinger Bands", lambda r, df: evaluate_bollinger(r)),
        ("ML Strategy", lambda r, df: evaluate_ml_strategy())
    ]

    votes = {"BUY": 0, "SELL": 0}
    signals = []

    for name, func in strategy_functions:
        try:
            signal = func(row, full_df)
            print(f"[{name}] Signal: {signal}")
            if signal and signal["action"].upper() in votes:
                action = signal["action"].upper()
                votes[action] += 1
                signals.append({
                    "strategy": name,
                    "action": action,
                    "reason": signal.get("reason", "")
                })
        except Exception as e:
            print(f"[{name} ERROR] {e}")

    if votes["BUY"] >= 2:
        return {
            "action": "BUY",
            "strategy": "cumulative_vote",
            "reason": str([s['strategy'] for s in signals if s['action'] == 'BUY'])
        }
    elif votes["SELL"] >= 2:
        return {
            "action": "SELL",
            "strategy": "cumulative_vote",
            "reason": str([s['strategy'] for s in signals if s['action'] == 'SELL'])
        }
    return None

# === Handle WebSocket Messages ===
def handle_socket_message(symbol):
    def inner(msg):
        try:
            if msg['e'] != 'kline' or not msg['k']['x']:
                return

            kline = msg['k']
            candle = {
                't': int(kline['t']),
                'o': float(kline['o']),
                'h': float(kline['h']),
                'l': float(kline['l']),
                'c': float(kline['c']),
                'v': float(kline['v']),
            }
            store_to_db(symbol, candle)
            df = load_features(symbol)
            if df.empty or len(df) < 30:
                return
            row = df.iloc[-1]
            signal = evaluate_all_strategies(row, df)
            if signal:
                executed = execution_engine.execute_paper_trade(signal, row['close'], symbol)
                if executed:
                    log_signal_to_db(signal, row['close'], symbol)
        except Exception as e:
            print(f"[{symbol.upper()} WebSocket Error] {e}")
    return inner

# === Log PnL Summary ===
def log_pnl():
    pnl_log = execution_engine.get_pnl_log()
    if pnl_log:
        print("\n--- PnL Summary ---")
        for trade in pnl_log:
            print(f"Symbol: {trade['symbol']} | Entry: {trade['entry_time']} | Exit: {trade['exit_time']} | PnL: {trade['pnl']:.2f}")
        print(f"[Balance] ${execution_engine.get_balance():.2f}\n")

# === Retrain ML ===
def activate_lightgbm():
    global lstm_active
    train_lightgbm()
    lstm_active = True
    print("[ML] ✅ LightGBM model retrained")

# === Main Bot Runner ===
if __name__ == '__main__':
    twm = ThreadedWebsocketManager()
    twm.start()

    for symbol in SYMBOLS:
        print(f"[WebSocket] 🔄 Starting stream for {symbol.upper()}...")
        twm.start_kline_socket(callback=handle_socket_message(symbol), symbol=symbol, interval=INTERVAL)

    scheduler = BackgroundScheduler()
    scheduler.add_job(log_pnl, 'interval', minutes=1)
    scheduler.add_job(activate_lightgbm, 'cron', hour=0, minute=0)
    scheduler.start()

    print("[Bot] ✅ Multi-symbol scalping bot active")
    while True:
        time.sleep(1)
