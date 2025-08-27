# wsgi.py
from app import create_app

# La función create_app ahora nos devuelve la app ya configurada.
app, socketio = create_app()