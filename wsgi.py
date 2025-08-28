# wsgi.py
import eventlet

# 1. Aplicamos el parche general ANTES que cualquier otra cosa.
eventlet.monkey_patch()

# 2. Aplicamos el parche específico para la base de datos.
#    Esta es la pieza clave que resuelve el error del "lock".
try:
    from psycogreen.eventlet import patch_psycopg
    patch_psycopg()
    print("psycogreen patch applied successfully.")
except ImportError:
    print("psycogreen not found, database connections might block.")

# 3. Ahora, con el entorno completamente parcheado, creamos la app.
from app import create_app, socketio

app = create_app()