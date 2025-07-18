import pandas as pd
import pyarrow.parquet as pq
from collections import defaultdict
import gc
import fastparquet
from sqlalchemy import create_engine

#trips functions

def convert_unix_to_local_time(all_trips: pd.DataFrame) -> pd.DataFrame:
    """
    Convert UNIX timestamps in 'all_trips' DataFrame to New York local time and remove timezone info.
    Also converts 'date' column to just the date part.
    
    Parameters:
        all_trips (pd.DataFrame): DataFrame with columns 'start_time', 'last_observed', 'marked_past', and 'date'.

    Returns:
        pd.DataFrame: Updated DataFrame with converted datetime columns.
    """
    # Convert UNIX time columns to datetime in New York timezone
    for col in ['start_time', 'last_observed', 'marked_past']:
        all_trips[col] = pd.to_datetime(all_trips[col], unit='s', utc=True)\
                            .dt.tz_convert('America/New_York')\
                            .dt.tz_localize(None)
    
    # Convert 'date' column to just the date (no time)
    all_trips['date'] = pd.to_datetime(all_trips['date']).dt.strftime('%Y-%m-%d')

    # Optional: Uncomment the next line to preview results in testing
    # print(all_trips.head())

    return all_trips

def add_fare_column(all_trips: pd.DataFrame, fare_per_trip: float = 2.90) -> pd.DataFrame:
    """
    Add a fixed fare per trip column to the DataFrame.

    Parameters:
        all_trips (pd.DataFrame): The DataFrame containing trip records.
        fare_per_trip (float): The fixed fare amount to assign to each trip.

    Returns:
        pd.DataFrame: Updated DataFrame with a 'fare_per_trip' column added.
    """
    all_trips['fare_per_trip'] = fare_per_trip
    
    # Optional: Preview the updated DataFrame
    # print(all_trips.head())
    
    return all_trips

def clean_and_filter_trips(all_trips: pd.DataFrame) -> pd.DataFrame:
    """
    - Fill missing values in 'marked_past' using 'last_observed' in both DataFrames.
    - Drop rows in 'all_stop_times' with missing 'departure_time' or 'arrival_time', in chunks.

    Parameters:
        all_trips (pd.DataFrame): DataFrame with 'marked_past' and 'last_observed'.
        

    Returns:
        dataframe: cleaned_all_trips
    """
    # Fill missing values in 'marked_past'
    all_trips['marked_past'] = all_trips['marked_past'].fillna(all_trips['last_observed'])

    return all_trips

def clean_subway_data_trips(trips_df):
    
    print("Convert UNIX timestamps in 'all_trips' DataFrame to New York local time and remove timezone info")
    trips_df = convert_unix_to_local_time(trips_df)
    
    print("Fill missing values in 'marked_past' using 'last_observed' in both DataFrames")
    trips_df = clean_and_filter_trips(trips_df)

    return trips_df

def feat_engineering_subway_data_trips(trips_df, fare_per_trip):
    


    print("Add a fixed fare per trip column to the DataFrame")
    trips_df = add_fare_column(trips_df, fare_per_trip)

    return trips_df

#stops functions

#optimized

def read_process_save_stops_chuncks(stops_filename, temp_filename, output_stop_filename):

    parquet_file_stops = pq.ParquetFile(stops_filename)
    
    num_row_groups = parquet_file_stops.num_row_groups
    first = True
    track_counts = defaultdict(lambda: defaultdict(int))
    global_modes = {}
    total_sum = 0.0
    total_count = 0
    global_duration_mean = 0
    
    
    
    for i in range(num_row_groups):
        stop_chunk = parquet_file_stops.read_row_group(i).to_pandas()
        print(f'Processing chunk: {i}')
        stop_chunk = convert_chunked_unix_to_local_time_per_chunck(stop_chunk)
        stop_chunk = add_stop_duration_per_chunk(stop_chunk)
          # ✅ Calculate partial mean stats
        total_sum, total_count = collect_global_mean_stop_duration(stop_chunk, total_sum, total_count)

        collect_track_per_chunk(stop_chunk, track_counts)

        save_stops_chunk(stop_chunk, temp_filename, first)
        first = False

        del stop_chunk
        gc.collect()
        
    global_duration_mean = total_sum / total_count if total_count > 0 else 0

    calculate_global_track_mode(track_counts, global_modes)

    read_mode_track_save_stops_chuncks(temp_filename, output_stop_filename, global_modes, global_duration_mean)

def read_mode_track_save_stops_chuncks(temp_filename, output_stop_filename, global_modes, global_duration_mean):

    parquet_file_stops = pq.ParquetFile(temp_filename)
    
    num_row_groups = parquet_file_stops.num_row_groups
    first = True
    
    
    for i in range(num_row_groups):
        stop_chunk = parquet_file_stops.read_row_group(i).to_pandas()
        print(f'Getting chunk: {i}')
        
        # ✅ Impute 0-duration values with global mean
        stop_chunk['stop_duration_seconds'] = stop_chunk['stop_duration_seconds'].fillna(global_duration_mean)
        zero_duration_mask = stop_chunk['stop_duration_seconds'] == 0
        stop_chunk.loc[zero_duration_mask, 'stop_duration_seconds'] = global_duration_mean
        
         # Fill missing 'track' values using precomputed modes
        mask = stop_chunk['track'].isna()
        stop_chunk.loc[mask, 'track'] = stop_chunk.loc[mask, 'stop_id'].map(global_modes)

        save_stops_chunk(stop_chunk, output_stop_filename, first)
        first = False

        del stop_chunk
        gc.collect()

def convert_chunked_unix_to_local_time_per_chunck(all_stop_times_chunk):
     
    for col in ['arrival_time', 'departure_time', 'last_observed', 'marked_past']:
            all_stop_times_chunk[col] = pd.to_datetime(
                all_stop_times_chunk[col], unit='s', utc=True
            ).dt.tz_convert('America/New_York').dt.tz_localize(None)

    all_stop_times_chunk['date'] = pd.to_datetime(all_stop_times_chunk['date']).dt.strftime('%Y-%m-%d')

    return all_stop_times_chunk

def add_stop_duration_per_chunk(all_stop_trips_chunk: pd.DataFrame) -> pd.DataFrame:
  
    all_stop_trips_chunk['stop_duration_seconds'] = (
        all_stop_trips_chunk['departure_time'] - all_stop_trips_chunk['arrival_time']
    ).dt.total_seconds()
    
    return all_stop_trips_chunk

def clean_and_filter_stops_per_chunk(all_stop_times_chunk: pd.DataFrame) -> pd.DataFrame:
    
    # Fill missing values in 'marked_past'
    all_stop_times_chunk['marked_past'] = all_stop_times_chunk['marked_past'].fillna(all_stop_times_chunk['last_observed'])
    # Drop rows with missing arrival/departure in chunks
    all_stop_times_chunk = all_stop_times_chunk[all_stop_times_chunk['departure_time'].notna() & all_stop_times_chunk['arrival_time'].notna()]

    return all_stop_times_chunk

def collect_track_per_chunk(all_stop_times_chunk, track_counts):
    grouped = all_stop_times_chunk.dropna(subset=["track"]).groupby(["stop_id", "track"]).size()

    for (stop_id, track), count in grouped.items():
        track_counts[stop_id][track] += count

def calculate_global_track_mode(track_counts, global_modes):
    
    print('alclate_global_track_mode')

    for stop_id, track_freqs in track_counts.items():
        global_modes[stop_id] = max(track_freqs.items(), key=lambda x: x[1])[0]

def collect_global_mean_stop_duration(stop_chunk, total_sum, total_count):
     # ✅ Calculate partial mean stats
        pos = stop_chunk['stop_duration_seconds'] > 0
        total_sum += stop_chunk.loc[pos, 'stop_duration_seconds'].sum()
        total_count += pos.sum()
        
        return total_sum, total_count
        
def save_stops_chunk(stops_chunk, stops_outputfilename, first):
  
    if first:
        stops_chunk.to_parquet(stops_outputfilename, engine="fastparquet", compression="snappy", index=False)
    else:
        fastparquet.write(stops_outputfilename, stops_chunk, append=True)



#non-optimized

def convert_chunked_unix_to_local_time(all_stop_times: pd.DataFrame, chunk_size: int = 350_000) -> pd.DataFrame:
    """
    Convert UNIX timestamp columns in chunks to New York local time, removing timezone info.
    Also converts the 'date' column to date only.

    Parameters:
        all_stop_times (pd.DataFrame): The DataFrame with UNIX timestamp columns.
        chunk_size (int): Number of rows per chunk for processing.

    Returns:
        pd.DataFrame: The updated DataFrame with converted datetime and date columns.
    """
    n_rows = len(all_stop_times)

    for start in range(0, n_rows, chunk_size):
        end = min(start + chunk_size, n_rows)
        chunk = all_stop_times.iloc[start:end]

        for col in ['arrival_time', 'departure_time', 'last_observed', 'marked_past']:
            all_stop_times.loc[start:end-1, col] = pd.to_datetime(chunk[col], unit='s', utc=True)\
                                                    .dt.tz_convert('America/New_York')\
                                                    .dt.tz_localize(None)

        all_stop_times.loc[start:end-1, 'date'] = pd.to_datetime(chunk['date']).dt.strftime('%Y-%m-%d')

    # Optional preview
    # print(all_stop_times.head())

    return all_stop_times

def add_stop_duration(all_stop_trips: pd.DataFrame) -> pd.DataFrame:
    """
    Add a 'stop_duration_seconds' column to the DataFrame by calculating the difference
    between 'departure_time' and 'arrival_time' in seconds.

    Parameters:
        all_stop_trips (pd.DataFrame): DataFrame containing 'arrival_time' and 'departure_time' columns.

    Returns:
        pd.DataFrame: Updated DataFrame with a new 'stop_duration_seconds' column.
    """
    all_stop_trips['stop_duration_seconds'] = (
        all_stop_trips['departure_time'] - all_stop_trips['arrival_time']
    ).dt.total_seconds()
    
    return all_stop_trips

def clean_and_filter_stops(all_stop_times: pd.DataFrame, chunk_size: int = 500_000) -> pd.DataFrame:
    """
    - Fill missing values in 'marked_past' using 'last_observed' in both DataFrames.
    - Drop rows in 'all_stop_times' with missing 'departure_time' or 'arrival_time', in chunks.

    Parameters:
        all_stop_times (pd.DataFrame): DataFrame with 'marked_past', 'last_observed', 'arrival_time', and 'departure_time'.
        chunk_size (int): Number of rows per chunk to process for filtering.

    Returns:
        dataframe: cleaned_all_stop_times
    """
    # Fill missing values in 'marked_past'
    all_stop_times['marked_past'] = all_stop_times['marked_past'].fillna(all_stop_times['last_observed'])

    # Drop rows with missing arrival/departure in chunks
    n = len(all_stop_times)
    filtered_chunks = []

    for i in range(0, n, chunk_size):
        chunk = all_stop_times.iloc[i:i + chunk_size]
        filtered_chunk = chunk[chunk['departure_time'].notna() & chunk['arrival_time'].notna()]
        filtered_chunks.append(filtered_chunk)

    all_stop_times = pd.concat(filtered_chunks, ignore_index=True)

    return all_stop_times

def fill_missing_track_with_mode(all_stop_times: pd.DataFrame) -> pd.DataFrame:
    """
    Fill missing 'track' values in the DataFrame using the mode of each 'stop_id' group.

    Parameters:
        all_stop_times (pd.DataFrame): DataFrame containing 'stop_id' and 'track' columns.

    Returns:
        pd.DataFrame: Updated DataFrame with missing 'track' values filled.
    """
    all_stop_times['track'] = all_stop_times.groupby('stop_id')['track']\
        .transform(lambda x: x.fillna(x.mode().iloc[0] if not x.mode().empty else None))
    
    return all_stop_times


#DAG functions


def process_subway_data_trips(trips_df_filenname, fare_per_trip, trips_df_outputfilename):
    
    print('Reading trips dataset')
    trips_df = pd.read_parquet(trips_df_filenname)

    print('Cleaning trips datasets')
    trips_df = clean_subway_data_trips(trips_df)

    print('Feature engineering on trip datasets')
    trips_df = feat_engineering_subway_data_trips(trips_df, fare_per_trip)

    print('Saving cleaned trips datasets')
    trips_df.to_parquet(trips_df_outputfilename, index=False)

def load_to_postgres_subway_trips(conn, trips_filename):
    print('Preparing conn')
    engine = create_engine(conn)
    if(engine.connect()):
        print('connected successfully')
        trips_df = pd.read_parquet(trips_filename)
        print('saving to database')
        trips_df.to_sql('trips', engine, if_exists='replace', index=False, method='multi',  # Better batch performance
                chunksize=10_000  # Controls the batch insert to SQL
                )

    else:
        print('failed to connect')

def process_subway_data_stops(stops_df_filename, temp_filename, stops_df_outputfilename):
    
    print('Reading and processing stops data chunks')
    read_process_save_stops_chuncks(stops_df_filename, temp_filename, stops_df_outputfilename)

def add_trip_duration_merge(all_trips_filename, all_stop_filename, final_trips_file):
    all_trips = pd.read_parquet(all_trips_filename)
    all_stop_times = pd.read_parquet(all_stop_filename)
    
    # Ensure datetime
    for col in ['arrival_time', 'departure_time']:
        all_stop_times[col] = pd.to_datetime(all_stop_times[col], errors='coerce')

    # Compute min arrival and max departure per trip
    agg_times = all_stop_times.groupby('trip_uid').agg({
        'arrival_time': 'min',
        'departure_time': 'max'
    }).reset_index()

    agg_times['trip_duration_hours'] = (
        (agg_times['departure_time'] - agg_times['arrival_time']).dt.total_seconds() / 3600
    )

    # Merge back to all_trips
    all_trips = all_trips.merge(agg_times[['trip_uid', 'trip_duration_hours']], on='trip_uid', how='left')
    all_trips.to_parquet(final_trips_file, index=False)

def load_to_postgres_subway_stops_chunked(conn_str, stops_filename, table_name='stops', sql_chunk_size=100_000):
    print("Preparing connection...")
    engine = create_engine(conn_str)

    with engine.connect() as connection:
        print("Connected successfully")

        # Read parquet as row groups using PyArrow
        parquet_file = pq.ParquetFile(stops_filename)
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

   





