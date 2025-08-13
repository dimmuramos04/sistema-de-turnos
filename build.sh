#!/usr/bin/env bash
# exit on error
set -o errexit

# Instalar dependencias
pip install -r requirements.txt

# Inicializar la base de datos
python -m flask db upgrade

# Crear tablas y poblar datos iniciales
python -m flask seed

# Iniciar la aplicación
exec gunicorn --bind 0.0.0.0:$PORT app:app