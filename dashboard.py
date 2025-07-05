# dashboard.py

import streamlit as st
import pandas as pd
import plotly.graph_objs as go
import requests
from sqlalchemy import create_engine
from datetime import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# === CONFIG ===
DB_USER = 'postgres.ahrkjfvcriprqucdfcvs'
DB_PASS = 'Hajara-2006#'
DB_HOST = 'aws-0-eu-west-2.pooler.supabase.com'
DB_PORT = '5432'
DB_NAME = 'postgres'
STARTING_BALANCE = 50000
SYMBOL_LIST = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]

# === STREAMLIT SETUP ===
st.set_page_config(page_title="📊 Trading Bot Dashboard", layout="wide")
st_autorefresh(interval=10_000, key="refresh")  # Refresh every 10 seconds
st.sidebar.header("⚙️ Controls")

symbol = st.sidebar.selectbox("Symbol", SYMBOL_LIST, index=0)
interval = st.sidebar.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"], index=0)
strategy_filter = st.sidebar.selectbox("Strategy", ["All", "RSI", "EMA Crossover", "MACD", "Bollinger Bands", "ML Strategy"])

# === DATABASE ===
DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)
utc = pytz.UTC

# === FUNCTIONS ===
def load_market_data(symbol, interval="1m", limit=100):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        response = requests.get(url)
        response.raise_for_status()
        raw = response.json()

        df = pd.DataFrame(raw, columns=[
            'timestamp', 'open', 'high', 'low', 'close',
            'volume', 'close_time', 'quote_asset_volume',
            'num_trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])

        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.astype({'open': float, 'high': float, 'low': float, 'close': float})
        return df[['timestamp', 'open', 'high', 'low', 'close']]

    except Exception as e:
        st.error(f"❌ Binance API error: {e}")
        return pd.DataFrame()

def load_signals(strategy=None, symbol=None):
    try:
        query = "SELECT * FROM strategy_signals WHERE executed = TRUE"
        filters = []

        if strategy and strategy != "All":
            filters.append(f"strategy = '{strategy}'")
        if symbol:
            filters.append(f"symbol = '{symbol.lower()}'")

        if filters:
            query += " AND " + " AND ".join(filters)

        query += " ORDER BY timestamp DESC LIMIT 100"
        df = pd.read_sql(query, engine)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        return df

    except Exception as e:
        st.error(f"❌ Failed to load signals: {e}")
        return pd.DataFrame()

def calculate_pnl(symbol=None):
    try:
        query = "SELECT * FROM trades"
        if symbol:
            query += f" WHERE symbol = '{symbol.lower()}'"
        query += " ORDER BY timestamp DESC"

        df = pd.read_sql(query, engine)
        pnl_total = df['net_pnl'].sum()
        trade_count = df[df['net_pnl'].notnull()].shape[0]
        balance = STARTING_BALANCE + pnl_total
        return balance, pnl_total, trade_count
    except Exception as e:
        st.error(f"❌ Failed to calculate PnL: {e}")
        return STARTING_BALANCE, 0, 0

def plot_candlestick(df, signals):
    if df.empty:
        return go.Figure()

    fig = go.Figure()

    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df['timestamp'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Candles',
        increasing_line_color='lime',
        decreasing_line_color='red'
    ))

    # Signals
    if not signals.empty:
        buy = signals[signals['action'].str.lower() == 'buy']
        sell = signals[signals['action'].str.lower() == 'sell']

        fig.add_trace(go.Scatter(
            x=buy['timestamp'], y=buy['price'],
            mode='markers+text',
            name='Buy Signal',
            marker=dict(color='green', size=10, symbol='triangle-up'),
            text=['BUY'] * len(buy),
            textposition="top center"
        ))

        fig.add_trace(go.Scatter(
            x=sell['timestamp'], y=sell['price'],
            mode='markers+text',
            name='Sell Signal',
            marker=dict(color='red', size=10, symbol='triangle-down'),
            text=['SELL'] * len(sell),
            textposition="bottom center"
        ))

    fig.update_layout(
        template="plotly_dark",
        title=f"{symbol} Price Chart + Executed Signals",
        xaxis_title="Time",
        yaxis_title="Price (USDT)",
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        height=600,
        margin=dict(l=10, r=10, t=50, b=20),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom")
    )

    return fig

# === DATA LOADING ===
market_df = load_market_data(symbol, interval)
signals_df = load_signals(strategy_filter, symbol)
balance, pnl, trades = calculate_pnl(symbol)

# === DISPLAY ===
st.subheader("📈 Price Chart & Executed Signals")
st.plotly_chart(plot_candlestick(market_df, signals_df), use_container_width=True)

col1, col2, col3 = st.columns(3)
col1.metric("💰 Balance", f"${balance:,.2f}")
col2.metric("📈 Net PnL", f"${pnl:,.2f}")
col3.metric("📊 Trades", f"{trades}")

st.subheader("📋 Executed Strategy Signals")
if not signals_df.empty:
    st.dataframe(signals_df[['timestamp', 'strategy', 'action', 'price', 'reason']], use_container_width=True)
else:
    st.info("No executed signals found.")
