#!/bin/bash

if [ "$1" = "webserver" ]; then
	uvicorn veridash_backend.webserver.app:app --host 0.0.0.0 --port 80 --workers 8
elif [ "$1" = "worker" ]; then
	celery -A veridash_backend.worker.app worker --concurrency=8 -E
else
	echo "No valid entrypoint command specified. Please use 'webserver' or 'worker'."
	exit 1
fi

