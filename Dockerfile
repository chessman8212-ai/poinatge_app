# Utiliser Python 3.12 (stable, wheels dispo pour psycopg2-binary)
FROM python:3.12-slim

# Définir le dossier de travail
WORKDIR /app

# Installer dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de dépendances
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copier tout le code de l’application
COPY . .

# Définir la variable PORT (Fly l’injecte de toute façon)
ENV PORT=8080

# Commande de démarrage en production avec Gunicorn
CMD ["sh", "-c", "gunicorn wsgi:app --bind 0.0.0.0:${PORT} --workers 2 --threads 4"]
