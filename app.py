
import os, sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'static', 'uploads')
DB_PATH = os.path.join(BASE_DIR, 'buracos.db')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with get_conn() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS holes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, description TEXT,
            lat REAL, lng REAL, created_at TEXT
        )''')
        conn.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.post('/submit')
def submit():
    title = request.form.get('title')
    desc = request.form.get('description')
    lat = request.form.get('lat')
    lng = request.form.get('lng')
    if not lat or not lng:
        flash('Clique no mapa para preencher latitude e longitude.', 'danger')
        return redirect(url_for('index'))
    with get_conn() as conn:
        conn.execute('INSERT INTO holes (title, description, lat, lng, created_at) VALUES (?, ?, ?, ?, ?)',
                     (title, desc, float(lat), float(lng), datetime.utcnow().isoformat()))
        conn.commit()
    flash('Buraco registrado!', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
