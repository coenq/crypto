# macd_strategy.py
import pandas as pd

def evaluate_macd(row):
    try:
        # Ensure MACD values are not NaN or None
        if pd.isna(row['macd']) or pd.isna(row['macd_signal']):
            return None

        # Basic crossover logic
        if row['macd'] > row['macd_signal']:
            return {'action': 'BUY', 'reason': 'MACD crossed above signal line'}
        elif row['macd'] < row['macd_signal']:
            return {'action': 'SELL', 'reason': 'MACD crossed below signal line'}

    except KeyError as e:
        print(f"[MACD Strategy Error] Missing column: {e}")
    except Exception as e:
        print(f"[MACD Strategy Error] {e}")

    return None
