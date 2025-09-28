#!/usr/bin/env python3
"""
forecast_rainfall.py

Fetch 5-day local rainfall forecast for Gurdaspur and save to
forecast_rainfall.csv with columns: Date, Rainfall

Behavior:
 - Uses Open-Meteo (no API key) by default.
 - If the API call fails, writes a zero/placeholder forecast (so downstream pipeline still runs).
 - Always overwrites any existing forecast_rainfall.csv.
"""
from datetime import datetime, timedelta
import os
import requests
import pandas as pd
import sys

OUT = "forecast_rainfall.csv"

# Replace with exact Gurdaspur coordinates if you prefer
LAT = 32.03
LON = 75.40
FORECAST_DAYS = 5
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

def fetch_open_meteo(lat, lon, days=5):
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_sum",
        "forecast_days": days,
        "timezone": "UTC"
    }
    resp = requests.get(OPEN_METEO_URL, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()

def build_local_df_from_api(json_resp):
    # expected keys: daily.time, daily.precipitation_sum
    daily = json_resp.get("daily", {})
    times = daily.get("time", [])
    prec = daily.get("precipitation_sum", [])
    df = pd.DataFrame({"Date": pd.to_datetime(times), "Rainfall": prec})
    return df

def fallback_zero_forecast(days=5, start=None):
    if start is None:
        start = datetime.utcnow().date()
    days_list = [start + timedelta(days=i) for i in range(days)]
    df = pd.DataFrame({"Date": pd.to_datetime(days_list), "Rainfall": [0.0]*days})
    return df

def write_out(df):
    # ensure overwrite
    if os.path.exists(OUT):
        os.remove(OUT)
    df.to_csv(OUT, index=False)    
    print("--- Saved fresh", OUT)
    print(df.to_string(index=False))

def main():
    try:
        print("Fetching local forecast (Open-Meteo)...")
        resp = fetch_open_meteo(LAT, LON, FORECAST_DAYS)
        df = build_local_df_from_api(resp)
    except Exception as e:
        print("--- Open-Meteo fetch failed:", str(e))
        print("Writing fallback zero forecast")
        df = fallback_zero_forecast(FORECAST_DAYS)
    # Ensure column names are exactly Date, Rainfall (for downstream expectation)
    if "Date" not in df.columns or "Rainfall" not in df.columns:
        df = df.rename(columns={df.columns[0]: "Date", df.columns[1]: "Rainfall"})
    # write
    write_out(df)

if __name__ == "__main__":
    main()
