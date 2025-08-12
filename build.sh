#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

echo "Aplicando migraciones de la base de datos..."
flask db upgrade
echo "Migraciones aplicadas."
echo "Build finalizado."