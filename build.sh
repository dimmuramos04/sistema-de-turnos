#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Instalando dependencias..."
pip install -r requirements.txt

# LÍNEA CLAVE: Le decimos a los comandos 'flask' que usen la fábrica de
# la aplicación directamente, ignorando el wsgi.py con los parches.
export FLASK_APP="app:create_app"

# Forzar un reinicio completo de la base de datos para limpiar el estado anterior
echo "Limpiando y reiniciando la base de datos..."
flask db downgrade base

echo "Aplicando todas las migraciones desde cero..."
flask db upgrade

echo "Poblando la base de datos con datos iniciales..."
flask seed

echo "Build finalizado correctamente."