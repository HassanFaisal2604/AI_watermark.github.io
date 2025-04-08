from server import app

# This file is used by gunicorn in production
# No need for the if __name__ block since gunicorn will import this file directly

# The app variable is imported from server.py and will be used by gunicorn
# as specified in the Procfile: web: gunicorn wsgi:app