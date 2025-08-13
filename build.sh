#!/usr/bin/env bash
# exit on error
set -o errexit

# Instalar dependencias
pip install -r requirements.txt

# Asegurarse de que no haya migraciones pendientes
python -m flask db stamp head
python -m flask db migrate
python -m flask db upgrade

# Crear tablas si no existen
python -c "from app import app, db; app.app_context().push(); db.create_all()"

# Poblar datos iniciales
python -m flask seed

# Iniciar la aplicación
exec gunicorn --bind 0.0.0.0:$PORT app:app