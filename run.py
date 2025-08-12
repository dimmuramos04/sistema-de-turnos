# Este es el contenido de run.py

import eventlet
eventlet.monkey_patch()

# Importamos la app y socketio desde nuestro archivo app
from app import app, socketio

if __name__ == '__main__':
    # Usamos socketio.run para iniciar el servidor
    socketio.run(app, debug=True)