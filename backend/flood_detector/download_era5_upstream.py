import cdsapi
import xarray as xr
import pandas as pd
import os
import zipfile

# Bounding box: [north, west, south, east]
BBOX = [33.2, 75.6, 32.3, 77.4]  # Himachal basin feeding Madhopur

START_YEAR, END_YEAR = 1981, 2025
OUT_CSV = "upstream_rainfall_era5.csv"

c = cdsapi.Client()

all_dfs = []

for year in range(START_YEAR, END_YEAR + 1):
    nc_file = f"era5_upstream_{year}.nc"
    zip_file = f"era5_upstream_{year}.nc.zip"

    # Download if missing
    if not os.path.exists(nc_file):
        print(f"Downloading ERA5 for {year}...")
        c.retrieve(
            'reanalysis-era5-land',
            {
                'variable': 'total_precipitation',
                'area': BBOX,
                'year': str(year),
                'month': [f"{m:02d}" for m in range(1, 13)],
                'day': [f"{d:02d}" for d in range(1, 32)],
                'time': '00:00',
                'format': 'netcdf',   # ensure NetCDF format
            },
            zip_file
        )

        # If CDS gave us a zip file, extract it
        if os.path.exists(zip_file):
            with zipfile.ZipFile(zip_file, 'r') as zf:
                zf.extractall(".")
                for name in zf.namelist():
                    if name.endswith(".nc"):
                        os.rename(name, nc_file)
            os.remove(zip_file)

    else:
        print(f"Found {nc_file}, skipping download.")

    # Convert NetCDF → DataFrame
    print(f"Processing {nc_file} ...")
    ds = xr.open_dataset(nc_file, engine="netcdf4")
    rain = ds['tp'] * 1000.0  # convert meters → mm

    # detect time dimension
    if "time" in ds.dims:
        time_dim = "time"
    elif "valid_time" in ds.dims:
        time_dim = "valid_time"
    else:
        raise KeyError(f"No time dimension found in {nc_file}")

    # aggregate daily and spatial mean
    rain_daily = rain.resample({time_dim: "1D"}).mean()
    rain_series = rain_daily.mean(dim=["latitude", "longitude"])

    df = rain_series.to_dataframe().reset_index()
    df = df.rename(columns={time_dim: "date", "tp": "upstream_rain"})
    df["date"] = pd.to_datetime(df["date"])
    all_dfs.append(df)

# Concatenate all years
df_all = pd.concat(all_dfs).sort_values("date").reset_index(drop=True)

# Save to CSV
df_all.to_csv(OUT_CSV, index=False)
print(f"Saved {OUT_CSV} with {len(df_all)} rows ({START_YEAR}–{END_YEAR}).")
