import pandas as pd
from sqlalchemy import create_engine




def standardize_operational_days(df, display_results=True):
    """
    Standardizes the 'Days' column by converting to lowercase and replacing
    '7 days/week' with 'all days'.

    Args:
        df: pandas DataFrame containing the 'Days' column.
        display_results: If True, displays the updated distribution of 'Days'.

    Returns:
        pandas DataFrame with the standardized 'Days' column.
    """
    # Ensure 'Days' column exists
    if 'Days' not in df.columns:
        print("Error: 'Days' column not found in the DataFrame.")
        return df

    # Convert to lowercase and standardize '7 days/week'
    df['Days'] = df['Days'].str.lower().str.replace('7 days/week', 'all days', regex=False)

    # Display updated distribution if requested
    if display_results:
        print("Updated Distribution of Operational Days after standardization:")
        print(df['Days'].value_counts())

    return df

def apply_standardize_hours_to_df(df, hours_column='Hours', standardized_column_name='Hours_24hr_Standardized', display_results=True):
    """
    Standardizes the operational hours in a specified column of the DataFrame
    to a 24-hour format and creates a new column for it.

    Args:
        df: pandas DataFrame containing the hours column.
        hours_column: The name of the column containing the operational hours strings.
        standardized_column_name: The name for the new column with standardized hours.
        display_results: If True, displays the first few rows with the original
                         and standardized hours columns.

    Returns:
        pandas DataFrame with the new standardized hours column added.
    """
    if hours_column not in df.columns:
        print(f"Error: '{hours_column}' column not found in the DataFrame.")
        return df

    def parse_hours_to_24hr_internal(hours_str):
        """
        Parses a string representing operational hours and converts it to a standardized
        24-hour format. This is an internal helper function.
        """
        if pd.isna(hours_str):
            return None

        # Apply the cleaning steps to the individual hours_str
        hours_str = str(hours_str).lower().replace(' ', '')
        hours_str = hours_str.replace('24hrs', '24hours')
        hours_str = hours_str.replace('24hour', '24hours')
        hours_str = hours_str.replace('24hourss', '24hours')


        if hours_str == '24hours':
            return [('00:00', '24:00')] # Represent 24 hours

        ranges = hours_str.split('/')
        standardized_ranges = []

        def convert_to_24hr(time_str):
            """Converts a time string (e.g., 7am, 2pm) to 24-hour format (HH:MM)."""
            time_str = time_str.strip()
            if 'am' in time_str:
                hour = int(time_str.replace('am', ''))
                if hour == 12: # 12am is 00:00
                    hour = 0
            elif 'pm' in time_str:
                hour = int(time_str.replace('pm', ''))
                if hour != 12: # 12pm is 12:00, others add 12
                    hour += 12
            else: # Assume 24-hour format already or simple hour
                 # Attempt to handle cases like "7" or "14"
                 try:
                     hour = int(time_str)
                 except ValueError:
                      print(f"Warning: Could not parse time string {time_str} to integer hour.")
                      return None # Indicate parsing failure
            return f'{hour:02d}:00'


        for time_range_str in ranges:
            try:
                start_time_str, end_time_str = time_range_str.split('-')

                start_time_24hr = convert_to_24hr(start_time_str)
                end_time_24hr = convert_to_24hr(end_time_str)

                # Only append if both start and end times were successfully converted
                if start_time_24hr is not None and end_time_24hr is not None:
                     standardized_ranges.append((start_time_24hr, end_time_24hr))
                else:
                     print(f"Skipping range due to parsing error: {time_range_str}")

            except ValueError:
                print(f"Could not split time range by '-': {time_range_str} from {hours_str}")
                # Decide how to handle ranges that cannot be split (e.g., return None, skip)
                pass # Skip this range if it can't be split


        # If no ranges were successfully parsed, return None
        if not standardized_ranges:
             return None


        return standardized_ranges


    # Apply the internal parsing function to the specified column
    df[standardized_column_name] = df[hours_column].apply(parse_hours_to_24hr_internal)

    if display_results:
        print(f"First few rows with original '{hours_column}' and standardized '{standardized_column_name}':")
        print(df[[hours_column, standardized_column_name]].head())

    return df

def drop_duplicates_excluding(df, exclude_column='Hours_24hr_Standardized', keep='first', display_results=True):
    """
    Drops duplicate rows from a DataFrame, excluding a specified column, and returns the cleaned DataFrame.

    Args:
        df: pandas DataFrame to drop duplicates from.
        exclude_column: The name of the column to exclude from the duplicate check.
        keep: Determines which duplicates (if any) to keep.
              'first': Drop duplicates except for the first occurrence.
              'last': Drop duplicates except for the last occurrence.
              False: Drop all duplicates.
        display_results: If True, prints the number of rows before and after dropping.

    Returns:
        pandas DataFrame with duplicate rows dropped.
    """
    # Get the list of columns excluding the specified column
    columns_to_check = [col for col in df.columns if col != exclude_column]

    initial_rows = len(df)

    # Drop duplicate rows based on the selected columns, modifying df in place
    df.drop_duplicates(subset=columns_to_check, keep=keep, inplace=True)

    final_rows = len(df)

    if display_results:
        print("DataFrame after dropping duplicate rows:")
        print("Number of rows in original DataFrame:", initial_rows)
        print("Number of rows in cleaned DataFrame:", final_rows) # Should be the same as final_rows


    return df # Return the modified DataFrame

def drop_rows_with_nulls_in_subset(df, columns_to_check, display_results=True):
    """
    Drops rows from a DataFrame that have null values in any of the specified columns.

    Args:
        df: pandas DataFrame to drop rows from.
        columns_to_check: A list of column names to check for null values.
        display_results: If True, prints the number of rows before and after dropping.

    Returns:
        pandas DataFrame with the specified rows dropped.
    """
    initial_rows = len(df)
    df_cleaned = df.dropna(subset=columns_to_check).copy()
    final_rows = len(df_cleaned)

    if display_results:
        print("DataFrame after dropping rows with nulls in specified columns:")
        print("Number of rows in original DataFrame:", initial_rows)
        print("Number of rows after dropping nulls:", final_rows)

    return df_cleaned

def standardize_and_impute_lane_width(df, display_results=True):
    """
    Standardizes values and imputes nulls in the 'Lane_width' column.

    Args:
        df: pandas DataFrame containing the 'Lane_width' column.
        display_results: If True, displays the updated distribution of 'Lane_width'.

    Returns:
        pandas DataFrame with the standardized and imputed 'Lane_width' column.
    """
    if 'Lane_width' not in df.columns:
        print("Error: 'Lane_width' column not found in the DataFrame.")
        return df

    # Standardize values in the 'Lane_width' column
    df['Lane_width'] = df['Lane_width'].replace({
        'Double': 'Dual',
        'Contra Flow': 'Dual',
        'Contra flow': 'Dual',
        'Left-Turn Bay': 'Left-Turn'
    })

    # Fill null values with 'Single'
    df['Lane_width'].fillna('Single', inplace=True)

    # Display updated distribution if requested
    if display_results:
        print("Updated Distribution of Lane_width values after standardization and imputation:")
        print(df['Lane_width'].value_counts(dropna=False))

    return df

def impute_lane_color_nulls(df, fill_value='Red', display_results=True):
    """
    Imputes null values in the 'Lane_Color' column with a specified value.

    Args:
        df: pandas DataFrame containing the 'Lane_Color' column.
        fill_value: The value to use for imputation (default is 'Red').
        display_results: If True, displays the updated distribution of 'Lane_Color'.

    Returns:
        pandas DataFrame with the null values in 'Lane_Color' imputed.
    """
    if 'Lane_Color' not in df.columns:
        print("Error: 'Lane_Color' column not found in the DataFrame.")
        return df

    # Fill null values in 'Lane_Color' with the specified fill_value
    df['Lane_Color'].fillna(fill_value, inplace=True)

    # Display updated distribution if requested
    if display_results:
        print(f"Distribution of Lane_Color values after imputing nulls with '{fill_value}':")
        print(df['Lane_Color'].value_counts(dropna=False))

    return df

def handle_lane_type_nulls(df, display_results=True):
    """
    Handles null values in 'Lane_Type1' and 'Lane_Type2' by dropping rows
    where both are null and imputing remaining nulls in 'Lane_Type2' from 'Lane_Type1'.

    Args:
        df: pandas DataFrame containing 'Lane_Type1' and 'Lane_Type2' columns.
        display_results: If True, displays the null counts for both columns after operations.

    Returns:
        pandas DataFrame with null values in 'Lane_Type1' and 'Lane_Type2' handled.
    """
    if 'Lane_Type1' not in df.columns or 'Lane_Type2' not in df.columns:
        print("Error: 'Lane_Type1' or 'Lane_Type2' column not found in the DataFrame.")
        return df

    # Drop rows where both 'Lane_Type1' and 'Lane_Type2' are null
    initial_rows = len(df)
    df.dropna(subset=['Lane_Type1', 'Lane_Type2'], how='all', inplace=True)
    rows_after_dropping = len(df)
    print(f"Dropped {initial_rows - rows_after_dropping} rows where both Lane_Type1 and Lane_Type2 were null.")


    # Impute remaining nulls in 'Lane_Type2' with values from 'Lane_Type1'
    df['Lane_Type2'].fillna(df['Lane_Type1'], inplace=True)

    if display_results:
        print("\nNull values for Lane_Type1 and Lane_Type2 after dropping and imputing:")
        print(df[['Lane_Type1', 'Lane_Type2']].isnull().sum())

    return df

def Handle_SBS_Route_Nulls(df, display_results=True):
    """
    Drops the 'SBS_Route3' and 'SBS_Route2' columns and imputes nulls
    in 'SBS_Route1' with 'Unknown'. Modifies the DataFrame in place.

    Args:
        df: pandas DataFrame to process.
        display_results: If True, displays results of imputation and remaining columns.
    """
    columns_to_drop = ['SBS_Route3', 'SBS_Route2']

    # Drop the specified columns, ignoring errors if columns are already dropped
    # Operate directly on the input DataFrame 'df'
    df.drop(columns_to_drop, axis=1, errors='ignore', inplace=True)

    # Fill null values in 'SBS_Route1' with 'Unknown'
    if 'SBS_Route1' in df.columns:
        df['SBS_Route1'].fillna('Unknown', inplace=True)
        if display_results:
            print("\nNull values for SBS_Route1 after imputation:")
            print(df['SBS_Route1'].isnull().sum())
            print("\nDistribution of SBS_Route1 values after imputation:")
            print(df['SBS_Route1'].value_counts(dropna=False))
    else:
         if display_results:
              print("\nSBS_Route1 column not found after dropping other SBS columns.")


    if display_results:
        print(f"\nDataFrame columns after handling SBS Route nulls (dropped {columns_to_drop}):")
        print(df.columns)

    # Although modifying in place, it's good practice to return the DataFrame
    return df



def standardize_bus_lane(df, display_results=True):
    df = standardize_operational_days(df, display_results)
    df = apply_standardize_hours_to_df(df)
    df = standardize_and_impute_lane_width(df, display_results)
    
    return df

def impute_bus_lane(df, display_results=True):
    df = impute_lane_color_nulls(df)
    df = handle_lane_type_nulls(df, display_results)
    df = Handle_SBS_Route_Nulls(df, display_results)
    
    return df

def drop_ops_bus_lane(df, display_results):
    columns_to_drop_nulls = ['TrafDir', 'RW_TYPE', 'Hours', 'Days', 'Last_Updat', 'Hours_24hr_Standardized']
    df = drop_duplicates_excluding(df)
    df = drop_rows_with_nulls_in_subset(df, columns_to_drop_nulls, display_results)

    return df

#DAG methods

def clean_bus_lane(filename, outputfilename, display_results):
    print('Reading main dataset')
    df = pd.read_csv(filename)

    print('Standradize operations')
    df = standardize_bus_lane(df, display_results)

    print('Impute operations')
    df = impute_bus_lane(df, display_results)

    print('Handling null values')
    df = drop_ops_bus_lane(df, display_results)

    print('Saving cleaned dataset')

    df.to_csv(outputfilename, index=False)


def load_to_postgres_bus_lane(conn, filename):
    print('Preparing conn')
    engine = create_engine(conn)
    if(engine.connect()):
        print('connected successfully')
        df = pd.read_csv(filename)
        df.to_sql('bus_lanes', engine, if_exists='replace', index=False)
    else:
        print('failed to connect')
   
   