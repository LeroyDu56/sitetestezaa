FROM python:3.11-slim

WORKDIR /app

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copier et installer les requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY . .

# Créer les dossiers pour les fichiers statiques et media
RUN mkdir -p /app/static /app/media

# Exposer le port
EXPOSE 8000

# Script de démarrage
CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn minecraft_site.wsgi:application --bind 0.0.0.0:8000"]