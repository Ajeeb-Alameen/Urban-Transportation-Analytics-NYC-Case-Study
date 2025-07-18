import pyarrow.parquet as pq
import pandas as pd
from collections import defaultdict
import numpy as np
import gc
import fastparquet
import geopandas as gpd
from sqlalchemy import create_engine

def pass1_accumulate_stats(parquet_file, group_means, group_medians):
    
    group_keys = ['route_id', 'borough', 'trip_type']
    service_cols = ['scheduled_number_of_buses', 'actual_number_of_buses', 'service_delivered']
    mean_cols = ['average_speed', 'wait_assessment']

    # For mean: store sum and count per group
    mean_stats = {col: defaultdict(lambda: [0, 0]) for col in mean_cols}  # {col: {(group_key): [sum, count]}}
    # For median: store values per group in temporary files or in-memory lists if small (risky for big data)
    median_values = {col: defaultdict(list) for col in service_cols}  

    for rg in range(parquet_file.num_row_groups):
        table = parquet_file.read_row_group(rg)
        df = table.to_pandas()
        print(f'Processing pass1 for chunk {rg}')
        # accumulate mean stats
        for col in mean_cols:
            for name, group in df.groupby(group_keys):
                s = group[col].dropna().sum()
                c = group[col].dropna().count()
                mean_stats[col][name][0] += s
                mean_stats[col][name][1] += c

        # accumulate median values (may be memory-heavy)
        for col in service_cols:
            for name, group in df.groupby(group_keys):
                median_values[col][name].extend(group[col].dropna().tolist())

        del df
        gc.collect()

        # Calculate global and group means
        for col in mean_cols:
            for key, (s, c) in mean_stats[col].items():
                group_means[col][key] = s / c if c > 0 else np.nan
            group_means[col]['__global__'] = sum(s for s, c in mean_stats[col].values()) / max(sum(c for s, c in mean_stats[col].values()),1)

        # Calculate group medians (slow)
        for col in service_cols:
            for key, values in median_values[col].items():
                group_medians[col][key] = np.median(values) if values else np.nan
            # global median for col:
            all_values = []
            for v in median_values[col].values():
                all_values.extend(v)
            group_medians[col]['__global__'] = np.median(all_values) if all_values else np.nan


def pass2_process_save(parquet_file, dim_stop, group_means, group_medians, outputfilename):
    # Prepare route_geo once
    route_geo = (
        dim_stop.groupby('Route ID')
        .agg({
            'Latitude': 'mean',
            'Longitude': 'mean',
            'Georeference': 'first'
        })
        .reset_index()
        .rename(columns={'Route ID': 'route_id'})
    )

    # Convert group_medians and group_means dicts to DataFrames for merging
    def dict_to_df(d, col_name):
        rows = []
        for k, v in d.items():
            if k != '__global__':  # skip global stats here
                rows.append({'route_id': k[0], 'borough': k[1], 'trip_type': k[2], col_name: v})
        return pd.DataFrame(rows)

    # Prepare median DataFrames for merging
    median_dfs = {col: dict_to_df(group_medians[col], col) for col in group_medians}
    mean_dfs = {col: dict_to_df(group_means[col], col) for col in group_means}

    # Store global stats separately for fallback
    global_medians = {col: group_medians[col].get('__global__', pd.NA) for col in group_medians}
    global_means = {col: group_means[col].get('__global__', pd.NA) for col in group_means}

    first_write = True  # Correctly track first write outside loop

    for rg in range(parquet_file.num_row_groups):
        table = parquet_file.read_row_group(rg)
        df = table.to_pandas()
        
        print(f'Processing pass2 for chunk {rg}')

        df['missing_service_info'] = df['scheduled_number_of_buses'].isna().astype('uint8')

        # Impute service_cols using merge + fillna
        service_cols = ['scheduled_number_of_buses', 'actual_number_of_buses', 'service_delivered']
        for col in service_cols:
            df = df.merge(
                median_dfs[col], on=['route_id', 'borough', 'trip_type'], how='left', suffixes=('', '_group_median')
            )
            df[col] = df[col].fillna(df[f'{col}_group_median']).fillna(global_medians[col])
            df.drop(columns=[f'{col}_group_median'], inplace=True)

        # Impute mean_cols using merge + fillna
        mean_cols = ['average_speed', 'wait_assessment']
        for col in mean_cols:
            df = df.merge(
                mean_dfs[col], on=['route_id', 'borough', 'trip_type'], how='left', suffixes=('', '_group_mean')
            )
            df[col] = df[col].fillna(df[f'{col}_group_mean']).fillna(global_means[col])
            df.drop(columns=[f'{col}_group_mean'], inplace=True)

        # Merge route-level geo data
        df = df.merge(route_geo, on='route_id', how='left')
        df = df.dropna(subset=['Latitude', 'Longitude', 'Georeference'])

        # Remove irrelevant rows
        df = df[
            (df['borough'] != 'Systemwide') &
            (df['route_id'] != 'Systemwide') &
            (df['trip_type'] != 'Systemwide')
        ]

        df = df.rename(columns={
            'scheduled_number_of_buses': 'scheduled_bus_trips',
            'actual_number_of_buses': 'actual_bus_trips'
        })

        df = df.drop_duplicates()
        df = df[df['missing_service_info'] == 0]
        df = df.drop_duplicates(subset=['route_id', 'month', 'scheduled_bus_trips'])

        # Feature engineering
        df['month'] = pd.to_datetime(df['month'])
        df['year'] = df['month'].dt.year
        df['month_num'] = df['month'].dt.month
        df['trip_gap'] = df['scheduled_bus_trips'] - df['actual_bus_trips']
        df['wait_assessment'] = pd.to_numeric(df['wait_assessment'], errors='coerce')
        df['service_delivered'] = pd.to_numeric(df['service_delivered'], errors='coerce')
        df['efficiency_score'] = df['wait_assessment'] * df['service_delivered']
        df['capped_service'] = df['service_delivered'].clip(upper=1.0)
        df['capped_efficiency'] = df['wait_assessment'] * df['capped_service']
        df['lateness_gap'] = 1.0 - df['wait_assessment']
        df['under_service_flag'] = (df['service_delivered'] < 1.0).astype(int)
        df['performance_index'] = 0.5 * df['wait_assessment'] + 0.5 * df['capped_service']
        df['performance_level'] = pd.cut(
            df['performance_index'],
            bins=[0, 0.5, 0.7, 0.85, 1.0],
            labels=['Low', 'Moderate', 'Good', 'Excellent'],
            include_lowest=True
        )
        df['early_indicator'] = (df['additional_travel_time'] < 0).astype(int)

        # Save chunk
        if first_write:
            df.to_parquet(outputfilename, engine="fastparquet", compression="snappy", index=False)
            first_write = False
        else:
            fastparquet.write(outputfilename, df, append=True)

        del df
        gc.collect()

def process_bus_geo_save(parquet_file, geo_file, final_file):
    
    first_write = True
    
    world = gpd.read_file(geo_file)

    # Simplify columns (optional)
    world = world[["ADMIN", "ISO_A2", "geometry"]].rename(columns={
        "ADMIN": "country_name",
        "ISO_A2": "iso_code"
    })
    
     # Ensure same CRS
    world = world.to_crs("EPSG:4326")

    for rg in range(parquet_file.num_row_groups):
        table = parquet_file.read_row_group(rg)
        df = table.to_pandas()
        
        print(f'Processing geo info for chunk {rg}')
    
        gdf = gpd.GeoDataFrame(
            df, 
            geometry=gpd.points_from_xy(df["Longitude"], df["Latitude"]),
            crs="EPSG:4326"
        )
        
        del df 
       

        # Spatial join
        joined = gpd.sjoin(gdf, world, how="left", predicate="within")

        # Final result
        df_with_iso = joined.drop(columns=["geometry", "index_right"])
        df_with_iso = df_with_iso.rename(columns={"iso_code": "country_iso", "country_name": "country"})
        
        # Save chunk
        if first_write:
            df_with_iso.to_parquet(final_file, engine="fastparquet", compression="snappy", index=False)
            first_write = False
        else:
            fastparquet.write(final_file, df_with_iso, append=True)

        
        del df_with_iso
        gc.collect()

     
#DAG functions

def process_save_bus_data(busfilename, bus_stopsfilename, geo_file, bus_temp_file, bus_outputfilename):
    
    parquet_file = pq.ParquetFile(busfilename)
    dim_stop = pd.read_parquet(bus_stopsfilename).dropna(subset=['Latitude', 'Longitude'])

    group_keys = ['route_id', 'borough', 'trip_type']
    service_cols = ['scheduled_number_of_buses', 'actual_number_of_buses', 'service_delivered']
    mean_cols = ['average_speed', 'wait_assessment']

    group_means = {col: {} for col in mean_cols}
    group_medians = {col: {} for col in service_cols}


    pass1_accumulate_stats(parquet_file, group_means, group_medians)

    pass2_process_save(parquet_file, dim_stop, group_means, group_medians, bus_temp_file)
    
    del parquet_file
    gc.collect()
    
    cleaned_parquet_file = pq.ParquetFile(bus_temp_file)
    
    process_bus_geo_save(cleaned_parquet_file, geo_file, bus_outputfilename)
    


def load_to_postgres_bus_chunked(conn_str, bus_filename, table_name='bus', sql_chunk_size=35_000):
    print("Preparing connection...")
    engine = create_engine(conn_str)

    with engine.connect() as connection:
        print("Connected successfully")

        # Read parquet as row groups using PyArrow
        parquet_file = pq.ParquetFile(bus_filename)
        num_row_groups = parquet_file.num_row_groups

        first_chunk = True

        for i in range(num_row_groups):
            print(f"Processing chunk {i+1}/{num_row_groups}")
            chunk_df = parquet_file.read_row_group(i).to_pandas()

            chunk_df.to_sql(
                name=table_name,
                con=connection,
                if_exists='replace' if first_chunk else 'append',
                index=False,
                method='multi',  # Better batch performance
                chunksize=sql_chunk_size  # Controls the batch insert to SQL
            )

            first_chunk = False
            del chunk_df
            gc.collect()

    

    
   