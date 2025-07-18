import dask.dataframe as dd
import pyarrow.parquet as pq
import pandas as pd
import geopandas as gpd
import numpy as np
import fastparquet
from typing import List, Optional, Tuple
from collections import defaultdict
import gc
import logging
import pyarrow.parquet as pq
import pandas as pd
import numpy as np
import joblib
from scipy import sparse
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.model_selection import train_test_split
from sqlalchemy import create_engine

#Green Yellow datasets

def check_and_drop_duplicates(
    df: pd.DataFrame,
 ) -> pd.DataFrame:
    """
    Check and remove duplicate rows from a DataFrame. Optionally export duplicate records.

    Parameters:
        df (pd.DataFrame): Input DataFrame to process.
        df_name (str): Name of the DataFrame (used in file naming).
        output_dir (str): Directory to save duplicate records if export=True.
        export (bool): Whether to export duplicate records to CSV.

    Returns:
        pd.DataFrame: DataFrame with duplicates removed.
    """
    # duplicated_count = df.duplicated().sum()
    
    # if duplicated_count > 0 and export:
    #     os.makedirs(output_dir, exist_ok=True)
    #     dup_df = df[df.duplicated(keep=False)]
    #     dup_df.to_csv(f"{output_dir}/{df_name}_duplicates.csv", index=False)
    
    # Drop duplicates and return clean DataFrame
    df_cleaned = df.drop_duplicates().reset_index(drop=True)
    return df_cleaned


def standardize_location_columns(
    df: pd.DataFrame,
    undefined_locations: List[str] = ["264", "265"],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Converts PULocationID and DOLocationID to string and relabels special location IDs
    like '264' and '265' to standard values (e.g., 'Undefined', 'Outside NYC').

    Parameters:
        df (pd.DataFrame): Input DataFrame
        df_name (str): Dataset name used for export file naming
        undefined_locations (List[str]): LocationIDs to relabel
        output_dir (Optional[str]): Path to export the summary report, if provided

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: Cleaned DataFrame and change summary
    """
    # Step 1: Ensure columns exist and convert to string
    if 'PULocationID' not in df.columns or 'DOLocationID' not in df.columns:
        raise ValueError("Missing required columns: PULocationID or DOLocationID")

    df['PULocationID'] = df['PULocationID'].astype('Int64').astype('string')
    df['DOLocationID'] = df['DOLocationID'].astype('Int64').astype('string')

    # Step 2: Define relabeling dictionary
    label_map = {
        "264": {"borough": "Undefined", "zone": "Undefined", "service_zone": "Undefined"},
        "265": {"borough": "Outside NYC", "zone": "Outside NYC", "service_zone": "Outside NYC"},
    }

    #change_log = []

    # Step 3: Relabel PU locations
    for loc_id in undefined_locations:
        mask = df['PULocationID'] == loc_id
        if mask.any():
            df.loc[mask, 'PU_Borough'] = label_map[loc_id]['borough']
            df.loc[mask, 'PU_Zone'] = label_map[loc_id]['zone']
            df.loc[mask, 'PU_ServiceZone'] = label_map[loc_id]['service_zone']
            #change_log.append(("Pickup", loc_id, mask.sum()))

    # Step 4: Relabel DO locations
    for loc_id in undefined_locations:
        mask = df['DOLocationID'] == loc_id
        if mask.any():
            df.loc[mask, 'DO_Borough'] = label_map[loc_id]['borough']
            df.loc[mask, 'DO_Zone'] = label_map[loc_id]['zone']
            df.loc[mask, 'DO_ServiceZone'] = label_map[loc_id]['service_zone']
            #change_log.append(("Dropoff", loc_id, mask.sum()))

    # Step 5: Build summary
    #change_summary = pd.DataFrame(change_log, columns=["TripPoint", "LocationID", "RecordsUpdated"])

    # Step 6: Optionally save the report
    # if output_dir:
    #     os.makedirs(output_dir, exist_ok=True)
    #     summary_path = os.path.join(output_dir, f"{df_name}_special_location_summary.csv")
    #     change_summary.to_csv(summary_path, index=False)

    return df


def impute_passenger_count_by_location(df, group_col='PULocationID'):
    """
    Cleans 'passenger_count' by:
    - Replacing invalid values (0, >6, NaN) with mode per pickup location
    - Falls back to overall mode (1) if group has no valid mode
    - Tracks all changes and exports modified rows with before values

    Parameters:
    - df (pd.DataFrame): Input dataset
    - df_name (str): Name for file export
    - group_col (str): Grouping column (default: PULocationID)

    Returns:
    - pd.DataFrame: Cleaned DataFrame
    """

    # df = df.copy()
    # original = df.copy()
    
    # --- Step 1: Pre-cleaning Report ---
    # total = len(df)
    # nulls = df['passenger_count'].isna().sum()
    # zeros = (df['passenger_count'] == 0).sum()
    # too_high = (df['passenger_count'] > 6).sum()
    # valid = ((df['passenger_count'] >= 1) & (df['passenger_count'] <= 6)).sum()

    
    # --- Step 2: Flag invalids as NaN ---
    df['passenger_count'] = df['passenger_count'].apply(
        lambda x: x if pd.notnull(x) and 1 <= x <= 6 else np.nan
    )
    
    # --- Step 3: Compute mode per group ---
    mode_by_group = df.groupby(group_col)['passenger_count'].agg(
        lambda x: x.mode().iloc[0] if not x.mode().empty else np.nan
    )

    # --- Step 4: Impute group mode ---
    df['passenger_count'] = df.apply(
        lambda row: mode_by_group[row[group_col]]
        if pd.isnull(row['passenger_count']) else row['passenger_count'],
        axis=1
    )
    
    # --- Step 5: Fallback to global mode = 1 ---
    df['passenger_count'] = df['passenger_count'].fillna(1)
    
    # # --- Step 6: Report Changes ---
   
    # changes = (df['passenger_count'] != original['passenger_count']).sum()
  
    
    # # --- Step 7: Save changes ---
    # changed = original[df['passenger_count'] != original['passenger_count']].copy()
    # changed['passenger_count_after'] = df.loc[changed.index, 'passenger_count']

    # if not changed.empty:
    #     os.makedirs('cleaned_data', exist_ok=True)
    #     path = f'cleaned_data/{df_name}__passenger_count_corrections.csv'
    #     changed.to_csv(path, index=False)

    return df

def impute_airport_fee(df):
    """
    Simplified Airport_fee cleaner:
    - Sets $1.75 fee for JFK (132) and LGA (138) pickups
    - Sets $0.00 for all other locations
    - Handles negatives, missing values, and incorrect amounts
    - Provides clear before/after reporting
    """
    
    # Keep original for comparison
    #original = df.copy()
    
    # Constants
    AIRPORT_IDS = {132, 138}  # JFK and LGA
    AIRPORT_ZONES = {'JFK Airport', 'LaGuardia Airport'}
    CORRECT_FEE = 1.75
    
    # Determine airport pickups
    is_airport = (
        df['PULocationID'].isin(AIRPORT_IDS) | 
        df['PU_Zone'].isin(AIRPORT_ZONES)
    )
    
    # --- Cleaning Process ---
    #changes = 0
    
    # 1. Fix missing values
    missing = df['Airport_fee'].isna()
    df.loc[missing & is_airport, 'Airport_fee'] = CORRECT_FEE
    df.loc[missing & ~is_airport, 'Airport_fee'] = 0.0
    #changes += missing.sum()
    
    # 2. Fix negative values
    negatives = (df['Airport_fee'] < 0)
    df.loc[negatives & is_airport, 'Airport_fee'] = CORRECT_FEE
    df.loc[negatives & ~is_airport, 'Airport_fee'] = 0.0
    #changes += negatives.sum()
    
    # 3. Fix incorrect positive amounts
    incorrect = (df['Airport_fee'] > 0) & (df['Airport_fee'] != CORRECT_FEE)
    df.loc[incorrect & is_airport, 'Airport_fee'] = CORRECT_FEE
    df.loc[incorrect & ~is_airport, 'Airport_fee'] = 0.0
    #changes += incorrect.sum()
    
    # # Save changed records
    # changed = df[df['Airport_fee'] != original['Airport_fee']]
    # os.makedirs('cleaned_data', exist_ok=True)
    # changed.to_csv('cleaned_data/yellow_airport_fee_corrections.csv', index=False)
    
    return df

def impute_congestion_surcharge(df):
    """
    Cleans 'congestion_surcharge' by:
    - Keeping only $2.50 as valid value
    - Imputing missing/invalid entries based on (PU, DO) mode
    - Defaults to $0.00 if no mode available
    - Logs changes and saves modified records with before/after values
    """

    # df = df.copy()
    # original = df.copy()
    
    # --- Step 1: Report Before ---
    # total = len(df)
    # valid = (df['congestion_surcharge'] == 2.50).sum()
    # invalid = (df['congestion_surcharge'] != 2.50).sum()

    
    # --- Step 2: Mark invalids ---
    invalid_mask = (df['congestion_surcharge'] != 2.50)
    
    # --- Step 3: Compute mode from valid data only ---
    valid_df = df[~invalid_mask]
    mode_lookup = valid_df.groupby(['PULocationID', 'DOLocationID'])['congestion_surcharge'].agg(
        lambda x: x.mode().iloc[0] if not x.mode().empty else np.nan
    )
    
    # --- Step 4: Apply imputations ---
    def impute_fee(row):
        key = (row['PULocationID'], row['DOLocationID'])
        return mode_lookup.get(key, 0.00)

    df.loc[invalid_mask, 'congestion_surcharge'] = df[invalid_mask].apply(impute_fee, axis=1)
    df['congestion_surcharge'] = df['congestion_surcharge'].fillna(0.00)

    # # --- Step 5: Reporting after ---
    # changes = (df['congestion_surcharge'] != original['congestion_surcharge']).sum()

    # # --- Step 6: Save changed records only ---
    # changed = original[df['congestion_surcharge'] != original['congestion_surcharge']].copy()
    # changed['congestion_surcharge_after'] = df.loc[changed.index, 'congestion_surcharge']

    # if not changed.empty:
    #     os.makedirs('cleaned_data', exist_ok=True)
    #     path = f'cleaned_data/{df_name}__congestion_fee_corrections.csv'
    #     changed.to_csv(path, index=False)

    return df

def clean_ratecodeid_simple(df):
    """
    Cleans the 'RatecodeID' column by handling missing values only.

    Rules:
    - NaN values are replaced with 99 (indicating 'unknown' or 'null')
    - All existing (non-NaN) values are kept as-is, even if not in [1–6]
    - Tracks changes and exports only affected rows with original values

    Parameters:
    - df (pd.DataFrame): Input DataFrame
    - df_name (str): Optional name used in the exported filename

    Returns:
    - pd.DataFrame: Cleaned DataFrame
    """

    # df = df.copy()
    # original = df.copy()
    NULL_CODE = 99

    # total_rows = len(df)
    # null_count = df['RatecodeID'].isna().sum()


    # --- Step 2: Cleaning ---
    df['RatecodeID'] = df['RatecodeID'].fillna(NULL_CODE)

    # # --- Step 3: Post-cleaning Report ---
 
    # changes = (df['RatecodeID'] != original['RatecodeID']).sum()


    # # --- Step 4: Save Only Changed Rows ---
    # changed = original[df['RatecodeID'] != original['RatecodeID']].copy()
    # changed['RatecodeID_after'] = NULL_CODE

    # if not changed.empty:
    #     os.makedirs('cleaned_data', exist_ok=True)
    #     filename = f'cleaned_data/{df_name}__ratecodeid_corrections.csv'
    #     changed.to_csv(filename, index=False)

    return df

def clean_store_and_fwd_flag(df):
    """
    Cleans the 'store_and_fwd_flag' column in a DataFrame.

    Rules:
    - Valid values are 'Y' (store-and-forward) or 'N' (real-time transmission)
    - Invalid or missing values (NaN or others) are replaced with the mode of valid data
    - Tracks and reports all changes
    - Saves only changed rows with before/after values to a CSV in 'cleaned_data/' directory

    Parameters:
    - df (pd.DataFrame): Input DataFrame
    - df_name (str): Optional name used for the output CSV file

    Returns:
    - pd.DataFrame: Cleaned DataFrame
    """


    # df = df.copy()
    # original = df.copy()

    # --- Step 1: Pre-cleaning Report ---
    #total_rows = len(df)
    valid_mask = df['store_and_fwd_flag'].isin(['Y', 'N'])
    invalid_mask = ~valid_mask | df['store_and_fwd_flag'].isna()

    #valid_count = valid_mask.sum()
    #invalid_count = invalid_mask.sum()


    # --- Step 2: Determine Replacement Value ---
    valid_values = df.loc[valid_mask, 'store_and_fwd_flag']
    mode_value = valid_values.mode()[0] if not valid_values.empty else 'N'

    # --- Step 3: Apply Cleaning ---
    df.loc[invalid_mask, 'store_and_fwd_flag'] = mode_value

    # # --- Step 4: Post-cleaning Report ---

    # changes = (df['store_and_fwd_flag'] != original['store_and_fwd_flag']).sum()


    # # --- Step 5: Save Only Changed Rows ---
    # changed_rows = original.loc[invalid_mask].copy()
    # changed_rows['store_and_fwd_flag_after'] = mode_value

    # if not changed_rows.empty:
    #     os.makedirs('cleaned_data', exist_ok=True)
    #     filename = f'cleaned_data/{df_name}_store_and_fwd_flag_corrections.csv'
    #     changed_rows.to_csv(filename, index=False)

    return df

def drop_ehail_fee(df):
    """
    Drops the ehail_fee column if it exists in the DataFrame.
    
    Parameters:
        df (pd.DataFrame): Input DataFrame
    
    Returns:
        pd.DataFrame: DataFrame without ehail_fee column
    """
    if 'ehail_fee' in df.columns:
        df = df.drop(columns=['ehail_fee'])
    
    return df

def impute_trip_type_with_mode(df):
    """
    Imputes missing 'trip_type' values using the mode of the column.
    Logs imputation summary and saves ONLY changed rows to CSV.
    
    Returns:
        pd.DataFrame: Updated DataFrame with imputed 'trip_type' values.
    """
    #df = df.copy()

    # Step 1: Compute mode (most frequent value)
    mode_value = df['trip_type'].mode(dropna=True)[0]

    # Step 2: Identify rows with missing 'trip_type'
    missing_mask = df['trip_type'].isna()
    missing_count = missing_mask.sum()


    if missing_count > 0:
        # Step 3: Create copy of changed rows with before/after info
        # changed_rows = df[missing_mask].copy()
        # changed_rows['trip_type_before'] = changed_rows['trip_type']
        # changed_rows['trip_type_after'] = mode_value

        # Step 4: Impute values
        df.loc[missing_mask, 'trip_type'] = mode_value

        # # Step 5: Save changed rows to CSV only
        # os.makedirs(output_dir, exist_ok=True)
        # change_path = os.path.join(output_dir, 'green_imputed_trip_type_rows.csv')
        # changed_rows.to_csv(change_path, index=False)

    return df

def clean_payment_type_nans(df):
    """
    Cleans 'payment_type' by replacing NaNs with 5 (unknown/undefined).
    Tracks modified rows and saves them with before/after value.
    """

    #df = df.copy()
    UNKNOWN_PAYMENT_TYPE = 5

    # --- Pre-Cleaning Report ---
    #total = len(df)


    # Store original for comparison
    #original = df['payment_type'].copy()

    # --- Cleaning ---
    df['payment_type'] = df['payment_type'].fillna(UNKNOWN_PAYMENT_TYPE)

    # # --- Post-Cleaning Report ---
    # changed_mask = df['payment_type'] != original
    # changes = changed_mask.sum()

    # # --- Save Changed Rows ---
    # if changes > 0:
    #     changed = df.loc[changed_mask].copy()
    #     changed['payment_type_before'] = original.loc[changed_mask]
    #     changed['payment_type_after'] = changed['payment_type']
    #     os.makedirs(output_dir, exist_ok=True)
    #     path = os.path.join(output_dir, filename)
    #     changed.to_csv(path, index=False)

    return df

def drop_invalid_zero_fares_silent(df):
    """
    Silent version: Drops all zero-fare trips where payment_type ≠ 3 (No Charge).
    - No print statements
    - Still saves removed rows to disk for traceability

    Parameters:
        df (pd.DataFrame): Input DataFrame
        df_name (str): Used for naming the output file
        output_dir (str): Directory where dropped records will be saved

    Returns:
        pd.DataFrame: Cleaned DataFrame
    """


    # Identify invalid zero-fare trips
    zero_fares = df[(df['fare_amount'] == 0) & (df['payment_type'] != 3)]

    # Remove invalid zero-fare rows
    cleaned_df = df.drop(zero_fares.index)

    # # Save removed rows
    # if not zero_fares.empty:
    #     os.makedirs(output_dir, exist_ok=True)
    #     file_path = os.path.join(output_dir, f"{df_name}_zero_fares_invalid_paytype.csv")
    #     zero_fares.to_csv(file_path, index=False)

    return cleaned_df

def fix_orphan_negated_fares(df):
    """
    Corrects orphaned negative fares in NYC taxi data with dynamic dataset naming.
    
    Enhanced Features:
    - Works for both yellow and green taxi DataFrames
    - Auto-generates filename based on dataset name
    - Creates output directory if needed
    - Improved reporting with dataset context
    
    Parameters:
        df (pd.DataFrame): Input DataFrame
        df_name (str): Name of dataset ('yellow' or 'green')
        export_dir (str): Directory for output files
    
    Returns:
        pd.DataFrame: Cleaned DataFrame
    """
   
    
    # # Create output directory
    # os.makedirs(export_dir, exist_ok=True)
    
    # # Dynamic filename
    # export_path = f"{export_dir}/{df_name}_fixed_negative_fares.csv"
    
    # 1. Define fare-related fields (compatible with both taxi types)
    fare_fields = [
        "fare_amount", "extra", "mta_tax", "tip_amount",
        "tolls_amount", "improvement_surcharge",
        "congestion_surcharge", "total_amount"
    ]
    
    # Only include Airport_fee if present
    if 'Airport_fee' in df.columns:
        fare_fields.append("Airport_fee")

    # 2. Filter negative fares
    neg_fare_df = df[df["fare_amount"] < 0].copy()
    neg_fare_df["was_fixed"] = "no"

    # 3. Detection rule
    def is_orphan_negated(row):
        try:
            components = [row[field] for field in fare_fields if field != "total_amount"]
            if any(pd.isna(components)) or pd.isna(row["total_amount"]):
                return False

            abs_sum = round(sum(abs(val) for val in components if not pd.isna(val)), 2)
            abs_total = round(abs(row["total_amount"]), 2)
            return (abs_sum == abs_total) and (row["total_amount"] < 0)
        except:
            return False

    # 4. Apply correction
    mask = neg_fare_df.apply(is_orphan_negated, axis=1)
    neg_fare_df.loc[mask, fare_fields] = neg_fare_df.loc[mask, fare_fields].abs()
    neg_fare_df.loc[mask, "was_fixed"] = "yes"

    # 5. Update main DataFrame
    unfixed_index = neg_fare_df[neg_fare_df["was_fixed"] == "no"].index
    df = df.drop(index=unfixed_index)
    df.update(neg_fare_df.loc[mask, fare_fields])

    # # 6. Save audit report
    # neg_fare_df.to_csv(export_path, index=False)

    return df

def impute_zero_trip_distance_mismatchloc(df):
    """
    Fixes zero trip distances where PU ≠ DO using route medians.
    
    Features:
    - Imputes zero trip_distance based on median of PU-DO pairs
    - Drops rows where no median is available
    - Generates a full fix report: 'imputed' vs 'dropped'
    - Supports both Yellow and Green datasets via df_name
    
    Parameters:
        df (pd.DataFrame): Input DataFrame
        df_name (str): Used for report file naming
        export_dir (str): Directory to store the report

    Returns:
        pd.DataFrame: Cleaned DataFrame with imputed values and unfixable rows removed
    """
   

    # original = df.copy()

    # # --- Pre-Cleaning Report ---
    zero_trips = (df['trip_distance'] == 0)
    eligible = zero_trips & (df['PULocationID'] != df['DOLocationID'])


    # Step 1: Build PU-DO median dictionary
    pu_do_medians = (
        df[df['trip_distance'] > 0]
        .groupby(['PULocationID', 'DOLocationID'])['trip_distance']
        .median()
        .to_dict()
    )

    # Step 2: Mark fixability
    df['was_fixed'] = ''
    route_keys = list(zip(df['PULocationID'], df['DOLocationID']))
    fixable_mask = pd.Series(route_keys, index=df.index).isin(pu_do_medians)

    # Step 3: Apply fixes
    df.loc[eligible, 'was_fixed'] = np.where(
        fixable_mask[eligible],
        'yes',
        'no'
    )
    for idx in df[eligible & fixable_mask].index:
        pu, do = df.at[idx, 'PULocationID'], df.at[idx, 'DOLocationID']
        df.at[idx, 'trip_distance'] = pu_do_medians[(pu, do)]

    # Step 4: Filter cleaned vs unfixable
    #fixed = df[df['was_fixed'] == 'yes']
    unfixable = df[df['was_fixed'] == 'no']
    cleaned_df = df[~df.index.isin(unfixable.index)]



    # # Step 5: Save fix report
    # if len(fixed) > 0 or len(unfixable) > 0:
    #     os.makedirs(export_dir, exist_ok=True)
    #     fix_report = pd.concat([
    #         fixed.assign(action='imputed'),
    #         unfixable.assign(action='dropped')
    #     ])
    #     report_path = os.path.join(export_dir, f'{df_name}_trip_distance_fix_report.csv')
    #     fix_report.to_csv(report_path, index=False)


    # Step 6: Return cleaned version
    return cleaned_df.drop(columns=['was_fixed'], errors='ignore')

def fare_distance_cleaning_pipeline(df):
    """
    Wrapper that applies fare and distance cleaning steps in order:
    1. Drop invalid zero-fares
    2. Fix orphaned negative fares
    3. Impute zero trip distance (PU ≠ DO)
    
    Parameters:
        df (pd.DataFrame): The input dataset
        df_name (str): Used in naming audit reports
        export_dir (str): Directory to store logs and removed rows
    
    Returns:
        pd.DataFrame: Cleaned DataFrame
    """
    # Step 1: Drop zero-fare trips with invalid payment_type
    df = drop_invalid_zero_fares_silent(df)

    # Step 2: Fix orphaned negative fare rows (abs component sum = abs total)
    df = fix_orphan_negated_fares(df)

    # Step 3: Impute trip_distance=0 where PU ≠ DO using route median
    df = impute_zero_trip_distance_mismatchloc(df)

    return df

def add_duration_column(df, pickup_col, dropoff_col):
    """
    Adds a 'duration_inMin' column to the DataFrame, representing the trip duration in fractional minutes.
    Handles invalid datetime strings safely.
    
    Parameters:
        df (pd.DataFrame): DataFrame containing pickup and dropoff datetime columns.
        pickup_col (str): Name of the pickup datetime column.
        dropoff_col (str): Name of the dropoff datetime column.
        
    Returns:
        pd.DataFrame: DataFrame with an added 'duration_inMin' column.
    """
    df[pickup_col] = pd.to_datetime(df[pickup_col], errors='coerce')
    df[dropoff_col] = pd.to_datetime(df[dropoff_col], errors='coerce')
    
    # calculate duration in minutes
    df['duration_inMin'] = (df[dropoff_col] - df[pickup_col]).dt.total_seconds() / 60.0


    
    return df

def add_time_columns(df, 
                     pickup_col, 
                     dropoff_col):
    """
    Adds time-based features to the DataFrame:
    - Extracts pickup hour, day of week, month, dropoff hour, trip weekday name, and weekend flag.
    
    Parameters:
        df (pd.DataFrame): Input DataFrame
        pickup_col (str): Name of pickup datetime column
        dropoff_col (str): Name of dropoff datetime column
        
    Returns:
        pd.DataFrame: DataFrame with added time columns
    """
    #df = df.copy()

    # Convert to datetime
    df[pickup_col] = pd.to_datetime(df[pickup_col], errors='coerce')
    df[dropoff_col] = pd.to_datetime(df[dropoff_col], errors='coerce')

    # Add time-based features
    df['pickup_hour'] = df[pickup_col].dt.hour
    df['pickup_dayofweek'] = df[pickup_col].dt.dayofweek
    df['pickup_month'] = df[pickup_col].dt.month
    df['dropoff_hour'] = df[dropoff_col].dt.hour
    df['is_weekend'] = df[pickup_col].dt.dayofweek.isin([5, 6])
    

    return df

def add_average_speed_column(df):
    """
    Adds an 'average_speed' column in miles per hour to the DataFrame.
    Avoids division by zero and assigns 0 mph when distance or duration is zero.
    """
    #df = df.copy()
    distance_col='trip_distance'
    duration_col='duration_inMin'
    # Compute safe speed only where duration > 0 and distance > 0
    valid_mask = (df[duration_col] > 0) & (df[distance_col] > 0)

    # Create a new column with default 0, then assign speed where valid
    df['average_speed'] = 0.0
    df.loc[valid_mask, 'average_speed'] = (
        df.loc[valid_mask, distance_col] / (df.loc[valid_mask, duration_col] / 60)
    )

    return df

def add_median_speed_transform(df):
    """
    Computes median speed for each group and broadcasts to rows WITHOUT merging.
    More memory-efficient for large datasets.
    """
    groupby_columns=['PULocationID', 'pickup_hour']
    speed_col='average_speed'
    new_col='median_speed'

    # Convert to numeric (keeps NAs)
    df[speed_col] = pd.to_numeric(df[speed_col], errors='coerce')
    
    # Calculate and broadcast medians
    df[new_col] = df.groupby(groupby_columns, observed=True)[speed_col].transform('median')
    
    return df

def tag_congestion(df):
    """
    Flag likely congestion events based on multiple criteria:
    1. Trip is significantly slower than location-time median (ratio rule).
    2. Or absolute speed is below congestion threshold.
    3. Disregard obviously erroneous cases (too fast).
    """
    #df = df.copy()
    slow_ratio=0.5
    absolute_slow=5
    abs_fast=70
    
    df['is_congestion'] = (
        (
            (df['average_speed'] < df['median_speed'] * slow_ratio) & 
            (df['average_speed'] >= absolute_slow)
        )
        | 
        (df['average_speed'] < absolute_slow)
    ) & (df['average_speed'] <= abs_fast)

    return df

def add_fare_efficiency_columns(
    df  
):
    """
    Adds 'fare_per_mile' and (if duration column exists) 'fare_per_minute' to the DataFrame.
    Ensures safe division (avoids divide-by-zero and negative values).
    """
    fare_col='fare_amount'
    distance_col='trip_distance'
    duration_col='duration_inMin'

    # Fare per mile
    valid_distance_mask = df[distance_col] > 0
    df['fare_per_mile'] = 0.0
    df.loc[valid_distance_mask, 'fare_per_mile'] = (
        df.loc[valid_distance_mask, fare_col] / df.loc[valid_distance_mask, distance_col]
    )

    # Fare per minute — only if duration column exists
    if duration_col in df.columns:
        valid_duration_mask = df[duration_col] > 0
        df['fare_per_minute'] = 0.0
        df.loc[valid_duration_mask, 'fare_per_minute'] = (
            df.loc[valid_duration_mask, fare_col] / df.loc[valid_duration_mask, duration_col]
        )
    else:
        print(f"⚠️ Column '{duration_col}' not found — skipping fare_per_minute.")

    return df
#Grouped functions
#1
def merge_lookup_dask_green_yellow(df: dd.DataFrame, lookup: dd.DataFrame) -> dd.DataFrame:
    """
    Performs two successive left joins with the taxi zone lookup table on pickup and dropoff location IDs.
    Adds PU and DO Borough, Zone, and service_zone columns.

    Parameters:
        df (dd.DataFrame): Dask DataFrame to merge.
        pickup_col (str): Column name for pickup location ID.
        dropoff_col (str): Column name for dropoff location ID.
        lookup (dd.DataFrame): Dask DataFrame containing the taxi zone lookup.

    Returns:
        dd.DataFrame: Merged Dask DataFrame with PU_ and DO_ location details.
    """
    df = df.merge(
        lookup, left_on='PULocationID', right_on="LocationID", how="left"
    ).rename(
        columns={
            "Borough": "PU_Borough",
            "Zone": "PU_Zone",
            "service_zone": "PU_ServiceZone"
        }
    ).drop(columns=["LocationID"])

    df = df.merge(
        lookup, left_on='DOLocationID', right_on="LocationID", how="left"
    ).rename(
        columns={
            "Borough": "DO_Borough",
            "Zone": "DO_Zone",
            "service_zone": "DO_ServiceZone"
        }
    ).drop(columns=["LocationID"])

    return df

#Yellow only functions
#2
def yellow_data_cleaning(df):
    """
    Wrapper function to clean NYC Yellow Taxi data using standardized helper functions.
    Steps included:
    1. Clean RatecodeID
    2. Impute Passenger Count
    3. Clean Congestion Surcharge
    4. Clean Airport Fee
    5. Clean Store and Forward Flag
    Returns:
        Cleaned DataFrame
    """

    df = check_and_drop_duplicates(df)
    
    #drop 2009 valued row
    
    df['tpep_pickup_datetime'] = pd.to_datetime(df['tpep_pickup_datetime'], errors='coerce')
    date_mask = df['tpep_pickup_datetime'] < pd.Timestamp("2024-01-01")
    if date_mask.any():
        df = df[~date_mask]
    
    df = standardize_location_columns(df, undefined_locations = ["264", "265"])
    
    # Step 1: Clean RatecodeID
    df = clean_ratecodeid_simple(df)

    # Step 2: Impute passenger_count
    df = impute_passenger_count_by_location(df, group_col="PULocationID")

    # Step 3: Clean congestion_surcharge
    df = impute_congestion_surcharge(df)

    # Step 4: Clean Airport_fee
    df = impute_airport_fee(df)

    # Step 5: Clean store_and_fwd_flag
    df = clean_store_and_fwd_flag(df)


    df = fare_distance_cleaning_pipeline(df)

    return df

#3
def yellow_feature_engineering(df):
    """
    feature engineering pipeline for NYC taxi data.
    
    Parameters:
        df (pd.DataFrame): Raw taxi data (yellow or green)
        df_name (str): Name of dataset ('yellow' or 'green')
        pickup_col (str): Pickup datetime column
        dropoff_col (str): Dropoff datetime column
        output_dir (str): Directory for saving fix logs
        enable_print (bool): If True, enables internal print statements
        
    Returns:
        pd.DataFrame: enriched DataFrame
    """

    # Step 2: Feature engineering
    df = add_duration_column(df, pickup_col='tpep_pickup_datetime', dropoff_col='tpep_dropoff_datetime')
    df = add_time_columns(df, pickup_col='tpep_pickup_datetime', dropoff_col='tpep_dropoff_datetime')
    df = add_average_speed_column(df)
    df = add_median_speed_transform(df)
    df = tag_congestion(df)
    df = add_fare_efficiency_columns(df)



    return df


#Green only functions
#2
def green_data_cleaning(df):
    """
    Cleans NYC Green Taxi data using a series of modular cleaning steps.
    Returns:
        pd.DataFrame: Fully cleaned Green Taxi DataFrame
    """

    df = check_and_drop_duplicates(df)

    df = standardize_location_columns(df, undefined_locations = ["264", "265"])

    # Step 1: Drop ehail_fee column if it exists
    df = drop_ehail_fee(df)

    # Step 2: Impute missing 'trip_type' using mode
    df = impute_trip_type_with_mode(df)

    # Step 3: Clean 'store_and_fwd_flag' column
    df = clean_store_and_fwd_flag(df)

    # Step 4: Clean 'RatecodeID'
    df = clean_ratecodeid_simple(df)

    # Step 5: Impute missing 'passenger_count' using group-based mode
    df = impute_passenger_count_by_location(df, group_col='PULocationID')

    # Step 6: Impute missing 'congestion_surcharge'
    df = impute_congestion_surcharge(df)

    # Step 7: Fill missing 'payment_type' values with 5 (unknown) and track
    df = clean_payment_type_nans(df)

    df = fare_distance_cleaning_pipeline(df)

    return df
#3
def green_feature_engineering(df):
    """
    feature engineering pipeline for NYC taxi data.
    
    Parameters:
        df (pd.DataFrame): Raw taxi data (yellow or green)
        df_name (str): Name of dataset ('yellow' or 'green')
        pickup_col (str): Pickup datetime column
        dropoff_col (str): Dropoff datetime column
        output_dir (str): Directory for saving fix logs
        enable_print (bool): If True, enables internal print statements
        
    Returns:
        pd.DataFrame: enriched DataFrame
    """

    # Step 2: Feature engineering
    df = add_duration_column(df, pickup_col='lpep_pickup_datetime', dropoff_col='lpep_dropoff_datetime')
    df = add_time_columns(df, pickup_col='lpep_pickup_datetime', dropoff_col='lpep_dropoff_datetime')
    df = add_average_speed_column(df)
    df = add_median_speed_transform(df)
    df = tag_congestion(df)
    df = add_fare_efficiency_columns(df)



    return df


#Common functions

# def create_shape_lookup(shape_filename, outputlookup, o_lookup_filename):
#     logger = logging.getLogger("airflow.task")
    
#     # 1. Load shapefile
#     gdf = gpd.read_file(shape_filename)
#     logger.info(f"Shape file loaded: {shape_filename}")
#     gdf = gdf.rename(columns={"zone": "Zone", "borough": "Borough"})

#     # Reproject to projected CRS before centroids
#     gdf = gdf.to_crs(epsg=2263)
#     gdf["Latitude"] = gdf.geometry.centroid.y
#     gdf["Longitude"] = gdf.geometry.centroid.x

#     # Back to WGS84
#     gdf = gdf.to_crs(epsg=4326)

#     # 2. Build mini coordinate table
#     coords_df = gdf[["LocationID", "Latitude", "Longitude"]].copy()
#     logger.info("Coordinate data extracted.")

#     # 3. Load old lookup
#     old_lookup = pd.read_csv(o_lookup_filename)
#     logger.info(f"Old lookup file loaded: {o_lookup_filename}")

#     # 4. Merge
#     merged_lookup = pd.merge(
#         old_lookup, coords_df, on="LocationID", how="left"
#     )
#     logger.info("Merge completed.")
#     logger.info(f"Sample merged data: \n{merged_lookup.head()}")
#     logger.info(f"Columns: {merged_lookup.columns.tolist()}")

#     # 5. Save
#     merged_lookup.to_csv(outputlookup, index=False)
#     logger.info(f"Final lookup saved to: {outputlookup}")

   


#4
def sanitize_taxi_data(df):
    """
    Performs full cleaning for NYC taxi data:
    1. Fixes negative 'extra' charges
    2. Drops rows with extreme or invalid values in duration, distance, fare, total_amount, and average speed
    3. Exports audit logs for dropped and fixed records

    Parameters:
        df (pd.DataFrame): Input DataFrame
        df_name (str): Dataset name ('yellow' or 'green')
        report_dir (str): Directory for audit exports

    Returns:
        pd.DataFrame: Cleaned DataFrame
    """
  

    # df = df.copy()
    # os.makedirs(report_dir, exist_ok=True)
    ### STEP 1: Flip negative 'extra' values
    if 'extra' in df.columns:
        neg_mask = df['extra'] < 0
        if neg_mask.any():
            # Save original rows
            #df[neg_mask].to_csv(f"{report_dir}/{df_name}_negative_extra_corrections.csv", index=False)
            # Flip to positive
            df.loc[neg_mask, 'extra'] = df.loc[neg_mask, 'extra'].abs()

    ### STEP 2: Clean extreme values
    thresholds = {
        'duration_inMin': {'min': 0.1, 'max': df['duration_inMin'].quantile(0.99)},
        'trip_distance': {'min': 0.01, 'max': df['trip_distance'].quantile(0.99)},
        'fare_amount': {'min': 1.0, 'max': df['fare_amount'].quantile(0.99)},
        'total_amount': {'min': 0.0},
        'average_speed': {'max': 70.0}
    }

    valid_mask = (
        (df['duration_inMin'] >= thresholds['duration_inMin']['min']) &
        (df['duration_inMin'] <= thresholds['duration_inMin']['max']) &
        (df['trip_distance'] >= thresholds['trip_distance']['min']) &
        (df['trip_distance'] <= thresholds['trip_distance']['max']) &
        (df['fare_amount'] >= thresholds['fare_amount']['min']) &
        (df['fare_amount'] <= thresholds['fare_amount']['max']) &
        (df['total_amount'] >= thresholds['total_amount']['min']) &
        (df['average_speed'] <= thresholds['average_speed']['max'])
    )

    # Separate valid and invalid
    valid_df = df[valid_mask].copy()
    del df
    gc.collect()
    #invalid_df = df[~valid_mask].copy()

    # if not invalid_df.empty:
    #     invalid_df.to_csv(f"{report_dir}/{df_name}_dropped_extreme_values.csv", index=False)

    return valid_df

#fhvhv datasets

def merge_lookup(chunk, lookup_df):
    chunk = chunk.merge(lookup_df, left_on="PULocationID", right_on="LocationID", how="left").rename(
        columns={"Borough": "PU_Borough", "Zone": "PU_Zone", "service_zone": "PU_ServiceZone"}).drop(columns="LocationID")
    chunk = chunk.merge(lookup_df, left_on="DOLocationID", right_on="LocationID", how="left").rename(
        columns={"Borough": "DO_Borough", "Zone": "DO_Zone", "service_zone": "DO_ServiceZone"}).drop(columns="LocationID")
    return chunk

def impute_on_scene_datetime(df, median_val):
    df[['request_datetime', 'on_scene_datetime', 'pickup_datetime']] = df[['request_datetime', 'on_scene_datetime', 'pickup_datetime']].apply(pd.to_datetime, errors='coerce')
    missing_mask = df['on_scene_datetime'].isna() & df['request_datetime'].notna()
    df.loc[missing_mask, 'on_scene_datetime'] = df.loc[missing_mask, 'request_datetime'] + pd.to_timedelta(median_val, unit='s')
    return df

def fill_modes(df, mode_lookup):
    for col, loc_col in [
        ('PU_Borough', 'PULocationID'), ('DO_Borough', 'DOLocationID'),
        ('PU_Zone', 'PULocationID'), ('DO_Zone', 'DOLocationID'),
        ('PU_ServiceZone', 'PULocationID'), ('DO_ServiceZone', 'DOLocationID')
    ]:
        if col in df.columns:
            mask_valid = ~df[loc_col].isin([264, 265]) & df[col].isna()
            df.loc[mask_valid, col] = df.loc[mask_valid, loc_col].map(mode_lookup.get((col, loc_col), {}))
    return df

def clean_chunk(df):

    df.drop(columns='originating_base_num', errors='ignore', inplace=True)

    df.loc[df['PULocationID'] == 264, ['PU_Borough', 'PU_Zone', 'PU_ServiceZone']] = 'Unknown'
    df.loc[df['DOLocationID'] == 264, ['DO_Borough', 'DO_Zone', 'DO_ServiceZone']] = 'Unknown'
    df.loc[df['PULocationID'] == 265, ['PU_Borough', 'PU_Zone', 'PU_ServiceZone']] = 'Outside NYC'
    df.loc[df['DOLocationID'] == 265, ['DO_Borough', 'DO_Zone', 'DO_ServiceZone']] = 'Outside NYC'

    df['calculated_trip_time'] = (df['dropoff_datetime'] - df['pickup_datetime']).dt.total_seconds()
    df['trip_time_diff'] = df['trip_time'] - df['calculated_trip_time']
    df = df[df['trip_time_diff'].abs() <= 300].copy()
    df.drop(columns=['calculated_trip_time', 'trip_time_diff'], inplace=True)

    fare_cols = ['tolls', 'sales_tax', 'bcf', 'congestion_surcharge', 'airport_fee']
    df['fare_components_sum'] = df[fare_cols].sum(axis=1)
    mask = df['base_passenger_fare'] < 0
    df.loc[mask, 'base_passenger_fare'] = df.loc[mask, 'fare_components_sum']
    df.drop(columns='fare_components_sum', inplace=True)

    mask = df['driver_pay'] < 0
    df.loc[mask, 'driver_pay'] = df.loc[mask, 'base_passenger_fare'] + df.loc[mask, 'tips']

    df = df[~((df['trip_miles'] <= 0.05) & (df['base_passenger_fare'] > 0))]

    license_mapping = {"HV0002": "Juno", "HV0003": "Uber", "HV0004": "Via", "HV0005": "Lyft"}
    df['fhvhv_type'] = df['hvfhs_license_num'].map(license_mapping)

    df['average_speed'] = df.apply(
        lambda row: row['trip_miles'] / (row['trip_time'] / 3600) if row['trip_time'] > 0 else 0, axis=1)

    df['fare_per_mile'] = df['base_passenger_fare'] / df['trip_miles']
    df['fare_per_mile'].replace([np.inf, -np.inf], np.nan, inplace=True)

    df['total_fare_components'] = df[['base_passenger_fare'] + fare_cols].sum(axis=1)

    df['pickup_hour'] = pd.to_datetime(df['pickup_datetime'], errors='coerce').dt.hour
    df['dropoff_hour'] = pd.to_datetime(df['dropoff_datetime'], errors='coerce').dt.hour

    df['trip_category'] = df['shared_match_flag'].map(lambda x: 'Shared' if x == 'Y' else 'Solo')
    df['is_congested'] = df['average_speed'] < 5

    df['trip_distance_class'] = pd.cut(
        df['trip_miles'], bins=[0, 2, 7, np.inf], labels=['short', 'medium', 'long'], right=True, include_lowest=True)

    df.drop(columns=['pickup_date'], errors='ignore', inplace=True)

    return df


#ML

#Green_Yellow


def detect_iqr_outliers(df):
    """
    Detects outliers using the IQR method on predefined numeric columns.
    """
    iqr_multiplier=1.5
    return_removed=False
    
    target_columns = [
        'trip_distance','fare_amount', 'extra',
        'tip_amount', 'tolls_amount','total_amount','duration_inMin',
        'average_speed','median_speed'
    ]

    outlier_columns = []
    mask = pd.Series([False] * len(df), index=df.index)

    for col in target_columns:
        if col not in df.columns:
            continue
        if df[col].nunique() <= 1:
            continue
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - iqr_multiplier * iqr
        upper = q3 + iqr_multiplier * iqr
        col_mask = (df[col] < lower) | (df[col] > upper)
        if col_mask.any():
            outlier_columns.append(col)
            mask = mask | col_mask

    if return_removed:
        df = df[~mask]

    return df, outlier_columns

def transform_outlier_columns_log(df, outlier_columns):
    """
    Applies log(x + 1) transformation to outlier columns (if numeric),
    and saves the result to 'analysis_ready/{df_name}_ready_ml.csv'.

    Parameters:
    - df (pd.DataFrame): Input DataFrame
    - outlier_columns (list): Columns to transform
    - df_name (str): Name to use in output filename (e.g., 'yellow', 'green')

    Returns:
    - pd.DataFrame: Transformed DataFrame
    """
    
    

    for col in outlier_columns:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            df[col] = np.log1p(df[col])  # log(x + 1)

    return df

#fhvhv

def process_parquet_in_chunks(parquet_path, output_x_pro, output_y, x_train_file, y_train_file, x_test_file, y_test_file, pre_file, row_limit=None):
    
    target_col='base_passenger_fare'
    
    parquet_file = pq.ParquetFile(parquet_path)
    collected_X, collected_y = [], []

    # STEP 1: Prepare sample for fitting
    sample_rows = []
    for i in range(parquet_file.num_row_groups):
        df = parquet_file.read_row_group(i).to_pandas()
        sample_rows.append(df)
        if row_limit and sum(len(d) for d in sample_rows) >= row_limit:
            break
    sample_df = pd.concat(sample_rows)
    if row_limit:
        sample_df = sample_df.sample(n=row_limit, random_state=42)

    # STEP 2: Feature engineering logic
    def engineer_features(df):
        df['pickup_datetime'] = pd.to_datetime(df['pickup_datetime'], errors='coerce')
        df['pickup_hour'] = df['pickup_datetime'].dt.hour
        df['pickup_unix'] = df['pickup_datetime'].astype('int64') // 10**9
        df['pickup_day'] = df['pickup_datetime'].dt.dayofweek
        df['is_weekend'] = df['pickup_day'] >= 5
        df['pickup_bucket'] = pd.cut(df['pickup_hour'], bins=[-1, 6, 12, 18, 24],
                                     labels=['Night', 'Morning', 'Afternoon', 'Evening'])
        df['zone_pair'] = df['PU_Zone'].astype(str) + "_" + df['DO_Zone'].astype(str)
        df['fare_to_pay_ratio'] = df['base_passenger_fare'] / (df['driver_pay'] + 1e-6)
        df['time_to_pickup'] = (
            pd.to_datetime(df['pickup_datetime'], errors='coerce') -
            pd.to_datetime(df['on_scene_datetime'], errors='coerce')
        ).dt.total_seconds()

        drop_cols = [
            'request_datetime', 'on_scene_datetime', 'pickup_datetime', 'dropoff_datetime',
            'pickup_hour', 'dropoff_hour',
            'PU_Borough', 'PU_ServiceZone', 'DO_Borough', 'DO_ServiceZone'
        ]
        df.drop(columns=drop_cols, inplace=True, errors='ignore')
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df.dropna(inplace=True)
        df = df[(df['fare_per_mile'] > 0) & (df['fare_per_mile'] < 50)]
        df = df[(df['average_speed'] > 0) & (df['average_speed'] < 80)]
        df = df[df[target_col].notna()]

        flag_cols = [
            'shared_request_flag', 'shared_match_flag',
            'access_a_ride_flag', 'wav_request_flag', 'wav_match_flag'
        ]
        for col in flag_cols:
            if col in df.columns:
                df[col] = df[col].astype("category")
        return df

    # STEP 3: Fit preprocessor on sample
    sample_df = engineer_features(sample_df)
    X_sample = sample_df.drop(columns=[target_col])
    numeric_cols = X_sample.select_dtypes(include=['int64', 'float64']).columns.tolist()
    categorical_cols = X_sample.select_dtypes(include=['object', 'category']).columns.tolist()
    preprocessor = ColumnTransformer(transformers=[
        ('num', StandardScaler(), numeric_cols),
        ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=True), categorical_cols)
    ])
    preprocessor.fit(X_sample)

    # STEP 4: Process all chunks
    for i in range(parquet_file.num_row_groups):
        df = parquet_file.read_row_group(i).to_pandas()
        df = engineer_features(df)
        if df.empty: continue
        y_chunk = df[target_col]
        X_chunk = df.drop(columns=[target_col])
        X_processed = preprocessor.transform(X_chunk)
        collected_X.append(X_processed)
        collected_y.append(y_chunk)
        
        del df, X_chunk, y_chunk, X_processed
        gc.collect()

    # STEP 5: Merge and export
    X_all = sparse.vstack(collected_X)
    y_all = pd.concat(collected_y)
    sparse.save_npz(output_x_pro, X_all)
    y_all.to_frame().to_parquet(output_y, index=False)

    # STEP 6: Split and export
    X_train, X_test, y_train, y_test = train_test_split(X_all, y_all, test_size=0.2, random_state=42)
    sparse.save_npz(x_train_file, X_train)
    sparse.save_npz(x_test_file, X_test)
    y_train.to_frame().to_parquet(y_train_file, index=False)
    y_test.to_frame().to_parquet(y_test_file, index=False)

    # STEP 7: Save preprocessor
    joblib.dump(preprocessor, pre_file)

    print(f"✅ Processed and exported {X_all.shape[0]:,} rows.")
   


#DAG functions

def create_shape_lookup(shape_filename, outputlookup):
    
    # Load shapefile
    gdf = gpd.read_file(shape_filename)

    # Rename to standard naming
    gdf = gdf.rename(columns={"zone": "Zone", "borough": "Borough"})
    
    gdf = gdf.to_crs(epsg=4326)

    # Calculate centroid coordinates
    gdf["Latitude"] = gdf.geometry.centroid.y
    gdf["Longitude"] = gdf.geometry.centroid.x

    # Select only needed columns
    zone_lookup = gdf[["LocationID", "Borough", "Zone", "Latitude", "Longitude"]]

    # Save to CSV
    zone_lookup.to_csv(outputlookup, index=False)

#Yellow/Green datasets

def clean_taxi_yellow_data(y_filename, lookup_filename, y_cleaned_filename):
    
    initial_df = dd.read_parquet(y_filename)
    lookup_dd = dd.read_csv(lookup_filename)

    initial_df = merge_lookup_dask_green_yellow(initial_df, lookup_dd)

    df = initial_df.compute()

    df = yellow_data_cleaning(df)

    df.to_parquet(y_cleaned_filename, engine="pyarrow", index=False)

def clean_taxi_green_data(g_filename, lookup_filename, g_cleaned_filename):
    
    initial_df = dd.read_parquet(g_filename)
    lookup_dd = dd.read_csv(lookup_filename)

    initial_df = merge_lookup_dask_green_yellow(initial_df, lookup_dd)

    df = initial_df.compute()

    df = green_data_cleaning(df)

    df.to_parquet(g_cleaned_filename, engine="pyarrow", index=False)


def feat_engineering_taxi_yellow_data(y_cleandfilename, y_featfilename):
        df = pd.read_parquet(y_cleandfilename)

        df = yellow_feature_engineering(df)

        df.to_parquet(y_featfilename, engine="pyarrow", index=False)

def feat_engineering_taxi_green_data(g_cleandfilename, g_featfilename):
        df = pd.read_parquet(g_cleandfilename)

        df = green_feature_engineering(df)

        df.to_parquet(g_featfilename, engine="pyarrow", index=False)


def sanitize_save_taxi_yellow_data(y_featfilename, y_finalname):
    df = pd.read_parquet(y_featfilename)

    df= sanitize_taxi_data(df)
    
    

    df.to_parquet(y_finalname, engine="pyarrow", index=False)

def sanitize_save_taxi_green_data(g_featfilename, g_finalname):
    df = pd.read_parquet(g_featfilename)

    df = sanitize_taxi_data(df)
    

    df.to_parquet(g_finalname, engine="pyarrow", index=False)


def load_to_postgres_taxi_yellow_data(conn, y_finalname, sql_chunksize):
    print('Preparing conn')
    engine = create_engine(conn)
    if(engine.connect()):
        print('connected successfully')
        df = pd.read_parquet(y_finalname)
        print('saving to database')
        df.to_sql('yellow', engine, if_exists='replace', index=False, method='multi',  # Better batch performance
                chunksize=sql_chunksize  # Controls the batch insert to SQL
                )
        
def load_to_postgres_taxi_green_data(conn, g_finalname, sql_chunksize):
    print('Preparing conn')
    engine = create_engine(conn)
    if(engine.connect()):
        print('connected successfully')
        df = pd.read_parquet(g_finalname)
        print('saving to database')
        df.to_sql('green', engine, if_exists='replace', index=False, method='multi',  # Better batch performance
                chunksize=sql_chunksize  # Controls the batch insert to SQL
                )

#fhvhv datasets

def process_save_taxi_fh_data(fh_filename, lookup_filename, fh_cleaned_filename):
    # Open the Parquet file
    parquet_file = pq.ParquetFile(fh_filename)


    # Storage for stats
    arrival_deltas = []
    zone_values = defaultdict(list) 
    global_median_arrival_delta = None
    mode_lookup = {}

    # Check number of row groups (i.e., chunks)
    print(f"Total row groups: {parquet_file.num_row_groups}")

    # Loop over each row group (chunk)
    for i in range(parquet_file.num_row_groups):
        print(f"\n🔹 Reading row group {i + 1} of {parquet_file.num_row_groups}")
        
        # Read the chunk as a pandas DataFrame
        chunk = parquet_file.read_row_group(i).to_pandas()
        
        # Do something with the chunk
        print(f"✅ Loaded chunk {i} with {len(chunk):,} rows and {chunk.shape[1]} columns")

        print('Calculating global median for arrival_delta and mode for locationsIDs ')


        # ⏱️ Collect valid arrival deltas
        for col in ['request_datetime', 'on_scene_datetime']:
            chunk[col] = pd.to_datetime(chunk[col], errors='coerce')

        mask = chunk['on_scene_datetime'].notna() & chunk['request_datetime'].notna()
        delta = (chunk.loc[mask, 'on_scene_datetime'] - chunk.loc[mask, 'request_datetime']).dt.total_seconds()
        delta = delta[(delta > 0) & (delta < 1800)]
        arrival_deltas.append(delta)

        # 📍 Collect data for mode-based zone imputation
        for col, loc_col in [
            ('PU_Borough', 'PULocationID'), ('DO_Borough', 'DOLocationID'),
            ('PU_Zone', 'PULocationID'), ('DO_Zone', 'DOLocationID'),
            ('PU_ServiceZone', 'PULocationID'), ('DO_ServiceZone', 'DOLocationID')
        ]:
            if col in chunk.columns:
                mask_valid = ~chunk[loc_col].isin([264, 265]) & chunk[col].notna()
                sub_chunk = chunk.loc[mask_valid, [loc_col, col]]
                zone_values[(col, loc_col)].append(sub_chunk)
        
        del chunk
        gc.collect()

    print("✅ Finished first pass (collection). Now computing global stats...")

    # 🎯 Global median for arrival delta
    global_median_arrival_delta = pd.concat(arrival_deltas).median()
    print(f"📏 Global median dispatch-to-arrival time: {global_median_arrival_delta:.1f} seconds")

    # 🎯 Global mode per LocationID
    mode_lookup = {}
    for (col, loc_col), frames in zone_values.items():
        combined = pd.concat(frames)
        grouped = combined.groupby(loc_col)[col]
        mode_lookup[(col, loc_col)] = grouped.agg(
            lambda x: x.mode().iloc[0] if not x.mode().empty else None
        ).to_dict()

    print("✅ Global mode lookup tables ready.")

    lookup_df = pd.read_csv(lookup_filename)

    first = True


    for i in range(parquet_file.num_row_groups):
        print(f"\n🔹 Reading row group {i + 1} of {parquet_file.num_row_groups}")
        
        # Read the chunk as a pandas DataFrame
        chunk = parquet_file.read_row_group(i).to_pandas()
        
        # Do something with the chunk
        print(f"✅ Loaded chunk {i} with {len(chunk):,} rows and {chunk.shape[1]} columns")
        print('Cleaning and Saving chunks')

        chunk = merge_lookup(chunk, lookup_df)
        chunk = impute_on_scene_datetime(chunk, global_median_arrival_delta)
        chunk = fill_modes(chunk, mode_lookup)
        chunk = clean_chunk(chunk)

        if first:
            chunk.to_parquet(fh_cleaned_filename, engine="fastparquet", compression="snappy", index=False)
            first = False
        else:
            fastparquet.write(fh_cleaned_filename, chunk, append=True)

        del chunk
        gc.collect()

def load_to_postgres_taxi_fh_chunked(conn_str, fh_filename, table_name='fhvhv', sql_chunk_size=35_000):
    print("Preparing connection...")
    engine = create_engine(conn_str)

    with engine.connect() as connection:
        print("Connected successfully")

        # Read parquet as row groups using PyArrow
        parquet_file = pq.ParquetFile(fh_filename)
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


#ML

def process_yellow_ML(yfilename, ml_y_ready_filename):
    yellow_df = pd.read_parquet(yfilename)
    
    print("Detecting outliers")
    
    yellow_df, outlier_columns = detect_iqr_outliers(yellow_df)
    
    print("Transforming outliers")
    
    yellow_df = transform_outlier_columns_log(yellow_df, outlier_columns)
    
    print("Saving ML ready to file")
    
    yellow_df.to_parquet(ml_y_ready_filename, engine='pyarrow', compression='snappy', index=False)
    
def process_green_ML(gfilename, ml_g_ready_filename):
    green_df = pd.read_parquet(gfilename)
    
    print("Detecting outliers")
    
    green_df, outlier_columns = detect_iqr_outliers(green_df)
    
    green_df = transform_outlier_columns_log(green_df, outlier_columns)
    
    green_df.to_parquet(ml_g_ready_filename, engine='pyarrow', compression='snappy', index=False)
    
def process_fhvhv_ML(parquet_path, output_x_pro, output_y, x_train_file, y_train_file, x_test_file, y_test_file, pre_file, row_limit):
    
    print("Processing fhvhv dataset for ML logic")
    process_parquet_in_chunks(parquet_path, output_x_pro, output_y, x_train_file, y_train_file, x_test_file, y_test_file, pre_file, row_limit)
    
    






