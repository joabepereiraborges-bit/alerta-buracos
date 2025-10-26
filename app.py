import os, sqlite3
from datetime import datetime
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory, flash
from PIL import Image

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'static', 'uploads')
DB_PATH = os.path.join('/tmp' if os.environ.get('RENDER') else BASE_DIR, 'buracos.db')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY','dev-key')
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with get_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS holes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, description TEXT,
            lat REAL, lng REAL, neighborhood TEXT,
            image TEXT, concluded INTEGER DEFAULT 0,
            created_at TEXT
        )""")
        conn.commit()

@app.get('/')
def index():
    return render_template('index.html', title='Mapa')

@app.get('/api/holes')
def api_holes():
    show_concluded = request.args.get('show_concluded','0') == '1'
    neighborhood = (request.args.get('neighborhood') or '').strip().lower()
    with get_conn() as conn:
        rows = conn.execute('SELECT * FROM holes').fetchall()
    out = []
    for r in rows:
        if not show_concluded and r['concluded']:
            continue
        if neighborhood and r['neighborhood'] and neighborhood not in r['neighborhood'].lower():
            continue
        out.append({
            'id': r['id'],
            'title': r['title'],
            'description': r['description'],
            'lat': r['lat'],
            'lng': r['lng'],
            'neighborhood': r['neighborhood'],
            'image': r['image'],
            'concluded': bool(r['concluded']),
            'created_at': r['created_at']
        })
    return jsonify(out)

def _save_image(storage):
    try:
        raw = storage.read()
        if len(raw) > 2*1024*1024:
            raise ValueError('Arquivo excede 2MB')
        img = Image.open(BytesIO(raw))
        img.verify()
    except Exception:
        raise ValueError('Imagem inválida ou corrompida.')
    ext = os.path.splitext(storage.filename or '')[1].lower()
    if ext not in ['.jpg','.jpeg','.png','.webp']:
        ext = '.jpg'
    fname = f"img_{int(datetime.utcnow().timestamp())}{ext}"
    path = os.path.join(UPLOAD_DIR, fname)
    img = Image.open(BytesIO(raw)).convert('RGB')
    img.save(path, format='JPEG', quality=85)
    return fname

@app.post('/submit')
def submit():
    title = request.form.get('title') or ''
    description = request.form.get('description') or ''
    lat = request.form.get('lat')
    lng = request.form.get('lng')
    neighborhood = request.form.get('neighborhood') or ''
    image_name = None

    if not lat or not lng:
        flash('Defina latitude e longitude clicando no mapa.', 'danger')
        return redirect(url_for('index'))

    file = request.files.get('image')
    if file and file.filename:
        try:
            image_name = _save_image(file)
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('index'))

    with get_conn() as conn:
        conn.execute("""INSERT INTO holes(title, description, lat, lng, neighborhood, image, concluded, created_at)
                        VALUES(?,?,?,?,?,?,0,?)""", (title, description, float(lat), float(lng), neighborhood, image_name, datetime.utcnow().isoformat()))
        conn.commit()
    flash('Ocorrência registrada com sucesso!', 'success')
    return redirect(url_for('index'))

@app.post('/conclude/<int:hid>')
def conclude(hid):
    with get_conn() as conn:
        conn.execute('UPDATE holes SET concluded=1 WHERE id=?', (hid,))
        conn.commit()
    return redirect(url_for('index'))

@app.get('/uploads/<path:filename>')
def uploads(filename):
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=False)

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
