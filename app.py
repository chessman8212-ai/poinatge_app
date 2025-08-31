import os
import csv
from io import StringIO, BytesIO
from datetime import date
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_file, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.security import generate_password_hash, check_password_hash

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
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

# Exposer generate_csrf() à Jinja comme "csrf_token"
@app.context_processor
def csrf_token_processor():
    return dict(csrf_token=generate_csrf)

# --- Modèles ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), default="user")  # "user" / "admin"

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

class Pointage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)       # username du user connecté
    service = db.Column(db.String(100))
    arrivee = db.Column(db.String(10), nullable=False)
    depart = db.Column(db.String(10))
    note = db.Column(db.String(200))
    jour = db.Column(db.Date, default=date.today, index=True)

# --- Décorateurs ---
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

# --- Bootstrap : créer tables + 1er admin si nécessaire ---
with app.app_context():
    db.create_all()
    admin_user = os.getenv("ADMIN_USERNAME", "admin")
    admin_pass = os.getenv("ADMIN_PASSWORD", "admin123")
    if not User.query.filter_by(role="admin").first():
        if not User.query.filter_by(username=admin_user).first():
            u = User(username=admin_user, role="admin")
            u.set_password(admin_pass)
            db.session.add(u)
            db.session.commit()

# --- Routes ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            flash("Connexion réussie.", "success")
            return redirect(url_for("index"))
        flash("Nom d'utilisateur ou mot de passe incorrect.", "error")
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
        password = request.form.get("password") or ""
        role = request.form.get("role") or "user"

        if not username or not password:
            flash("Nom d'utilisateur et mot de passe sont requis.", "error")
            return redirect(url_for("register"))

        if User.query.filter_by(username=username).first():
            flash("Ce nom d'utilisateur existe déjà.", "error")
            return redirect(url_for("register"))

        u = User(username=username, role=role)
        u.set_password(password)
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
    rows = Pointage.query.order_by(Pointage.jour.asc(), Pointage.nom.asc()).all()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["id", "nom", "service", "arrivee", "depart", "note", "jour"])
    for r in rows:
        cw.writerow([r.id, r.nom, r.service or "", r.arrivee, r.depart or "", r.note or "", r.jour.isoformat()])
    data = si.getvalue().encode("utf-8")
    return send_file(
        BytesIO(data),
        mimetype="text/csv",
        as_attachment=True,
        download_name="pointages.csv"
    )

# 403 personnalisé (optionnel)
@app.errorhandler(403)
def forbidden(_e):
    return render_template("403.html"), 403
