# run.py
from app import create_app

# Obtenemos la app y socketio de nuestra fábrica.
app, socketio = create_app()

if __name__ == '__main__':
    # Usamos socketio.run, que ya tiene el monkey_patching manejado por app.py
    socketio.run(app, debug=True)