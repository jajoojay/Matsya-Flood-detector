#!/usr/bin/env python3
"""
train_river_model.py

Trains a river-level regression model using cleaned_data.csv.
Outputs:
 - river_model.pkl
 - river_feature_order.txt
"""
import os, pickle
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error

DATA_FILE = "cleaned_data.csv"
MODEL_OUT = "river_model.pkl"
FEAT_OUT = "river_feature_order.txt"

def main():
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"{DATA_FILE} not found. Run data_prep.py first.")
    
    # Force date parsing
    df = pd.read_csv(DATA_FILE)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date").reset_index(drop=True)

    # Ensure upstream_rain column exists
    if "upstream_rain" not in df.columns:
        df["upstream_rain"] = 0.0

    upstream = df["upstream_rain"].fillna(0.0)

    # create lags
    for i in range(1, 8):
        df[f"up_lag_{i}"] = upstream.shift(i)
    # rolling sums
    df["up_roll_3"] = upstream.rolling(3).sum().shift(1)
    df["up_roll_5"] = upstream.rolling(5).sum().shift(1)
    df["up_roll_7"] = upstream.rolling(7).sum().shift(1)

    df["river_lag_1"] = df["river_level"].shift(1)

    # handle any missing/non-datetime date
    if pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["month"] = df["date"].dt.month
        df["doy"] = df["date"].dt.dayofyear
    else:
        df["month"] = 0
        df["doy"] = 0

    # target: river_level
    required = ["river_level", "river_lag_1"] + [f"up_lag_{i}" for i in range(1, 8)]
    df_model = df.dropna(subset=required).copy()
    if df_model.shape[0] < 30:
        raise RuntimeError(f"Not enough rows to train river model after dropna. Rows: {df_model.shape[0]}")

    feature_cols = [f"up_lag_{i}" for i in range(1, 8)] + \
                   ["up_roll_3", "up_roll_5", "up_roll_7", "river_lag_1", "month", "doy"]
    X = df_model[feature_cols].astype(float)
    y = df_model["river_level"].astype(float)

    print(f"Training river regression on {len(X)} rows with features: {feature_cols}")
    model = RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1)
    model.fit(X, y)

    preds = model.predict(X)
    rmse = np.sqrt(mean_squared_error(y, preds))
    mae = mean_absolute_error(y, preds)
    print(f"River model train RMSE={rmse:.3f}, MAE={mae:.3f}")

    with open(MODEL_OUT, "wb") as f:
        pickle.dump(model, f)
    with open(FEAT_OUT, "w") as f:
        f.write("\n".join(feature_cols))

    print("Saved", MODEL_OUT, FEAT_OUT)

if __name__ == "__main__":
    main()
