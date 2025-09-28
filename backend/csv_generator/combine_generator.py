import pandas as pd
import requests
import datetime
import joblib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# --- Config ---
API_KEY = "2721668f5af648c798692645252209"  # Replace with your API key
LAT, LON = 32.04, 75.40
MODEL_FILE = "flood_model.pkl"
HISTORICAL_CSV = "rainfall_data.csv"  # daily rainfall 1981-2025
CSV_OUTPUT = "flood_prediction.csv"
PLOT_OUTPUT = "flood_prediction.png"

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

# --- User input ---
choice = input("Do you want prediction for (1) recent/future or (2) historical date? Enter 1 or 2: ").strip()

df_new = pd.DataFrame()

if choice == "1":
    today = datetime.date.today()
    past_start = today - datetime.timedelta(days=14)
    forecast_days = 5

    # --- Fetch past 14 days via history API ---
    records = []
    for d in pd.date_range(past_start, today):
        try:
            rainfall = fetch_history(d)
            records.append({"Date": d, "Rainfall": rainfall})
        except Exception as e:
            print(f"History API failed for {d}: {e}. Using CSV fallback.")
            df_csv = pd.read_csv(HISTORICAL_CSV, parse_dates=['Date'], dayfirst=True)
            df_csv['Date'] = pd.to_datetime(df_csv['Date'], format="%d-%m-%Y", errors='coerce')
            df_hist = df_csv[df_csv['Date'] == pd.Timestamp(d)]
            if not df_hist.empty:
                records.append({"Date": d, "Rainfall": float(df_hist['Rainfall'].values[0])})
    df_new = pd.DataFrame(records)

    # --- Fetch forecast for next 5 days ---
    try:
        df_fore = fetch_forecast(forecast_days)
        df_new = pd.concat([df_new, df_fore], ignore_index=True)
    except Exception as e:
        print(f"Forecast API failed: {e}. Skipping future days.")

elif choice == "2":
    date_str = input("Enter the date for prediction (YYYY-MM-DD): ").strip()
    target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    start_date = target_date - datetime.timedelta(days=10)
    end_date = target_date + datetime.timedelta(days=10)
    df_csv = pd.read_csv(HISTORICAL_CSV, parse_dates=['Date'], dayfirst=True)
    df_csv['Date'] = pd.to_datetime(df_csv['Date'], format="%d-%m-%Y", errors='coerce')
    df_new = df_csv[(df_csv['Date'] >= pd.Timestamp(start_date)) & (df_csv['Date'] <= pd.Timestamp(end_date))].copy()
else:
    print("Invalid choice.")
    exit()

# --- Check if we have data ---
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

# --- Smooth predictions ---
df_new['Flood_Prob_Smoothed'] = df_new['Flood_Prob'].rolling(window=3, center=True, min_periods=1).max()
df_new['Flood_Pred_Smoothed'] = df_new['Flood_Prob_Smoothed'] >= 0.5
df_new['Flood_Pred_Smoothed'] = df_new['Flood_Pred_Smoothed'].astype(bool)

# --- Identify continuous flood periods ---
flood_periods = []
start = None
for i, is_flood in enumerate(df_new['Flood_Pred_Smoothed']):
    if is_flood and start is None:
        start = df_new['Date'].iloc[i]
    elif not is_flood and start is not None:
        end = df_new['Date'].iloc[i-1]
        flood_periods.append((start, end))
        start = None
if start is not None:
    flood_periods.append((start, df_new['Date'].iloc[-1]))

# --- Plotting ---
plt.figure(figsize=(12,6))
for start, end in flood_periods:
    plt.axvspan(start - pd.Timedelta(hours=12), end + pd.Timedelta(hours=12), color='red', alpha=0.2)
    mid_date = start + (end - start)/2
    plt.text(mid_date, df_new['Rainfall'].max()*1.05, 'Flood Period', color='red',
             fontsize=10, fontweight='bold', ha='center', va='bottom')

plt.bar(df_new['Date'], df_new['Rainfall'], color='skyblue', alpha=0.6, label='Daily Rainfall (mm)')
plt.plot(df_new['Date'], df_new['Flood_Prob'], color='orange', marker='o', label='Flood Probability')
plt.plot(df_new['Date'], df_new['Flood_Prob_Smoothed'], color='red', linestyle='--', marker='x', label='Smoothed Flood Probability')

# Legend
flood_patch = mpatches.Patch(color='red', alpha=0.2, label='Continuous Flood Period (Smoothed Prediction)')
plt.legend(handles=[flood_patch,
                    plt.Line2D([], [], color='skyblue', marker='s', linestyle='None', label='Daily Rainfall (mm)'),
                    plt.Line2D([], [], color='orange', marker='o', linestyle='-', label='Flood Probability'),
                    plt.Line2D([], [], color='red', marker='x', linestyle='--', label='Smoothed Flood Probability')],
           loc='upper right')

plt.xlabel('Date')
plt.ylabel('Rainfall / Flood Probability')
plt.title('Flood Prediction')
plt.xticks(rotation=45)
plt.tight_layout()

# --- Save CSV + plot (overwrite each run) ---
df_new.to_csv(CSV_OUTPUT, index=False)
plt.savefig(PLOT_OUTPUT)
plt.show()
