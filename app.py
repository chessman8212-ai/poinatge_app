import os
import csv
from io import StringIO
from datetime import date, time, datetime
from functools import wraps
from urllib.parse import urlparse, urljoin

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, Response, current_app
)
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash, check_password_hash

# ------------------------------------------------------------------------------
# App & sécurité
# ------------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "changeme-dev-key")

# Cookies sûrs (prod en HTTPS)
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# ------------------------------------------------------------------------------
# Base de données (Postgres/SQLite)
# ------------------------------------------------------------------------------
# --- Base de données (Postgres/SQLite) ---
db_url = os.getenv("DATABASE_URL", "sqlite:///pointage.db")

# Compat Postgres → psycopg3
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
# sslmode explicite si manquant (utile en prod Fly). En local SQLite, ça ne s'applique pas.
if db_url.startswith("postgresql+psycopg://") and "sslmode=" not in db_url:
    sep = "&" if "?" in db_url else "?"
    db_url = f"{db_url}{sep}sslmode=disable"

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# --- Engine options adaptées ---
engine_opts = {}

if db_url.startswith("postgresql+psycopg://"):
    # Options utiles pour Postgres (prod Fly)
    engine_opts = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_timeout": 10,
        "pool_size": 5,
        "max_overflow": 10,
        "connect_args": {
            "connect_timeout": 5,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        },
    }
elif db_url.startswith("sqlite:///") or db_url.startswith("sqlite://"):
    # SQLite : ne PAS passer d'arguments Postgres
    # Optionnel: autoriser l'accès multi-threads si besoin
    engine_opts = {
        "pool_pre_ping": True,
        "connect_args": {"check_same_thread": False},
    }

app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_opts



db = SQLAlchemy(app)
csrf = CSRFProtect(app)

# Exposer generate_csrf() à Jinja comme "csrf_token"
@app.context_processor
def csrf_token_processor():
    return dict(csrf_token=generate_csrf)

# ------------------------------------------------------------------------------
# Modèles
# ------------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # "user" | "admin"

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)


class Pointage(db.Model):
    __tablename__ = "pointage"
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(150), nullable=False)
    service = db.Column(db.String(100), nullable=True)  # Nature du pointage
    arrivee = db.Column(db.Time, nullable=False)
    depart = db.Column(db.Time, nullable=True)
    note = db.Column(db.String(300), nullable=True)
    jour = db.Column(db.Date, nullable=False, index=True, default=date.today)

# ------------------------------------------------------------------------------
# Bootstrap DB & admin initial (via secrets ADMIN_USERNAME / ADMIN_PASSWORD)
# ------------------------------------------------------------------------------
with app.app_context():
    db.create_all()
    admin_user = os.getenv("ADMIN_USERNAME")
    admin_pass = os.getenv("ADMIN_PASSWORD")
    if admin_user and admin_pass:
        u = User.query.filter_by(username=admin_user).first()
        if not u:
            u = User(username=admin_user, role="admin")
            u.set_password(admin_pass)
            db.session.add(u)
            db.session.commit()
        # si tu veux forcer le mot de passe depuis les secrets à chaque boot, décommente :
        # else:
        #     u.role = "admin"
        #     u.set_password(admin_pass)
        #     db.session.commit()

# ------------------------------------------------------------------------------
# Auth helpers + garde global
# ------------------------------------------------------------------------------
def is_safe_url(target):
    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))
    return redirect_url.scheme in ("http", "https") and host_url.netloc == redirect_url.netloc

def login_required(f):
    @wraps(f)
    def _wrap(*a, **kw):
        if not session.get("user_id"):
            nxt = request.full_path if request.query_string else request.path
            return redirect(url_for("login", next=nxt))
        return f(*a, **kw)
    return _wrap

def admin_required(f):
    @wraps(f)
    def _wrap(*a, **kw):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        if session.get("role") != "admin":
            flash("Accès réservé à l’administrateur.", "error")
            return redirect(url_for("index"))
        return f(*a, **kw)
    return _wrap

WHITELIST = {"login", "logout", "static", "healthz", "dbcheck"}

@app.before_request
def require_login_everywhere():
    # Autoriser login/logout/static/health
    if request.endpoint in WHITELIST:
        return
    # Rediriger vers /login si non connecté
    if not session.get("user_id"):
        nxt = request.full_path if request.query_string else request.path
        return redirect(url_for("login", next=nxt))

# ------------------------------------------------------------------------------
# Natures de pointage
# ------------------------------------------------------------------------------
POINTAGE_NATURES = [
    "TC - Travaux centre",
    "RC - Repos compensateur",
    "Déplacement",
    "PE - Permission exceptionnelle",
    "Congé",
    "Maladie",
    "Autre",
]

# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        try:
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            next_url = request.form.get("next") or request.args.get("next")

            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                session["user_id"] = user.id
                session["username"] = user.username
                session["role"] = user.role
                flash("Connexion réussie.", "success")
                if next_url and is_safe_url(next_url):
                    return redirect(next_url)
                return redirect(url_for("index"))
            flash("Nom d'utilisateur ou mot de passe incorrect.", "error")
            return redirect(url_for("login", next=next_url))
        except Exception:
            current_app.logger.exception("Erreur pendant /login")
            flash("Erreur serveur pendant la connexion.", "error")
            return redirect(url_for("login", next=request.args.get("next", "")))

    # GET
    next_url = request.args.get("next", "")
    return render_template("login.html", next_url=next_url)

@app.route("/logout")
def logout():
    session.clear()
    flash("Déconnecté.", "success")
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    # Saisie (POST)
    if request.method == "POST":
        try:
            nom = (request.form.get("nom") or "").strip()
            service = request.form.get("service") or None
            arrivee_str = request.form.get("arrivee") or ""
            depart_str = request.form.get("depart") or ""
            note = request.form.get("note") or None
            jour_str = request.form.get("jour") or ""

            if not nom:
                flash("Le nom est obligatoire.", "error")
                return redirect(url_for("index"))

            # Date (autorise antérieur)
            if jour_str:
                try:
                    jour = datetime.strptime(jour_str, "%Y-%m-%d").date()
                except ValueError:
                    flash("Format de date invalide.", "error")
                    return redirect(url_for("index"))
            else:
                jour = date.today()

            # Heures 24h
            def parse_time(s):
                if not s:
                    return None
                try:
                    hh, mm = s.split(":")
                    return time(int(hh), int(mm), 0)
                except Exception:
                    return None

            arrivee_t = parse_time(arrivee_str)
            depart_t = parse_time(depart_str)
            if not arrivee_t:
                flash("L’heure d’arrivée est obligatoire (format 24h HH:MM).", "error")
                return redirect(url_for("index"))

            p = Pointage(
                nom=nom, service=service,
                arrivee=arrivee_t, depart=depart_t,
                note=note, jour=jour
            )
            db.session.add(p)
            db.session.commit()
            flash("Pointage enregistré.", "success")
            return redirect(url_for("index", jour=jour.isoformat()))
        except OperationalError as e:
            current_app.logger.warning("OperationalError on INSERT, retry once: %s", e)
            db.session.rollback()
            flash("La base a été momentanément indisponible. Réessayez.", "error")
            return redirect(url_for("index"))
        except Exception:
            current_app.logger.exception("Erreur pendant la saisie du pointage")
            db.session.rollback()
            flash("Erreur serveur pendant l’enregistrement.", "error")
            return redirect(url_for("index"))

    # GET (liste du jour choisi ou du jour courant)
    try:
        jour_qs = request.args.get("jour")
        if jour_qs:
            try:
                the_day = datetime.strptime(jour_qs, "%Y-%m-%d").date()
            except ValueError:
                the_day = date.today()
        else:
            the_day = date.today()

        rows = (
            Pointage.query
            .filter(Pointage.jour == the_day)
            .order_by(Pointage.arrivee.asc())
            .all()
        )
    except OperationalError as e:
        current_app.logger.warning("OperationalError on SELECT, retry once: %s", e)
        db.session.rollback()
        the_day = date.today()
        rows = (
            Pointage.query
            .filter(Pointage.jour == the_day)
            .order_by(Pointage.arrivee.asc())
            .all()
        )

    is_admin = (session.get("role") == "admin")
    return render_template(
        "index.html",
        rows=rows,
        is_admin=is_admin,
        natures=POINTAGE_NATURES,
        today=the_day,
    )

@app.route("/admin")
@admin_required
def admin():
    try:
        users = User.query.order_by(User.id.asc()).all()
        today = date.today()
        rows = (
            Pointage.query
            .filter(Pointage.jour == today)
            .order_by(Pointage.arrivee.asc())
            .all()
        )
        return render_template("admin.html", users=users, rows=rows)
    except Exception:
        current_app.logger.exception("Erreur sur /admin")
        flash("Erreur serveur.", "error")
        return redirect(url_for("index"))

@app.route("/register", methods=["GET", "POST"])
@admin_required
def register():
    if request.method == "POST":
        try:
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            role = (request.form.get("role") or "user").strip()
            if not username or not password:
                flash("Nom d’utilisateur et mot de passe requis.", "error")
                return redirect(url_for("register"))
            if role not in ("user", "admin"):
                role = "user"
            if User.query.filter_by(username=username).first():
                flash("Ce nom d’utilisateur existe déjà.", "error")
                return redirect(url_for("register"))

            u = User(username=username, role=role)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            flash("Utilisateur créé.", "success")
            return redirect(url_for("admin"))
        except Exception:
            current_app.logger.exception("Erreur pendant /register (POST)")
            db.session.rollback()
            flash("Erreur serveur pendant la création.", "error")
            return redirect(url_for("register"))
    return render_template("register.html")

@app.post("/delete_pointage/<int:pid>")
@admin_required
def delete_pointage(pid):
    try:
        p = Pointage.query.get_or_404(pid)
        db.session.delete(p)
        db.session.commit()
        flash("Pointage supprimé.", "success")
    except Exception:
        current_app.logger.exception("Erreur suppression pointage")
        db.session.rollback()
        flash("Erreur serveur pendant la suppression.", "error")
    return redirect(url_for("admin"))

@app.post("/delete_user/<int:user_id>")
@admin_required
def delete_user(user_id):
    try:
        u = User.query.get_or_404(user_id)
        if u.username == session.get("username"):
            flash("Vous ne pouvez pas supprimer votre propre compte connecté.", "error")
            return redirect(url_for("admin"))
        db.session.delete(u)
        db.session.commit()
        flash("Utilisateur supprimé.", "success")
    except Exception:
        current_app.logger.exception("Erreur suppression utilisateur")
        db.session.rollback()
        flash("Erreur serveur pendant la suppression.", "error")
    return redirect(url_for("admin"))

@app.route("/export_csv")
@admin_required
def export_csv():
    try:
        rows = Pointage.query.order_by(Pointage.jour.desc(), Pointage.arrivee.asc()).all()
        si = StringIO()
        w = csv.writer(si, delimiter=";")
        w.writerow(["ID", "Date", "Nom", "Nature", "Arrivee", "Depart", "Note"])
        for r in rows:
            w.writerow([
                r.id,
                r.jour.isoformat(),
                r.nom,
                r.service or "",
                r.arrivee.strftime("%H:%M") if r.arrivee else "",
                r.depart.strftime("%H:%M") if r.depart else "",
                r.note or "",
            ])
        csv_text = si.getvalue()
        headers = {
            "Content-Disposition": "attachment; filename=pointages.csv"
        }
        return Response(csv_text, mimetype="text/csv; charset=utf-8", headers=headers)
    except Exception:
        current_app.logger.exception("Erreur export CSV")
        flash("Erreur serveur pendant l’export.", "error")
        return redirect(url_for("admin"))

# ------------------------------------------------------------------------------
# Diagnostics
# ------------------------------------------------------------------------------
@app.route("/healthz")
def healthz():
    return "ok", 200

@app.route("/dbcheck")
def dbcheck():
    try:
        cnt = db.session.execute(db.select(func.count(User.id))).scalar_one()
        return f"db ok, users={cnt}", 200
    except Exception as e:
        current_app.logger.exception("DB check failed")
        return f"db error: {e}", 500

# ------------------------------------------------------------------------------
# Main (dev local uniquement)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
