# Sistema de Gestión de Turnos Web

Este es un sistema de gestión de filas y atención al cliente completo, desarrollado con Flask y Python. La aplicación permite registrar tickets de atención, llamarlos desde un panel de personal y visualizar los llamados en tiempo real en una pantalla pública. Incluye un panel de administración para gestionar usuarios, servicios y visualizar analíticas de rendimiento.

Este proyecto evolucionó desde un simple script en Tkinter hasta una aplicación web full-stack, multiusuario y en tiempo real.

## ✨ Características Principales

* **Pantalla Pública en Tiempo Real:** Muestra la llamada actual y los últimos tickets llamados, actualizándose instantáneamente sin necesidad de recargar la página, gracias a WebSockets.
* **Alertas Sonoras y Visuales:** Emite un sonido y una animación CSS para notificar un nuevo llamado.
* **Sistema de Roles:**
    * **Administrador:** Gestiona usuarios y servicios, y visualiza las analíticas.
    * **Staff (Atención):** Llama a los tickets de su módulo asignado, los vuelve a llamar o finaliza la atención.
    * **Registrador:** Registra los nuevos tickets en el sistema.
* **Panel de Administración Completo:**
    * Gestión de Usuarios (CRUD: Crear, Leer, Editar, Eliminar).
    * Gestión de Servicios (CRUD: Crear, Leer, Editar, Eliminar).
    * Dashboard con estadísticas en tiempo real y gráficos históricos (distribución por servicio y flujo por hora).
* **Seguridad:**
    * Contraseñas cifradas (hashing).
    * Protección de rutas por rol y sesión iniciada.
    * Formularios seguros con protección CSRF.
    * Gestión de secretos y contraseñas a través de variables de entorno (`.env`).
* **Exportación de Datos:** Funcionalidad para descargar un reporte completo de todos los tickets en formato CSV.

## 🚀 Pila Tecnológica (Tech Stack)

* **Backend:**
    * Python 3
    * Flask (Framework principal)
    * Flask-SocketIO (para WebSockets y tiempo real)
    * Flask-SQLAlchemy (para interacción con la base de datos)
    * Flask-Login (para gestión de sesiones de usuario)
    * Flask-WTF (para formularios y seguridad CSRF)
    * Eventlet (Servidor asíncrono para Socket.IO)
    * Psycopg2 (Conector para PostgreSQL)
    * Python-Dotenv (Gestión de variables de entorno)
* **Base de Datos:**
    * PostgreSQL
* **Frontend:**
    * HTML5 con plantillas Jinja2
    * CSS3 (con Flexbox y Grid para maquetación responsiva)
    * JavaScript (nativo)
    * Chart.js (para la visualización de gráficos)

## 🔧 Instalación y Configuración Local

Sigue estos pasos para levantar el proyecto en un entorno de desarrollo.

### Prerrequisitos
* Tener Python 3 instalado.
* Tener un servidor de PostgreSQL instalado y corriendo.

### Pasos

1.  **Clonar el Repositorio**
    ```bash
    git clone <url-del-repositorio>
    cd <nombre-de-la-carpeta>
    ```

2.  **Crear y Activar el Entorno Virtual**
    ```bash
    # Crear el entorno
    python -m venv venv
    # Activar en Windows
    venv\Scripts\activate
    # Activar en macOS/Linux
    source venv/bin/activate
    ```

3.  **Crear el Archivo `requirements.txt`**
    Si no tienes este archivo, créalo con todas las dependencias instaladas:
    ```bash
    pip freeze > requirements.txt
    ```

4.  **Instalar Dependencias**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Configurar la Base de Datos**
    * Abre `pgAdmin` o tu cliente de PostgreSQL preferido.
    * Crea una nueva base de datos vacía (ej: `turnos_db`).

6.  **Configurar las Variables de Entorno**
    * En la raíz del proyecto, crea un archivo llamado `.env`.
    * Copia el contenido de `.env.example` (si existe) o añade las siguientes variables, reemplazando con tus valores:
    ```env
    SECRET_KEY='tu_clave_secreta_larga_y_aleatoria'
    DATABASE_URL='postgresql://tu_usuario:tu_contraseña@localhost/turnos_db'
    SENTRY_DSN='tu_dsn_opcional_de_sentry'
    ```

7.  **Inicializar la Base de Datos**
    Ejecuta los siguientes scripts en orden para crear las tablas y añadir los datos iniciales:
    ```bash
    python create_db.py
    python seed_db.py
    ```

## 🏃 Uso de la Aplicación

1.  **Ejecutar la Aplicación**
    ```bash
    python app.py
    ```
    La aplicación estará disponible en `http://127.0.0.1:5000`.

2.  **Crear el Primer Usuario (Admin)**
    La primera vez, necesitarás crear un usuario administrador para poder gestionar el resto.
    ```bash
    python create_user.py
    ```
    Sigue las instrucciones y crea un usuario con el rol `admin`.

3.  **Acceder a la Aplicación**
    * **Panel de Admin:** Ve a `/login` e inicia sesión como `admin`. Serás redirigido a `/admin/dashboard`.
    * **Panel de Staff:** Crea un usuario con rol `staff` y accede a `/panel`.
    * **Panel de Registro:** Crea un usuario con rol `registrador` y accede a `/registro`.
    * **Pantalla Pública:** Accede a `/` para ver la pantalla de llamados.