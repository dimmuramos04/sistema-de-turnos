#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Instalando dependencias..."
pip install -r requirements.txt

echo "Forzando reinicio de migraciones..."
flask db downgrade base
echo "Aplicando migraciones de la base de datos..."
flask db upgrade

echo "Poblando la base de datos con datos iniciales..."
flask seed

echo "Build finalizado correctamente."