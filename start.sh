#!/usr/bin/env bash
# exit on error
set -o errexit

# Start Gunicorn
cd /opt/render/project/src
gunicorn digidine.wsgi:application --bind 0.0.0.0:$PORT 