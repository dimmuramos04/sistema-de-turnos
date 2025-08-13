#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Instalando dependencias..."
pip install -r requirements.txt

# Forzar un reinicio completo de la base de datos para limpiar el estado anterior
echo "Limpiando y reiniciando la base de datos..."
flask db downgrade base

echo "Aplicando todas las migraciones desde cero..."
flask db upgrade

echo "Poblando la base de datos con datos iniciales..."
flask seed

echo "Build finalizado correctamente."