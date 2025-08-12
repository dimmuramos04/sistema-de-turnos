from app import app, db

# Este script ahora BORRA las tablas antiguas y LUEGO crea las nuevas.
with app.app_context():
    print("Borrando todas las tablas...")
    db.drop_all()
    print("Creando todas las tablas...")
    db.create_all()
    print("Base de datos y tablas creadas exitosamente.")