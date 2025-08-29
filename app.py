
import os, datetime, csv, io
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session, abort
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, Integer, String, Date, Text, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from dotenv import load_dotenv
load_dotenv()
class Base(DeclarativeBase):
    pass
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user")
class Pointage(Base):
    __tablename__ = "pointages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom: Mapped[str] = mapped_column(String(120))
    service: Mapped[str] = mapped_column(String(120), nullable=True)
    arrivee: Mapped[str] = mapped_column(String(8))
    depart: Mapped[str] = mapped_column(String(8), nullable=True)
    date_pointage: Mapped[datetime.date] = mapped_column(Date, default=datetime.date.today)
    note: Mapped[str] = mapped_column(Text, nullable=True)
def get_database_url():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return "sqlite:///pointage.db"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url
def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "change_me")
    CSRFProtect(app)
    engine = create_engine(get_database_url(), pool_pre_ping=True)
    Base.metadata.create_all(engine)
    from sqlalchemy.exc import SQLAlchemyError
    with Session(engine) as s:
        admin_u = os.getenv("ADMIN_USERNAME", "admin")
        admin_p = os.getenv("ADMIN_PASSWORD", "admin123")
        try:
            existing_admin = s.execute(select(User).where(User.role == "admin")).scalar_one_or_none()
        except SQLAlchemyError:
            existing_admin = None
        if existing_admin is None:
            existing = s.execute(select(User).where(User.username == admin_u)).scalar_one_or_none()
            if existing is None:
                s.add(User(username=admin_u, password_hash=generate_password_hash(admin_p), role="admin"))
                s.commit()
    def is_admin():
        return session.get("role") == "admin"
    @app.context_processor
    def inject_globals():
        return {"is_admin": is_admin()}
    @app.route("/", methods=["GET", "POST"])
    def index():
        with Session(engine) as s:
            if request.method == "POST":
                nom = (request.form.get("nom") or "").strip()
                service = (request.form.get("service") or "").strip()
                arrivee = (request.form.get("arrivee") or "").strip()
                depart = (request.form.get("depart") or "").strip()
                note = (request.form.get("note") or "").strip()
                if not nom or not arrivee:
                    flash("Nom et Heure d’arrivée sont obligatoires.", "error")
                    return redirect(url_for("index"))
                rec = Pointage(nom=nom, service=service or None, arrivee=arrivee, depart=depart or None, date_pointage=datetime.date.today(), note=note or None)
                s.add(rec)
                s.commit()
                flash("Pointage enregistré ✅", "success")
                return redirect(url_for("index"))
            today = datetime.date.today()
            rows = s.execute(select(Pointage).where(Pointage.date_pointage == today).order_by(Pointage.arrivee.asc())).scalars().all()
            return render_template("index.html", rows=rows, today=today.isoformat())
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            with Session(engine) as s:
                user = s.execute(select(User).where(User.username == username)).scalar_one_or_none()
                if user and check_password_hash(user.password_hash, password):
                    session["username"] = user.username
                    session["role"] = user.role
                    flash("Connexion réussie.", "success")
                    return redirect(url_for("admin" if user.role == "admin" else "index"))
            flash("Identifiants incorrects.", "error")
            return redirect(url_for("login"))
        return render_template("login.html")
    @app.route("/logout")
    def logout():
        session.clear()
        flash("Déconnecté.", "success")
        return redirect(url_for("index"))
    def require_admin():
        if not is_admin():
            abort(403)
    @app.route("/admin")
    def admin():
        require_admin()
        with Session(engine) as s:
            rows = s.execute(select(Pointage).order_by(Pointage.date_pointage.desc(), Pointage.arrivee.asc())).scalars().all()
            stats = s.execute(select(Pointage.date_pointage,  func.count(Pointage.id)).group_by(Pointage.date_pointage).order_by(Pointage.date_pointage.desc())).all()
        return render_template("admin.html", rows=rows, stats=stats)
    @app.route("/delete/<int:pid>", methods=["POST"])
    def delete(pid):
        require_admin()
        with Session(engine) as s:
            p = s.get(Pointage, pid)
            if p:
                s.delete(p)
                s.commit()
        flash("Enregistrement supprimé 🗑️", "success")
        return redirect(url_for("admin"))
    @app.route("/export_csv")
    def export_csv():
        require_admin()
        with Session(engine) as s:
            rows = s.execute(select(Pointage).order_by(Pointage.date_pointage.desc(), Pointage.arrivee.asc())).scalars().all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id","nom","service","arrivee","depart","date_pointage","note"])
        for r in rows:
            writer.writerow([r.id, r.nom, r.service or "", r.arrivee, r.depart or "", r.date_pointage.isoformat(), r.note or ""])
        output.seek(0)
        return send_file(io.BytesIO(output.getvalue().encode("utf-8")), mimetype="text/csv", as_attachment=True, download_name="pointages.csv")
    return app
app = create_app()
