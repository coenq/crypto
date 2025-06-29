import os
import joblib
import pandas as pd
from sklearn.preprocessing import StandardScaler
import lightgbm as lgb
from sqlalchemy import create_engine

# Adjust your DB settings
DB_URI = "postgresql+psycopg2://postgres.ahrkjfvcriprqucdfcvs:Hajara-2006#@aws-0-eu-west-2.pooler.supabase.com:5432/postgres"
engine = create_engine(DB_URI)

def train_lightgbm():
    print("[ML Trainer] 📊 Starting LightGBM training...")

    # 1. Load market data
    df = pd.read_sql("SELECT * FROM market_data ORDER BY timestamp DESC LIMIT 1000", engine)
    df = df.sort_values('timestamp')

    if df.empty or len(df) < 100:
        print("[ML Trainer] ❌ Not enough data to train.")
        return

    # 2. Feature engineering
    import talib
    df['rsi'] = talib.RSI(df['close'], timeperiod=14)
    df['ema_fast'] = talib.EMA(df['close'], timeperiod=9)
    df['ema_slow'] = talib.EMA(df['close'], timeperiod=21)
    macd, signal, _ = talib.MACD(df['close'])
    df['macd'] = macd
    df['macd_signal'] = signal
    df['volume'] = df['volume'].astype(float)

    df = df.dropna()

    # 3. Create labels (next close - current close as return %)
    df['target'] = df['close'].pct_change().shift(-1) * 100
    df.dropna(inplace=True)

    # 4. Select features and labels
    features = ['rsi', 'ema_fast', 'ema_slow', 'macd', 'macd_signal', 'volume']
    X = df[features]
    y = df['target']

    # 5. Normalize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 6. Train model
    model = lgb.LGBMRegressor()
    model.fit(X_scaled, y)

    # 7. Save model and scaler
    os.makedirs("models", exist_ok=True)
    joblib.dump(model, "models/lightgbm_model.pkl")
    joblib.dump(scaler, "models/scaler.pkl")

    print("[ML Trainer] ✅ Model and scaler saved.")

if __name__ == "__main__":
    train_lightgbm()