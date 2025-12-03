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

# Expone el puerto (Documentación)
EXPOSE 8080

# === CAMBIO CRÍTICO AQUÍ ===
# Usamos "sh -c" para poder leer la variable $PORT de Railway
CMD ["sh", "-c", "gunicorn main:app --bind 0.0.0.0:${PORT:-8080}"]
