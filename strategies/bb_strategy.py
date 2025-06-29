# bb_strategy.py
import pandas as pd

def evaluate_bollinger(row, prev_row=None):
    try:
        if pd.isna(row['bb_upper']) or pd.isna(row['bb_lower']) or pd.isna(row['close']):
            return None

        # Reversion Buy Signal
        if prev_row and row['close'] > row['bb_lower'] and prev_row['close'] < prev_row['bb_lower']:
            return {'action': 'BUY', 'reason': 'Price bounced above lower Bollinger Band (reversion)'}

        # Reversion Sell Signal
        elif prev_row and row['close'] < row['bb_upper'] and prev_row['close'] > prev_row['bb_upper']:
            return {'action': 'SELL', 'reason': 'Price dropped below upper Bollinger Band (reversion)'}

    except Exception as e:
        print(f"[BB Strategy Error] {e}")

    return None
