from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.utils.helpers import chain
from airflow.utils.task_group import TaskGroup
from airflow.models import Variable

from utils.taxi_dataset_perp import (
    
    clean_taxi_yellow_data, clean_taxi_green_data,
    feat_engineering_taxi_yellow_data, feat_engineering_taxi_green_data,
    sanitize_save_taxi_yellow_data, sanitize_save_taxi_green_data,
    load_to_postgres_taxi_yellow_data, load_to_postgres_taxi_green_data,
    process_save_taxi_fh_data, load_to_postgres_taxi_fh_chunked,
    process_yellow_ML, process_green_ML, process_fhvhv_ML
)

# Default DAG arguments
default_args = {
    "owner": "Capstone_Project_team",
    "depends_on_past": False,
    "start_date": days_ago(2),
    "retries": 2,
}

# Branching logic

def choose_pipeline_based_on_variable():
    pipeline = Variable.get("taxi_pipeline_switch", default_var="all")

    if pipeline == "yellow":
        return "yellow_pipeline.clean_yellow"
    elif pipeline == "green":
        return "green_pipeline.clean_green"
    elif pipeline == "fhvhv":
        return "fhvhv_pipeline.process_fhvhv"
    elif pipeline == "ml":
        return "ml_process_pipeline.ml_process_yellow"
    else:
        return ["yellow_pipeline.clean_yellow", "green_pipeline.clean_green"]


with DAG(
    dag_id='capstone_taxi_data_processing',
    schedule_interval=None,
    default_args=default_args,
    tags=['pipeline', 'etl', 'analysis'],
) as dag:

    # Dummy nodes
    start = DummyOperator(task_id="start")
      # Branching node
    branch = BranchPythonOperator(
        task_id="choose_pipeline",
        python_callable=choose_pipeline_based_on_variable
    )
    join = DummyOperator(task_id="join_after_all_pipelines", trigger_rule="none_failed_min_one_success")
    end = DummyOperator(task_id="end")
    

#     preprocess_shape_lookup = PythonOperator(
#     task_id="create_shape_lookup",
#     python_callable=create_shape_lookup,
#     op_kwargs={
#                 'shape_filename': '/opt/airflow/data/taxi_zones/taxi_zones.shp',
#                 'outputlookup': '/opt/airflow/data/taxi_zone_lookup_s.csv',
#                 'o_lookup_filename': '/opt/airflow/data/taxi_zone_lookup.csv',
#             }
# )


    # ✅ Yellow Task Group
    with TaskGroup("yellow_pipeline", tooltip="Yellow Taxi Pipeline") as yellow_group:
        clean_yellow = PythonOperator(
            task_id='clean_yellow',
            python_callable=clean_taxi_yellow_data,
            op_kwargs={
                'y_filename': '/opt/airflow/data/yellow_merged24_daily_sample.parquet',
                'lookup_filename': '/opt/airflow/data/merged_zones_data.csv',
                'y_cleaned_filename': '/opt/airflow/data/yellow_cleaned.parquet',
            }
        )

        f_engineering_yellow = PythonOperator(
            task_id='f_engineering_yellow',
            python_callable=feat_engineering_taxi_yellow_data,
            op_kwargs={
                'y_cleandfilename': '/opt/airflow/data/yellow_cleaned.parquet',
                'y_featfilename': '/opt/airflow/data/yellow_feat.parquet',
            }
        )

        san_save_yellow = PythonOperator(
            task_id='san_save_yellow',
            python_callable=sanitize_save_taxi_yellow_data,
            op_kwargs={
                'y_featfilename': '/opt/airflow/data/yellow_feat.parquet',
                'y_finalname': '/opt/airflow/data/yellow_final.parquet',
            }
        )

        load_to_db_taxi_yellow = PythonOperator(
            task_id='load_to_db_taxi_yellow',
            python_callable=load_to_postgres_taxi_yellow_data,
            op_kwargs={
                'conn': 'postgresql://root:root@pgdatabase:5432/capstone_project_taxi',
                'y_finalname': '/opt/airflow/data/yellow_final.parquet',
                'sql_chunksize': 35_000
            }
        )
        
        end_yellow = DummyOperator(task_id="Yellow_end")

        chain(clean_yellow, f_engineering_yellow, san_save_yellow, load_to_db_taxi_yellow, end_yellow)

    # ✅ Green Task Group
    with TaskGroup("green_pipeline", tooltip="Green Taxi Pipeline") as green_group:
        clean_green = PythonOperator(
            task_id='clean_green',
            python_callable=clean_taxi_green_data,
            op_kwargs={
                'g_filename': '/opt/airflow/data/green_merged24_daily_sample.parquet',
                'lookup_filename': '/opt/airflow/data/merged_zones_data.csv',
                'g_cleaned_filename': '/opt/airflow/data/green_cleaned.parquet',
            }
        )

        f_engineering_green = PythonOperator(
            task_id='f_engineering_green',
            python_callable=feat_engineering_taxi_green_data,
            op_kwargs={
                'g_cleandfilename': '/opt/airflow/data/green_cleaned.parquet',
                'g_featfilename': '/opt/airflow/data/green_feat.parquet',
            }
        )

        san_save_green = PythonOperator(
            task_id='san_save_green',
            python_callable=sanitize_save_taxi_green_data,
            op_kwargs={
                'g_featfilename': '/opt/airflow/data/green_feat.parquet',
                'g_finalname': '/opt/airflow/data/green_final.parquet',
            }
        )

        load_to_db_taxi_green = PythonOperator(
            task_id='load_to_db_taxi_green',
            python_callable=load_to_postgres_taxi_green_data,
            op_kwargs={
                'conn': 'postgresql://root:root@pgdatabase:5432/capstone_project_taxi',
                'g_finalname': '/opt/airflow/data/green_final.parquet',
                'sql_chunksize': 35_000
            }
        )
        
        end_green = DummyOperator(task_id="Green_end")

        chain(clean_green, f_engineering_green, san_save_green, load_to_db_taxi_green, end_green)

    # ✅ FHVHV Task Group
    with TaskGroup("fhvhv_pipeline", tooltip="FHVHV Pipeline") as fhvhv_group:
        process_fhvhv = PythonOperator(
            task_id='process_fhvhv',
            python_callable=process_save_taxi_fh_data,
            op_kwargs={
                'fh_filename': '/opt/airflow/data/fhvhv_merged24_daily_sample.parquet',
                'lookup_filename': '/opt/airflow/data/merged_zones_data.csv',
                'fh_cleaned_filename': '/opt/airflow/data/fhvhv_cleaned.parquet',
            }
        )

        load_to_db_taxi_fhvhv = PythonOperator(
            task_id='load_to_db_taxi_fhvhv',
            python_callable=load_to_postgres_taxi_fh_chunked,
            op_kwargs={
                'conn_str': 'postgresql://root:root@pgdatabase:5432/capstone_project_taxi',
                'fh_filename': '/opt/airflow/data/fhvhv_cleaned.parquet',
                'sql_chunk_size': 75_000
            }
        )
        
        end_fhvhv = DummyOperator(task_id="FHVHV_end")

        chain(process_fhvhv, load_to_db_taxi_fhvhv, end_fhvhv)
        
    # ✅ ML Task Group
    with TaskGroup("ml_process_pipeline", tooltip="ml process pipeline") as ml_group:
        
        ml_process_yellow = PythonOperator(
            task_id='ml_process_yellow',
            python_callable=process_yellow_ML,
            op_kwargs={
                'yfilename': '/opt/airflow/data/yellow_final.parquet',
                'ml_y_ready_filename': '/opt/airflow/data/yellow_ml_ready.parquet',
                
            }
        )

        ml_process_green = PythonOperator(
            task_id='ml_process_green',
            python_callable=process_green_ML,
            op_kwargs={
                'gfilename': '/opt/airflow/data/green_final.parquet',
                'ml_g_ready_filename': '/opt/airflow/data/green_ml_ready.parquet',
                
            }
        )
        
        ml_process_fhvhv = PythonOperator(
            task_id='ml_process_fhvhv',
            python_callable=process_fhvhv_ML,
            op_kwargs={
                'parquet_path': '/opt/airflow/data/fhvhv_cleaned.parquet',
                'output_x_pro': '/opt/airflow/data/fhvhv_x_processed.npz',
                'output_y': '/opt/airflow/data/fhvhv_o_y_.parquet',
                'x_train_file': '/opt/airflow/data/fhvhv_x_train.npz',
                'y_train_file': '/opt/airflow/data/fhvhv_y_train.parquet',
                'x_test_file': '/opt/airflow/data/fhvhv_x_test.npz',
                'y_test_file': '/opt/airflow/data/fhvhv_y_test.parquet',
                'pre_file': '/opt/airflow/data/fhvhv_preprocessor.pkl',
                'row_limit': 50_000
                
            }
        )
        
        ML_process_end = DummyOperator(task_id="ML_process_end")

        chain(ml_process_yellow, ml_process_green, ml_process_fhvhv, ML_process_end)

        

 
    
    start >> branch

    branch >> yellow_group
    branch >> green_group
    branch >> fhvhv_group
    branch >> ml_group

    # Join all possible groups back
    yellow_group >> join
    green_group >> join
    fhvhv_group >> join
    ml_group >> join

    # Final end
    join >> end

