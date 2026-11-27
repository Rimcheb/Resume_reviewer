#!/bin/sh
# Use Render's assigned port and the existing Flask application factory.
set -eu
exec gunicorn --bind "0.0.0.0:${PORT:-10000}" --workers 1 'app:create_app()'
