# run.py
import eventlet
eventlet.monkey_patch()

# Importamos la fábrica Y el objeto socketio por separado
from app import create_app, socketio

# Creamos la app
app = create_app()

if __name__ == '__main__':
    # Ejecutamos el servidor a través del objeto socketio
    socketio.run(app, debug=True)