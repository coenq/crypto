# model_utils.py
"""
Utility functions for loading the trained LSTM model and scaler,
and for preparing features for inference.
"""

import numpy as np
import joblib
import pandas as pd
from keras.models import load_model

MODEL_PATH = 'lstm_price_model.h5'
SCALER_PATH = 'scaler.pkl'
LOOKBACK = 30

_model = None
_scaler = None


def get_model():
    global _model
    if _model is None:
        _model = load_model(MODEL_PATH)
    return _model


def get_scaler():
    global _scaler
    if _scaler is None:
        _scaler = joblib.load(SCALER_PATH)
    return _scaler


def prepare_input(df):
    scaler = get_scaler()
    recent = df[['close', 'volume', 'rsi']].dropna().tail(LOOKBACK).values
    if len(recent) < LOOKBACK:
        raise ValueError("Not enough data for LSTM input")
    scaled = scaler.transform(recent)
    return np.expand_dims(scaled, axis=0)  # shape (1, LOOKBACK, 3)


def predict_next_price(df):
    model = get_model()
    X = prepare_input(df)
    predicted_scaled = model.predict(X, verbose=0)
    # pad with zeros to match scaler's expected input shape
    full_input = np.hstack([predicted_scaled, np.zeros((1, 2))])
    predicted = get_scaler().inverse_transform(full_input)[0][0]
    return predicted
