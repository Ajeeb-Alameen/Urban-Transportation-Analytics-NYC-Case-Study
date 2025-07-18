#!/bin/bash

# Shut down each compose stack
echo "Shutting down services..."

# Shut down superset
docker compose -f ./docker/superset/docker-compose.yml down && echo "Superset shut down"

# Shut down Airflow
docker compose -f ./docker/airflow/docker-compose.yml down && echo "Airflow shut down"

#Shut down Postgres
docker compose -f ./docker/postgres/docker-compose.yml down && echo "Postgres shutdown"
