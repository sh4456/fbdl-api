#!/bin/sh
# Render free: single worker (512MB RAM)
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
