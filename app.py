import os
<<<<<<< HEAD
import csv
from io import StringIO, BytesIO
from datetime import date
=======
import re
import csv
from io import StringIO, BytesIO
from datetime import datetime, date
>>>>>>> 4a314f4 (Refonte app + templates (date, types, HH:MM, PRG, CSV))
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
<<<<<<< HEAD
    session, flash, send_file, abort
=======
    session, flash, send_file
>>>>>>> 4a314f4 (Refonte app + templates (date, types, HH:MM, PRG, CSV))
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.security import generate_password_hash, check_password_hash
<<<<<<< HEAD

# --- App & sécurité ---
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "changeme")

# Cookies sûrs en prod (HTTPS sur Fly)
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# DB URL (Postgres/SQLite)
db_url = os.getenv("DATABASE_URL", "sqlite:///pointage.db")
# SQLAlchemy attend postgresql+psycopg2://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
=======
from sqlalchemy.exc import IntegrityError

# ---------------------------
# Mapping des types de pointage
# ---------------------------
POINTAGE_TYPES = {
    "TC": "Travaux centre",
    "RC": "Repos compensateur",
    "DEP": "Déplacement",
    "PE": "Permission exceptionnelle",
    "CONGE": "Congé",
    "MAL": "Maladie",
    "FORM": "Formation",
    "AST": "Astreinte",
    "FERIE": "Jour férié",
    "RTT": "RTT",
    "AUTRE": "Autre",
}

# ---------------------------
# Helpers
# ---------------------------
def _parse_iso_date(s: str | None) -> date:
    if not s:
        return date.today()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return date.today()

def to_hhmm(s: str | None):
    """Normalise une valeur 'H:M' ou 'HH:MM' en 'HH:MM' (24h)."""
    if not s:
        return None
    s = s.strip()
    m = re.match(r'^(\d{1,2}):(\d{1,2})$', s)
    if not m:
        return s  # format inattendu, on laisse tel quel
    h = int(m.group(1))
    mi = int(m.group(2))
    return f"{h:02d}:{mi:02d}"

def format_time(t):
    """Affichage 24h, quelle que soit la forme stockée (string/time)."""
    try:
        # si Time ou Datetime
        return t.strftime("%H:%M")
    except Exception:
        # string brute
        return to_hhmm(t) or ""

# ---------------------------
# App & sécurité
# ---------------------------
app = Flask(__name__, template_folder="templates", static_folder="static")

# Clé secrète (mettre en prod via secret Fly)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "changeme")

# Cookies : secure seulement en prod
IS_PRODUCTION = bool(os.getenv("FLY_APP_NAME")) or os.getenv("FLASK_ENV") == "production"
app.config["SESSION_COOKIE_SECURE"] = IS_PRODUCTION
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Base de données
db_url = os.getenv("DATABASE_URL", "sqlite:///pointage.db")
# psycopg v3: postgresql+psycopg://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://") and "+psycopg" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

>>>>>>> 4a314f4 (Refonte app + templates (date, types, HH:MM, PRG, CSV))
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# ... après avoir construit db_url ...
# Options de pool pour reconnecter automatiquement si la connexion est coupée
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,    # teste la connexion avant chaque usage, reconnecte si morte
    "pool_recycle": 300,      # recycle les connexions toutes les 5 min
    "pool_timeout": 10,       # attente max pour obtenir une connexion du pool
    "pool_size": 5,           # taille du pool
    "max_overflow": 10,       # connexions temporaires en plus si pic
}


db = SQLAlchemy(app)
<<<<<<< HEAD
csrf = CSRFProtect(app)

# Exposer generate_csrf() à Jinja comme "csrf_token"
@app.context_processor
def csrf_token_processor():
    return dict(csrf_token=generate_csrf)

# --- Modèles ---
=======

# CSRF
csrf = CSRFProtect(app)

# Exposer helpers à Jinja
@app.context_processor
def inject_helpers():
    return dict(
        csrf_token=generate_csrf,
        format_time=format_time,
        POINTAGE_TYPES=POINTAGE_TYPES,
    )

# ---------------------------
# Modèles
# ---------------------------
>>>>>>> 4a314f4 (Refonte app + templates (date, types, HH:MM, PRG, CSV))
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
<<<<<<< HEAD
    role = db.Column(db.String(10), default="user")  # "user" / "admin"

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
=======
    role = db.Column(db.String(10), default="user")  # "user" | "admin"

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
>>>>>>> 4a314f4 (Refonte app + templates (date, types, HH:MM, PRG, CSV))
        return check_password_hash(self.password_hash, raw)

class Pointage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
<<<<<<< HEAD
    nom = db.Column(db.String(100), nullable=False)       # username du user connecté
    service = db.Column(db.String(100))
    arrivee = db.Column(db.String(10), nullable=False)
    depart = db.Column(db.String(10))
    note = db.Column(db.String(200))
    jour = db.Column(db.Date, default=date.today, index=True)

# --- Décorateurs ---
=======
    nom = db.Column(db.String(100), nullable=False)   # username
    service = db.Column(db.String(20))                # code (TC, RC, ...)
    arrivee = db.Column(db.String(5), nullable=False) # "HH:MM"
    depart = db.Column(db.String(5))                  # "HH:MM" ou None
    note = db.Column(db.String(200))
    jour = db.Column(db.Date, default=date.today, index=True)

# ---------------------------
# Décorateurs d'accès
# ---------------------------
>>>>>>> 4a314f4 (Refonte app + templates (date, types, HH:MM, PRG, CSV))
def login_required(f):
    @wraps(f)
    def _wrap(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*a, **kw)
    return _wrap

def admin_required(f):
    @wraps(f)
    def _wrap(*a, **kw):
        if session.get("role") != "admin":
            flash("Accès réservé à l'administrateur.", "error")
            return redirect(url_for("index"))
        return f(*a, **kw)
    return _wrap

<<<<<<< HEAD
# --- Bootstrap : créer tables + 1er admin si nécessaire ---
with app.app_context():
    db.create_all()
    admin_user = os.getenv("ADMIN_USERNAME", "admin")
    admin_pass = os.getenv("ADMIN_PASSWORD", "admin123")
    if not User.query.filter_by(role="admin").first():
=======
# ---------------------------
# Bootstrap DB + premier admin
# ---------------------------
with app.app_context():
    db.create_all()
    if not User.query.filter_by(role="admin").first():
        admin_user = os.getenv("ADMIN_USERNAME", "admin")
        admin_pass = os.getenv("ADMIN_PASSWORD", "admin123")
>>>>>>> 4a314f4 (Refonte app + templates (date, types, HH:MM, PRG, CSV))
        if not User.query.filter_by(username=admin_user).first():
            u = User(username=admin_user, role="admin")
            u.set_password(admin_pass)
            db.session.add(u)
            db.session.commit()

<<<<<<< HEAD
# --- Routes ---
=======
# ---------------------------
# Routes
# ---------------------------
>>>>>>> 4a314f4 (Refonte app + templates (date, types, HH:MM, PRG, CSV))
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()
<<<<<<< HEAD
=======

>>>>>>> 4a314f4 (Refonte app + templates (date, types, HH:MM, PRG, CSV))
        if user and user.check_password(password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            flash("Connexion réussie.", "success")
<<<<<<< HEAD
            return redirect(url_for("index"))
        flash("Nom d'utilisateur ou mot de passe incorrect.", "error")
=======
            return redirect(url_for("index"))  # PRG

        flash("Nom d'utilisateur ou mot de passe incorrect.", "error")
        return redirect(url_for("login"))      # PRG

>>>>>>> 4a314f4 (Refonte app + templates (date, types, HH:MM, PRG, CSV))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Déconnecté.", "success")
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
@admin_required
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
<<<<<<< HEAD
        password = request.form.get("password") or ""
        role = request.form.get("role") or "user"
=======
        password = (request.form.get("password") or "").strip()
        role = (request.form.get("role") or "user").strip().lower()
>>>>>>> 4a314f4 (Refonte app + templates (date, types, HH:MM, PRG, CSV))

        if not username or not password:
            flash("Nom d'utilisateur et mot de passe sont requis.", "error")
            return redirect(url_for("register"))
<<<<<<< HEAD

        if User.query.filter_by(username=username).first():
=======
        if role not in {"user", "admin"}:
            flash("Rôle invalide (user ou admin).", "error")
            return redirect(url_for("register"))

        # doublon case-insensitive
        exists = User.query.filter(db.func.lower(User.username) == username.lower()).first()
        if exists:
>>>>>>> 4a314f4 (Refonte app + templates (date, types, HH:MM, PRG, CSV))
            flash("Ce nom d'utilisateur existe déjà.", "error")
            return redirect(url_for("register"))

        u = User(username=username, role=role)
        u.set_password(password)
<<<<<<< HEAD
        db.session.add(u)
        db.session.commit()
        flash("Utilisateur créé avec succès.", "success")
        return redirect(url_for("admin"))
    return render_template("register.html")

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        service = (request.form.get("service") or "").strip()
        arrivee = (request.form.get("arrivee") or "").strip()
        depart = (request.form.get("depart") or "").strip()
        note = (request.form.get("note") or "").strip()

        if not arrivee:
            flash("Heure d'arrivée obligatoire.", "error")
            return redirect(url_for("index"))

        p = Pointage(
            nom=session["username"],
            service=service or None,
            arrivee=arrivee,
            depart=depart or None,
            note=note or None,
            jour=date.today()
        )
        db.session.add(p)
        db.session.commit()
        flash("Pointage enregistré ✅", "success")
        return redirect(url_for("index"))

    # Filtre visibilité
    if session.get("role") == "admin":
        rows = Pointage.query.filter_by(jour=date.today()).order_by(Pointage.arrivee.asc()).all()
    else:
        rows = (Pointage.query
                .filter_by(jour=date.today(), nom=session["username"])
                .order_by(Pointage.arrivee.asc())
                .all())
    return render_template("index.html", today=date.today(), rows=rows)

@app.route("/admin")
@admin_required
def admin():
    rows = Pointage.query.order_by(Pointage.jour.desc(), Pointage.arrivee.asc()).all()
    users = User.query.order_by(User.role.desc(), User.username.asc()).all()
    return render_template("admin.html", rows=rows, users=users)

@app.route("/pointage/<int:pid>/delete", methods=["POST"])
@admin_required
def delete_pointage(pid):
    p = Pointage.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    flash("Enregistrement supprimé 🗑️", "success")
    return redirect(url_for("admin"))

@app.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    # sécurité : pas supprimer soi-même
    if session.get("user_id") == user_id:
        flash("Vous ne pouvez pas supprimer votre propre compte.", "error")
        return redirect(url_for("admin"))

    user = User.query.get_or_404(user_id)

    # sécurité : pas supprimer le dernier admin
=======
        try:
            db.session.add(u)
            db.session.commit()
            flash("Utilisateur créé avec succès.", "success")
            return redirect(url_for("admin"))
        except IntegrityError:
            db.session.rollback()
            flash("Ce nom d'utilisateur existe déjà.", "error")
            return redirect(url_for("register"))
        except Exception:
            db.session.rollback()
            flash("Erreur serveur pendant la création de l'utilisateur.", "error")
            return redirect(url_for("register"))

    return render_template("register.html")

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        jour = _parse_iso_date(request.form.get("jour"))
        nature = (request.form.get("service") or "").strip().upper()
        arrivee = to_hhmm(request.form.get("arrivee"))
        depart = to_hhmm(request.form.get("depart"))
        note = (request.form.get("note") or "").strip()

        # Option : interdire le futur
        # if jour > date.today():
        #     flash("Impossible de saisir une date future.", "error")
        #     return redirect(url_for("index", d=date.today().isoformat()))

        if not arrivee:
            flash("Heure d'arrivée obligatoire.", "error")
            return redirect(url_for("index", d=jour.isoformat()))
        if nature and nature not in POINTAGE_TYPES:
            flash("Type de pointage invalide.", "error")
            return redirect(url_for("index", d=jour.isoformat()))

        p = Pointage(
            nom=session["username"],
            service=(nature or None),
            arrivee=arrivee,
            depart=(depart or None),
            note=(note or None),
            jour=jour,
        )
        db.session.add(p)
        db.session.commit()
        flash("Pointage enregistré ✅", "success")
        return redirect(url_for("index", d=jour.isoformat()))  # PRG: revenir sur la même date

    # GET avec filtre date (?d=YYYY-MM-DD)
    selected_date = _parse_iso_date(request.args.get("d"))

    if session.get("role") == "admin":
        rows = (Pointage.query
                .filter_by(jour=selected_date)
                .order_by(Pointage.arrivee.asc())
                .all())
    else:
        rows = (Pointage.query
                .filter_by(jour=selected_date, nom=session["username"])
                .order_by(Pointage.arrivee.asc())
                .all())

    return render_template(
        "index.html",
        selected_date=selected_date,
        rows=rows
    )

@app.route("/admin")
@admin_required
def admin():
    selected_date = _parse_iso_date(request.args.get("d"))

    rows = (Pointage.query
            .filter_by(jour=selected_date)
            .order_by(Pointage.arrivee.asc())
            .all())
    users = User.query.order_by(User.role.desc(), User.username.asc()).all()

    return render_template(
        "admin.html",
        rows=rows,
        users=users,
        selected_date=selected_date
    )

@app.route("/pointage/<int:pid>/delete", methods=["POST"])
@admin_required
def delete_pointage(pid):
    p = Pointage.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    flash("Enregistrement supprimé 🗑️", "success")
    # revenir sur la même date si possible
    d = request.args.get("d")
    if d:
        return redirect(url_for("admin", d=d))
    return redirect(url_for("admin"))

@app.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    if session.get("user_id") == user_id:
        flash("Vous ne pouvez pas supprimer votre propre compte.", "error")
        return redirect(url_for("admin"))

    user = User.query.get_or_404(user_id)

>>>>>>> 4a314f4 (Refonte app + templates (date, types, HH:MM, PRG, CSV))
    if user.role == "admin":
        nb_admins = User.query.filter_by(role="admin").count()
        if nb_admins <= 1:
            flash("Impossible de supprimer le dernier administrateur.", "error")
            return redirect(url_for("admin"))

    db.session.delete(user)
    db.session.commit()
    flash(f"Utilisateur « {user.username} » supprimé.", "success")
    return redirect(url_for("admin"))

@app.route("/export_csv")
@admin_required
def export_csv():
<<<<<<< HEAD
    rows = Pointage.query.order_by(Pointage.jour.asc(), Pointage.nom.asc()).all()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["id", "nom", "service", "arrivee", "depart", "note", "jour"])
    for r in rows:
        cw.writerow([r.id, r.nom, r.service or "", r.arrivee, r.depart or "", r.note or "", r.jour.isoformat()])
=======
    d = request.args.get("d")
    if d:
        jour = _parse_iso_date(d)
        q = Pointage.query.filter_by(jour=jour).order_by(Pointage.nom.asc())
        filename = f"pointages_{jour.isoformat()}.csv"
    else:
        q = Pointage.query.order_by(Pointage.jour.asc(), Pointage.nom.asc())
        filename = "pointages.csv"

    rows = q.all()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["id", "nom", "type_code", "type_libelle", "arrivee", "depart", "note", "jour"])
    for r in rows:
        cw.writerow([
            r.id,
            r.nom,
            r.service or "",
            POINTAGE_TYPES.get(r.service or "", r.service or ""),
            format_time(r.arrivee),
            format_time(r.depart),
            r.note or "",
            r.jour.isoformat()
        ])
>>>>>>> 4a314f4 (Refonte app + templates (date, types, HH:MM, PRG, CSV))
    data = si.getvalue().encode("utf-8")
    return send_file(
        BytesIO(data),
        mimetype="text/csv",
        as_attachment=True,
<<<<<<< HEAD
        download_name="pointages.csv"
    )

# 403 personnalisé (optionnel)
@app.errorhandler(403)
def forbidden(_e):
    return render_template("403.html"), 403
=======
        download_name=filename
    )

# 403 optionnel
@app.errorhandler(403)
def forbidden(_e):
    return render_template("403.html"), 403

# Entrée locale
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)  # http://127.0.0.1:5000
>>>>>>> 4a314f4 (Refonte app + templates (date, types, HH:MM, PRG, CSV))
