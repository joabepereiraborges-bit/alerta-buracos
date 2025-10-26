
import os, sqlite3, datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join("/tmp" if os.environ.get("RENDER") else BASE_DIR, "buracos.db"))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif"}
MAX_IMG_SIZE = 2 * 1024 * 1024  # 2MB

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_IMG_SIZE + 51200  # margem extra para multipart boundaries
app.secret_key = os.environ.get("SECRET_KEY", "troque_esta_chave_por_uma_secreta")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_schema(conn):
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS holes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        lat REAL,
        lng REAL,
        image TEXT,
        owner_id INTEGER,
        concluded INTEGER DEFAULT 0,
        neighborhood TEXT,
        created_at TEXT,
        FOREIGN KEY(owner_id) REFERENCES users(id)
    )""")
    # garantir coluna neighborhood para compatibilidade com versões antigas
    c.execute("PRAGMA table_info(holes)")
    cols = [r[1] for r in c.fetchall()]
    if "neighborhood" not in cols:
        try:
            c.execute("ALTER TABLE holes ADD COLUMN neighborhood TEXT")
        except Exception:
            pass
    conn.commit()

def init_db(fresh=False):
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    if fresh and os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except Exception:
            pass
    conn = get_db()
    ensure_schema(conn)
    c = conn.cursor()
    # criar admin padrão se não existir
    c.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    if not c.fetchone():
        c.execute("INSERT INTO users (username,password,is_admin) VALUES (?,?,1)",
                  ("admin", generate_password_hash("1234")))
    conn.commit(); conn.close()

def current_user():
    uid = session.get("user_id")
    if not uid: return None
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id, username, is_admin FROM users WHERE id=?", (uid,))
    row = c.fetchone(); conn.close()
    return row

def allowed_file(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXT

def is_image_file(path):
    # valida usando Pillow (robusto e compatível com Python 3.13+)
    try:
        with Image.open(path) as img:
            img.verify()  # verifica a integridade
        return True
    except Exception:
        return False

@app.route("/")
def index():
    return render_template("index.html", user=current_user())

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        if not username or not password:
            flash("Informe usuário e senha.", "warning")
            return redirect(url_for("login"))
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        user = c.fetchone(); conn.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("index"))
        flash("Usuário ou senha inválidos.", "danger")
    return render_template("login.html", user=current_user())

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        if not username or not password:
            flash("Informe usuário e senha.", "warning")
            return redirect(url_for("register"))
        try:
            conn = get_db(); c = conn.cursor()
            c.execute("INSERT INTO users (username,password) VALUES (?,?)", (username, generate_password_hash(password)))
            conn.commit(); conn.close()
            flash("Conta criada. Faça login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Usuário já existe.", "danger")
    return render_template("register.html", user=current_user())

@app.route("/api/holes")
def api_holes():
    show_concluded = request.args.get("show_concluded", "0")
    neighborhood = request.args.get("neighborhood", "").strip()

    where = []
    params = []
    if show_concluded != "1":
        where.append("concluded = 0")
    if neighborhood:
        where.append("LOWER(COALESCE(neighborhood,'')) LIKE ?")
        params.append(f"%{neighborhood.lower()}%")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""SELECT h.*, u.username AS owner
              FROM holes h LEFT JOIN users u ON h.owner_id = u.id
              {where_sql}
              ORDER BY h.created_at DESC"""
    conn = get_db(); c = conn.cursor()
    c.execute(sql, params)
    rows = [dict(r) for r in c.fetchall()]; conn.close()
    return jsonify(rows)

@app.route("/submit", methods=["POST"])
def submit():
    user = current_user()
    if not user:
        flash("Faça login para registrar.", "warning")
        return redirect(url_for("login"))
    title = request.form.get("title","").strip()
    description = request.form.get("description","").strip()
    lat = request.form.get("lat"); lng = request.form.get("lng")
    neighborhood = request.form.get("neighborhood","").strip()
    if not lat or not lng:
        flash("Selecione as coordenadas no mapa.", "warning")
        return redirect(url_for("index"))

    image_name = None
    if "image" in request.files and request.files["image"].filename:
        f = request.files["image"]
        if not allowed_file(f.filename):
            flash("Formato de imagem inválido. Use png/jpg/jpeg/gif.", "danger")
            return redirect(url_for("index"))
        f.seek(0, os.SEEK_END); size = f.tell(); f.seek(0)
        if size > MAX_IMG_SIZE:
            flash("Imagem acima de 2MB.", "danger")
            return redirect(url_for("index"))
        fname = secure_filename(f.filename)
        ts = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        image_name = f"{ts}_{fname}"
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], image_name)
        f.save(save_path)
        if not is_image_file(save_path):
            try: os.remove(save_path)
            except Exception: pass
            flash("Arquivo enviado não é uma imagem válida.", "danger")
            return redirect(url_for("index"))

    conn = get_db(); c = conn.cursor()
    c.execute("""INSERT INTO holes (title,description,lat,lng,image,owner_id,neighborhood,created_at)
                 VALUES (?,?,?,?,?,?,?,?)""",
              (title, description, float(lat), float(lng), image_name, user["id"], neighborhood or None, datetime.datetime.utcnow().isoformat()))
    conn.commit(); conn.close()
    flash("Registro salvo com sucesso.", "success")
    return redirect(url_for("index"))

@app.route("/conclude/<int:hid>", methods=["POST"])
def conclude(hid):
    user = current_user()
    if not user:
        flash("Faça login.", "warning")
        return redirect(url_for("login"))
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT owner_id FROM holes WHERE id=?", (hid,))
    row = c.fetchone()
    if not row:
        conn.close()
        flash("Registro não encontrado.", "warning")
        return redirect(url_for("index"))
    if user["is_admin"] != 1 and row["owner_id"] != user["id"]:
        conn.close()
        flash("Permissão negada.", "danger")
        return redirect(url_for("index"))
    c.execute("UPDATE holes SET concluded=1 WHERE id=?", (hid,))
    conn.commit(); conn.close()
    flash("Registro marcado como concluído.", "success")
    return redirect(url_for("index"))

@app.route("/admin")
def admin_panel():
    user = current_user()
    if not user or user["is_admin"] != 1:
        flash("Acesso negado.", "danger")
        return redirect(url_for("login"))
    conn = get_db(); c = conn.cursor()
    c.execute("""SELECT h.*, u.username AS owner
                 FROM holes h LEFT JOIN users u ON h.owner_id = u.id
                 ORDER BY h.created_at DESC""")
    rows = c.fetchall(); conn.close()
    return render_template("admin.html", rows=rows, user=user)

@app.route("/admin/delete/<int:hid>", methods=["POST"])
def admin_delete(hid):
    user = current_user()
    if not user or user["is_admin"] != 1:
        flash("Acesso negado.", "danger")
        return redirect(url_for("login"))
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT image FROM holes WHERE id=?", (hid,))
    r = c.fetchone()
    if r and r["image"]:
        try:
            os.remove(os.path.join(app.config["UPLOAD_FOLDER"], r["image"]))
        except Exception:
            pass
    c.execute("DELETE FROM holes WHERE id=?", (hid,))
    conn.commit(); conn.close()
    flash("Registro excluído.", "success")
    return redirect(url_for("admin_panel"))

@app.route("/uploads/<path:filename>")
def uploads(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

if __name__ == "__main__":
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    # fresh=True garante um banco limpo ao rodar localmente pela primeira vez desta versão
    init_db(fresh=False)
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
