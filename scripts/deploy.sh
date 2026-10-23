#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py shell -c 'from ai_assist.tasks import harvest_ontologies_task; print(harvest_ontologies_task.delay().id)'
