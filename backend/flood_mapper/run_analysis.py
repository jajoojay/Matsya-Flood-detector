import os
import logging
import json
import numpy as np
import rasterio

from mapper import inputs, threat, vulnerability, combine, utils

# --- Configuration ---
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

# Construct an absolute path to the config file relative to this script's location.
# This makes the script runnable from any directory.
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.yml')

def main():
    """
    Main function to run the entire flood risk mapping pipeline.
    """
    logging.info("--- Starting Flood Mapper v3 Analysis ---")

    # 1. Load Configuration
    try:
        config = utils.load_config(CONFIG_PATH)
        logging.info("Configuration loaded successfully.")
    except FileNotFoundError:
        logging.error(f"Configuration file not found at {CONFIG_PATH}. Exiting.")
        return
    except Exception as e:
        logging.error(f"Error loading configuration: {e}. Exiting.")
        return

    # Resolve relative paths in config to be absolute based on config file location
    config_dir = os.path.dirname(CONFIG_PATH)
    for key, path in config['paths'].items():
        # Only resolve if it's not already an absolute path
        if not os.path.isabs(path):
            config['paths'][key] = os.path.normpath(os.path.join(config_dir, path))
    logging.info("Resolved relative file paths in configuration to be absolute.")
    
    output_dir = config['paths']['output_dir']
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logging.info(f"Created output directory: {output_dir}")

    # 2. Load and Preprocess Data
    logging.info("Step 1: Loading and preprocessing input data...")
    try:
        clipped_data = inputs.load_and_clip_data(config)
        logging.info("All input data loaded and clipped to boundary.")
    except Exception as e:
        logging.error(f"Failed during data loading and preprocessing: {e}")
        return

    # 3. Calculate Threat Score and perform Safe-Check
    logging.info("Step 2: Calculating threat score and performing safe-check...")
    try:
        threat_score, is_safe = threat.calculate_threat_score(
            clipped_data['rain_forecast'], config
        )
    except Exception as e:
        logging.error(f"Failed during threat calculation: {e}")
        return

    if is_safe:
        logging.warning("SAFE-CHECK PASSED. Conditions are safe. Generating a 'Very Low Risk' map.")
        # Create a safe raster (all pixels = 1)
        profile = clipped_data['dem_profile']
        safe_raster = np.ones(clipped_data['dem_array'].shape, dtype=np.uint8)
        
        # Generate minimal outputs for a safe scenario
        combine.generate_safe_outputs(
            safe_raster, profile, clipped_data['boundary'], clipped_data['waterbodies'], config
        )
        logging.info("--- Analysis complete (Safe Scenario) ---")
        return

    logging.info(f"SAFE-CHECK FAILED. Threat score: {threat_score:.4f}. Proceeding with full analysis.")

    # 4. Calculate Vulnerability
    logging.info("Step 3: Calculating spatial vulnerability layer...")
    try:
        vulnerability_raster = vulnerability.calculate_vulnerability(
            clipped_data, config, threat_score
        )
        logging.info("Vulnerability layer calculated successfully.")
    except Exception as e:
        logging.error(f"Failed during vulnerability calculation: {e}")
        return

    # 5. Combine and Classify
    logging.info("Step 4: Combining vulnerability and threat, and classifying risk...")
    try:
        classified_raster, composite_risk = combine.combine_and_classify(
            vulnerability_raster, threat_score, clipped_data, config
        )
        logging.info("Risk classification complete.")
    except Exception as e:
        logging.error(f"Failed during combination and classification: {e}")
        return
        
    # 6. Generate Outputs
    logging.info("Step 5: Generating final output files...")
    try:
        report_data = combine.generate_outputs(
            classified_raster=classified_raster,
            composite_raster=composite_risk,
            profile=clipped_data['dem_profile'],
            boundary_gdf=clipped_data['boundary'],
            waterbodies_gdf=clipped_data['waterbodies'],
            config=config,
            threat_score=threat_score
        )
        logging.info(f"Outputs generated in '{config['paths']['output_dir']}' directory.")
        logging.info(f"Analysis Summary: {report_data['summary']}")

    except Exception as e:
        logging.error(f"Failed during output generation: {e}")
        return

    logging.info("--- Flood Mapper v3 Analysis Completed Successfully ---")


if __name__ == "__main__":
    main()