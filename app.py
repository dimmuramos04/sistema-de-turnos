#app.py

import os

from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import func
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Optional
from flask_wtf.csrf import CSRFProtect
from functools import wraps
from datetime import datetime, date
from flask_socketio import SocketIO, join_room
from flask_migrate import Migrate
import sentry_sdk
from logging.handlers import RotatingFileHandler
import logging
import io
import csv
import pytz
from dotenv import load_dotenv

# --- INICIALIZACIÓN DE EXTENSIONES (SIN APP) ---
# Creamos las instancias de las extensiones aquí, pero sin inicializarlas.
# Se inicializarán dentro de la función create_app.
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
socketio = SocketIO()

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

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_ticket = db.Column(db.String(10), nullable=False, unique=True)
    rut_cliente = db.Column(db.String(15), nullable=False)
    modulo_solicitado = db.Column(db.String(100), nullable=False)
    estado = db.Column(db.String(20), default='en_espera')
    hora_registro = db.Column(db.DateTime, nullable=False)
    hora_llamado = db.Column(db.DateTime, nullable=True)
    hora_finalizado = db.Column(db.DateTime, nullable=True)
    atendido_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    servicio_id = db.Column(db.Integer, db.ForeignKey('servicio.id'), nullable=False)
    servicio = relationship('Servicio')
    numero_meson = db.Column(db.Integer, nullable=True)

# --- FORMULARIOS ---
# Los formularios también pueden definirse aquí.
class LoginForm(FlaskForm):
    username = StringField('Nombre de Funcionario', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Ingresar')

class RegistroForm(FlaskForm):
    rut = StringField('RUT del Solicitante', validators=[DataRequired()])
    servicio = SelectField('Servicio Solicitado', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Registrar y Generar Número')

class AccionForm(FlaskForm):
    submit = SubmitField()

class CrearUsuarioForm(FlaskForm):
    username = StringField('Nombre de Funcionario', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    rol = SelectField('Rol', choices=[('staff', 'Staff (Atención)'), ('registrador', 'Registrador')], validators=[DataRequired()])
    modulo_asignado = SelectField('Módulo Asignado', coerce=int, validators=[Optional()])
    numero_meson = StringField('Número de Mesón (solo para rol staff)')
    submit = SubmitField('Crear Usuario')

class EditarUsuarioForm(FlaskForm):
    username = StringField('Nombre de Funcionario', validators=[DataRequired()])
    password = PasswordField('Nueva Contraseña (dejar en blanco para no cambiar)')
    rol = SelectField('Rol', choices=[('staff', 'Staff (Atención)'), ('registrador', 'Registrador'), ('admin', 'Administrador')], validators=[DataRequired()])
    modulo_asignado = SelectField('Módulo Asignado', coerce=int, validators=[Optional()])
    numero_meson = StringField('Número de Mesón (solo para rol staff)')
    submit = SubmitField('Actualizar Usuario')

class CrearServicioForm(FlaskForm):
    nombre_modulo = StringField('Nombre del Módulo', validators=[DataRequired()])
    prefijo_ticket = StringField('Prefijo del Ticket (1-3 letras)', validators=[DataRequired()])
    color_hex = StringField('Color (código hexadecimal, ej: #000000)', validators=[DataRequired()])
    submit = SubmitField('Crear Servicio')

class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('Contraseña Actual', validators=[DataRequired()])
    new_password = PasswordField('Nueva Contraseña', validators=[DataRequired()])
    confirm_password = PasswordField('Confirmar Nueva Contraseña', validators=[DataRequired()])
    submit = SubmitField('Cambiar Contraseña')


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

    # --- DEFINICIONES DENTRO DEL CONTEXTO DE LA APP ---
    zona_horaria_chile = pytz.timezone('America/Santiago')

    def role_required(role):
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if not current_user.is_authenticated or current_user.rol != role:
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
    def registro():
        form = RegistroForm()
        # Llenamos dinámicamente las opciones del menú desplegable
        form.servicio.choices = [(s.id, s.nombre_modulo) for s in Servicio.query.all()]

        if form.validate_on_submit():
            rut_cliente = form.rut.data
            servicio_id = form.servicio.data
        
            servicio = db.session.get(Servicio, servicio_id)
        
            # --- Lógica para generar el número (la movemos aquí dentro) ---
            letra_para_ticket = servicio.letra_actual
            numero_para_ticket = servicio.numero_actual
            siguiente_numero = numero_para_ticket + 1
            siguiente_letra = letra_para_ticket
            if siguiente_numero > 99:
                siguiente_numero = 0
                siguiente_letra = chr(ord(letra_para_ticket) + 1)
        
            numero_ticket_str = f"{servicio.prefijo_ticket}-{letra_para_ticket}{numero_para_ticket:02d}"
        
            servicio.numero_actual = siguiente_numero
            servicio.letra_actual = siguiente_letra
        
            nuevo_ticket = Ticket(
                numero_ticket=numero_ticket_str,
                rut_cliente=rut_cliente,
                modulo_solicitado=servicio.nombre_modulo,
                servicio_id=servicio.id,
                hora_registro=datetime.now(zona_horaria_chile)
            )
        
            db.session.add(nuevo_ticket)
            db.session.commit()

            # Emitimos evento para paneles staff del módulo correspondiente
            datos_ticket = {
                'numero_ticket': numero_ticket_str,
                'modulo_solicitado': servicio.nombre_modulo,
                'color_hex': servicio.color_hex,
                'hora_registro': nuevo_ticket.hora_registro.isoformat()
            }
            # Usamos el nombre del módulo como "sala" para que solo el staff correspondiente reciba el evento
            socketio.emit('nuevo_ticket_registrado', datos_ticket, room=servicio.nombre_modulo)

            flash(f"¡Registro Exitoso! Número Asignado: {numero_ticket_str}", "success")
            return redirect(url_for('registro'))

        return render_template('registro.html', form=form)


    @app.route('/login', methods=['GET', 'POST'])
    def login():
        form = LoginForm()
        if form.validate_on_submit():
            nombre = form.username.data
            password = form.password.data
            usuario = Usuario.query.filter_by(nombre_funcionario=nombre).first()

            if usuario and usuario.check_password(password):
                login_user(usuario)

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
        hoy = date.today()
    
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
        # -----------------------------------------------------------------
    
        return render_template(
            'admin_dashboard.html', 
            tickets_hoy=tickets_hoy,
            tickets_en_espera=tickets_en_espera,
            tickets_en_atencion=tickets_en_atencion,
            tickets_finalizados_hoy=tickets_finalizados_hoy,
            chart_data_dona=chart_data_dona,
            chart_data_lineas=datos_grafico_lineas
        )

    @app.route('/admin/reporte/tickets')
    @login_required
    @role_required('admin')
    def descargar_reporte_tickets():
        # 1. Obtenemos todos los tickets de la base de datos
        tickets = db.session.query(Ticket, Usuario).outerjoin(
            Usuario, Ticket.atendido_por_id == Usuario.id
        ).order_by(Ticket.hora_registro.asc()).all()

        # 2. Creamos un "archivo" en la memoria para escribir el CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # 3. Escribimos la fila del encabezado
        writer.writerow([
            'ID Ticket', 'Numero Ticket', 'RUT Cliente', 'Modulo Solicitado', 'Estado', 
            'Hora Registro', 'Hora Llamado', 'Hora Finalizado', 
            'Atendido Por', 'Numero Meson'
        ])

        # 4. Escribimos los datos de cada ticket
        for ticket, usuario in tickets:
            # Si un ticket fue atendido, 'usuario' tendrá los datos del funcionario.
            # Si no, será 'None'.
            nombre_funcionario = usuario.nombre_funcionario if usuario else ''
        
            writer.writerow([
                ticket.id, 
                ticket.numero_ticket, 
                ticket.rut_cliente, 
                ticket.modulo_solicitado,
                ticket.estado, 
                ticket.hora_registro.strftime('%Y-%m-%d %H:%M:%S') if ticket.hora_registro else '',
                ticket.hora_llamado.strftime('%Y-%m-%d %H:%M:%S') if ticket.hora_llamado else '',
                ticket.hora_finalizado.strftime('%Y-%m-%d %H:%M:%S') if ticket.hora_finalizado else '',
                nombre_funcionario,
                ticket.numero_meson
            ])

        # 5. Preparamos la respuesta para el navegador
        output.seek(0)
        final_csv_string = '\ufeff' + output.getvalue()

        return Response(
            final_csv_string.encode('utf-8'),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=reporte_tickets.csv"}
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
                
                    if form.numero_meson.data:
                        nuevo_usuario.numero_meson = int(form.numero_meson.data)

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
                if form.numero_meson.data:
                    usuario_a_editar.numero_meson = int(form.numero_meson.data)
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
                    color_hex=form.color_hex.data
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
    def llamar_siguiente():
        # 1. Buscar el ticket más antiguo que esté "en_espera" para el módulo del funcionario
        ticket_a_llamar = Ticket.query.filter_by(
            modulo_solicitado=current_user.modulo_asignado,
            estado='en_espera'
        ).order_by(Ticket.hora_registro.asc()).first()

        # 2. Si se encuentra un ticket, se actualiza su estado
        if ticket_a_llamar:
            # Primero, revisa si este mismo funcionario ya tiene un ticket "en_atencion"
            ticket_previo = Ticket.query.filter_by(
                atendido_por_id=current_user.id,
                estado='en_atencion'
            ).first()
        
            # Si lo tiene, lo marca como "finalizado" antes de llamar al nuevo
            if ticket_previo:
                ticket_previo.estado = 'finalizado'

            # Ahora sí, actualizamos el nuevo ticket
            ticket_a_llamar.estado = 'en_atencion'
            ticket_a_llamar.hora_llamado = datetime.now(zona_horaria_chile)
            ticket_a_llamar.atendido_por_id = current_user.id
            ticket_a_llamar.numero_meson = current_user.numero_meson
        
            db.session.commit()
            # --- LÍNEAS NUEVAS PARA LA ALERTA EN TIEMPO REAL ---
            datos_llamado = {
                'id_ticket': ticket_a_llamar.id,
                'nombre_modulo': ticket_a_llamar.servicio.nombre_modulo,
                'numero_ticket': ticket_a_llamar.numero_ticket,
                'color_hex': ticket_a_llamar.servicio.color_hex,
                'numero_meson': ticket_a_llamar.numero_meson
            }
            payload = {
                'llamado': datos_llamado,
                'historial': _get_historial_data()
            }
            socketio.emit('nuevo_llamado', payload, room='pantalla_publica')
            # --------------------------------------------------
            flash(f"Llamando al ticket {ticket_a_llamar.numero_ticket}", "success")
        else:
            # 3. Si no se encuentran tickets, se informa al funcionario
            flash("No hay más personas en espera.", "info")

        return redirect(url_for('panel'))

    @app.route('/rellamar', methods=['POST'])
    @login_required
    @role_required('staff')
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
                'numero_meson': ticket_a_rellamar.numero_meson
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
    def finalizar_atencion():
        ticket_id = request.form['ticket_id']
        ticket_a_finalizar = db.session.get(Ticket, ticket_id)

        # Verificación de seguridad: nos aseguramos de que el ticket
        # realmente le pertenezca al funcionario que lo quiere finalizar.
        if ticket_a_finalizar and ticket_a_finalizar.atendido_por_id == current_user.id:
            ticket_a_finalizar.estado = 'finalizado'
            ticket_a_finalizar.hora_finalizado = datetime.now(zona_horaria_chile)
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
            # Aquí podrías añadir lógica de validación. Por ejemplo,
            # que un usuario 'staff' solo pueda unirse a la sala de su módulo.
            if current_user.is_authenticated and current_user.rol == 'staff':
                if room == current_user.modulo_asignado:
                    join_room(room)
            elif room == 'pantalla_publica': # Cualquiera puede unirse a la pantalla pública
                join_room(room)

    return app