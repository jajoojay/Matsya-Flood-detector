#!/usr/bin/env python3
"""
train_flood_model.py

Trains a flood classification model using cleaned_data.csv.
Outputs:
 - flood_model.pkl
 - flood_feature_order.txt
"""
import os, pickle
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score

DATA_FILE = "cleaned_data.csv"
MODEL_OUT = "flood_model.pkl"
FEAT_OUT = "flood_feature_order.txt"

def main():
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"{DATA_FILE} not found. Run data_prep.py first.")

    # Force datetime
    df = pd.read_csv(DATA_FILE)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date").reset_index(drop=True)

    # Ensure flood_label exists
    if "flood_label" not in df.columns:
        raise KeyError("flood_label column missing in cleaned_data.csv")

    # Date features (safe)
    if pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["month"] = df["date"].dt.month
        df["doy"] = df["date"].dt.dayofyear
    else:
        df["month"] = 0
        df["doy"] = 0

    # Features
    feature_cols = []
    for col in ["gurd_rain", "upstream_rain", "river_level"]:
        if col in df.columns:
            feature_cols.append(col)

    # Add lag/roll features if available
    feature_cols += [c for c in df.columns if "prev" in c or "lag" in c or "roll" in c]

    if not feature_cols:
        raise RuntimeError("No usable features found for flood model training!")

    df_model = df.dropna(subset=feature_cols + ["flood_label"]).copy()
    X = df_model[feature_cols].astype(float)
    y = df_model["flood_label"].astype(int)

    print(f"Training flood classifier on {len(X)} rows with features: {feature_cols}")
    clf = RandomForestClassifier(n_estimators=300, random_state=42, class_weight="balanced")
    clf.fit(X, y)

    preds = clf.predict(X)
    probas = clf.predict_proba(X)[:, 1]

    auc = roc_auc_score(y, probas)
    print("Classification Report:\n", classification_report(y, preds))
    print(f"ROC AUC: {auc:.3f}")

    with open(MODEL_OUT, "wb") as f:
        pickle.dump(clf, f)
    with open(FEAT_OUT, "w") as f:
        f.write("\n".join(feature_cols))

    print("Saved", MODEL_OUT, FEAT_OUT)

if __name__ == "__main__":
    main()
