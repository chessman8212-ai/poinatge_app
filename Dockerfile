# Image légère et récente
FROM python:3.13-slim

# Empêche Python de bufferiser la sortie (logs visibles)
ENV PYTHONUNBUFFERED=1

# Dossier de travail
WORKDIR /code

# Déps système minimales (certs, locales…)
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Copier et installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copier le code de l’app
COPY . .

# Fly route le trafic vers ce port interne
EXPOSE 8080

# Lancer avec Gunicorn (prod, 2 workers suffisent pour démarrer)
# "app:app" = module:fla sk_app
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "app:app"]
