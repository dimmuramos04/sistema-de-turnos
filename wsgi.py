# wsgi.py
import eventlet

# 1. Aplicamos el parche general de eventlet ANTES que nada.
eventlet.monkey_patch()

# 2. Aplicamos el parche específico para psycopg2.
#    Esto es lo que nos faltaba y lo que resuelve el conflicto.
try:
    from psycogreen.eventlet import patch_psycopg
    patch_psycopg()
    print("psycogreen patch applied successfully.")
except ImportError:
    print("psycogreen not found, database connections might block.")

# 3. Ahora, con el entorno completamente parcheado, creamos la app.
from app import create_app

app, socketio = create_app()