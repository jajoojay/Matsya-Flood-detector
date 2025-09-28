from flask import Flask, jsonify, send_from_directory, make_response
from flask_cors import CORS
import pandas as pd
import os
import subprocess
import sys

# Initialize Flask app
app = Flask(__name__)
# Enable Cross-Origin Resource Sharing for all routes
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- Define project paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_GENERATOR_PATH = os.path.join(BASE_DIR, 'csv_generator')
FLOOD_DETECTOR_PATH = os.path.join(BASE_DIR, 'flood_detector')
FLOOD_MAPPER_PATH = os.path.join(BASE_DIR, 'flood_mapper')

# --- Helper Functions ---
def get_risk_level(prob):
    """Converts a probability score into a risk category."""
    if prob > 0.7:
        return {"status": "High", "level": "high"}
    elif prob > 0.3:
        return {"status": "Moderate", "level": "medium"}
    else:
        return {"status": "Low", "level": "low"}

# --- API Endpoints ---

@app.route('/api/current_flood_risk', methods=['GET'])
def get_current_flood_risk():
    """Endpoint to get the current flood risk."""
    try:
        file_path = os.path.join(CSV_GENERATOR_PATH, 'flood_prediction.csv')
        df = pd.read_csv(file_path)
        latest_risk_prob = df['Flood_Prob'].iloc[-1]
        risk = get_risk_level(latest_risk_prob)
        return jsonify(risk)
    except Exception as e:
        return jsonify({"error": f"Could not retrieve flood risk: {str(e)}"}), 500

@app.route('/api/river_level', methods=['GET'])
def get_river_level():
    """Endpoint to get the current river level."""
    try:
        file_path = os.path.join(FLOOD_DETECTOR_PATH, 'predicted_river_level.csv')
        df = pd.read_csv(file_path)
        current_level = df['pred_river_level'].iloc[0]
        response = {
            "riverName": "Ravi River",
            "stationName": "Madhopur Station",
            "currentLevel": round(current_level, 2),
            "unit": "m"
        }
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": f"Could not retrieve river level: {str(e)}"}), 500

@app.route('/api/forecast_rain', methods=['GET'])
def get_forecast_rain():
    """Endpoint for 5-day rainfall forecast."""
    try:
        file_path = os.path.join(FLOOD_DETECTOR_PATH, 'forecast_rainfall.csv')
        df = pd.read_csv(file_path)
        df = df.rename(columns={"Date": "day", "Rainfall": "rainfall"})
        # Ensure we only take 5 days
        return jsonify(df.head(5).to_dict(orient='records'))
    except Exception as e:
        return jsonify({"error": f"Could not retrieve rain forecast: {str(e)}"}), 500

@app.route('/api/forecast_river', methods=['GET'])
def get_forecast_river():
    """Endpoint for 5-day river level forecast."""
    try:
        file_path = os.path.join(FLOOD_DETECTOR_PATH, 'predicted_river_level.csv')
        df = pd.read_csv(file_path)
        # Skip the first row (current day) and take the next 5 days
        df = df.iloc[1:6]
        df = df.rename(columns={"date": "day", "pred_river_level": "level"})
        df['level'] = df['level'].round(2)
        return jsonify(df.to_dict(orient='records'))
    except Exception as e:
        return jsonify({"error": f"Could not retrieve river forecast: {str(e)}"}), 500

@app.route('/api/history_river', methods=['GET'])
def get_history_river():
    """Endpoint for previous 30 days of river levels."""
    try:
        file_path = os.path.join(FLOOD_DETECTOR_PATH, 'combined_daily_2019_2025.csv')
        df = pd.read_csv(file_path, parse_dates=['date'])
        df = df.sort_values(by='date', ascending=False).head(30)
        df = df[['date', 'stage_mean']].rename(columns={"date": "day", "stage_mean": "level"})
        df['day'] = df['day'].dt.strftime('%Y-%m-%d')
        df['level'] = df['level'].round(2)
        return jsonify(df.sort_values(by='day').to_dict(orient='records'))
    except Exception as e:
        return jsonify({"error": f"Could not retrieve river history: {str(e)}"}), 500

@app.route('/api/rainfall_comparison', methods=['GET'])
def get_rainfall_comparison():
    """Endpoint for monthly rainfall comparison for the last 12 months."""
    try:
        file_path = os.path.join(CSV_GENERATOR_PATH, 'rainfall_data.csv')
        df = pd.read_csv(file_path, parse_dates=['Date'], dayfirst=True)
        df['Month'] = df['Date'].dt.to_period('M')
        monthly_data = df.groupby('Month')['Rainfall'].sum().reset_index()
        monthly_data = monthly_data.sort_values(by='Month', ascending=False).head(12)
        monthly_data['Month'] = monthly_data['Month'].dt.strftime('%Y-%m')
        response = monthly_data.rename(columns={"Month": "month", "Rainfall": "rainfall"}).to_dict(orient='records')
        return jsonify(sorted(response, key=lambda x: x['month']))
    except Exception as e:
        return jsonify({"error": f"Could not retrieve rainfall comparison: {str(e)}"}), 500

@app.route('/api/map', methods=['GET'])
def get_map():
    """Serves the HTML map file."""
    map_directory = os.path.join(FLOOD_MAPPER_PATH, 'output')
    try:
        return send_from_directory(map_directory, 'risk_overlay.html')
    except FileNotFoundError:
        return jsonify({'error': 'Map file not found.'}), 404
    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/api/run-models', methods=['POST'])
def run_models():
    """Triggers the execution of the machine learning models."""
    try:
        print("--- Running Script: CSV Generator ---")
        subprocess.run([sys.executable, 'generator.py'], capture_output=True, text=True, check=True, cwd=CSV_GENERATOR_PATH)
        print("--- CSV Generator Complete ---")

        print("--- Running Model 1: Flood Detector ---")
        subprocess.run([sys.executable, 'combine.py'], capture_output=True, text=True, check=True, cwd=FLOOD_DETECTOR_PATH)
        print("--- Model 1 Complete ---")

        print("--- Running Model 2: Flood Mapper ---")
        subprocess.run([sys.executable, 'run_analysis.py'], capture_output=True, text=True, check=True, cwd=FLOOD_MAPPER_PATH)
        print("--- Model 2 Complete ---")
        
        return jsonify({"message": "Models executed successfully."})

    except subprocess.CalledProcessError as e:
        return jsonify({"error": "A model script failed.", "details": e.stderr}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)