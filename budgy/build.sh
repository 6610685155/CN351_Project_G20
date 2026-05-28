#!/usr/bin/env bash
# Exit on error
set-o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py flush --no-input
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py createsuperuser --no-input --username $DJANGO_SUPERUSER_USERNAME --email $DJANGO_SUPERUSER_EMAIL