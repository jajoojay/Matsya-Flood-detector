#!/usr/bin/env python3
"""
predict_flood.py

Produces flood_forecast.csv (date, local_rain, upstream_rain, pred_river_level,
flood_probability (0-1), flood_probability_pct, risk_class)

Behavior:
 - Loads flood_model.pkl and flood_feature_order.txt if available; otherwise
   falls back to a simple heuristic probability for demonstration.
 - Seeds lag buffers from cleaned_data.csv where available (gurd_rain/local, upstream_rain).
 - Iterates over forecast horizon found in predicted_river_level.csv (primary)
 - Overwrites existing flood_forecast.csv file
 - Classification thresholds:
      No: p < 0.10
      Low: 0.10 <= p < 0.30
      Moderate: 0.30 <= p < 0.60
      High: p >= 0.60
"""
import os
import pickle
import pandas as pd
import numpy as np

MODEL_FILE = "flood_model.pkl"
FEAT_FILE = "flood_feature_order.txt"
CLEANED_FILE = "cleaned_data.csv"
RIVER_PRED = "predicted_river_level.csv"
LOCAL_FC = "forecast_rainfall.csv"
UP_FC = "upstream_forecast_gfs.csv"
OUT = "flood_forecast.csv"

def classify_prob(p):
    if p < 0.10:
        return "No"
    elif p < 0.30:
        return "Low"
    elif p < 0.60:
        return "Moderate"
    else:
        return "High"

def load_local_forecast():
    if not os.path.exists(LOCAL_FC):
        raise FileNotFoundError(f"{LOCAL_FC} missing. Run forecast_rainfall.py first.")
    df = pd.read_csv(LOCAL_FC)
    # accept Date or date column names
    if "Date" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"Date":"date"})
    if "Rainfall" in df.columns and "local_rain" not in df.columns:
        df = df.rename(columns={"Rainfall":"local_rain"})
    if "gurd_rain" in df.columns and "local_rain" not in df.columns:
        df = df.rename(columns={"gurd_rain":"local_rain"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "local_rain" not in df.columns:
        # attempt second column
        other = [c for c in df.columns if c != "date"]
        df["local_rain"] = df[other[0]] if other else 0.0
    return df[["date","local_rain"]].sort_values("date").reset_index(drop=True)

def load_upstream_forecast():
    if os.path.exists(UP_FC):
        df = pd.read_csv(UP_FC)
        if "date" not in df.columns and "Date" in df.columns:
            df = df.rename(columns={"Date":"date"})
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        if "upstream_rain" not in df.columns:
            others = [c for c in df.columns if c!="date"]
            df["upstream_rain"] = df[others[0]] if others else 0.0
        return df[["date","upstream_rain"]].sort_values("date").reset_index(drop=True)
    else:
        # build zeros for same horizon as local
        local = load_local_forecast()
        return pd.DataFrame({"date": local["date"], "upstream_rain": [0.0]*len(local)})

def load_river_preds():
    if not os.path.exists(RIVER_PRED):
        raise FileNotFoundError(f"{RIVER_PRED} missing. Run predict_river_level.py first.")
    df = pd.read_csv(RIVER_PRED, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    return df

def load_model_and_feats():
    if os.path.exists(MODEL_FILE) and os.path.exists(FEAT_FILE):
        with open(MODEL_FILE, "rb") as f:
            clf = pickle.load(f)
        with open(FEAT_FILE) as f:
            feat_order = [l.strip() for l in f if l.strip()]
        return clf, feat_order
    return None, None

def heuristic_probability(local_rain, upstream_rain, pred_river_level, baseline=349.5):
    """
    Basic heuristic mapping to a probability in [0,1].
    This is a fallback only when no classifier is available.
    """
    p = 0.08 * local_rain + 0.06 * upstream_rain + 0.003 * max(0.0, pred_river_level - baseline)
    return float(np.clip(p, 0.0, 1.0))

def main():
    # Load forecasts
    df_local = load_local_forecast()
    df_up = load_upstream_forecast()
    df_river = load_river_preds()

    # Primary horizon from river preds; merge with local and upstream by date
    df = pd.merge(df_river, df_local, on="date", how="left")
    df = pd.merge(df, df_up, on="date", how="left")

    df["local_rain"] = df["local_rain"].fillna(0.0)
    df["upstream_rain"] = df["upstream_rain"].fillna(0.0)

    # seed lags from cleaned history
    hist = pd.read_csv(CLEANED_FILE, parse_dates=["date"]).sort_values("date").reset_index(drop=True) if os.path.exists(CLEANED_FILE) else pd.DataFrame()
    up_lags = [float(hist.iloc[-i]["upstream_rain"]) if (len(hist) >= i and "upstream_rain" in hist.columns) else 0.0 for i in range(1,8)]
    local_lags = [float(hist.iloc[-i].get("gurd_rain", hist.iloc[-i].get("local_rain", 0.0))) if len(hist) >= i else 0.0 for i in range(1,8)]
    last_river = float(hist.iloc[-1]["river_level"]) if (len(hist) > 0 and "river_level" in hist.columns and not pd.isna(hist.iloc[-1]["river_level"])) else 0.0

    # load classifier if available
    clf, feat_order = load_model_and_feats()
    use_model = clf is not None and feat_order is not None
    if use_model:
        print("Loaded flood classifier and feature order.")
    else:
        print("--- flood_model.pkl / flood_feature_order.txt not found. Using heuristic probability.")

    out_rows = []
    pred_river_map = dict(zip(df_river["date"], df_river["pred_river_level"]))

    # iterative feature building
    for idx, row in df.iterrows():
        fdate = row["date"]
        up_today = float(row["upstream_rain"])
        local_today = float(row["local_rain"])
        # update lags
        up_lags = [up_today] + up_lags[:-1]
        local_lags = [local_today] + local_lags[:-1]

        # rolling sums
        up_roll3 = sum(up_lags[:3]); up_roll5 = sum(up_lags[:5]); up_roll7 = sum(up_lags[:7])
        local_roll3 = sum(local_lags[:3]); local_roll5 = sum(local_lags[:5]); local_roll7 = sum(local_lags[:7])

        # river lag: use previous predicted river if available
        prev_dates = sorted([d for d in pred_river_map.keys() if d < fdate])
        if prev_dates:
            river_lag_1 = float(pred_river_map[prev_dates[-1]])
        else:
            river_lag_1 = last_river

        # build feature dict consistent with training feature names (feat_order)
        feat = {}
        for j in range(1,8):
            feat[f"up_lag_{j}"] = up_lags[j-1]
            feat[f"local_lag_{j}"] = local_lags[j-1]
        feat["up_roll_3"] = up_roll3; feat["up_roll_5"] = up_roll5; feat["up_roll_7"] = up_roll7
        feat["local_roll_3"] = local_roll3; feat["local_roll_5"] = local_roll5; feat["local_roll_7"] = local_roll7
        feat["river_lag_1"] = river_lag_1
        feat["river_present"] = 1 if river_lag_1 > 0 else 0
        feat["month"] = int(pd.to_datetime(fdate).month) if not pd.isna(fdate) else 0
        feat["doy"] = int(pd.to_datetime(fdate).dayofyear) if not pd.isna(fdate) else 0

        if use_model:
            # align with feat_order
            Xrow = [ feat.get(c, 0.0) for c in feat_order ]
            X = pd.DataFrame([Xrow], columns=feat_order).astype(float)
            prob = float(clf.predict_proba(X)[0,1])
        else:
            prob = heuristic_probability(local_today, up_today, float(row.get("pred_river_level", river_lag_1)))

        pct = round(prob*100, 1)
        out_rows.append({
            "date": fdate,
            "local_rain": local_today,
            "upstream_rain": up_today,
            "pred_river_level": float(row.get("pred_river_level", river_lag_1)),
            "flood_probability": prob,
            "flood_probability_pct": f"{pct}%",
            "risk_class": classify_prob(prob)
        })

    out_df = pd.DataFrame(out_rows)
    # overwrite existing file
    if os.path.exists(OUT):
        os.remove(OUT)
    out_df.to_csv(OUT, index=False)    
    print("--- Saved fresh", OUT)
    # print results
    pd.set_option("display.width", 120)
    print(out_df.to_string(index=False))

if __name__ == "__main__":
    main()
