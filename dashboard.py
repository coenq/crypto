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
SYMBOL_DEFAULT = "BTCUSDT"
INTERVAL_DEFAULT = "1m"

# === PAGE SETUP ===
st.set_page_config(page_title="Trading Bot Dashboard", layout="wide")
st.title("📊 BTC/USDT Smart Trading Bot Dashboard")

# Auto-refresh every 10 seconds
st_autorefresh(interval=10_000, key="refresh")

# SQLAlchemy engine
DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

utc = pytz.UTC

# === LIVE MARKET DATA FROM BINANCE ===
def load_market_data(symbol="BTCUSDT", interval="1m", limit=100):
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
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)

        return df[['timestamp', 'open', 'high', 'low', 'close']]

    except Exception as e:
        st.error(f"❌ Binance API error: {e}")
        return pd.DataFrame()

# === LOAD STRATEGY SIGNALS ===
def load_signals(strategy=None):
    try:
        df = pd.read_sql("SELECT * FROM strategy_signals WHERE executed = TRUE ORDER BY timestamp DESC LIMIT 100", engine)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        if strategy and strategy != "All":
            df = df[df['strategy'] == strategy]
        return df
    except Exception as e:
        st.error(f"❌ Signal loading error: {e}")
        return pd.DataFrame()

# === LOAD PnL ===
def calculate_pnl():
    try:
        df = pd.read_sql("SELECT * FROM trades ORDER BY timestamp", engine)
        pnl_total = df['net_pnl'].sum()
        trades = df[df['net_pnl'].notnull()]
        balance = STARTING_BALANCE + pnl_total
        return balance, pnl_total, len(trades)
    except Exception as e:
        st.error(f"❌ PnL calculation error: {e}")
        return STARTING_BALANCE, 0, 0

# === CANDLESTICK CHART ===
def plot_candles(df, signals):
    if df.empty:
        return go.Figure()

    fig = go.Figure()

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df['timestamp'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Price',
        increasing_line_color='lime',
        decreasing_line_color='red',
        line_width=2
    ))

    # Strategy Signal Markers
    if not signals.empty:
        buy_signals = signals[signals['action'].str.lower() == 'buy']
        sell_signals = signals[signals['action'].str.lower() == 'sell']

        fig.add_trace(go.Scatter(
            x=buy_signals['timestamp'],
            y=buy_signals['price'],
            mode='markers+text',
            name='Buy',
            marker=dict(color='green', size=10, symbol='triangle-up'),
            text=['BUY'] * len(buy_signals),
            textposition="top center"
        ))

        fig.add_trace(go.Scatter(
            x=sell_signals['timestamp'],
            y=sell_signals['price'],
            mode='markers+text',
            name='Sell',
            marker=dict(color='red', size=10, symbol='triangle-down'),
            text=['SELL'] * len(sell_signals),
            textposition="bottom center"
        ))

    # Layout Styling
    fig.update_layout(
        title="📈 Live Candlestick Chart with Trade Signals",
        xaxis_title="Time",
        yaxis_title="Price (USDT)",
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        height=600,
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return fig


# === SIDEBAR ===
st.sidebar.header("🔧 Controls")
strategy_filter = st.sidebar.selectbox(
    "Filter by Strategy",
    ["All", "evaluate_rsi", "evaluate_ema_crossover", "evaluate_macd", "evaluate_bollinger", "evaluate_lstm"]
)

symbol = st.sidebar.text_input("Symbol (Binance)", SYMBOL_DEFAULT)
interval = st.sidebar.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"], index=0)

# === MAIN ===
market_df = load_market_data(symbol, interval, 5000)
signals_df = load_signals(strategy_filter)

# === CHART ===
st.subheader("📈 Price Action + Strategy Signals")
st.plotly_chart(plot_candles(market_df, signals_df), use_container_width=True)

# === METRICS ===
balance, pnl, trade_count = calculate_pnl()
col1, col2, col3 = st.columns(3)
col1.metric("💰 Balance", f"${balance:.2f}")
col2.metric("📈 Total PnL", f"${pnl:.2f}")
col3.metric("📊 Trades Executed", trade_count)

# === SIGNAL LOGS ===
st.subheader("📋 Strategy Signal Log")
if not signals_df.empty:
    st.dataframe(signals_df[['timestamp', 'strategy', 'action', 'price', 'reason']], use_container_width=True)
else:
    st.info("No recent signals found.")
