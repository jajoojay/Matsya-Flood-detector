#!/usr/bin/env python3
"""
final_flood_dashboard.py

Runs minimal required steps (if missing) and shows the dashboard
in a matplotlib window (no images saved). Also shows a simple map
with upstream bbox and Gurdaspur location colored by risk.
"""
import os
import subprocess
import pandas as pd
import matplotlib.pyplot as plt

# Define script directory at the module level for global access
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def ensure_core_outputs():
    # If any required outputs missing, run combine (which produced everything)
    required = ["forecast_rainfall.csv","upstream_forecast_gfs.csv","predicted_river_level.csv","flood_forecast.csv"]
    missing = [p for p in required if not os.path.exists(p)]
    if missing:
        # Use the globally defined SCRIPT_DIR
        combine_script = "combine.py"
        combine_path = os.path.join(SCRIPT_DIR, combine_script)

        print("Missing outputs:", missing)
        print(f"Running {combine_script} (this will retrain and produce outputs).")
        res = subprocess.run(f"python {combine_path}", shell=True, cwd=SCRIPT_DIR)
        if res.returncode != 0:
            raise RuntimeError(f"{combine_script} failed; fix errors first.")

def show_plots_and_map():
    df = pd.read_csv("flood_forecast.csv", parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    print("\nFlood forecast (5-day):")
    print(df.to_string(index=False))

    # classification mapping (must match predict_flood)
    def classify(p):
        if p < 0.10: return "No"
        elif p < 0.30: return "Low"
        elif p < 0.60: return "Moderate"
        else: return "High"

    df["risk_class"] = df["flood_probability"].apply(classify)
    df["flood_probability_pct"] = (df["flood_probability"]*100).round(1)

    # Plotting: three subplots
    fig, axs = plt.subplots(3, 1, figsize=(10, 12), sharex=True)

    # 1. Local rainfall
    axs[0].bar(df["date"], df["local_rain"], color="skyblue", label="Local rain (Gurdaspur)")
    axs[0].set_ylabel("mm/day")
    axs[0].set_title("Local (Gurdaspur) Forecast")
    axs[0].legend()

    # 2. Upstream rainfall (use upstream_forecast_gfs.csv if exists)
    upstream_gfs_path = os.path.join(SCRIPT_DIR, "upstream_forecast_gfs.csv") # Now uses global SCRIPT_DIR
    if os.path.exists(upstream_gfs_path):
        up = pd.read_csv(upstream_gfs_path, parse_dates=["date"]).sort_values("date")
        axs[1].bar(up["date"], up["upstream_rain"], color="lightcoral", label="Upstream rain (Himachal)")
        axs[1].set_ylabel("mm/day")
        axs[1].set_title("Upstream Forecast")
        axs[1].legend()
    else:
        axs[1].text(0.1,0.5,"No upstream forecast found", transform=axs[1].transAxes)

    # 3. Predicted river level and flood probability on twin axis
    axs[2].plot(df["date"], df["pred_river_level"], marker="o", color="green", label="Predicted river level")
    ax2 = axs[2].twinx()
    ax2.plot(df["date"], df["flood_probability"]*100, marker="s", color="red", linestyle="--", label="Flood probability (%)")
    axs[2].set_ylabel("River level")
    ax2.set_ylabel("Flood prob (%)")
    axs[2].set_title("River level & Flood prob")
    # Combine legends from both y-axes for a cleaner look
    lines, labels = axs[2].get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines + lines2, labels + labels2, loc="upper left")

    plt.xticks(rotation=25)
    plt.tight_layout()
    plt.show()

    # --- Simple map view (no external GIS libs) ---
    # Box for upstream bbox from user earlier: lon_min,lat_min,lon_max,lat_max ~ (75.6E,32.3N,77.4E,33.2N)
    lon_min, lat_min, lon_max, lat_max = 75.6, 32.3, 77.4, 33.2
    himachal_centroid = ((lat_min+lat_max)/2.0, (lon_min+lon_max)/2.0)
    gurdaspur_coord = (32.03, 75.4)  # lat, lon

    latest = df.iloc[-1]
    risk = latest["risk_class"]

    color_map = {"No":"green","Low":"yellow","Moderate":"orange","High":"red"}

    fig2, ax = plt.subplots(figsize=(7,7))
    ax.set_title("Simple Flood Risk Map")
    ax.set_xlim(lon_min-0.5, lon_max+0.5)
    ax.set_ylim(lat_min-0.5, lat_max+0.5)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    # draw upstream bbox
    rect_lon = [lon_min, lon_max, lon_max, lon_min, lon_min]
    rect_lat = [lat_min, lat_min, lat_max, lat_max, lat_min]
    ax.plot(rect_lon, rect_lat, linestyle='-', color='blue', linewidth=1)
    ax.text(himachal_centroid[1], himachal_centroid[0], "Upstream\n(Himachal)", ha="center", va="center", color="blue")

    # plot gurdaspur
    ax.scatter(gurdaspur_coord[1], gurdaspur_coord[0], s=200, c=color_map.get(risk,"gray"), edgecolor='k')
    ax.text(gurdaspur_coord[1]+0.05, gurdaspur_coord[0], f"Gurdaspur: {risk}", va="center")

    plt.tight_layout()
    plt.show()

def main():
    ensure_core_outputs()
    show_plots_and_map()

if __name__ == "__main__":
    main()
