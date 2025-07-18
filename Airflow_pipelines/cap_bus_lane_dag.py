from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import PythonOperator



from utils.bus_lane_dataset_prep import load_to_postgres_bus_lane, clean_bus_lane


# Default arguments
default_args = {
    "owner": "Capstone_Project_team",
    "depends_on_past": False,
    "start_date": days_ago(2),
    "retries": 2,
}

with DAG(
    dag_id = 'capstone_bus_lane_data_processing',
    schedule_interval = None, # could be @daily, @hourly, etc or a cron expression '* * * * *'
    default_args = default_args,
    tags = ['pipeline', 'etl', 'analysis'],
)as dag:

# DAG definition

#Bus Lane Tasks

# Task 1: clean dataset

    clean_bus_lane_data = PythonOperator(
        task_id = 'clean_bus_lane_data',
        python_callable = clean_bus_lane,
        op_kwargs = {
            'filename': '/opt/airflow/data/Bus_Lanes_-_Local_Streets_20250409.csv',
            'outputfilename': '/opt/airflow/data/cleaned_bus_lanes.csv',
            'display_results': True
        }
        
    )

# Task 2: load to db

    load_to_db_bus_lane = PythonOperator(
        task_id = 'load_to_db_bus_lane',
        python_callable = load_to_postgres_bus_lane,
        op_kwargs = {
            'conn': 'postgresql://root:root@pgdatabase:5432/capstone_project_bus_lane',
            'filename': '/opt/airflow/data/cleaned_bus_lanes.csv'
        }
        
    )

start = DummyOperator(task_id="start")
end = DummyOperator(task_id="end")

# Task dependencies

start >> clean_bus_lane_data >> load_to_db_bus_lane >> end
