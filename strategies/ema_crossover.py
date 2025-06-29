# ema_crossover.py

def evaluate_ema_crossover(row):
    if row['ema_fast'] is None or row['ema_slow'] is None:
        return None

    if row['ema_fast'] > row['ema_slow']:
        return {'action': 'BUY', 'reason': 'EMA fast crossed above EMA slow'}
    elif row['ema_fast'] < row['ema_slow']:
        return {'action': 'SELL', 'reason': 'EMA fast crossed below EMA slow'}

    return None
