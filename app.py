#app.py

import os

from flask import Flask, config, render_template, request, redirect, url_for, flash, session, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, aliased
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Optional
from flask_wtf.csrf import CSRFProtect
from functools import wraps
from datetime import datetime, date, timedelta
from flask_socketio import SocketIO, join_room
from flask_migrate import Migrate
import sentry_sdk
from logging.handlers import RotatingFileHandler
import logging
import io
import csv
import pytz
import qrcode
import base64
from dotenv import load_dotenv

# --- INICIALIZACIÓN DE EXTENSIONES (SIN APP) ---
# Creamos las instancias de las extensiones aquí, pero sin inicializarlas.
# Se inicializarán dentro de la función create_app.
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
socketio = SocketIO()

# Definimos la zona horaria globalmente para usarla en los modelos
zona_horaria_chile = pytz.timezone('America/Santiago')

# --- MODELOS DE LA BASE DE DATOS ---
# Los modelos pueden definirse aquí sin problemas.
class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nombre_funcionario = db.Column(db.String(100), nullable=False, unique=True)
    password_hash = db.Column(db.String(256))
    rol = db.Column(db.String(50), nullable=False)
    modulo_asignado = db.Column(db.String(100), nullable=True)
    numero_meson = db.Column(db.Integer, nullable=True)
    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Servicio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre_modulo = db.Column(db.String(100), nullable=False, unique=True)
    prefijo_ticket = db.Column(db.String(3), nullable=False, unique=True)
    letra_actual = db.Column(db.String(1), default='A', nullable=False)
    numero_actual = db.Column(db.Integer, default=0)
    color_hex = db.Column(db.String(7), nullable=False, default='#000000')
    visible_en_pantalla = db.Column(db.Boolean, default=True, nullable=False)

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_ticket = db.Column(db.String(10), nullable=False, unique=False)
    rut_cliente = db.Column(db.String(15), nullable=False)
    modulo_solicitado = db.Column(db.String(100), nullable=False)
    estado = db.Column(db.String(20), default='en_espera')
    hora_registro = db.Column(db.DateTime, nullable=False)
    hora_llamado = db.Column(db.DateTime, nullable=True)
    hora_finalizado = db.Column(db.DateTime, nullable=True)
    atendido_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    registrado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    registrador = relationship('Usuario', foreign_keys=[registrado_por_id])
    es_preferencial = db.Column(db.Boolean, default=False)
    servicio_id = db.Column(db.Integer, db.ForeignKey('servicio.id'), nullable=False)
    servicio = relationship('Servicio')
    numero_meson = db.Column(db.Integer, nullable=True)

    def get_hora_chile(self, fecha):
        """Convierte una fecha UTC (o naive) a hora de Chile."""
        if not fecha:
            return None
        if fecha.tzinfo is None:
            # Si es naive, asumimos que YA ES hora de Chile (porque así se guarda en la DB)
            return zona_horaria_chile.localize(fecha)
        return fecha.astimezone(zona_horaria_chile)

# --- FORMULARIOS ---
# Los formularios también pueden definirse aquí.
class LoginForm(FlaskForm):
    username = StringField('Nombre de Funcionario', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Ingresar')

class RegistroForm(FlaskForm):
    rut = StringField('RUT del Solicitante', validators=[DataRequired()])
    servicio = SelectField('Servicio Solicitado', coerce=int, validators=[DataRequired()])
    es_preferencial = BooleanField('¿Atención Preferencial?')
    submit = SubmitField('Registrar y Generar Número')

class AccionForm(FlaskForm):
    submit = SubmitField()

class CrearUsuarioForm(FlaskForm):
    username = StringField('Nombre de Funcionario', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    rol = SelectField('Rol', choices=[('staff', 'Staff (Atención)'), ('registrador', 'Registrador'), ('admin', 'Administrador')], validators=[DataRequired()])
    modulo_asignado = SelectField('Módulo Asignado', coerce=int, validators=[Optional()])
    numero_meson = IntegerField('Número de Mesón (solo para rol staff)', validators=[Optional()])
    submit = SubmitField('Crear Usuario')

class EditarUsuarioForm(FlaskForm):
    username = StringField('Nombre de Funcionario', validators=[DataRequired()])
    password = PasswordField('Nueva Contraseña (dejar en blanco para no cambiar)')
    rol = SelectField('Rol', choices=[('staff', 'Staff (Atención)'), ('registrador', 'Registrador'), ('admin', 'Administrador')], validators=[DataRequired()])
    modulo_asignado = SelectField('Módulo Asignado', coerce=int, validators=[Optional()])
    numero_meson = IntegerField('Número de Mesón (solo para rol staff)', validators=[Optional()])
    submit = SubmitField('Actualizar Usuario')

class CrearServicioForm(FlaskForm):
    nombre_modulo = StringField('Nombre del Módulo', validators=[DataRequired()])
    prefijo_ticket = StringField('Prefijo del Ticket (1-3 letras)', validators=[DataRequired()])
    color_hex = StringField('Color (código hexadecimal, ej: #000000)', validators=[DataRequired()])
    visible_en_pantalla = BooleanField('¿Mostrar en Pantalla Pública?')
    submit = SubmitField('Crear Servicio')

class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('Contraseña Actual', validators=[DataRequired()])
    new_password = PasswordField('Nueva Contraseña', validators=[DataRequired()])
    confirm_password = PasswordField('Confirmar Nueva Contraseña', validators=[DataRequired()])
    submit = SubmitField('Cambiar Contraseña')

# Configuración del sistema (por ejemplo, si está abierto o cerrado)
class ConfigSystem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(50), nullable=False) # 'true' o 'false'

# Función auxiliar para verificar si está abierto
def sistema_esta_abierto():
    config = ConfigSystem.query.filter_by(key='sistema_abierto').first()
    # Si no existe la config, asumimos que está abierto por defecto
    if not config:
        return True
    return config.value == 'true'


# --- DECORADORES ---
def check_sistema_abierto(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Si eres admin, pasas siempre
        if current_user.is_authenticated and current_user.rol == 'admin':
            return f(*args, **kwargs)
        
        # Si no eres admin, verificamos el interruptor
        if not sistema_esta_abierto():
            flash('El sistema está cerrado por el administrador. Vuelva mañana.', 'error')
            return redirect(url_for('login')) # O a una página de "Cerrado"
            
        return f(*args, **kwargs)
    return decorated_function

# Función auxiliar para obtener datos del historial
def _get_historial_data():
    """Busca los últimos 4 tickets para el historial y los serializa."""
    historial = Ticket.query.filter(Ticket.estado.in_(['en_atencion', 'finalizado'])) \
                        .order_by(Ticket.hora_llamado.desc()).limit(4).all()
    historial_data = [{
        'numero_ticket': t.numero_ticket,
        'modulo_solicitado': t.modulo_solicitado,
        'numero_meson': t.numero_meson,
        'color_hex': t.servicio.color_hex
    } for t in historial]
    return historial_data


# --- FUNCIÓN DE FÁBRICA DE LA APLICACIÓN ---
def create_app():
    load_dotenv()
    app = Flask(__name__)

    # Aplicamos el proxy fix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # --- CONFIGURACIÓN DE LA APLICACIÓN ---
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12) # La sesión durará 12 horas
    
    # ¡Importante! Asegurarse de que DEBUG esté desactivado en producción.
    is_production = os.getenv('FLASK_ENV') == 'production'
    app.config['DEBUG'] = not is_production

    if is_production:
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
        # Configuración de cookies seguras para producción
        app.config.update(
            SESSION_COOKIE_SECURE=True,      # Solo enviar cookies sobre HTTPS
            SESSION_COOKIE_HTTPONLY=True,    # Previene acceso desde JavaScript
            SESSION_COOKIE_SAMESITE='Lax',   # Protección contra ataques CSRF
        )
    else:
        basedir = os.path.abspath(os.path.dirname(__file__))
        db_path = os.path.join(basedir, "instance", "database.db")
        os.makedirs(os.path.join(basedir, "instance"), exist_ok=True)
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
        
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # --- INICIALIZACIÓN DE EXTENSIONES CON LA APP ---
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'login' # Si @login_required falla, ir aquí
    login_manager.login_message = "Su sesión ha expirado. Por favor ingrese nuevamente."
    login_manager.login_message_category = "error"
    csrf.init_app(app)
    # Pasamos el async_mode='eventlet' para producción.
    socketio.init_app(app, async_mode='eventlet', cors_allowed_origins="*")


    # --- CONFIGURACIÓN DE SENTRY Y LOGGING ---
    sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"), traces_sample_rate=1.0)
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/sistema_turnos.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Sistema de Turnos iniciado')


    def role_required(role):
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if not current_user.is_authenticated:
                    flash("Su sesión ha expirado. Por favor ingrese nuevamente.", "error")
                    return redirect(url_for('login'))
                
                if current_user.rol != role:
                    flash(f"Acceso denegado. Se requiere el rol de '{role}'.", "error")
                    return redirect(url_for('pantalla_publica'))
                return f(*args, **kwargs)
            return decorated_function
        return decorator

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Usuario, int(user_id))

    @app.route('/')
    def pantalla_publica():
        # Obtenemos los últimos 2 tickets que estén "en atención"
        llamados_actuales = Ticket.query.filter_by(estado='en_atencion').order_by(Ticket.hora_llamado.desc()).limit(2).all()

        # Buscamos los últimos 4 tickets finalizados o en atención para el historial
        historial = Ticket.query.filter(Ticket.estado.in_(['en_atencion', 'finalizado']))\
                            .order_by(Ticket.hora_llamado.desc()).limit(4).all()

        return render_template(
            'public_display.html',
            llamados=llamados_actuales,
            historial=historial
        )

    @app.route('/registro', methods=['GET', 'POST'])
    @login_required
    @role_required('registrador')
    @check_sistema_abierto
    def registro():
        form = RegistroForm()
        # Llenamos dinámicamente las opciones del menú desplegable
        form.servicio.choices = [(s.id, s.nombre_modulo) for s in Servicio.query.all()]

        if form.validate_on_submit():
            rut_cliente = form.rut.data
            servicio_id = form.servicio.data
            
            intentos = 0
            max_intentos = 3 # Intentará 3 veces antes de rendirse
            
            while intentos < max_intentos:
                try:
                    # Importante: Buscamos el servicio DENTRO del loop para tener el dato fresco
                    servicio = db.session.get(Servicio, servicio_id)
                
                    # --- Lógica para generar el número ---
                    letra_para_ticket = servicio.letra_actual
                    numero_para_ticket = servicio.numero_actual
                    siguiente_numero = numero_para_ticket + 1
                    siguiente_letra = letra_para_ticket
                    if siguiente_numero > 99:
                        siguiente_numero = 0
                        siguiente_letra = chr(ord(letra_para_ticket) + 1)
                        if siguiente_letra > 'E':
                            siguiente_letra = 'A'
                
                    numero_ticket_str = f"{servicio.prefijo_ticket}-{letra_para_ticket}{numero_para_ticket:02d}"
                
                    # Actualizamos el servicio
                    servicio.numero_actual = siguiente_numero
                    servicio.letra_actual = siguiente_letra
                
                    nuevo_ticket = Ticket(
                        numero_ticket=numero_ticket_str,
                        rut_cliente=rut_cliente,
                        modulo_solicitado=servicio.nombre_modulo,
                        servicio_id=servicio.id,
                        hora_registro=datetime.now(zona_horaria_chile).replace(tzinfo=None),
                        es_preferencial=form.es_preferencial.data,
                        registrado_por_id=current_user.id
                    )
                
                    db.session.add(nuevo_ticket)
                    db.session.commit() # AQUÍ es donde podría chocar

                    # --- SI LLEGA AQUÍ, TODO SALIÓ BIEN ---
                    
                    # Emitimos evento para paneles staff
                    datos_ticket = {
                        'numero_ticket': numero_ticket_str,
                        'modulo_solicitado': servicio.nombre_modulo,
                        'color_hex': servicio.color_hex,
                        'hora_registro': nuevo_ticket.get_hora_chile(nuevo_ticket.hora_registro).isoformat()
                    }
                    socketio.emit('nuevo_ticket_registrado', datos_ticket, room=servicio.nombre_modulo)

                    # --- 🔴 NUEVO BLOQUE: GENERACIÓN DE QR ---
                    # 1. Creamos el link (asegúrate de haber creado la ruta 'estado_ticket_movil' en app.py)
                    url_destino = url_for('estado_ticket_movil', ticket_id=nuevo_ticket.id, _external=True)
                    
                    # 2. Generamos la imagen en memoria
                    img = qrcode.make(url_destino)
                    buffer = io.BytesIO()
                    img.save(buffer, format="PNG")
                    qr_b64 = base64.b64encode(buffer.getvalue()).decode()

                    #flash(f"¡Registro Exitoso! Número Asignado: {numero_ticket_str}", "success")
                    return render_template('registro.html', 
                                         form=form, 
                                         ticket_exito=nuevo_ticket, # Pasamos el ticket
                                         qr_code=qr_b64)            # Pasamos el QR
                
                except IntegrityError:
                    # ¡CHOQUE DETECTADO!
                    db.session.rollback() # Cancelamos la transacción fallida
                    intentos += 1
                    # El bucle se repite, vuelve a leer el servicio (que ya tendrá el número actualizado por el otro usuario) y prueba de nuevo.
                    continue

            # Si sale del while es que falló 3 veces seguidas (muy raro)
            flash("Error de concurrencia: El sistema está muy ocupado, intente nuevamente.", "error")

        return render_template('registro.html', form=form)


    # En app.py

    @app.route('/seguimiento/<int:ticket_id>')
    def estado_ticket_movil(ticket_id):
        ticket = db.session.get(Ticket, ticket_id)

        if not ticket:
            return "Ticket no encontrado", 404
        # Lógica de optimización:
        # Si el ticket ya finalizó, mostramos una vista estática (sin sockets)
        if ticket.estado == 'finalizado':
            return render_template('mobile_view.html', ticket=ticket, espera=0, finalizado=True)

        # Si está vivo, calculamos cuántos hay antes que él en SU servicio
        tickets_antes = Ticket.query.filter(
            Ticket.servicio_id == ticket.servicio_id,
            Ticket.estado == 'en_espera',
            Ticket.id < ticket.id  # IDs menores significan que llegaron antes
        ).count()

        return render_template('mobile_view.html', ticket=ticket, espera=tickets_antes, finalizado=False)
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        form = LoginForm()
        if form.validate_on_submit():
            nombre = form.username.data
            password = form.password.data
            usuario = Usuario.query.filter_by(nombre_funcionario=nombre).first()

            if usuario and usuario.check_password(password):
                login_user(usuario)
                session.permanent = True # Activa la duración de 12 horas configurada arriba

                # --- REGISTRO DE INICIO DE SESIÓN ---
                app.logger.info(f"Inicio de sesión exitoso: Usuario '{usuario.nombre_funcionario}' (Rol: {usuario.rol})")
                # ------------------------------------

                # -- LÓGICA DE REDIRECCIÓN POR ROL ---
                if usuario.rol == 'admin':
                    return redirect(url_for('admin_dashboard'))
                if usuario.rol == 'staff':
                    return redirect(url_for('panel'))
                elif usuario.rol == 'registrador':
                    return redirect(url_for('registro'))
                else:
                    # Si en el futuro hay más roles, los mandamos a la página principal
                    return redirect(url_for('pantalla_publica'))
                # ------------------------------------
            else:
                flash('Usuario o contraseña incorrectos.', 'error')
                return redirect(url_for('login'))

        return render_template('login.html', form=form)

    @app.route('/admin')
    @login_required
    @role_required('admin')
    def admin_dashboard():
        # --- CÁLCULO DE ESTADÍSTICAS ---
        hoy = datetime.now(zona_horaria_chile).date()
    
        tickets_hoy = Ticket.query.filter(func.date(Ticket.hora_registro) == hoy).count()
        tickets_en_espera = Ticket.query.filter_by(estado='en_espera').count()
        tickets_en_atencion = Ticket.query.filter_by(estado='en_atencion').count()
        tickets_finalizados_hoy = Ticket.query.filter(
            func.date(Ticket.hora_registro) == hoy,
            Ticket.estado == 'finalizado'
        ).count()

        # --- CONSULTA PARA GRÁFICO DE DONA (TICKETS POR SERVICIO) ---
        datos_grafico_dona_raw = db.session.query(
            Servicio.nombre_modulo, 
            Servicio.color_hex,
            func.count(Ticket.id)
        ).join(Ticket, Servicio.id == Ticket.servicio_id).group_by(
            Servicio.nombre_modulo, 
            Servicio.color_hex
        ).all()
        chart_data_dona = [list(row) for row in datos_grafico_dona_raw]

        # --- CONSULTA PARA GRÁFICO DE LÍNEAS (TICKETS POR HORA) ---
        tickets_por_hora_raw = db.session.query(
            func.extract('hour', Ticket.hora_registro).label('hora'),
            func.count(Ticket.id).label('cantidad')
        ).filter(func.date(Ticket.hora_registro) == hoy).group_by('hora').order_by('hora').all()

        datos_grafico_lineas = {f"{h:02d}": 0 for h in range(8, 19)} # Horario de 8am a 6pm
        for row in tickets_por_hora_raw:
            datos_grafico_lineas[f"{int(row.hora):02d}"] = row.cantidad

        # --- CÁLCULO DE PROMEDIO DE ESPERA ---
        # Buscamos tickets atendidos hoy que tengan hora de llamado
        tickets_atendidos_hoy_data = Ticket.query.filter(
            func.date(Ticket.hora_registro) == hoy,
            Ticket.hora_llamado.isnot(None)
        ).all()

        promedio_espera_str = "0 min"
        if tickets_atendidos_hoy_data:
            total_segundos = 0
            count = 0
            for t in tickets_atendidos_hoy_data:
                # Tiempo espera = Hora Llamado - Hora Registro
                delta = t.hora_llamado - t.hora_registro
                total_segundos += delta.total_seconds()
                count += 1
            
            if count > 0:
                promedio_minutos = int((total_segundos / count) / 60)
                promedio_espera_str = f"{promedio_minutos} min"
        # -----------------------------------------------------------------
    
        return render_template(
            'admin_dashboard.html', 
            tickets_hoy=tickets_hoy,
            tickets_en_espera=tickets_en_espera,
            tickets_en_atencion=tickets_en_atencion,
            tickets_finalizados_hoy=tickets_finalizados_hoy,
            promedio_espera=promedio_espera_str,
            chart_data_dona=chart_data_dona,
            chart_data_lineas=datos_grafico_lineas,
            sistema_abierto=sistema_esta_abierto()
        )

    @app.route('/admin/reporte/tickets')
    @login_required
    @role_required('admin')
    def descargar_reporte_tickets():
        # Creamos alias para distinguir al Registrador del Atendedor
        Registrador = aliased(Usuario)
        Atendedor = aliased(Usuario)

        # Consulta avanzada uniendo la tabla Usuario dos veces
        tickets_query = db.session.query(Ticket, Registrador, Atendedor).outerjoin(
            Registrador, Ticket.registrado_por_id == Registrador.id
        ).outerjoin(
            Atendedor, Ticket.atendido_por_id == Atendedor.id
        ).order_by(Ticket.hora_registro.asc()).all()

        output = io.StringIO()
        writer = csv.writer(output)

        # Agregamos la columna 'Registrado Por' al encabezado
        writer.writerow([
            'ID Ticket', 'Numero Ticket', 'RUT Cliente', 'Modulo Solicitado', 'Estado', 
            'Hora Registro', 'Hora Llamado', 'Hora Finalizado', 
            'Registrado Por', 'Atendido Por', 'Numero Meson'
        ])

        for ticket, registrador, atendedor in tickets_query:
            # Obtenemos los nombres o dejamos string vacío si no existe
            nombre_registrador = registrador.nombre_funcionario if registrador else 'Sistema/Antiguo'
            nombre_atendedor = atendedor.nombre_funcionario if atendedor else ''
        
            h_reg = ticket.get_hora_chile(ticket.hora_registro)
            h_llam = ticket.get_hora_chile(ticket.hora_llamado)
            h_fin = ticket.get_hora_chile(ticket.hora_finalizado)
    
            writer.writerow([
                ticket.id, 
                ticket.numero_ticket, 
                ticket.rut_cliente, 
                ticket.modulo_solicitado,
                ticket.estado, 
                h_reg.strftime('%Y-%m-%d %H:%M:%S') if h_reg else '',
                h_llam.strftime('%Y-%m-%d %H:%M:%S') if h_llam else '',
                h_fin.strftime('%Y-%m-%d %H:%M:%S') if h_fin else '',
                nombre_registrador,  # <--- Nuevo dato en el CSV
                nombre_atendedor,
                ticket.numero_meson
            ])

        output.seek(0)
        final_csv_string = '\ufeff' + output.getvalue()

        return Response(
            final_csv_string.encode('utf-8'),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=reporte_tickets_completo.csv"}
        )

    @app.route('/admin/crear_usuario', methods=['GET', 'POST'])
    @login_required
    @role_required('admin')
    def crear_usuario():
        form = CrearUsuarioForm()
        # Llenamos dinámicamente las opciones del menú desplegable
        form.modulo_asignado.choices = [(s.id, s.nombre_modulo) for s in Servicio.query.all()]
        form.modulo_asignado.choices.insert(0, (0, 'Ninguno'))

        if form.validate_on_submit():
            usuario_existente = Usuario.query.filter_by(nombre_funcionario=form.username.data).first()
            if usuario_existente:
                flash('El nombre de funcionario ya existe.', 'error')
            else:
                nuevo_usuario = Usuario(
                    nombre_funcionario=form.username.data,
                    rol=form.rol.data
                )
                nuevo_usuario.password = form.password.data

                if nuevo_usuario.rol == 'staff':
                    # Obtenemos el nombre del servicio a partir del ID seleccionado
                    servicio_seleccionado = db.session.get(Servicio, form.modulo_asignado.data)
                    if servicio_seleccionado:
                        nuevo_usuario.modulo_asignado = servicio_seleccionado.nombre_modulo
                
                    if form.numero_meson.data is not None:
                        nuevo_usuario.numero_meson = form.numero_meson.data

                db.session.add(nuevo_usuario)
                db.session.commit()
                flash('Nuevo usuario creado exitosamente.', 'success')
                return redirect(url_for('gestionar_usuarios'))
            
        return render_template('crear_usuario.html', form=form)

    @app.route('/admin/eliminar_usuario/<int:user_id>', methods=['POST'])
    @login_required
    @role_required('admin')
    def eliminar_usuario(user_id):
        # Nos aseguramos de que el admin no se pueda eliminar a sí mismo
        if user_id == current_user.id:
            flash('No puedes eliminar tu propia cuenta de administrador.', 'error')
            return redirect(url_for('gestionar_usuarios'))

        usuario_a_eliminar = db.session.get(Usuario, user_id)
    
        if usuario_a_eliminar:
            db.session.delete(usuario_a_eliminar)
            db.session.commit()
            flash('Usuario eliminado exitosamente.', 'success')
        else:
            flash('El usuario no fue encontrado.', 'error')

        return redirect(url_for('gestionar_usuarios'))

    @app.route('/admin/editar_usuario/<int:user_id>', methods=['GET', 'POST'])
    @login_required
    @role_required('admin')
    def editar_usuario(user_id):
        usuario_a_editar = db.session.get(Usuario, user_id)
        if not usuario_a_editar:
            flash('Usuario no encontrado.', 'error')
            return redirect(url_for('gestionar_usuarios'))
    
        form = EditarUsuarioForm(obj=usuario_a_editar)

        # --- LÓGICA PARA EL MENÚ DESPLEGABLE ---
        # Obtenemos todos los servicios y los añadimos como opciones
        form.modulo_asignado.choices = [(s.id, s.nombre_modulo) for s in Servicio.query.all()]
        # Añadimos una opción para "Ninguno"
        form.modulo_asignado.choices.insert(0, (0, 'Ninguno'))
    
        # Seleccionamos el módulo actual del usuario
        if usuario_a_editar.modulo_asignado:
            servicio_actual = Servicio.query.filter_by(nombre_modulo=usuario_a_editar.modulo_asignado).first()
            if servicio_actual:
                form.modulo_asignado.data = servicio_actual.id
        # ------------------------------------

        if form.validate_on_submit():
            # Actualizamos los datos
            usuario_a_editar.nombre_funcionario = form.username.data
            usuario_a_editar.rol = form.rol.data
        
            # Si el campo de contraseña no está vacío, la actualizamos
            if form.password.data:
                usuario_a_editar.password = form.password.data
        
            if usuario_a_editar.rol == 'staff':
                servicio_seleccionado = db.session.get(Servicio, form.modulo_asignado.data)
                if servicio_seleccionado:
                    usuario_a_editar.modulo_asignado = servicio_seleccionado.nombre_modulo
                else:
                    usuario_a_editar.modulo_asignado = None

                if form.numero_meson.data is not None:
                    usuario_a_editar.numero_meson = form.numero_meson.data
            else:
                usuario_a_editar.modulo_asignado = None
                usuario_a_editar.numero_meson = None

            db.session.commit()
            flash('Usuario actualizado exitosamente.', 'success')
            return redirect(url_for('gestionar_usuarios'))
        # Renombramos el campo 'username' para que no choque
        form.username.data = usuario_a_editar.nombre_funcionario
        return render_template('editar_usuario.html', form=form, usuario=usuario_a_editar)

    @app.route('/admin/usuarios')
    @login_required
    @role_required('admin')
    def gestionar_usuarios():
        # Esta función solo se preocupa de buscar y mostrar los usuarios
        usuarios = Usuario.query.all()
        return render_template('gestionar_usuarios.html', usuarios=usuarios)

    @app.route('/admin/reset_servicio/<int:service_id>', methods=['POST'])
    @login_required
    @role_required('admin')
    def reset_servicio(service_id):
        servicio = db.session.get(Servicio, service_id)
        if servicio:
            # 1. ELIMINAMOS los tickets antiguos de este servicio
            # Esto es necesario para liberar los números (ej: A00) y que no dé error de duplicado.
            Ticket.query.filter_by(servicio_id=service_id).delete()
            
            # 2. REINICIAMOS los contadores a A - 0
            servicio.letra_actual = 'A'
            servicio.numero_actual = 0
            
            db.session.commit()
            flash(f'Historial borrado y contador reiniciado para "{servicio.nombre_modulo}".', 'success')
        else:
            flash('Servicio no encontrado.', 'error')
        return redirect(url_for('gestionar_servicios'))

    @app.route('/admin/servicios')
    @login_required
    @role_required('admin')
    def gestionar_servicios():
        servicios = Servicio.query.all()
        return render_template('gestionar_servicios.html', servicios=servicios)

    @app.route('/admin/crear_servicio', methods=['GET', 'POST'])
    @login_required
    @role_required('admin')
    def crear_servicio():
        form = CrearServicioForm()
        if form.validate_on_submit():
            # Verificamos que el nombre y el prefijo no existan ya
            servicio_existente = Servicio.query.filter(
                (Servicio.nombre_modulo == form.nombre_modulo.data) | 
                (Servicio.prefijo_ticket == form.prefijo_ticket.data)
            ).first()
        
            if servicio_existente:
                flash('Ya existe un servicio con ese nombre o prefijo.', 'error')
            else:
                nuevo_servicio = Servicio(
                    nombre_modulo=form.nombre_modulo.data,
                    prefijo_ticket=form.prefijo_ticket.data,
                    color_hex=form.color_hex.data,
                    visible_en_pantalla=form.visible_en_pantalla.data
                )
                db.session.add(nuevo_servicio)
                db.session.commit()
                flash('Nuevo servicio creado exitosamente.', 'success')
                return redirect(url_for('gestionar_servicios'))
            
        return render_template('crear_servicio.html', form=form)

    @app.route('/admin/editar_servicio/<int:service_id>', methods=['GET', 'POST'])
    @login_required
    @role_required('admin')
    def editar_servicio(service_id):
        servicio_a_editar = db.session.get(Servicio, service_id)
        if not servicio_a_editar:
            flash('Servicio no encontrado.', 'error')
            return redirect(url_for('gestionar_servicios'))

        # Reutilizamos el formulario de creación, pasándole el objeto a editar
        form = CrearServicioForm(obj=servicio_a_editar)
        # Renombramos el texto del botón
        form.submit.label.text = 'Actualizar Servicio'

        if form.validate_on_submit():
            # Actualizamos los datos del objeto con los datos del formulario
            servicio_a_editar.nombre_modulo = form.nombre_modulo.data
            servicio_a_editar.prefijo_ticket = form.prefijo_ticket.data
            servicio_a_editar.color_hex = form.color_hex.data
            servicio_a_editar.visible_en_pantalla = form.visible_en_pantalla.data
        
            db.session.commit()
            flash('Servicio actualizado exitosamente.', 'success')
            return redirect(url_for('gestionar_servicios'))

        return render_template('editar_servicio.html', form=form, servicio=servicio_a_editar)

    @app.route('/admin/eliminar_servicio/<int:service_id>', methods=['POST'])
    @login_required
    @role_required('admin')
    def eliminar_servicio(service_id):
        servicio_a_eliminar = db.session.get(Servicio, service_id)
    
        if not servicio_a_eliminar:
            flash('Servicio no encontrado.', 'error')
            return redirect(url_for('gestionar_servicios'))

        # Verificamos si existen tickets asociados a este servicio
        tickets_asociados = Ticket.query.filter_by(servicio_id=service_id).first()
    
        if tickets_asociados:
            flash('No se puede eliminar este servicio porque tiene tickets históricos asociados.', 'error')
        else:
            db.session.delete(servicio_a_eliminar)
            db.session.commit()
            flash('Servicio eliminado exitosamente.', 'success')

        return redirect(url_for('gestionar_servicios'))

    @app.route('/panel')
    @login_required
    @role_required('staff')
    @check_sistema_abierto
    def panel():
        # Busca los tickets en espera para el módulo del funcionario
        tickets_en_espera = Ticket.query.filter_by(
            modulo_solicitado=current_user.modulo_asignado,
            estado='en_espera'
        ).order_by(Ticket.hora_registro.asc()).all()

        # Busca si este funcionario tiene un ticket "en atencion"
        ticket_en_atencion = Ticket.query.filter_by(
            atendido_por_id=current_user.id,
            estado='en_atencion'
        ).first()

        form = AccionForm()

        return render_template(
            'panel.html', 
            tickets_en_espera=tickets_en_espera, 
            ticket_en_atencion=ticket_en_atencion,  # <-- Enviamos el ticket actual a la plantilla
            form=form
        )

    @app.route('/llamar-siguiente', methods=['POST'])
    @login_required
    @role_required('staff')
    @check_sistema_abierto
    def llamar_siguiente():
        # Bucle infinito que se rompe solo cuando logramos tomar un ticket o no hay nadie
        while True:
            # 1. Buscar el candidato más antiguo
            ticket_candidato = Ticket.query.filter_by(
                modulo_solicitado=current_user.modulo_asignado,
                estado='en_espera'
            ).order_by(
                Ticket.es_preferencial.desc(),
                Ticket.hora_registro.asc()
            ).first()

            if not ticket_candidato:
                flash("No hay más personas en espera.", "info")
                break # Salimos del bucle porque no hay nadie

            # 2. INTENTO DE RESERVA ATÓMICA (La Clave Mágica)
            # Intentamos actualizar el ticket SOLO SI su estado sigue siendo 'en_espera'.
            # Si alguien (Bea) nos ganó el clic hace 1 milisegundo, el estado ya será 'en_atencion'
            # y esta actualización afectará a 0 filas.
            filas_actualizadas = Ticket.query.filter(
                Ticket.id == ticket_candidato.id,
                Ticket.estado == 'en_espera'
            ).update({
                'estado': 'en_atencion',
                'hora_llamado': datetime.now(zona_horaria_chile).replace(tzinfo=None),
                'atendido_por_id': current_user.id,
                'numero_meson': current_user.numero_meson
            }, synchronize_session=False)

            db.session.commit()

            # 3. Verificamos si ganamos la carrera
            if filas_actualizadas > 0:
                # ¡Ganamos! Somos dueños del ticket, procedemos a notificar.
                
                # (Opcional) Limpiar ticket anterior si había uno colgado
                Ticket.query.filter(
                    Ticket.atendido_por_id == current_user.id,
                    Ticket.estado == 'en_atencion',
                    Ticket.id != ticket_candidato.id # Que no sea el que acabamos de tomar
                ).update({'estado': 'finalizado'})
                db.session.commit()

                # --- Notificación por WebSockets ---
                datos_llamado = {
                    'id_ticket': ticket_candidato.id,
                    'nombre_modulo': ticket_candidato.servicio.nombre_modulo,
                    'numero_ticket': ticket_candidato.numero_ticket,
                    'color_hex': ticket_candidato.servicio.color_hex,
                    'numero_meson': current_user.numero_meson,
                    'es_preferencial': ticket_candidato.es_preferencial,
                    'visible': ticket_candidato.servicio.visible_en_pantalla,
                    'es_rellamado': False
                }
                payload = {
                    'llamado': datos_llamado,
                    'historial': _get_historial_data()
                }
                
                socketio.emit('nuevo_llamado', payload, room='pantalla_publica')
                
                flash(f"Llamando al ticket {ticket_candidato.numero_ticket}", "success")
                break # ¡Misión cumplida, salimos del bucle!
            
            else:
                # Alguien nos ganó el clic justo en este milisegundo.
                # No hacemos nada y dejamos que el "while True" repita el proceso
                # para buscar el SIGUIENTE ticket disponible.
                continue

        return redirect(url_for('panel'))

    @app.route('/rellamar', methods=['POST'])
    @login_required
    @role_required('staff')
    @check_sistema_abierto
    def rellamar_ticket():
        ticket_id = request.form['ticket_id']
        ticket_a_rellamar = db.session.get(Ticket, ticket_id)

        # Verificación de seguridad
        if ticket_a_rellamar and ticket_a_rellamar.atendido_por_id == current_user.id:
            # Preparamos los mismos datos que en 'llamar_siguiente'
            datos_llamado = {
                'id_ticket': ticket_a_rellamar.id,
                'nombre_modulo': ticket_a_rellamar.servicio.nombre_modulo,
                'numero_ticket': ticket_a_rellamar.numero_ticket,
                'color_hex': ticket_a_rellamar.servicio.color_hex,
                'numero_meson': ticket_a_rellamar.numero_meson,
                'es_preferencial': ticket_a_rellamar.es_preferencial,
                'visible': ticket_a_rellamar.servicio.visible_en_pantalla,
                'es_rellamado': True

            }
            payload = {
                'llamado': datos_llamado,
                'historial': _get_historial_data()
            }
            # Reenviamos el evento a la pantalla pública
            
            socketio.emit('nuevo_llamado', payload, room='pantalla_publica')
            flash(f"Se ha vuelto a llamar al ticket {ticket_a_rellamar.numero_ticket}", "info")
        else:
            flash("Error al intentar volver a llamar al ticket.", "error")

        return redirect(url_for('panel'))

    @app.route('/finalizar', methods=['POST'])
    @login_required
    @role_required('staff')
    @check_sistema_abierto
    def finalizar_atencion():
        ticket_id = request.form['ticket_id']
        ticket_a_finalizar = db.session.get(Ticket, ticket_id)

        # Verificación de seguridad: nos aseguramos de que el ticket
        # realmente le pertenezca al funcionario que lo quiere finalizar.
        if ticket_a_finalizar and ticket_a_finalizar.atendido_por_id == current_user.id:
            ticket_a_finalizar.estado = 'finalizado'
            ticket_a_finalizar.hora_finalizado = datetime.now(zona_horaria_chile).replace(tzinfo=None)
            db.session.commit()
            # Emitimos evento para actualizar la pantalla principal
            payload = {
                'id_ticket': ticket_a_finalizar.id,
                'historial': _get_historial_data()
            }
            socketio.emit('atencion_finalizada', payload, room='pantalla_publica')
            flash(f"Atención del ticket {ticket_a_finalizar.numero_ticket} finalizada.", "info")
        else:
            flash("Error al intentar finalizar el ticket.", "error")

        return redirect(url_for('panel'))

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        session.clear()
        flash('Has cerrado sesión exitosamente.', 'success')
        return redirect(url_for('login'))

    @app.route('/cambiar-contrasena', methods=['GET', 'POST'])
    @login_required
    def cambiar_contrasena():
        form = ChangePasswordForm()
        if form.validate_on_submit():
            # 1. Verificar que la contraseña actual sea correcta
            if not current_user.check_password(form.old_password.data):
                flash('La contraseña actual es incorrecta.', 'error')
                return redirect(url_for('cambiar_contrasena'))
        
            # 2. Verificar que la nueva contraseña y la confirmación coincidan
            if form.new_password.data != form.confirm_password.data:
                flash('La nueva contraseña y la confirmación no coinciden.', 'error')
                return redirect(url_for('cambiar_contrasena'))
            
            # 3. Actualizar la contraseña
            current_user.password = form.new_password.data
            db.session.commit()
        
            flash('¡Tu contraseña ha sido actualizada exitosamente!', 'success')
            # Redirigimos al panel correspondiente según el rol del usuario
            if current_user.rol == 'staff':
                return redirect(url_for('panel'))
            elif current_user.rol == 'registrador':
                return redirect(url_for('registro'))
            elif current_user.rol == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('pantalla_publica'))

        return render_template('cambiar_contrasena.html', form=form)
    
    @app.route('/admin/toggle_sistema', methods=['POST'])
    @login_required
    @role_required('admin')
    def toggle_sistema():
        config = ConfigSystem.query.filter_by(key='sistema_abierto').first()
        if not config:
            config = ConfigSystem(key='sistema_abierto', value='true')
            db.session.add(config)
    
        # Cambiar estado (si es true pasa a false, y viceversa)
        nuevo_estado = 'false' if config.value == 'true' else 'true'
        config.value = nuevo_estado
        db.session.commit()
    
        estado_msg = "ABIERTO" if nuevo_estado == 'true' else "CERRADO"
        flash(f'Sistema {estado_msg} exitosamente.', 'success')
        return redirect(url_for('admin_dashboard'))
    # --- COMANDOS DE LA CLI ---
    # Movemos el comando de seed aquí para que esté asociado a la app.
    @app.cli.command("seed")
    def seed_command():
        """Puebla la base de datos con datos iniciales."""
        servicios_iniciales = [
            {'nombre': 'Matrícula', 'prefijo': 'M', 'color': '#000000'},
            {'nombre': 'Bienestar Estudiantil', 'prefijo': 'B', 'color': '#CF142B'}
        ]
        for s_data in servicios_iniciales:
            if not Servicio.query.filter_by(nombre_modulo=s_data['nombre']).first():
                nuevo_servicio = Servicio(nombre_modulo=s_data['nombre'], prefijo_ticket=s_data['prefijo'], color_hex=s_data['color'])
                db.session.add(nuevo_servicio)
                print(f"Servicio '{s_data['nombre']}' creado.")
        
        if not Usuario.query.filter_by(rol='admin').first():
            admin_user = os.getenv('ADMIN_USERNAME', 'admin')
            admin_pass = os.getenv('ADMIN_PASSWORD', 'admin')
            if admin_pass == 'admin':
                print("ADVERTENCIA: Usando contraseña de administrador por defecto.")
            admin = Usuario(nombre_funcionario=admin_user, rol='admin')
            admin.password = admin_pass
            db.session.add(admin)
            print(f"Usuario administrador '{admin_user}' creado.")

        db.session.commit()
        print("Seeding de datos completado.")
    
    # --- HANDLERS DE SOCKET.IO ---
    
    @socketio.on('connect')
    def handle_connect():
        # Para la pantalla pública, permitimos conexiones anónimas.
        # Para los paneles, podríamos requerir autenticación.
        # Por ahora, es seguro, pero si añadieras eventos que requieren login,
        # deberías validarlo aquí.
        # Ejemplo:
        # if not current_user.is_authenticated and request.sid in private_namespaces:
        #     disconnect()
        print('Cliente conectado')

    @socketio.on('join')
    def handle_join(data):
        room = data.get('room')
        if room:
            # 1. Permitir que CUALQUIERA (incluido staff) se una a la pantalla pública
            if room == 'pantalla_publica':
                join_room(room)
            # 2. Si es staff intentando unirse a otra sala, verificamos que sea su módulo
            elif current_user.is_authenticated and current_user.rol == 'staff':
                if room == current_user.modulo_asignado:
                    join_room(room)

    return app
