from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import PythonOperator



from utils.bus_dataset_prep import process_save_bus_data, load_to_postgres_bus_chunked


# Default arguments
default_args = {
    "owner": "Capstone_Project_team",
    "depends_on_past": False,
    "start_date": days_ago(2),
    "retries": 2,
}

with DAG(
    dag_id = 'capstone_bus_data_processing',
    schedule_interval = None, # could be @daily, @hourly, etc or a cron expression '* * * * *'
    default_args = default_args,
    tags = ['pipeline', 'etl', 'analysis'],
)as dag:

# DAG definition

#Subway Tasks

# Task 1: clean datasets

    clean_bus_data = PythonOperator(
        task_id = 'clean_bus_data',
        python_callable = process_save_bus_data,
        op_kwargs = {
            'busfilename': '/opt/airflow/data/merged_mta_bus_data_final.parquet',
            'bus_stopsfilename': "/opt/airflow/data/fact_timepoints.parquet",
            'geo_file': "/opt/airflow/data//sp/ne_110m_admin_0_countries.shp",
            'bus_temp_file' : '/opt/airflow/data/cleaned_mta_bus_data_output.parquet',
            'bus_outputfilename' : '/opt/airflow/data/final_mta_bus_data_output.parquet'
        }
        
    )

# Task 2: load to db

    load_to_db_bus = PythonOperator(
        task_id = 'load_to_db_bus',
        python_callable = load_to_postgres_bus_chunked,
        op_kwargs = {
            'conn_str': 'postgresql://root:root@pgdatabase:5432/capstone_project_bus',
            'bus_filename': '/opt/airflow/data/cleaned_mta_bus_data_output.parquet',
            'sql_chunk_size': 75_000
        }
        
    )


start = DummyOperator(task_id="start")
end = DummyOperator(task_id="end")

# Task dependencies

start >> clean_bus_data >> load_to_db_bus >> end
