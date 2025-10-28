import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename
from PIL import Image
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
DB_URL = "sqlite:///" + os.path.join(BASE_DIR, "buracos.db")

os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {"png", "jpg", "jpeg"}
MAX_IMAGE_BYTES = 2 * 1024 * 1024  # 2 MB

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev"
app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_BYTES

Base = declarative_base()
engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

class Hole(Base):
    __tablename__ = "holes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(120), nullable=False)
    description = Column(String(1000), nullable=True)
    kind = Column(String(50), nullable=False, default="Buraco")
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    image_path = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="ativo")  # ativo|concluido
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

def save_image(file_storage):
    if not file_storage or file_storage.filename == "":
        return None
    filename = secure_filename(file_storage.filename)
    if not allowed_file(filename):
        abort(400, description="Formato de imagem inválido. Use JPG ou PNG.")
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    if size > MAX_IMAGE_BYTES:
        abort(400, description="Imagem maior que 2MB.")
    file_storage.seek(0)
    try:
        img = Image.open(file_storage.stream)
        img.verify()
    except Exception:
        abort(400, description="Arquivo enviado não é uma imagem válida.")
    file_storage.stream.seek(0)
    name, ext = os.path.splitext(filename)
    safe_name = f"{name}_{int(datetime.utcnow().timestamp())}{ext.lower()}"
    dest_path = os.path.join(UPLOAD_DIR, safe_name)
    file_storage.save(dest_path)
    return f"uploads/{safe_name}"

@app.route("/")
def index():
    return render_template("index.html", title="Alerta Buracos")

@app.get("/api/holes")
def api_get_holes():
    status = request.args.get("status", "ativo")
    with SessionLocal() as db:
        if status == "all":
            rows = db.query(Hole).order_by(Hole.created_at.desc()).all()
        else:
            rows = db.query(Hole).filter(Hole.status == status).order_by(Hole.created_at.desc()).all()
        data = [{
            "id": r.id,
            "title": r.title,
            "description": r.description,
            "kind": r.kind,
            "lat": r.lat,
            "lng": r.lng,
            "image_url": ("/static/" + r.image_path) if r.image_path else None,
            "status": r.status,
            "created_at": r.created_at.isoformat()
        } for r in rows]
        return jsonify(data)

@app.post("/api/holes")
def api_create_hole():
    title = (request.form.get("title") or "").strip() or "Buraco"
    description = (request.form.get("description") or "").strip()
    kind = (request.form.get("kind") or "Buraco").strip() or "Buraco"
    try:
        lat = float(request.form.get("lat"))
        lng = float(request.form.get("lng"))
    except (TypeError, ValueError):
        abort(400, description="Latitude e longitude são obrigatórias. Clique no mapa para preencher.")
    img_path = None
    if "image" in request.files and request.files["image"].filename:
        img_path = save_image(request.files["image"])
    with SessionLocal() as db:
        hole = Hole(title=title, description=description, kind=kind, lat=lat, lng=lng, image_path=img_path, status="ativo")
        db.add(hole)
        db.commit()
        db.refresh(hole)
        return jsonify({"ok": True, "id": hole.id}), 201

@app.post("/api/holes/<int:hid>/concluir")
def api_concluir(hid: int):
    with SessionLocal() as db:
        hole = db.query(Hole).get(hid)
        if not hole:
            abort(404)
        hole.status = "concluido"
        db.commit()
        return jsonify({"ok": True})

@app.delete("/api/holes/<int:hid>")
def api_delete(hid: int):
    with SessionLocal() as db:
        hole = db.query(Hole).get(hid)
        if not hole:
            abort(404)
        if hole.image_path:
            try:
                os.remove(os.path.join(BASE_DIR, "static", hole.image_path))
            except Exception:
                pass
        db.delete(hole)
        db.commit()
        return jsonify({"ok": True})

@app.route('/static/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
