# Usa una imagen oficial de Python completa
FROM python:3.11

# Establece el directorio de trabajo
WORKDIR /app

# Copia los requisitos
COPY requirements.txt .

# Instala los paquetes
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código
COPY . .

# IMPORTANTE: No exponemos un puerto fijo.
# Usamos el comando "sh -c" para que Docker pueda leer la variable $PORT de Railway
CMD ["sh", "-c", "gunicorn main:app --bind 0.0.0.0:${PORT:-8080}"]
