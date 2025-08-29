# Pointage — Application Web Internet-Ready (Flask)

## Fonctionnalités
- Saisie de pointage (Nom, Service, Arrivée, Départ, Note)
- Admin avec authentification (création automatique du 1er admin via .env)
- Export CSV
- SQLAlchemy (SQLite local ou PostgreSQL internet)
- Déploiement facile sur Render / Railway / Heroku-like (Procfile + gunicorn)

## Configuration
1. Copiez `.env.example` vers `.env` et remplissez :
```
FLASK_SECRET_KEY=...
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname   # ou sqlite:///pointage.db pour local
ADMIN_USERNAME=admin
ADMIN_PASSWORD=un_bon_mdp
PORT=8000
```

## Lancement local
```
python -m venv .venv
# PowerShell
.\.venv\Scriptsctivate.bat
pip install -r requirements.txt
python -m flask run --app app:app --host 0.0.0.0 --port 8000
```

## Déploiement Render (exemple rapide)
1. Poussez ce dossier vers GitHub.
2. Render.com → New → Web Service → Connecter le repo.
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `gunicorn wsgi:app --workers=2 --threads=4 --bind=0.0.0.0:${PORT}`
5. Ajouter les variables d'env: `FLASK_SECRET_KEY`, `DATABASE_URL` (PostgreSQL), `ADMIN_USERNAME`, `ADMIN_PASSWORD`.
6. Render fournit un domaine HTTPS.

## Déploiement VPS (Nginx + Gunicorn résumé)
- Gunicorn en service systemd sur 127.0.0.1:8000
- Nginx reverse proxy + Certbot pour HTTPS
- DNS: enreg. A du domaine → IP du VPS

## Sécurité
- Utilisez PostgreSQL en production (multi-utilisateur)
- Mettez un `FLASK_SECRET_KEY` long et unique
- Changez le mot de passe admin initial
- Sauvegardez la base
