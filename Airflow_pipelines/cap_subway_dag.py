from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import PythonOperator



from utils.subway_dataset_prep import (process_subway_data_trips, load_to_postgres_subway_trips, 
process_subway_data_stops, load_to_postgres_subway_stops_chunked, add_trip_duration_merge)


# Default arguments
default_args = {
    "owner": "Capstone_Project_team",
    "depends_on_past": False,
    "start_date": days_ago(2),
    "retries": 2,
}

with DAG(
    dag_id = 'capstone_subway_data_processing',
    schedule_interval = None, # could be @daily, @hourly, etc or a cron expression '* * * * *'
    default_args = default_args,
    tags = ['pipeline', 'etl', 'analysis'],
)as dag:

# DAG definition

#Subway Tasks

# Task 1: clean datasets

    clean_subway_data_trips = PythonOperator(
        task_id = 'clean_subway_data_trips',
        python_callable = process_subway_data_trips,
        op_kwargs = {
            'trips_df_filenname': '/opt/airflow/data/sample_trips.parquet',
            'fare_per_trip': 2.90,
            'trips_df_outputfilename' : '/opt/airflow/data/cleaned_trips.parquet'
        }
        
    )
    
    subway_trip_duration_merge = PythonOperator(
        task_id = 'subway_trip_duration_merge',
        python_callable = add_trip_duration_merge,
        op_kwargs = {
            'all_trips_filename': '/opt/airflow/data/cleaned_trips.parquet',
            'all_stop_filename': '/opt/airflow/data/cleaned_stops.parquet',
            'final_trips_file' : '/opt/airflow/data/final_trips.parquet'
        }
        
    )

    clean_subway_data_stops = PythonOperator(
        task_id = 'clean_subway_data_stops',
        python_callable = process_subway_data_stops,
        op_kwargs = {
            'stops_df_filename': '/opt/airflow/data/filtered_stops.parquet',
            'temp_filename': '/opt/airflow/data/temp_stops.parquet',
            'stops_df_outputfilename' : '/opt/airflow/data/cleaned_stops.parquet'
        }
        
    )

# Task 2: load to db

    load_to_db_subway_trips = PythonOperator(
        task_id = 'load_to_db_subway_trips',
        python_callable = load_to_postgres_subway_trips,
        op_kwargs = {
            'conn': 'postgresql://root:root@pgdatabase:5432/capstone_project_subway',
            'trips_filename': '/opt/airflow/data/final_trips.parquet',
        }
        
    )

    load_to_db_subway_stops = PythonOperator(
        task_id = 'load_to_db_subway_stops',
        python_callable = load_to_postgres_subway_stops_chunked,
        op_kwargs = {
            'conn_str': 'postgresql://root:root@pgdatabase:5432/capstone_project_subway',
            'stops_filename': '/opt/airflow/data/cleaned_stops.parquet',
            'table_name': 'stops',
            'sql_chunk_size' : 10_000
        }
        
    )

start = DummyOperator(task_id="start")
end = DummyOperator(task_id="end")

# Task dependencies

start >> clean_subway_data_trips >> clean_subway_data_stops >> subway_trip_duration_merge >> load_to_db_subway_trips >> load_to_db_subway_stops >> end
