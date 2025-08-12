#!/usr/bin/env bash
# exit on error
set -o errexit

# Le damos permiso de ejecución al script
chmod +x build.sh

pip install -r requirements.txt

echo "Creando tablas de la base de datos..."
python create_db.py
echo "Poblando la base de datos con datos iniciales..."
python seed_db.py
echo "Build finalizado."