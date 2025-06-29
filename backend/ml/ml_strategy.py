import pandas as pd
import joblib
import talib
from sqlalchemy import create_engine
from datetime import timezone, datetime

# Load model and scaler once
model = joblib.load("models/lightgbm_model.pkl")
scaler = joblib.load("models/scaler.pkl")

# Your DB settings
DB_URI = "postgresql+psycopg2://postgres.ahrkjfvcriprqucdfcvs:Hajara-2006#@aws-0-eu-west-2.pooler.supabase.com:5432/postgres"
engine = create_engine(DB_URI)

def evaluate_ml_strategy():
    try:
        # 1. Load last 100 candles
        df = pd.read_sql("SELECT * FROM market_data ORDER BY timestamp DESC LIMIT 100", engine)
        if df.empty or len(df) < 30:
            print("[ML Strategy] ⚠️ Not enough data for prediction.")
            return None

        df.sort_values('timestamp', inplace=True)

        # 2. Compute indicators
        df['rsi'] = talib.RSI(df['close'], timeperiod=14)
        df['ema_fast'] = talib.EMA(df['close'], timeperiod=9)
        df['ema_slow'] = talib.EMA(df['close'], timeperiod=21)
        macd, macdsignal, _ = talib.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
        df['macd'] = macd
        df['macd_signal'] = macdsignal
        df['volume'] = df['volume'].astype(float)

        # 3. Latest row for prediction
        latest = df.iloc[-1]
        features = latest[['rsi', 'ema_fast', 'ema_slow', 'macd', 'macd_signal', 'volume']].to_frame().T
        X = scaler.transform(features)

        predicted_return = model.predict(X)[0]  # in %

        print(f"[ML Strategy] Predicted return: {predicted_return:.2f}%")

        if predicted_return >= 0.5:
            return {
                "action": "BUY",
                "strategy": "evaluate_ml_strategy",
                "price": float(latest['close']),
                "reason": f"ML expects +{predicted_return:.2f}%",
            }

        return None

    except Exception as e:
        print(f"[ML Strategy Error] {e}")
        return None
