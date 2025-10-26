import os, sqlite3, datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
DB_PATH = os.path.join(BASE_DIR, 'buracos.db')
ALLOWED_EXT = {'png','jpg','jpeg','gif'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'troque_esta_chave_por_uma_secreta'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS holes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        lat REAL,
        lng REAL,
        image TEXT,
        owner_id INTEGER,
        concluded INTEGER DEFAULT 0,
        created_at TEXT,
        FOREIGN KEY(owner_id) REFERENCES users(id)
    )''')
    c.execute("SELECT id FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username,password,is_admin) VALUES (?,?,1)",
                  ('admin', generate_password_hash('1234')))
    conn.commit(); conn.close()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXT

def current_user():
    uid = session.get('user_id')
    if not uid: return None
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id,username,is_admin FROM users WHERE id=?", (uid,))
    row = c.fetchone(); conn.close()
    return row

@app.route('/')
def index():
    user = current_user()
    return render_template('index.html', user=user)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        user = c.fetchone(); conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        flash('Usuário ou senha inválidos','danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('index'))

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        if not username or not password:
            flash('Preencha usuário e senha','warning'); return redirect(url_for('register'))
        conn = get_db(); c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username,password) VALUES (?,?)", (username, generate_password_hash(password)))
            conn.commit(); flash('Conta criada com sucesso. Faça login.','success'); return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Usuário já existe','danger')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/api/holes')
def api_holes():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT h.*, u.username as owner FROM holes h LEFT JOIN users u ON h.owner_id = u.id WHERE concluded=0 ORDER BY h.created_at DESC")
    rows = [dict(r) for r in c.fetchall()]; conn.close()
    return jsonify(rows)

@app.route('/submit', methods=['POST'])
def submit():
    user = current_user()
    if not user: flash('Faça login para registrar','warning'); return redirect(url_for('login'))
    title = request.form.get('title','').strip()
    description = request.form.get('description','').strip()
    lat = request.form.get('lat'); lng = request.form.get('lng')
    if not lat or not lng:
        flash('Coordenadas obrigatórias','warning'); return redirect(url_for('index'))
    image_name = None
    if 'image' in request.files:
        f = request.files['image']
        if f and allowed_file(f.filename):
            fname = secure_filename(f.filename)
            ts = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
            image_name = f"{ts}_{fname}"
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], image_name))
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO holes (title,description,lat,lng,image,owner_id,created_at) VALUES (?,?,?,?,?,?,?)",
              (title,description,float(lat),float(lng),image_name,user['id'], datetime.datetime.utcnow().isoformat()))
    conn.commit(); conn.close()
    flash('Registro salvo com sucesso','success')
    return redirect(url_for('index'))

@app.route('/conclude/<int:id>', methods=['POST'])
def conclude(id):
    user = current_user()
    if not user: flash('Faça login','warning'); return redirect(url_for('index'))
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT owner_id FROM holes WHERE id=?", (id,)); row = c.fetchone()
    if not row: flash('Registro não encontrado','warning'); conn.close(); return redirect(url_for('index'))
    if user['is_admin']!=1 and row['owner_id']!=user['id']:
        flash('Permissão negada','danger'); conn.close(); return redirect(url_for('index'))
    c.execute("UPDATE holes SET concluded=1 WHERE id=?", (id,)); conn.commit(); conn.close()
    flash('Registro marcado como concluído','success'); return redirect(url_for('index'))

@app.route('/admin')
def admin_panel():
    user = current_user()
    if not user or user['is_admin']!=1:
        flash('Acesso negado','danger'); return redirect(url_for('login'))
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT h.*, u.username as owner FROM holes h LEFT JOIN users u ON h.owner_id = u.id ORDER BY h.created_at DESC")
    rows = c.fetchall(); conn.close()
    return render_template('admin.html', rows=rows)

@app.route('/admin/delete/<int:id>', methods=['POST'])
def admin_delete(id):
    user = current_user()
    if not user or user['is_admin']!=1:
        flash('Acesso negado','danger'); return redirect(url_for('login'))
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT image FROM holes WHERE id=?", (id,)); r = c.fetchone()
    if r and r['image']:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], r['image']))
        except Exception:
            pass
    c.execute("DELETE FROM holes WHERE id=?", (id,)); conn.commit(); conn.close()
    flash('Registro excluído','success'); return redirect(url_for('admin_panel'))

@app.route('/uploads/<path:filename>')
def uploads(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__=='__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    init_db()
    app.run(debug=True)