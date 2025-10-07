from app import create_app, db, Usuario

app = create_app()

with app.app_context():
    print("--- Creación de Nuevo Usuario ---")
    nombre = input("Nombre del funcionario: ")
    password = input("Contraseña: ")
    rol = input("Rol (registrador o staff): ")

    # Valores por defecto
    modulo = None
    meson = None

    # Solo pide módulo y mesón si el rol es 'staff'
    if rol == 'staff':
        modulo = input("Módulo asignado (ej: Matrícula, Bienestar Estudiantil): ")
        meson = int(input("Número de mesón/puesto: "))

    if Usuario.query.filter_by(nombre_funcionario=nombre).first():
        print("Error: ¡Ese nombre de funcionario ya existe!")
    else:
        nuevo_usuario = Usuario(
            nombre_funcionario=nombre, 
            rol=rol, 
            modulo_asignado=modulo,
            numero_meson=meson
        )
        # Se asigna la contraseña a través del setter para que se guarde el hash
        nuevo_usuario.password = password
        
        db.session.add(nuevo_usuario)
        db.session.commit()
        print(f"¡Usuario '{nombre}' con rol '{rol}' creado exitosamente!")
