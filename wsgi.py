# wsgi.py
import eventlet
eventlet.monkey_patch()

try:
    from psycogreen.eventlet import patch_psycopg
    patch_psycopg()
    print("psycogreen patch applied successfully.")
except ImportError:
    print("psycogreen not found, database connections might block.")

# Importamos la fábrica Y el objeto socketio global
from app import create_app, socketio

# Creamos la app
app = create_app()

# El objeto 'socketio' ya fue configurado dentro de create_app.
# Gunicorn necesita que le pasemos este objeto para ejecutar.