import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import csv
from io import StringIO
from datetime import date
from flask_wtf.csrf import CSRFProtect, generate_csrf
CSRFProtect(app)

@app.context_processor
def csrf_token_processor():
    return dict(csrf_token=generate_csrf)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "changeme")

# Base de données (Postgres ou SQLite)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///pointage.db")
if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgres://"):
    app.config["SQLALCHEMY_DATABASE_URI"] = app.config["SQLALCHEMY_DATABASE_URI"].replace("postgres://", "postgresql+psycopg2://")

db = SQLAlchemy(app)

# ---------- Modèles ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), default="user")  # "user" ou "admin"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Pointage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    service = db.Column(db.String(100))
    arrivee = db.Column(db.String(10), nullable=False)
    depart = db.Column(db.String(10))
    note = db.Column(db.String(200))
    date = db.Column(db.Date, default=date.today)

# ---------- Décorateurs ----------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Accès réservé à l'administrateur", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function

# ---------- Routes ----------
@app.route("/register", methods=["GET", "POST"])
@admin_required
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form.get("role", "user")

        if User.query.filter_by(username=username).first():
            flash("Nom d'utilisateur déjà utilisé.", "error")
            return redirect(url_for("register"))

        user = User(username=username, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Utilisateur créé avec succès.", "success")
        return redirect(url_for("admin"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            return redirect(url_for("index"))
        else:
            flash("Nom d'utilisateur ou mot de passe incorrect.", "error")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        nom = session.get("username")  # prend automatiquement le nom connecté
        service = request.form.get("service")
        arrivee = request.form.get("arrivee")
        depart = request.form.get("depart")
        note = request.form.get("note")

        p = Pointage(nom=nom, service=service, arrivee=arrivee, depart=depart, note=note)
        db.session.add(p)
        db.session.commit()

        flash("Pointage enregistré.", "success")
        return redirect(url_for("index"))

    if session.get("role") == "admin":
    rows = Pointage.query.filter_by(date=date.today()).all()
else:
    rows = Pointage.query.filter_by(date=date.today(), nom=session["username"]).all()

    return render_template("index.html", today=date.today(), rows=rows)

@app.route("/admin")
@admin_required
def admin():
    rows = Pointage.query.order_by(Pointage.date.desc()).all()
    users = User.query.all()
    return render_template("admin.html", rows=rows, users=users)

@app.route("/delete_user/<int:user_id>", methods=["POST"])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    # empêcher la suppression de soi-même
    if user.id == session.get("user_id"):
        flash("Vous ne pouvez pas supprimer votre propre compte.", "error")
        return redirect(url_for("admin"))

    db.session.delete(user)
    db.session.commit()
    flash("Utilisateur supprimé avec succès.", "success")
    return redirect(url_for("admin"))

@app.route("/export_csv")
@admin_required
def export_csv():
    rows = Pointage.query.all()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["Nom", "Service", "Arrivée", "Départ", "Note", "Date"])
    for r in rows:
        cw.writerow([r.nom, r.service, r.arrivee, r.depart, r.note, r.date])
    output = si.getvalue().encode("utf-8")
    return send_file(
        StringIO(si.getvalue()), 
        mimetype="text/csv", 
        as_attachment=True, 
        download_name="pointages.csv"
    )

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
