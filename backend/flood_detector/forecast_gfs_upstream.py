#!/usr/bin/env python3
"""
forecast_gfs_upstream.py

Fetch 5-day upstream rainfall using Open-Meteo (GFS backend) for the basin center.
Outputs upstream_forecast_gfs.csv with columns date, upstream_rain
"""
import requests
import pandas as pd

LAT, LON = 32.7, 76.5
url = "https://api.open-meteo.com/v1/gfs"
params = {
    "latitude": LAT,
    "longitude": LON,
    "daily": "precipitation_sum",
    "forecast_days": 5,
    "timezone": "auto"
}

def main():
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    df = pd.DataFrame({"date": data["daily"]["time"], "upstream_rain": data["daily"]["precipitation_sum"]})
    df["date"] = pd.to_datetime(df["date"])
    out = "upstream_forecast_gfs.csv"
    df.to_csv(out, index=False)
    print("Saved", out)
    print(df)

if __name__ == "__main__":
    main()
