# rsi_strategy.py

import pandas as pd

def evaluate_rsi(row, prev_row=None):
    try:
        # Ensure RSI is valid
        if pd.isna(row['rsi']):
            return None

        # Use 30/70 thresholds instead of 40/60 for more reliable signals
        if row['rsi'] < 40:
            return {'action': 'BUY', 'reason': 'RSI below 30 (strong oversold)'}
        elif row['rsi'] > 60:
            return {'action': 'SELL', 'reason': 'RSI above 70 (strong overbought)'}

        # Optional: detect RSI crossing the threshold
        if prev_row is not None and not pd.isna(prev_row['rsi']):
            if prev_row['rsi'] > 30 and row['rsi'] < 30:
                return {'action': 'BUY', 'reason': 'RSI just crossed below 30'}
            elif prev_row['rsi'] < 70 and row['rsi'] > 70:
                return {'action': 'SELL', 'reason': 'RSI just crossed above 70'}

    except Exception as e:
        print(f"[RSI Strategy Error] {e}")

    return None
