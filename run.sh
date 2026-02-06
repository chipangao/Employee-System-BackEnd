#!/bin/bash

source /Users/chipang/python/creation/venv/bin/activate

gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 wsgi:app