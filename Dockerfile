# Usar una imagen oficial de Python como base
FROM python:3.11-slim

# Establecer variables de entorno
ENV PYTHONUNBUFFERED True
ENV APP_HOME /app
WORKDIR $APP_HOME

# Instalar dependencias
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación al contenedor
COPY . ./

# Exponer el puerto que gunicorn usará
EXPOSE 8080

# Comando para ejecutar la aplicación en producción
# Usamos gunicorn con el worker de eventlet, crucial para Socket.IO
CMD exec gunicorn --worker-class eventlet -w 1 --bind :8080 wsgi:app