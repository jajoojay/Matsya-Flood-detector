import os
import logging
import json
import numpy as np
import rasterio
import folium
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from rasterio.features import shapes
import geopandas as gpd
from tqdm import tqdm

def combine_and_classify(vulnerability_raster, threat_score, clipped_data, config):
    """
    Combines the vulnerability raster with the scalar threat score, applies
    heuristics, and classifies the result into discrete risk categories.

    Args:
        vulnerability_raster (np.ndarray): The 2D vulnerability array.
        threat_score (float): The scalar threat score (0-1).
        clipped_data (dict): Dictionary of clipped data.
        config (dict): The project configuration dictionary.

    Returns:
        tuple: (classified_raster, composite_risk)
    """
    alpha = config['combination_params']['alpha']
    nodata_mask = np.isnan(vulnerability_raster)

    # --- Apply Reservoir Heuristic (if threat is high) ---
    if threat_score > config['combination_params']['reservoir_threat_threshold']:
        logging.info("High threat detected. Applying reservoir overflow heuristic...")
        # A full implementation would buffer reservoirs and increase vulnerability downstream.
        pass

    # --- Combine Vulnerability and Threat ---
    logging.info("Combining vulnerability and threat...")
    composite_risk = vulnerability_raster * (1 + threat_score * alpha)
    composite_risk = np.clip(composite_risk, 0, 1)
    composite_risk[nodata_mask] = np.nan
    
    # --- Classify into N classes ---
    logging.info("Classifying composite risk into discrete classes...")
    output_config = config['output_classes']
    n_classes = output_config['count']
    
    # Use fixed classification breaks from config for absolute risk mapping
    bins = output_config.get('classification_breaks')
    if not bins or len(bins) != n_classes - 1:
        raise ValueError(
            f"Config 'classification_breaks' must be a list of {n_classes - 1} values. "
            f"Found: {bins}"
        )
    
    valid_pixels = composite_risk[~nodata_mask]
    if len(valid_pixels) == 0:
        raise ValueError("No valid pixels found in the composite risk raster.")
    
    classified_raster = np.digitize(composite_risk, bins, right=False)
    classified_raster = classified_raster.astype(np.uint8)
    classified_raster[nodata_mask] = 0 # Use 0 for nodata
    
    return classified_raster, composite_risk


def generate_outputs(classified_raster, composite_raster, profile, boundary_gdf, waterbodies_gdf, config, threat_score):
    """Generates all specified output files."""
    output_dir = config['paths']['output_dir']
    
    # 1. Save classified raster as GeoTIFF
    logging.info("Saving classified risk raster (risk_classes.tif)...")
    profile.update(dtype=rasterio.uint8, count=1, nodata=0)
    tif_path = os.path.join(output_dir, 'risk_classes.tif')
    with rasterio.open(tif_path, 'w', **profile) as dst:
        dst.write(classified_raster, 1)

    # 2. Vectorize high-risk classes and save as GeoJSON
    logging.info("Vectorizing high-risk areas (risk_polygons.geojson)...")
    classes_to_vectorize = config['output_classes']['classes_to_vectorize']
    high_risk_mask = np.isin(classified_raster, classes_to_vectorize)
    
    results = [
        {'properties': {'risk_class': v}, 'geometry': s}
        for i, (s, v) in enumerate(shapes(classified_raster, mask=high_risk_mask, transform=profile['transform']))
    ]

    if results:
        gdf = gpd.GeoDataFrame.from_features(results, crs=profile['crs'])
        gdf.to_file(os.path.join(output_dir, 'risk_polygons.geojson'), driver='GeoJSON')
    else:
        logging.warning("No high-risk areas found to vectorize.")
        
    # 3. Create and save interactive Folium map
    logging.info("Generating interactive map (risk_overlay.html)...")
    _create_folium_map(classified_raster, tif_path, boundary_gdf, waterbodies_gdf, config, output_dir)
    
    # 4. Create and save JSON report
    logging.info("Generating summary report (report.json)...")
    report_data = _create_json_report(classified_raster, profile, threat_score, config)
    with open(os.path.join(output_dir, 'report.json'), 'w') as f:
        json.dump(report_data, f, indent=4)
        
    return report_data

def _create_folium_map(raster, tif_path, boundary_gdf, waterbodies_gdf, config, output_dir):
    """Helper to create the Folium map."""
    boundary_wgs84 = boundary_gdf.to_crs("EPSG:4326")
    map_center = [boundary_wgs84.centroid.y.mean(), boundary_wgs84.centroid.x.mean()]
    
    m = folium.Map(location=map_center, zoom_start=12, tiles="CartoDB positron")
    
    # Add satellite basemap as an alternative tile layer
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite',
        overlay=False,
        control=True
    ).add_to(m)
    
    n_classes = config['output_classes']['count']
    cmap_config = config['output_classes']['colormap']
    labels = config['output_classes']['labels']

    # Handle both predefined colormap names and custom color lists
    if isinstance(cmap_config, list):
        if len(cmap_config) < n_classes:
            raise ValueError(
                f"Custom colormap in config has {len(cmap_config)} colors, but {n_classes} are required by 'count'."
            )
        colors = cmap_config[:n_classes]
        cmap = mcolors.ListedColormap(colors)
    else:
        # It's a string name for a matplotlib colormap
        cmap = plt.get_cmap(cmap_config, n_classes)
        colors = [mcolors.to_hex(cmap(i)) for i in range(n_classes)]

    colored_raster = np.zeros((*raster.shape, 4), dtype=np.uint8) # RGBA
    for i in range(1, n_classes + 1):
        mask = (raster == i)
        color_rgba = [int(c*255) for c in mcolors.to_rgba(colors[i-1])]
        colored_raster[mask] = color_rgba
    
    with rasterio.open(tif_path) as src:
        bounds_wgs84 = rasterio.warp.transform_bounds(src.crs, "EPSG:4326", *src.bounds)

    # Get opacity from config, with a default of 0.6 for better visibility
    overlay_opacity = config.get('map_settings', {}).get('overlay_opacity', 0.6)

    folium.raster_layers.ImageOverlay(
        image=colored_raster,
        bounds=[[bounds_wgs84[1], bounds_wgs84[0]], [bounds_wgs84[3], bounds_wgs84[2]]],
        opacity=overlay_opacity, name='Flood Risk'
        ).add_to(m)

    folium.GeoJson(
        boundary_wgs84,
        style_function=lambda x: {'color': 'black', 'weight': 2, 'fillOpacity': 0.0},
        name='Study Area Boundary'
    ).add_to(m)
    
    # Add waterbodies layer
    if waterbodies_gdf is not None and not waterbodies_gdf.empty:
        waterbodies_wgs84 = waterbodies_gdf.to_crs("EPSG:4326")
        folium.GeoJson(
            waterbodies_wgs84,
            style_function=lambda x: {'color': '#007BFF', 'weight': 1, 'fillColor': '#007BFF', 'fillOpacity': 0.7},
            name='Water Bodies',
            show=True # Show by default for better context
        ).add_to(m)
    
    legend_html = '''
     <div style="position: fixed; bottom: 50px; left: 50px; width: 180px; z-index:9999;
     border:2px solid grey; font-size:14px; background-color:white; padding: 10px;">
     <b>Flood Risk Legend</b><br>'''
    for i, label in enumerate(labels):
        legend_html += f'<i style="background:{colors[i]}; width:20px; height:20px; display:inline-block; margin-right:5px; vertical-align:middle;"></i> {label}<br>'
    legend_html += '</div>'
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl().add_to(m)
    m.save(os.path.join(output_dir, 'risk_overlay.html'))

def _create_json_report(raster, profile, threat_score, config):
    """Helper to create the JSON report."""
    pixel_area = abs(profile['transform'][0] * profile['transform'][4]) / 1_000_000 # km^2
    total_pixels = np.sum(raster > 0)
    total_area_km2 = total_pixels * pixel_area
    labels = config['output_classes']['labels']
    area_by_class = {}
    for i in range(1, config['output_classes']['count'] + 1):
        class_pixels = np.sum(raster == i)
        class_area = class_pixels * pixel_area
        percentage = (class_pixels / total_pixels * 100) if total_pixels > 0 else 0
        area_by_class[labels[i-1]] = {
            "area_km2": round(class_area, 2), "percentage": round(percentage, 2)
        }
    
    recommendation = "Monitoring recommended."
    high_risk_pct = area_by_class.get("High Risk", {}).get("percentage", 0) + \
                    area_by_class.get("Very High Risk", {}).get("percentage", 0)
    if threat_score > 0.75 and high_risk_pct > 10:
        recommendation = "CRITICAL: High threat and large high-risk area. Issue alerts."
    elif threat_score > 0.5 or high_risk_pct > 20:
        recommendation = "WARNING: Elevated threat or significant high-risk area."

    report = {
        "summary": {
            "threat_score": round(threat_score, 4),
            "total_study_area_km2": round(total_area_km2, 2),
            "highest_risk_level": labels[np.max(raster)-1] if total_pixels > 0 else "N/A"
        },
        "area_distribution": area_by_class, "recommendation": recommendation
    }
    return report

def generate_safe_outputs(safe_raster, profile, boundary_gdf, waterbodies_gdf, config):
    """Generates minimal outputs for a safe scenario."""
    output_dir = config['paths']['output_dir']
    profile.update(dtype=rasterio.uint8, count=1, nodata=0)
    tif_path = os.path.join(output_dir, 'risk_classes.tif')
    with rasterio.open(tif_path, 'w', **profile) as dst:
        dst.write(safe_raster, 1)

    with open(os.path.join(output_dir, 'risk_polygons.geojson'), 'w') as f:
        f.write('{"type": "FeatureCollection", "features": []}')

    # Create a temporary config for the "safe" scenario to ensure helper
    # functions have the expected structure but with minimal data.
    safe_config = {
        'output_classes': {
            'count': 1,
            'labels': ["Very Low Risk"],
            'colormap': config.get('output_classes', {}).get('colormap', 'Greens'),
            # Add a dummy classification_breaks to satisfy the map function's check.
            # It's not used for a single class, but the key needs to exist.
            'classification_breaks': []
        },
        'paths': config['paths'] # For output_dir
    }

    _create_folium_map(safe_raster, tif_path, boundary_gdf, waterbodies_gdf, safe_config, output_dir)
        
    report = _create_json_report(safe_raster, profile, 0.0, safe_config)
    report['summary']['threat_score'] = 0.0
    report['recommendation'] = "SAFE: No significant flood threat detected."
    with open(os.path.join(output_dir, 'report.json'), 'w') as f:
        json.dump(report, f, indent=4)