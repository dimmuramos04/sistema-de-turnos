#!/usr/bin/env bash
# exit on error
set -o errexit

# Instalar dependencias
pip install -r requirements.txt

# Crear directorios de migraciones
mkdir -p migrations/versions

# Inicializar migraciones si no existe
python -m flask db init || true

# Asegurarse de que no haya migraciones pendientes
python -m flask db stamp head || true
python -m flask db migrate || true
python -m flask db upgrade

# Crear tablas si no existen
python -c "from app import app, db; app.app_context().push(); db.create_all()"

# Poblar datos iniciales
python -m flask seed

# Iniciar la aplicación
exec gunicorn --bind 0.0.0.0:$PORT app:app