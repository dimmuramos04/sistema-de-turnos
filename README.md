# Sistema de Gestión de Turnos Web (ULS)

Este es un sistema de gestión de filas y atención al cliente profesional, desarrollado con Flask y Python. La aplicación está diseñada para manejar entornos de **alta concurrencia** (como matrículas universitarias), permitiendo registrar tickets, priorizar atenciones preferenciales y visualizar los llamados en tiempo real en pantallas públicas.

## ✨ Características Principales

### 🎯 Gestión de Colas Inteligente
* **Atención Preferencial (VIP):** Sistema de priorización automática para adultos mayores, embarazadas o personas con movilidad reducida. Al marcar esta opción, el ticket "salta" la fila normal respetando la lógica de llegada dentro del grupo preferencial.
* **Pantalla Pública en Tiempo Real:** Actualización instantánea mediante WebSockets (Flask-SocketIO).
    * **Alerta Visual VIP:** Los tickets preferenciales aparecen con un distintivo rojo parpadeante y texto destacado.
    * **Alerta Sonora:** Reproducción de timbre al llamar un nuevo número.

### 🛡️ Robustez y Concurrencia
* **Manejo de Alto Tráfico:** Implementación de bloqueos optimistas y reintentos automáticos para evitar duplicidad de tickets cuando múltiples registradores operan simultáneamente.
* **Asignación Atómica:** Evita que dos funcionarios llamen al mismo número al mismo tiempo.

### 👥 Roles de Usuario
* **Administrador:**
    * Dashboard con métricas en tiempo real (Gráficos Chart.js).
    * Gestión CRUD completa de Usuarios y Servicios.
    * **Reinicio Diario:** Función para limpiar tickets del día y reiniciar contadores (A00) por servicio.
    * Descarga de reportes históricos en CSV.
* **Staff (Atención):** Panel para llamar al siguiente ticket (con lógica VIP automática), volver a llamar (re-call) o finalizar atención.
* **Registrador:** Interfaz optimizada para emisión rápida de tickets con opción de "Atención Preferencial".

## 🚀 Stack Tecnológico

* **Backend:**
    * Python 3 + Flask 3.x
    * **Flask-SocketIO + Eventlet:** Para comunicación asíncrona en tiempo real.
    * **SQLAlchemy:** ORM con soporte para SQLite (Dev) y PostgreSQL (Prod).
    * **Flask-Login:** Gestión segura de sesiones.
* **Frontend:**
    * Jinja2 Templates.
    * CSS3 (Animaciones, Grid, Flexbox, Variables CSS).
    * JavaScript Vanilla (Cliente Socket.IO ligero).
* **Infraestructura:**
    * Diseñado para correr en **Render** (Gunicorn con Eventlet worker).

## 📂 Estructura del Proyecto

```text
.
├── app.py             # Lógica principal, modelos y eventos SocketIO.
├── run.py             # Entry point para desarrollo.
├── wsgi.py            # Entry point para producción (Gunicorn).
├── requirements.txt   # Dependencias.
├── migrations/        # Historial de cambios de base de datos (Alembic).
├── static/            # Assets (CSS, JS, Logos, Sonidos).
└── templates/         # Vistas HTML (Admin, Staff, Pantalla, Registro).

🔧 Instalación y Configuración Local
1. Clonar y preparar entorno
Bash

git clone <url-del-repositorio>
cd sistema-de-turnos
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
2. Variables de Entorno (.env)
Crea un archivo .env en la raíz:

Fragmento de código

SECRET_KEY='tu_clave_secreta_segura'
# Desarrollo (SQLite):
SQLALCHEMY_DATABASE_URI='sqlite:///instance/database.db'
# Producción (PostgreSQL):
# SQLALCHEMY_DATABASE_URI='postgresql://user:pass@host/dbname'
3. Inicializar Base de Datos
Bash

flask db upgrade
flask seed  # Crea admin/admin y servicios base
4. Ejecutar
Bash

python run.py
# Accede a [http://127.0.0.1:5000](http://127.0.0.1:5000)
☁️ Despliegue en Producción (Render/Cloud)
Para garantizar el funcionamiento de los WebSockets y la estabilidad bajo carga:

Start Command: Es crítico usar un solo worker con la clase eventlet para mantener la sincronización de los sockets.

Bash

gunicorn --worker-class eventlet -w 1 wsgi:app
Base de Datos: Se recomienda PostgreSQL. Asegúrate de que la URL de conexión en las variables de entorno comience con postgresql:// (no postgres://).

🕹️ Guía de Uso Rápido
Registrador: Ingresa al panel /registro. Si llega una persona con prioridad, marca la casilla "¿Atención Preferencial?" antes de generar el ticket.

Staff: En el /panel, presiona "Llamar Siguiente". El sistema te asignará automáticamente al VIP más antiguo o, si no hay, al ticket normal más antiguo.

Pantalla Pública: Mantenla abierta en un monitor/TV visible. Los llamados VIP aparecerán con un marco rojo y la etiqueta "PREFERENCIAL".

Admin: Usa el botón "Reiniciar Contador" en la gestión de servicios solo al iniciar una nueva jornada operativa (esto borra los tickets pendientes del servicio).

Desarrollado para la Universidad de La Serena (ULS).


### ¿Qué cambios hice en esta versión?

1.  **Destaqué la "Atención Preferencial":** Agregué una sección específica explicando que ahora el sistema sabe priorizar VIPs y cómo se ve visualmente.
2.  **Mención a la Concurrencia:** Agregué la sección "Robustez y Concurrencia" para que quien lea el código (o tu jefe) sepa que el sistema no se caerá si 5 personas hacen clic a la vez.
3.  **Actualicé el comando de producción:** Enfatizo el uso de `eventlet` y `-w 1`, que fue un punto clave en nuestra conversación para evitar problemas con los WebSockets.
4.  **Guía de uso actualizada:** Incluí instrucciones sobre el checkbox VIP y el botón de Reinciar Contador.
