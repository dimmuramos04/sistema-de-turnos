from app import app, db, Servicio

servicios_iniciales = [
    {'nombre': 'Matrícula', 'prefijo': 'M', 'color': '#000000'},
    {'nombre': 'Bienestar Estudiantil', 'prefijo': 'B', 'color': '#CF142B'}
]

with app.app_context():
    for s in servicios_iniciales:
        servicio_existente = Servicio.query.filter_by(nombre_modulo=s['nombre']).first()
        if not servicio_existente:
            nuevo_servicio = Servicio(
                nombre_modulo=s['nombre'], 
                prefijo_ticket=s['prefijo'],
                color_hex=s['color']
            )
            db.session.add(nuevo_servicio)
            print(f"Servicio '{s['nombre']}' creado con prefijo '{s['prefijo']}' y color '{s['color']}'.")
            
    db.session.commit()
    print("Base de datos poblada con los servicios iniciales.")