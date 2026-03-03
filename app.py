import os
import secrets
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, abort, flash
from werkzeug.utils import secure_filename
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(16))
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 200
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "887321")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "mp4", "mov", "mkv", "avi", "pdf", "zip", "rar", "7z", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "txt"}

engine = create_engine(f"sqlite:///{os.path.join(BASE_DIR, 'site.db')}", future=True)
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False, unique=True)
    original_name = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def require_login():
    if not session.get("logged_in"):
        abort(403)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["logged_in"] = True
            flash("Berhasil masuk", "success")
            return redirect(url_for("dashboard"))
        flash("Kata sandi salah", "error")
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    db = SessionLocal()
    posts = db.query(Post).order_by(Post.uploaded_at.desc()).all()
    db.close()
    return render_template("dashboard.html", posts=posts)


@app.post("/upload")
def upload():
    require_login()
    if "file" not in request.files:
        flash("Tidak ada file yang dipilih", "error")
        return redirect(url_for("dashboard"))
    file = request.files["file"]
    if file.filename == "":
        flash("Nama file kosong", "error")
        return redirect(url_for("dashboard"))
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit(".", 1)[1].lower()
        new_name = f"{uuid.uuid4().hex}.{ext}"
        safe_name = secure_filename(new_name)
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
        file.save(save_path)
        db = SessionLocal()
        post = Post(filename=safe_name, original_name=file.filename, mime_type=file.mimetype or "")
        db.add(post)
        db.commit()
        db.close()
        flash("Upload berhasil", "success")
        return redirect(url_for("dashboard"))
    flash("Tipe file tidak diizinkan", "error")
    return redirect(url_for("dashboard"))


@app.get("/media/<path:fname>")
def media(fname):
    require_login()
    return send_from_directory(app.config["UPLOAD_FOLDER"], fname, as_attachment=False)


@app.get("/delete/<int:post_id>")
def delete_post(post_id):
    require_login()
    db = SessionLocal()
    post = db.query(Post).filter_by(id=post_id).first()
    if not post:
        db.close()
        flash("Item tidak ditemukan", "error")
        return redirect(url_for("dashboard"))
    path = os.path.join(app.config["UPLOAD_FOLDER"], post.filename)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
    db.delete(post)
    db.commit()
    db.close()
    flash("Item dihapus", "success")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=True)
