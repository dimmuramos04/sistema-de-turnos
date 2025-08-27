# wsgi.py

import eventlet

# Aseguramos que el monkey_patch se ejecute ANTES que cualquier otra cosa.
eventlet.monkey_patch()

# Ahora importamos la aplicación que Gunicorn necesita.
from app import app

# Flask-SocketIO se encarga de envolver 'app', por lo que solo necesitamos
# asegurarnos de que el objeto 'app' esté disponible.
# Gunicorn buscará la variable 'app' en este archivo.