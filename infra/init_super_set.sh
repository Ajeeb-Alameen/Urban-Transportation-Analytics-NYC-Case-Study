#!/bin/bash

with_build=$1

# Start each compose stack
if [[ "$with_build" == "build" ]]; then
	echo "Starting services with build..."
	# Start superset
	docker compose -f ./docker/superset/docker-compose.yml up --build -d --remove-orphans && echo "Superset started"
	
else
	echo "Starting services..."

	# Start superset
	docker compose -f ./docker/superset/docker-compose.yml up -d --remove-orphans && echo "Superset started"
fi






