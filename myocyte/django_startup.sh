#!/bin/sh
echo "Starting the django_startup.sh file"


# If TESTING=true, override host/port; otherwise use the normal ones
if [ "${TESTING:-false}" = "true" ]; then
  PG_HOST=${TEST_POSTGRES_HOST:-localhost}
  PG_PORT=${TEST_POSTGRES_PORT:-5432}
  echo "### Running in TESTING mode. ###"
else
  PG_HOST=${POSTGRES_HOST:-localhost}
  PG_PORT=${POSTGRES_PORT:-5432}
fi

if [ "${DATABASE:-}" = "postgres" ]; then
  echo "Waiting for PostgreSQL at ${PG_HOST}:${PG_PORT}…"
  # loop until the TCP port is open
  while ! nc -z -w2 "$PG_HOST" "$PG_PORT"; do
    sleep 0.2
  done
  echo "PostgreSQL is up on ${PG_HOST}:${PG_PORT}"
fi

# wait for the database to be ready
echo ">>> Waiting for the database to be ready"
sleep 3

echo ">>> About to migrate"
python3 manage.py migrate --no-input
echo "<<< Migrated."
sleep 0.1

# Stop doing this for a while: it removes the signed-in sessions of existing users.
#echo ">>> Clearing the caches"
#python3.manage.py clear_cache
#echo "<<< Cleared."
#sleep 1

echo ">>> About to collect static files"
# Don't add the "--clear" flag. This removes old apps, and also "documents" directory
# which is needed for file transfer.
python3 manage.py collectstatic --no-input
echo "<<< Collected."
sleep 0.1

# echo ">>> Creating the Django Q_CLUSTER queue. See settings.py file for details."
python3 manage.py createcachetable
sleep 0.1

echo ">>> Run clustering tool in background"
python3 manage.py qcluster &
sleep 0.1

if [ "$TESTING" = "true" ]; then
  echo "Running tests because TESTING is true"
  export DJANGO_SETTINGS_MODULE=mycote.settings
  pytest -v --junitxml=/tmp/test-results/results.xml --cov=toxtempass --cov-report=xml:/tmp/test-results/coverage.xml
  exit $?
fi

# remeber to assign some workers during gunicorn startup
# echo ">>> Run the clustering tool (in the background)."
# python3 manage.py qcluster &
# sleep 0.1

echo "Done setting up Django, exiting the django_startup.sh file."
exec "$@"
