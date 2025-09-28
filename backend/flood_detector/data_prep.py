#!/usr/bin/env python3
"""
data_prep.py

Prepares a cleaned dataset by merging:
- Local rainfall (Gurdaspur)
- River level (Madhopur)
- Upstream rainfall (Himachal region)
- Flood labels (from Gurdaspur)

Outputs:
 - cleaned_data.csv
"""

import pandas as pd

# === Input files ===
F_LOCAL = "combined_daily_2019_2025.csv"      # already engineered features
F_RIVER = "madhopur_river_level.csv"          # datetime, river_level
F_UP = "upstream_rainfall_era5.csv"           # date, upstream_rain
F_LABEL = "rainfall_labeled.csv"              # Date, Rainfall, Flood
OUT = "cleaned_data.csv"


def main():
    print("Loading datasets...")

    # --- Local rainfall & engineered features ---
    df_local = pd.read_csv(F_LOCAL, parse_dates=["date"])
    # it already has gurd_rain, lag features, etc.
    print("--- Local rainfall features:", list(df_local.columns))

    # --- River level (Madhopur) ---
    df_river = pd.read_csv(F_RIVER, parse_dates=["datetime"])
    df_river = df_river.rename(columns={"datetime": "date"})
    print("--- River level columns:", list(df_river.columns))

    # --- Upstream rainfall ---
    df_up = pd.read_csv(F_UP, parse_dates=["date"])
    # drop 'number' if it's just ensemble member
    if "number" in df_up.columns:
        df_up = df_up.drop(columns=["number"])
    print("--- Upstream rainfall columns:", list(df_up.columns))

    # --- Flood labels ---
    df_label = pd.read_csv(F_LABEL, parse_dates=["Date"])
    df_label = df_label.rename(columns={"Date": "date", "Flood": "flood_label"})
    print("--- Flood labels columns:", list(df_label.columns))

    # --- Merge all sources ---
    print("Merging...")
    df = pd.merge(df_local, df_river, on="date", how="outer")
    df = pd.merge(df, df_up, on="date", how="outer")
    df = pd.merge(df, df_label[["date", "flood_label"]], on="date", how="left")

    df = df.sort_values("date").reset_index(drop=True)

    # --- Fill missing values ---
    if "gurd_rain" in df.columns:
        df["gurd_rain"] = df["gurd_rain"].fillna(0)
    if "upstream_rain" in df.columns:
        df["upstream_rain"] = df["upstream_rain"].fillna(0)
    if "river_level" in df.columns:
        df["river_level"] = df["river_level"].interpolate()

    df["flood_label"] = df["flood_label"].fillna(0).astype(int)

    # --- Save cleaned dataset ---
    print("--- Saving cleaned dataset:", OUT)
    df.to_csv(OUT, index=False)

    print("Final columns:", list(df.columns))
    print("Final shape:", df.shape)


if __name__ == "__main__":
    main()
