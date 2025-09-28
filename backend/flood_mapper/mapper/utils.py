import logging
import yaml
import numpy as np
import geopandas as gpd

def load_config(config_path):
    """Loads the YAML configuration file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def normalize_array(arr):
    """Normalizes a NumPy array to a 0-1 scale."""
    min_val = np.nanmin(arr)
    max_val = np.nanmax(arr)
    if max_val == min_val:
        return np.zeros_like(arr)
    return (arr - min_val) / (max_val - min_val)

def ensure_crs(gdf, target_crs):
    """
    Ensures a GeoDataFrame is in the target CRS, reprojecting if necessary.

    Args:
        gdf (gpd.GeoDataFrame): The input GeoDataFrame.
        target_crs (str): The target CRS (e.g., 'EPSG:4326').

    Returns:
        gpd.GeoDataFrame: The GeoDataFrame in the target CRS.
    """
    if gdf.crs is None:
        raise ValueError("Input GeoDataFrame has no CRS defined.")
    if gdf.crs.to_string() != target_crs:
        logging.info(f"Reprojecting GeoDataFrame from {gdf.crs.to_string()} to {target_crs}.")
        return gdf.to_crs(target_crs)
    return gdf