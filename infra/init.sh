#!/bin/bash

with_build=$1

# Safe base dir in native Linux FS
BASE_DIR=$HOME/capstone
PG_BASE_DIR=$BASE_DIR/postgres
AF_BASE_DIR=$BASE_DIR/airflow

# Create volume folders for AirFlow
if ls -d $AF_BASE_DIR/; then
	echo "Folder already existed: $AF_BASE_DIR"
else
	echo "Creating Folder: $AF_BASE_DIR/ar-postgres-db"
	mkdir -p $AF_BASE_DIR/ar-postgres-db
	
	
	echo "Creating Folder: $AF_BASE_DIR/dags"
	mkdir -p $AF_BASE_DIR/dags
	mkdir -p $AF_BASE_DIR/dags/utils
	touch $AF_BASE_DIR/dags/utils/__init__.py
	
	
	
	echo "Creating Folder: $AF_BASE_DIR/logs"
	mkdir -p $AF_BASE_DIR/logs
	
	
	echo "Creating Folder: $AF_BASE_DIR/config"
	mkdir -p $AF_BASE_DIR/config
	
	
	echo "Creating Folder: $AF_BASE_DIR/plugins"
	mkdir -p $AF_BASE_DIR/plugins
	
	
	echo "Creating Folder: $AF_BASE_DIR/data"
	mkdir -p $AF_BASE_DIR/data
	
	
	echo "Creating Folder: $AF_BASE_DIR/src"
	mkdir -p $AF_BASE_DIR/src
	
fi


# Create volume folders for Postgres
if ls -ld $PG_BASE_DIR/; then
	echo "Folder already existed: $PG_BASE_DIR"
else
	echo "Creating Folder: $PG_BASE_DIR/postgres-data"
	mkdir -p $PG_BASE_DIR/postgres-data
	
	
	echo "Creating Folder: $PG_BASE_DIR/pgadmin-data"
	mkdir -p $PG_BASE_DIR/pgadmin-data
	
fi
echo "Giving higher access permissions for $BASE_DIR"
chmod -R 777 $BASE_DIR


# Name of the shared network
NETWORK_NAME=cp_shared_network

# Check if the network already exists
if ! docker network ls | grep -q "$NETWORK_NAME"; then
    echo "Creating Docker network: $NETWORK_NAME"
    docker network create "$NETWORK_NAME"
else
    echo "Docker network '$NETWORK_NAME' already exists."
fi

# Start each compose stack
if [[ "$with_build" == "build" ]]; then
	echo "Starting services with build..."
	#Start Postgres
	docker compose -f ./docker/postgres/docker-compose.yml up --build -d --remove-orphans && echo "Postgres started"

	# Start Airflow
	docker compose -f ./docker/airflow/docker-compose.yml up --build -d --remove-orphans && echo "Airflow started"
	
else
	echo "Starting services..."

	#Start Postgres
	docker compose -f ./docker/postgres/docker-compose.yml up -d --remove-orphans && echo "Postgres started"

	# Start Airflow
	docker compose -f ./docker/airflow/docker-compose.yml up -d --remove-orphans && echo "Airflow started"
fi






