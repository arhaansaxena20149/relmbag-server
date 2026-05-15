"""
WSGI entrypoint for production servers (e.g., gunicorn).

Run locally:
  gunicorn -w 2 -b 0.0.0.0:5050 wsgi:app
"""

from server import app

