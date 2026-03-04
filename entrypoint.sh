#!/usr/bin/env bash
exec gunicorn "app:create_app()" \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --threads 4 \
    --timeout 300
