import os
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
from werkzeug.utils import secure_filename
import sqlite3
from datetime import datetime

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB limit

DB = 'buracos.db'

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS buraco (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        lat REAL,
        lng REAL,
        image TEXT,
        status TEXT,
        created_at TEXT
    )''')
    conn.commit()
    conn.close()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/list', methods=['GET'])
def api_list():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, title, description, lat, lng, image, status, created_at FROM buraco ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    data = []
    for r in rows:
        data.append({
            "id": r[0],
            "title": r[1],
            "description": r[2],
            "lat": r[3],
            "lng": r[4],
            "image": r[5],
            "status": r[6],
            "created_at": r[7]
        })
    return jsonify(data)

@app.route('/api/register', methods=['POST'])
def api_register():
    title = request.form.get('title') or "Buraco reportado"
    description = request.form.get('description') or ""
    lat = request.form.get('lat')
    lng = request.form.get('lng')
    status = request.form.get('status') or "Registrada"
    if not lat or not lng:
        return jsonify({"error": "Coordenadas são obrigatórias."}), 400
    image_filename = None
    if 'image' in request.files:
        file = request.files['image']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            name = f"{int(datetime.utcnow().timestamp())}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], name)
            file.save(filepath)
            image_filename = name
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    ts = datetime.utcnow().isoformat()
    c.execute("INSERT INTO buraco (title, description, lat, lng, image, status, created_at) VALUES (?,?,?,?,?,?,?)",
              (title, description, float(lat), float(lng), image_filename, status, ts))
    conn.commit()
    conn.close()
    return jsonify({"status":"ok"}), 201

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/admin')
def admin():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, title, description, lat, lng, image, status, created_at FROM buraco ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return render_template('admin.html', rows=rows)

@app.route('/admin/delete/<int:id>', methods=['POST'])
def admin_delete(id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT image FROM buraco WHERE id=?", (id,))
    r = c.fetchone()
    if r and r[0]:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], r[0]))
        except Exception:
            pass
    c.execute("DELETE FROM buraco WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
