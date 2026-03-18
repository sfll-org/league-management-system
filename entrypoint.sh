#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
while ! python -c "import psycopg; psycopg.connect('${DATABASE_URL}')" 2>/dev/null; do
    sleep 1
done
echo "PostgreSQL is ready."

echo "Waiting for Redis..."
while ! python -c "import redis; redis.from_url('${REDIS_URL}').ping()" 2>/dev/null; do
    sleep 1
done
echo "Redis is ready."

echo "Running migrations..."
python manage.py migrate --no-input

echo "Starting: $@"
exec "$@"
