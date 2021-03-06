"""Gunicorn configuration file."""
import multiprocessing

bind = 'unix:/var/run/cloudigrade/gunicorn.sock'
workers = multiprocessing.cpu_count() * 2 + 1
