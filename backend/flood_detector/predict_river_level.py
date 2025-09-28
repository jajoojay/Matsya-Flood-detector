#!/usr/bin/env python3
"""
predict_river_level.py

Predict 5-day river level (Madhopur) using:
 - river_model.pkl (if available) trained on cleaned_data.csv
 - upstream_forecast_gfs.csv (preferred) OR fallback to forecast_rainfall.csv proxy

Outputs predicted_river_level.csv with columns: date, pred_river_level
Always overwrites any existing file.
"""
import os
import pickle
import pandas as pd
import numpy as np
from datetime import datetime

MODEL_FILE = "river_model.pkl"
FEATURE_FILE = "river_feature_order.txt"
CLEANED = "cleaned_data.csv"
UP_FORECAST = "upstream_forecast_gfs.csv"
LOCAL_FORECAST = "forecast_rainfall.csv"
OUT = "predicted_river_level.csv"
HORIZON = 5

def safe_read_csv_dates(path, date_col_candidates=("date","Date","datetime")):
    df = pd.read_csv(path)
    # try to detect date column
    for c in date_col_candidates:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
            df = df.rename(columns={c: "date"})
            return df
    # if none found, assume first column is date
    df.iloc[:,0] = pd.to_datetime(df.iloc[:,0], errors="coerce")
    df = df.rename(columns={df.columns[0]: "date"})
    return df

def load_upstream_forecast():
    if os.path.exists(UP_FORECAST):
        df = safe_read_csv_dates(UP_FORECAST)
        if "upstream_rain" not in df.columns:
            # try to infer
            other = [c for c in df.columns if c!="date"]
            if other:
                df = df.rename(columns={other[0]: "upstream_rain"})
            else:
                df["upstream_rain"] = 0.0
        return df[["date","upstream_rain"]].sort_values("date").reset_index(drop=True)
    # fallback: build proxy from local forecast
    if os.path.exists(LOCAL_FORECAST):
        df_local = safe_read_csv_dates(LOCAL_FORECAST)
        # column name may be Rainfall or local_rain
        if "Rainfall" in df_local.columns:
            df_local = df_local.rename(columns={"Rainfall": "local_rain"})
        if "local_rain" not in df_local.columns:
            # attempt to use first non-date column
            others = [c for c in df_local.columns if c!="date"]
            if others:
                df_local = df_local.rename(columns={others[0]:"local_rain"})
            else:
                df_local["local_rain"] = 0.0
        # create a simple proxy by scaling local -> upstream based on historical overlap if available
        # try historical cleaned data
        if os.path.exists(CLEANED):
            hist = pd.read_csv(CLEANED, parse_dates=["date"]).sort_values("date")
            if "gurd_rain" in hist.columns and "upstream_rain" in hist.columns:
                overlap = hist.dropna(subset=["gurd_rain","upstream_rain"])
                if len(overlap) >= 10:
                    A = overlap["gurd_rain"].values.reshape(-1,1)
                    y = overlap["upstream_rain"].values
                    A2 = np.column_stack([A, np.ones(len(A))])
                    a,b = np.linalg.lstsq(A2, y, rcond=None)[0]
                else:
                    a,b = 1.0,0.0
            else:
                a,b = 1.0,0.0
        else:
            a,b = 1.0,0.0
        df = df_local.head(HORIZON).copy()
        df["upstream_rain"] = (a * df["local_rain"].fillna(0.0) + b).clip(lower=0.0)
        return df[["date","upstream_rain"]].reset_index(drop=True)
    # last fallback: zeros
    today = pd.Timestamp(datetime.utcnow().date())
    dates = [today + pd.Timedelta(days=i) for i in range(HORIZON)]
    return pd.DataFrame({"date": dates, "upstream_rain": [0.0]*HORIZON})

def load_model_and_feats():
    if os.path.exists(MODEL_FILE) and os.path.exists(FEATURE_FILE):
        with open(MODEL_FILE, "rb") as f:
            model = pickle.load(f)
        with open(FEATURE_FILE) as f:
            feat_order = [l.strip() for l in f if l.strip()]
        return model, feat_order
    return None, None

def main():
    # load upstream forecast (preferred)
    up_fc = load_upstream_forecast().sort_values("date").reset_index(drop=True).head(HORIZON)
    print("Upstream forecast for horizon:")
    print(up_fc.to_string(index=False))

    # historical cleaned data for initial states
    if os.path.exists(CLEANED):
        hist = pd.read_csv(CLEANED, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    else:
        hist = pd.DataFrame()

    # last knowns
    if len(hist) > 0 and "upstream_rain" in hist.columns:
        last_up = float(hist.iloc[-1]["upstream_rain"])
    else:
        last_up = 0.0
    if len(hist) > 0 and "river_level" in hist.columns and not pd.isna(hist.iloc[-1]["river_level"]):
        last_river = float(hist.iloc[-1]["river_level"])
    else:
        last_river = 0.0

    # model
    model, feat_order = load_model_and_feats()
    use_model = model is not None and feat_order is not None
    if use_model:
        print("Loaded river regression model.")
    else:
        print("--- river_model.pkl or river_feature_order.txt not found — using heuristic fallback for river prediction")

    # seed lags (newest-first)
    up_lags = [last_up]*7
    river_prev = last_river

    preds = []
    for i, row in up_fc.iterrows():
        fdate = row["date"]
        upstream_today = float(row["upstream_rain"])

        # update lag buffers (most recent first)
        up_lags = [upstream_today] + up_lags[:-1]
        # rolling
        roll3 = sum(up_lags[:3]); roll5 = sum(up_lags[:5]); roll7 = sum(up_lags[:7])

        if use_model:
            # build feature dict aligned to feat_order
            feat = {}
            # expect names like up_lag_1..up_lag_7 and up_roll_{3,5,7} and river_lag_1, month, doy
            for j in range(1,8):
                feat[f"up_lag_{j}"] = up_lags[j-1]
            feat["up_roll_3"] = roll3
            feat["up_roll_5"] = roll5
            feat["up_roll_7"] = roll7
            feat["river_lag_1"] = river_prev
            feat["month"] = int(pd.to_datetime(fdate).month) if not pd.isna(fdate) else 0
            feat["doy"] = int(pd.to_datetime(fdate).dayofyear) if not pd.isna(fdate) else 0

            # create DataFrame aligned to feat_order, missing filled with 0
            Xf = pd.DataFrame([{c: feat.get(c, 0.0) for c in feat_order}]).astype(float)
            pred = float(model.predict(Xf)[0])
        else:
            # heuristic: base + 0.1 * rolling upstream 3-day + small inertia of river_prev
            base = river_prev if river_prev != 0 else 349.5
            pred = base + 0.12 * roll3 + 0.02 * (upstream_today) 
            # small smoothing/inertia
            pred = 0.6 * pred + 0.4 * river_prev

        preds.append({"date": fdate, "pred_river_level": float(pred)})
        # update river_prev for iterative prediction
        river_prev = pred

    out = pd.DataFrame(preds)
    # overwrite existing file if present
    if os.path.exists(OUT):
        os.remove(OUT)
    out.to_csv(OUT, index=False)    
    print("--- Saved fresh", OUT)
    print(out.to_string(index=False))

if __name__ == "__main__":
    main()
