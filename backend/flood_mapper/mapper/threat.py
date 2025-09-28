import logging
import pandas as pd
from datetime import timedelta

def calculate_threat_score(forecast_df, config):
    """
    Calculates a scalar threat score based on rainfall forecast data and
    performs a "safe-check" to see if the full analysis can be skipped.

    Args:
        forecast_df (pd.DataFrame): DataFrame with rainfall forecast data.
        config (dict): The project configuration dictionary.

    Returns:
        tuple: (threat_score, is_safe) where threat_score is a float (0-1)
               and is_safe is a boolean.
    """
    thresholds = config['safe_check_thresholds']
    
    # Assume 'today' is the latest date with a non-null 'Rainfall' value
    today = forecast_df.dropna(subset=['Rainfall']).iloc[-1]['Date']
    logging.info(f"Analysis date set to: {today.strftime('%Y-%m-%d')}")

    # --- Perform Safe-Check ---
    prev_15_days = forecast_df[
        (forecast_df['Date'] > today - timedelta(days=15)) & 
        (forecast_df['Date'] <= today)
    ]
    next_5_days = forecast_df[
        (forecast_df['Date'] > today) & 
        (forecast_df['Date'] <= today + timedelta(days=5))
    ]
    analysis_window = pd.concat([prev_15_days.tail(1), next_5_days]) # today + next 5 days

    recent_rain_sum = prev_15_days['Rainfall'].sum()
    forecast_rain_sum = next_5_days['Rainfall'].sum()
    any_flood_pred = next_5_days['Flood_Pred_Smoothed'].any()
    avg_flood_prob = analysis_window['Flood_Prob_Smoothed'].mean()

    is_safe = (
        recent_rain_sum < thresholds['R0_recent_mm'] and
        forecast_rain_sum < thresholds['R0_forecast_mm'] and
        not any_flood_pred and
        avg_flood_prob < thresholds['P0_prob']
    )

    if is_safe:
        return 0.0, True

    # --- Calculate Full Threat Score ---
    weights = config['threat_weights']
    norm_params = config['threat_normalization']
    
    today_data = forecast_df[forecast_df['Date'] == today].iloc[0]
    
    # Normalization based on configured high-percentile values
    norm_rain_3d = min(today_data['Rain_3d_sum'] / norm_params['rain_3d_sum_p95'], 1.0)
    norm_rain_7d = min(today_data['Rain_7d_sum'] / norm_params['rain_7d_sum_p95'], 1.0)
    
    # Use max future values as a conservative estimate
    # Handle cases where there is no future data by defaulting to 0.0
    norm_forecast_5d = 0.0
    if not next_5_days.empty and not next_5_days['Rain_5d_sum'].isnull().all():
        norm_forecast_5d = min(next_5_days['Rain_5d_sum'].max() / norm_params['forecast_5d_sum_p95'], 1.0)

    norm_flood_prob = analysis_window['Flood_Prob_Smoothed'].max() if not analysis_window.empty else 0.0
    
    # Weighted sum
    threat_score = (
        norm_rain_3d * weights['rain_3d_sum'] +
        norm_rain_7d * weights['rain_7d_sum'] +
        norm_forecast_5d * weights['forecast_5d_sum'] +
        norm_flood_prob * weights['flood_prob']
    )
    
    # Apply multiplier if a flood is predicted
    if any_flood_pred:
        multiplier = config['combination_params']['flood_pred_multiplier']
        threat_score *= multiplier
        logging.info(f"Flood prediction detected. Applying multiplier of {multiplier}.")

    return min(threat_score, 1.0), False