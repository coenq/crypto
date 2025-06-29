# backfill.py
"""
Fetch 7 days of 1-minute historical candles for BTCUSDT
and insert into the `market_data` table in PostgreSQL.
"""

import time
from datetime import datetime, timedelta, timezone
import pandas as pd
from binance.client import Client
from sqlalchemy import create_engine, text

# === CONFIG ===
DB_PARAMS = {
    'dbname': 'postgres',
    'user': 'postgres.ahrkjfvcriprqucdfcvs',
    'password': 'Hajara-2006#',
    'host': 'aws-0-eu-west-2.pooler.supabase.com',
    'port': '5432'
}
DB_URI = f"postgresql+psycopg2://{DB_PARAMS['user']}:{DB_PARAMS['password']}@{DB_PARAMS['host']}:{DB_PARAMS['port']}/{DB_PARAMS['dbname']}"
engine = create_engine(DB_URI)

BINANCE_API_KEY = ''  # Optional for public data
BINANCE_SECRET = ''

SYMBOL = 'BTCUSDT'
INTERVAL = Client.KLINE_INTERVAL_1MINUTE
DAYS_BACK = 7

# === Initialize Binance Client ===
client = Client(BINANCE_API_KEY, BINANCE_SECRET)

# === Fetch Historical Data ===
def fetch_data(symbol, interval, start_time, end_time):
    print(f"Fetching data from {start_time} to {end_time}")
    klines = client.get_historical_klines(
        symbol,
        interval,
        start_time.strftime("%d %b %Y %H:%M:%S"),
        end_time.strftime("%d %b %Y %H:%M:%S")
    )

    df = pd.DataFrame(klines, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_vol', 'taker_buy_quote_vol', 'ignore'
    ])
    df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    df = df.astype({
        'open': 'float', 'high': 'float', 'low': 'float',
        'close': 'float', 'volume': 'float'
    })
    return df

# === Store to PostgreSQL using SQLAlchemy ===
def store_to_db(df):
    with engine.begin() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS market_data (
                timestamp TIMESTAMPTZ PRIMARY KEY,
                open FLOAT, high FLOAT, low FLOAT, close FLOAT, volume FLOAT
            )
        '''))

        insert_query = '''
            INSERT INTO market_data (timestamp, open, high, low, close, volume)
            VALUES (:timestamp, :open, :high, :low, :close, :volume)
            ON CONFLICT (timestamp) DO NOTHING
        '''

        records = df.to_dict(orient='records')
        for row in records:
            row['timestamp'] = pd.to_datetime(row['timestamp'])  # ensure correct type
            conn.execute(text(insert_query), row)

# === Main ===
if __name__ == '__main__':
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=DAYS_BACK)

    all_data = pd.DataFrame()
    print("[Backfill] Starting 7-day historical download...")

    for i in range(DAYS_BACK):
        batch_start = start_time + timedelta(days=i)
        batch_end = batch_start + timedelta(days=1)
        df = fetch_data(SYMBOL, INTERVAL, batch_start, batch_end)
        store_to_db(df)
        all_data = pd.concat([all_data, df])
        time.sleep(1.2)  # avoid Binance rate limits

    print(f"[Backfill Complete] Inserted {len(all_data)} rows into market_data.")
