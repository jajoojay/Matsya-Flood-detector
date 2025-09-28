import pandas as pd
import requests
import datetime
import joblib
import os

# --- Get script's directory to build robust file paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Config ---
API_KEY = "2721668f5af648c798692645252209"  # Replace with your API key
LAT, LON = 32.04, 75.40
MODEL_FILE = os.path.join(SCRIPT_DIR, "flood_model.pkl")
HISTORICAL_CSV = os.path.join(SCRIPT_DIR, "rainfall_data.csv")
CSV_OUTPUT = os.path.join(SCRIPT_DIR, "flood_prediction.csv")

# --- Delete old files ---
if os.path.exists(CSV_OUTPUT):
    os.remove(CSV_OUTPUT)


# --- Load model ---
rf = joblib.load(MODEL_FILE)

# --- Helper functions ---
def fetch_history(date):
    url = f"http://api.weatherapi.com/v1/history.json?key={API_KEY}&q={LAT},{LON}&dt={date.strftime('%Y-%m-%d')}"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    return data["forecast"]["forecastday"][0]["day"]["totalprecip_mm"]

def fetch_forecast(days):
    url = f"http://api.weatherapi.com/v1/forecast.json?key={API_KEY}&q={LAT},{LON}&days={days}"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    records = []
    for day_data in data["forecast"]["forecastday"]:
        records.append({"Date": pd.to_datetime(day_data["date"]), "Rainfall": day_data["day"]["totalprecip_mm"]})
    return pd.DataFrame(records)

df_new = pd.DataFrame()

# --- Fetch data for recent and future dates ---
today = datetime.date.today()
past_start = today - datetime.timedelta(days=14)
forecast_days = 5

# --- Prepare CSV fallback data ---
df_csv_fallback = None
try:
    df_csv_fallback = pd.read_csv(HISTORICAL_CSV, parse_dates=['Date'], dayfirst=True)
    # Ensure 'Date' is just a date for easier comparison
    df_csv_fallback['Date'] = pd.to_datetime(df_csv_fallback['Date']).dt.date
    df_csv_fallback.set_index('Date', inplace=True)
except FileNotFoundError:
    print(f"Warning: Historical CSV fallback file not found at {HISTORICAL_CSV}")

# --- Fetch past 14 days via history API ---
records = []
for d in pd.date_range(past_start, today):
    try:
        rainfall = fetch_history(d)
        records.append({"Date": d, "Rainfall": rainfall})
    except requests.exceptions.RequestException as e:
        print(f"History API failed for {d.date()}: {e}. Attempting CSV fallback.")
        if df_csv_fallback is not None and d.date() in df_csv_fallback.index:
            rainfall = df_csv_fallback.loc[d.date(), 'Rainfall']
            records.append({"Date": d, "Rainfall": float(rainfall)})
            print(f"Successfully used fallback for {d.date()}.")
df_new = pd.DataFrame(records)

# --- Fetch forecast for next 5 days ---
try:
    df_fore = fetch_forecast(forecast_days)
    df_new = pd.concat([df_new, df_fore], ignore_index=True)
except Exception as e:
    print(f"Forecast API failed: {e}. Skipping future days.")

# --- Check if data exists ---
if df_new.empty:
    print("No rainfall data found for the selected range. Exiting.")
    exit()

# --- Compute rolling sums ---
df_new['Rain_3d_sum'] = df_new['Rainfall'].rolling(3, min_periods=1).sum()
df_new['Rain_5d_sum'] = df_new['Rainfall'].rolling(5, min_periods=1).sum()
df_new['Rain_7d_sum'] = df_new['Rainfall'].rolling(7, min_periods=1).sum()

# --- Predict flood probability ---
features = ['Rainfall', 'Rain_3d_sum', 'Rain_5d_sum', 'Rain_7d_sum']
df_new['Flood_Prob'] = rf.predict_proba(df_new[features])[:, 1]
df_new['Flood_Prob_%'] = (df_new['Flood_Prob'] * 100).round(2)

# --- Smooth predictions for continuous flood highlighting ---
df_new['Flood_Prob_Smoothed'] = df_new['Flood_Prob'].rolling(window=3, center=True, min_periods=1).max()
df_new['Flood_Pred_Smoothed'] = df_new['Flood_Prob_Smoothed'] >= 0.5
df_new['Flood_Pred_Smoothed'] = df_new['Flood_Pred_Smoothed'].astype(bool)

# --- Save CSV ---
df_new.to_csv(CSV_OUTPUT, index=False)
print(f"Flood predictions saved to {CSV_OUTPUT}")
