# Usar imagen base con Node y Python
FROM node:18-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*

# Crear directorio de la app
WORKDIR /app

# Copiar los archivos de la app
COPY . .

# Instalar dependencias de Node si existen
RUN if [ -f package.json ]; then npm install; fi

# Instalar dependencias de Python si existen
RUN if [ -f requirements.txt ]; then pip3 install -r requirements.txt; fi

# Exponer el puerto (Render usa PORT automáticamente)
EXPOSE 3000

# Comando de arranque
CMD ["node", "server.js"]
