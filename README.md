# Sistema de Gestión de Turnos Web

Este es un sistema de gestión de filas y atención al cliente completo, desarrollado con Flask y Python. La aplicación permite registrar tickets de atención, llamarlos desde un panel de personal y visualizar los llamados en tiempo real en una pantalla pública. Incluye un panel de administración para gestionar usuarios, servicios y visualizar analíticas de rendimiento.

## ✨ Características Principales

*   **Pantalla Pública en Tiempo Real:** Muestra la llamada actual y los últimos tickets llamados, actualizándose instantáneamente sin necesidad de recargar la página, gracias a WebSockets (Flask-SocketIO).
*   **Alertas Sonoras y Visuales:** Emite un sonido y una animación CSS para notificar un nuevo llamado en la pantalla pública.
*   **Sistema de Roles de Usuario:**
    *   **Administrador:** Acceso total. Gestiona usuarios y servicios, y visualiza un dashboard con estadísticas y gráficos de rendimiento.
    *   **Staff (Atención):** Accede a un panel personal para llamar tickets de su módulo asignado, volver a llamar o finalizar la atención.
    *   **Registrador:** Utiliza una interfaz simple para registrar nuevos tickets para los distintos servicios.
*   **Panel de Administración Completo:**
    *   Gestión de Usuarios (CRUD: Crear, Leer, Editar, Eliminar).
    *   Gestión de Servicios/Módulos (CRUD: Crear, Leer, Editar, Eliminar).
    *   Dashboard con estadísticas en tiempo real (tickets del día, en espera, etc.) y gráficos (distribución de tickets por servicio y flujo de atención por hora).
*   **Seguridad:**
    *   Contraseñas cifradas (hashing con Werkzeug).
    *   Protección de rutas por rol y sesión de usuario (Flask-Login).
    *   Formularios seguros con protección contra ataques CSRF (Flask-WTF).
    *   Gestión de secretos y configuración sensible a través de variables de entorno (`.env`).
*   **Exportación de Datos:** Funcionalidad para descargar un reporte completo de todos los tickets históricos en formato CSV.
*   **Base de Datos Flexible:** Soporte para SQLite en desarrollo y PostgreSQL en producción. Gestionado con SQLAlchemy y migraciones de Alembic (Flask-Migrate).

## 🚀 Stack Tecnológico

*   **Backend:**
    *   Python 3
    *   Flask (Framework principal)
    *   Flask-SocketIO (WebSockets para comunicación en tiempo real)
    *   Flask-SQLAlchemy (ORM para la base de datos)
    *   Flask-Migrate (Manejo de migraciones de base de datos con Alembic)
    *   Flask-Login (Gestión de sesiones de usuario)
    *   Flask-WTF (Formularios y seguridad CSRF)
    *   Eventlet (Servidor WSGI asíncrono, necesario para Flask-SocketIO)
    *   Python-Dotenv (Gestión de variables de entorno)
    *   Psycopg2-binary (Adaptador de PostgreSQL)
*   **Frontend:**
    *   HTML5 con plantillas Jinja2
    *   CSS3 (Estilos personalizados, Flexbox y Grid)
    *   JavaScript (Vanilla JS para interactuar con WebSockets y Chart.js)
    *   Chart.js (Visualización de gráficos en el dashboard)
*   **Base de Datos:**
    *   PostgreSQL (Recomendado para producción)
    *   SQLite (Por defecto para desarrollo)

## 📂 Estructura del Proyecto

```
.
├── app.py             # Fábrica de la aplicación, define modelos, rutas y lógica principal.
├── run.py             # Punto de entrada para ejecutar la app en modo desarrollo con SocketIO.
├── wsgi.py            # Punto de entrada para servidores WSGI en producción.
├── requirements.txt   # Lista de dependencias de Python.
├── .env.example       # Archivo de ejemplo para las variables de entorno.
├── migrations/        # Directorio de Alembic para las migraciones de la base de datos.
├── static/            # Archivos estáticos (CSS, JS, imágenes, sonidos).
└── templates/         # Plantillas HTML de Jinja2.
```

## 🔧 Instalación y Configuración

Sigue estos pasos para configurar y ejecutar el proyecto en un entorno de desarrollo local.

### 1. Prerrequisitos
*   Tener Python 3.8 o superior instalado.
*   Tener Git instalado.
*   (Opcional, para producción) Tener un servidor de PostgreSQL instalado.

### 2. Clonar el Repositorio
```bash
git clone <url-del-repositorio>
cd sistema-de-turnos
```

### 3. Crear y Activar un Entorno Virtual
Esto aísla las dependencias del proyecto.
```bash
# Crear el entorno virtual
python -m venv venv

# Activar en Windows
venv\Scripts\activate

# Activar en macOS/Linux
source venv/bin/activate
```

### 4. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 5. Configurar Variables de Entorno
Crea un archivo llamado `.env` en la raíz del proyecto, puedes copiar el ejemplo `.env.example` si existe, o crearlo desde cero con el siguiente contenido:

```env
# Clave secreta para proteger sesiones y formularios. Genera una clave segura.
# Puedes usar: python -c 'import secrets; print(secrets.token_hex())'
SECRET_KEY='tu_clave_secreta_aqui'

# URL de la base de datos.
# Para desarrollo con SQLite (opción por defecto, no necesitas instalar nada más):
SQLALCHEMY_DATABASE_URI='sqlite:///instance/database.db'
# Para producción con PostgreSQL (ejemplo):
# SQLALCHEMY_DATABASE_URI='postgresql://usuario:contraseña@localhost/nombre_db'

# Credenciales para el usuario administrador que se creará con el comando seed.
ADMIN_USERNAME='admin'
ADMIN_PASSWORD='admin'

# DSN de Sentry para monitoreo de errores (opcional)
SENTRY_DSN=''
```

### 6. Inicializar la Base de Datos
Estos comandos crearán las tablas en la base de datos según los modelos definidos.
```bash
# (Solo la primera vez) Inicializa el directorio de migraciones
flask db init

# Genera el script de migración inicial
flask db migrate -m "Creacion inicial de tablas"

# Aplica la migración a la base de datos
flask db upgrade
```

### 7. Poblar la Base de Datos
Este comando personalizado creará los servicios iniciales y el usuario administrador definido en tu archivo `.env`.
```bash
flask seed
```

## 🏃 Ejecución de la Aplicación

### Modo Desarrollo
Para correr la aplicación en un entorno de desarrollo con recarga automática y depuración:
```bash
python run.py
```
La aplicación estará disponible en `http://127.0.0.1:5000`.

### Modo Producción
Para producción, se debe utilizar un servidor WSGI como Gunicorn o uWSGI, apuntando al objeto `app` en `wsgi.py`.
```bash
# Ejemplo con Gunicorn y Eventlet para soportar WebSockets
gunicorn --worker-class eventlet -w 1 wsgi:app
```

## 🕹️ Uso

1.  **Acceder a la Aplicación:** Abre tu navegador y ve a `http://127.0.0.1:5000`.
2.  **Iniciar Sesión:** Ve a `/login` y usa las credenciales del administrador que creaste (`admin`/`admin` por defecto).
3.  **Panel de Administración:** Una vez logueado como admin, serás redirigido al dashboard (`/admin`). Aquí puedes:
    *   Crear más usuarios con roles de `staff` o `registrador`.
    *   Crear los servicios o módulos de atención que necesites.
    *   Asignar usuarios de `staff` a un módulo y un número de mesón.
4.  **Paneles de Roles:**
    *   **Registrador (`/registro`):** Inicia sesión con un usuario `registrador` para ver el formulario de creación de tickets.
    *   **Staff (`/panel`):** Inicia sesión con un usuario `staff` para ver la lista de espera de tu módulo y llamar clientes.
    *   **Pantalla Pública (`/`):** No necesita inicio de sesión. Muestra los llamados en tiempo real.
