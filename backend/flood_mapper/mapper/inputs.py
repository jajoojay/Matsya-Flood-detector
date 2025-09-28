import logging
import rasterio
from rasterio.mask import mask
import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping, box
from tqdm import tqdm
import numpy as np
from rasterio.warp import calculate_default_transform, reproject, Resampling
import tempfile
import os

from . import utils

def load_and_clip_data(config):
    """
    Loads all input data, reprojects to a common CRS, and clips to the
    study area boundary.

    Args:
        config (dict): The project configuration dictionary.

    Returns:
        dict: A dictionary containing all loaded and processed data, including
              GeoDataFrames, NumPy arrays, and raster profiles.
    """
    paths = config['paths']
    params = config['parameters']
    target_crs = params['target_crs']

    # Load boundary
    boundary_gdf = gpd.read_file(paths['boundary'])
    boundary_gdf = utils.ensure_crs(boundary_gdf, target_crs)
    if boundary_gdf.empty:
        raise ValueError("Boundary file is empty or could not be loaded.")
    
    # Get the total bounds of the boundary layer for consistent clipping
    total_bounds = boundary_gdf.total_bounds
    clipping_box = box(*total_bounds)
    clipping_geom = [mapping(clipping_box)]

    clipped_data = {'boundary': boundary_gdf}

    # --- RASTER CLIPPING ---
    rasters_to_clip = {'dem': paths['dem'], 'lulc': paths['lulc']}
    for name, path in tqdm(rasters_to_clip.items(), desc="Clipping Rasters"):
        with rasterio.open(path) as src:
            # Reproject if CRS does not match target
            if src.crs.to_string() != target_crs:
                logging.info(f"Reprojecting {name} from {src.crs} to {target_crs} using a temporary file.")
                
                with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmpfile:
                    tmp_filename = tmpfile.name
                
                try:
                    # Calculate transform and dimensions of reprojected raster
                    dst_transform, dst_width, dst_height = calculate_default_transform(
                        src.crs, target_crs, src.width, src.height, *src.bounds
                    )
                    
                    reprojected_meta = src.meta.copy()
                    reprojected_meta.update({
                        'crs': target_crs,
                        'transform': dst_transform,
                        'width': dst_width,
                        'height': dst_height,
                        'count': 1
                    })

                    with rasterio.open(tmp_filename, 'w', **reprojected_meta) as dst:
                        resampling_method = Resampling.nearest if name == 'lulc' else Resampling.bilinear
                        logging.info(f"Using {resampling_method.name} resampling for {name}")
                        reproject(
                            source=rasterio.band(src, 1),
                            destination=rasterio.band(dst, 1),
                            src_transform=src.transform,
                            src_crs=src.crs,
                            dst_transform=dst_transform,
                            dst_crs=rasterio.crs.CRS.from_string(target_crs),
                            resampling=resampling_method,
                        )

                    with rasterio.open(tmp_filename) as dataset:
                        out_image, out_transform = mask(dataset, clipping_geom, crop=True)

                    out_meta = reprojected_meta.copy()
                finally:
                    os.remove(tmp_filename)

            else:
                # Mask the original raster
                out_image, out_transform = mask(src, clipping_geom, crop=True)
                out_meta = src.meta.copy()

            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform
            })
            clipped_data[f'{name}_array'] = out_image[0] # Assume single band
            clipped_data[f'{name}_profile'] = out_meta
    
    logging.info("DEM and LULC rasters clipped successfully.")
    
    # --- VECTOR CLIPPING ---
    # Clip Rivers with a buffer
    logging.info("Clipping rivers with buffer...")
    rivers_gdf = gpd.read_file(paths['rivers'])
    rivers_gdf = utils.ensure_crs(rivers_gdf, target_crs)
    
    buffer_dist_m = params['river_buffer_km'] * 1000
    boundary_buffered = boundary_gdf.buffer(buffer_dist_m)
    
    # Use spatial index for performance
    sindex = rivers_gdf.sindex
    possible_matches_index = list(sindex.intersection(boundary_buffered.unary_union.bounds))
    possible_matches = rivers_gdf.iloc[possible_matches_index]
    precise_matches = possible_matches[possible_matches.intersects(boundary_buffered.unary_union)]
    clipped_data['rivers'] = precise_matches
    logging.info(f"Found {len(precise_matches)} river features within boundary buffer.")

    # Clip Water Bodies and filter by area
    logging.info("Clipping water bodies and filtering reservoirs...")
    waterbodies_gdf = gpd.read_file(paths['waterbodies'])
    waterbodies_gdf = utils.ensure_crs(waterbodies_gdf, target_crs)
    
    # Clip to the exact boundary
    clipped_wb = gpd.clip(waterbodies_gdf, boundary_gdf)
    
    # Filter reservoirs by area
    min_area_m2 = params['reservoir_min_ha'] * 10000
    clipped_wb['area_m2'] = clipped_wb.geometry.area
    reservoirs_gdf = clipped_wb[clipped_wb['area_m2'] >= min_area_m2].copy()
    
    clipped_data['waterbodies'] = clipped_wb
    clipped_data['reservoirs'] = reservoirs_gdf
    logging.info(f"Found {len(clipped_wb)} water bodies and {len(reservoirs_gdf)} significant reservoirs.")

    # --- FORECAST DATA ---
    logging.info("Loading rainfall forecast data...")
    forecast_df = pd.read_csv(paths['rain_forecast'], parse_dates=['Date'])
    # Explicitly convert to datetime to prevent errors if parsing fails silently
    forecast_df['Date'] = pd.to_datetime(forecast_df['Date'], dayfirst=True)
    logging.info(f"Forecast data 'Date' column type: {forecast_df['Date'].dtype}")

    clipped_data['rain_forecast'] = forecast_df
    logging.info("Forecast data loaded.")
    
    return clipped_data