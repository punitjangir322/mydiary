from flask import Flask, render_template_string, request, redirect, session, send_from_directory, g
import sqlite3, os, uuid
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'supersecretkey123!@#')

# Railway environment
DATABASE = "diary.db"
UPLOAD_FOLDER = "uploads"

# Create directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------- DATABASE CONNECTION ----------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()

# ---------------- INIT DATABASE ----------------

def init_db():
    """Initialize database with tables and admin user"""
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA foreign_keys = ON")
    
    # Check if tables exist
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not cursor.fetchone():
        # Create tables
        db.executescript("""
        CREATE TABLE users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE entries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE photos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(entry_id) REFERENCES entries(id) ON DELETE CASCADE
        );
        """)

        # Create admin user
        db.execute("INSERT INTO users (username,password) VALUES (?,?)",
                   ("admin", generate_password_hash("admin123")))
        db.commit()
    
    db.close()

# Initialize database
init_db()

# ---------------- LOGIN PAGE TEMPLATE ----------------

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<title>Login - Personal Diary</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:'Poppins',sans-serif;}
body{background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;}
.login-card{width:100%;max-width:400px;background:white;padding:40px;border-radius:20px;box-shadow:0 20px 40px rgba(0,0,0,0.2);}
h2{text-align:center;color:#333;margin-bottom:30px;font-size:28px;}
.tabs{display:flex;margin-bottom:30px;border-bottom:2px solid #eee;}
.tab{flex:1;text-align:center;padding:10px;cursor:pointer;color:#666;transition:all 0.3s;font-weight:500;}
.tab.active{color:#667eea;border-bottom:2px solid #667eea;margin-bottom:-2px;}
.form-container{padding:20px 0;}
.form-group{margin-bottom:20px;}
label{display:block;margin-bottom:5px;color:#555;font-weight:500;}
input{width:100%;padding:12px;border:2px solid #e0e0e0;border-radius:10px;font-size:14px;transition:all 0.3s;}
input:focus{outline:none;border-color:#667eea;}
button{width:100%;padding:14px;background:#667eea;color:white;border:none;border-radius:10px;font-size:16px;font-weight:600;cursor:pointer;transition:all 0.3s;}
button:hover{background:#5a67d8;transform:translateY(-2px);box-shadow:0 5px 15px rgba(102,126,234,0.4);}
button.signup-btn{background:#48bb78;}
button.signup-btn:hover{background:#38a169;}
.message{padding:12px;border-radius:8px;margin-bottom:20px;text-align:center;}
.success{background:#c6f6d5;color:#22543d;border:1px solid #9ae6b4;}
.error{background:#fed7d7;color:#742a2a;border:1px solid #feb2b2;}
.switch-text{text-align:center;margin-top:20px;color:#666;}
.switch-text span{color:#667eea;cursor:pointer;font-weight:600;}
.switch-text span:hover{text-decoration:underline;}
.info-box{background:#e6f7ff;border:1px solid #91d5ff;padding:10px;border-radius:8px;margin-bottom:20px;text-align:center;color:#0050b3;}
.info-box strong{color:#1890ff;}
</style>
</head>
<body>
<div class="login-card">
    <h2>📔 Personal Diary</h2>
    
    <div class="info-box">
        <strong>Admin Login:</strong> admin / admin123
    </div>
    
    {% if message %}
    <div class="message {{message_type}}">{{message}}</div>
    {% endif %}
    
    <div class="tabs">
        <div class="tab {% if active_tab == 'login' %}active{% endif %}" onclick="showLogin()">Login</div>
        <div class="tab {% if active_tab == 'signup' %}active{% endif %}" onclick="showSignup()">Sign Up</div>
    </div>
    
    <div id="login-form" class="form-container" {% if active_tab == 'signup' %}style="display:none;"{% endif %}>
        <form method="post" action="/login">
            <div class="form-group">
                <label>Username</label>
                <input type="text" name="username" required autocomplete="off">
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit">Login</button>
        </form>
        <div class="switch-text">
            Don't have an account? <span onclick="showSignup()">Sign up here</span>
        </div>
    </div>
    
    <div id="signup-form" class="form-container" {% if active_tab == 'login' %}style="display:none;"{% endif %}>
        <form method="post" action="/signup">
            <div class="form-group">
                <label>Username</label>
                <input type="text" name="username" required autocomplete="off">
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit" class="signup-btn">Create Account</button>
        </form>
        <div class="switch-text">
            Already have an account? <span onclick="showLogin()">Login here</span>
        </div>
    </div>
</div>

<script>
function showLogin() {
    document.getElementById('login-form').style.display = 'block';
    document.getElementById('signup-form').style.display = 'none';
    document.querySelectorAll('.tab')[0].classList.add('active');
    document.querySelectorAll('.tab')[1].classList.remove('active');
}

function showSignup() {
    document.getElementById('login-form').style.display = 'none';
    document.getElementById('signup-form').style.display = 'block';
    document.querySelectorAll('.tab')[0].classList.remove('active');
    document.querySelectorAll('.tab')[1].classList.add('active');
}
</script>
</body>
</html>
"""

# ---------------- MAIN APP TEMPLATE ----------------

MAIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<title>Premium Diary</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:'Poppins',sans-serif;}
body{background:linear-gradient(135deg,#667eea,#764ba2);height:100vh;overflow:hidden;}
.header{background:rgba(0,0,0,0.7);color:white;padding:15px 25px;display:flex;justify-content:space-between;align-items:center;}
.container{display:flex;height:calc(100vh - 60px);}
.sidebar{width:30%;background:rgba(255,255,255,0.15);backdrop-filter:blur(15px);padding:20px;overflow-y:auto;color:white;}
.editor{flex:1;background:white;padding:25px;overflow-y:auto;}
.entry-card{background:rgba(255,255,255,0.25);padding:12px;border-radius:10px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center;transition:all 0.3s;}
.entry-card:hover{background:rgba(255,255,255,0.35);}
.entry-card b{color:white;}
input,textarea{width:100%;padding:10px;margin-bottom:12px;border-radius:8px;border:1px solid #ddd;}
textarea{min-height:200px;}
button{padding:8px 15px;border:none;border-radius:6px;cursor:pointer;margin:5px;transition:all 0.3s;}
button:hover{opacity:0.9;transform:translateY(-1px);}
.primary{background:#667eea;color:white;}
.secondary{background:#48bb78;color:white;}
.danger{background:#f56565;color:white;}
.edit{background:#f6ad55;color:white;}
img{max-width:100%;margin-top:10px;border-radius:8px;}
.flash-message{padding:10px;border-radius:5px;margin-bottom:15px;text-align:center;}
.success{background:#48bb78;color:white;}
.error{background:#f56565;color:white;}
.user-item{background:rgba(255,255,255,0.25);padding:12px;border-radius:10px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center;}
.user-item b{color:white;}
.entry-preview{font-size:12px;opacity:0.8;margin-top:3px;}
.empty-state{text-align:center;color:#666;margin-top:50px;}
@media(max-width:768px){.container{flex-direction:column;}.sidebar{width:100%;height:40%;}.editor{height:60%;}}
</style>
</head>
<body>

<div class="header">
    <h3>📔 {{session['user']}}'s Diary</h3>
    <div>
        <a href="/" style="color:white;margin-right:15px;">Home</a>
        <a href="/logout"><button class="danger">Logout</button></a>
    </div>
</div>

<div class="container">

<div class="sidebar">
    {% if session.get('is_admin') %}
    <h3>👥 All Users ({{users|length}})</h3>
    {% for u in users %}
    <div class="user-item">
        <b>{{u.username}}</b>
        <a href="/admin_login/{{u.id}}">
            <button class="primary">Login as {{u.username}}</button>
        </a>
    </div>
    {% endfor %}
    {% else %}
    <h3>📝 Your Entries ({{entries|length}})</h3>
    <a href="/new"><button class="primary" style="width:100%;margin-bottom:15px;">+ New Entry</button></a>
    
    {% if entries %}
        {% for e in entries %}
        <div class="entry-card">
            <div>
                <b>{{e.date}}</b>
                {% if e.preview %}
                <div class="entry-preview">{{e.preview[:20]}}...</div>
                {% endif %}
            </div>
            <a href="/view/{{e.id}}">
                <button class="secondary">View</button>
            </a>
        </div>
        {% endfor %}
    {% else %}
        <p style="text-align:center;opacity:0.7;">No entries yet. Create your first diary entry!</p>
    {% endif %}
    {% endif %}
</div>

<div class="editor">
    {% if message %}
    <div class="flash-message {{message_type}}">{{message}}</div>
    {% endif %}
    
    {{content|safe}}
</div>

</div>

</body>
</html>
"""

# ---------------- ROUTES ----------------

@app.route("/")
def home():
    if not session.get("user"):
        return render_template_string(LOGIN_TEMPLATE, active_tab='login')
    
    db = get_db()
    
    if session.get("is_admin"):
        users = db.execute("SELECT id, username FROM users WHERE username != 'admin' ORDER BY username").fetchall()
        return render_template_string(MAIN_TEMPLATE, users=users)
    
    entries = db.execute("""
        SELECT id, date, 
               substr(content, 1, 30) as preview 
        FROM entries 
        WHERE user_id = ? 
        ORDER BY date DESC, created_at DESC
    """, (session["user_id"],)).fetchall()
    
    return render_template_string(MAIN_TEMPLATE, entries=entries, content="<h3 class='empty-state'>👈 Select an entry from sidebar or create new</h3>")

@app.route("/signup", methods=["POST"])
def signup():
    username = request.form["username"].strip()
    password = request.form["password"]
    
    if not username or not password:
        return render_template_string(LOGIN_TEMPLATE, 
                                    message="Username and password required", 
                                    message_type="error",
                                    active_tab='signup')
    
    if len(password) < 4:
        return render_template_string(LOGIN_TEMPLATE, 
                                    message="Password must be at least 4 characters", 
                                    message_type="error",
                                    active_tab='signup')
    
    db = get_db()
    try:
        db.execute("INSERT INTO users (username, password) VALUES (?,?)",
                   (username, generate_password_hash(password)))
        db.commit()
        return render_template_string(LOGIN_TEMPLATE, 
                                    message="Account created! Please login.", 
                                    message_type="success",
                                    active_tab='login')
    except sqlite3.IntegrityError:
        return render_template_string(LOGIN_TEMPLATE, 
                                    message="Username already exists", 
                                    message_type="error",
                                    active_tab='signup')

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"].strip()
    password = request.form["password"]
    
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?",
                      (username,)).fetchone()
    
    if user and check_password_hash(user["password"], password):
        session["user"] = user["username"]
        session["user_id"] = user["id"]
        session["is_admin"] = (user["username"] == "admin")
        return redirect("/")
    
    return render_template_string(LOGIN_TEMPLATE, 
                                message="Invalid username or password", 
                                message_type="error",
                                active_tab='login')

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/admin_login/<int:id>")
def admin_login(id):
    if not session.get("is_admin"):
        return redirect("/")
    
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (id,)).fetchone()
    
    if user:
        session["user"] = user["username"]
        session["user_id"] = user["id"]
        session["is_admin"] = False
        return redirect("/")
    
    return redirect("/")

@app.route("/new")
def new():
    if not session.get("user"):
        return redirect("/")
    
    today = datetime.now().strftime("%Y-%m-%d")
    form = f"""
    <h3 style="color:#333;margin-bottom:20px;">📝 New Diary Entry</h3>
    <form method='post' action='/save' enctype='multipart/form-data' style="max-width:600px;margin:0 auto;">
        <label style="font-weight:600;color:#555;">Date:</label>
        <input type='date' name='date' value='{today}' required style="margin-bottom:20px;">
        
        <label style="font-weight:600;color:#555;">Your thoughts:</label>
        <textarea name='content' placeholder="Write your diary entry here..." required style="min-height:150px;"></textarea>
        
        <label style="font-weight:600;color:#555;">Photos (optional):</label>
        <input type='file' name='photos' multiple accept="image/*" style="padding:5px;">
        <small style="display:block;color:#666;margin-bottom:15px;">You can select multiple photos</small>
        
        <div style="display:flex;gap:10px;">
            <button type='submit' class='primary'>💾 Save Entry</button>
            <a href='/'><button type='button' class='danger'>Cancel</button></a>
        </div>
    </form>
    """
    
    db = get_db()
    entries = db.execute("""
        SELECT id, date, 
               substr(content, 1, 30) as preview 
        FROM entries 
        WHERE user_id = ? 
        ORDER BY date DESC
    """, (session["user_id"],)).fetchall()
    
    return render_template_string(MAIN_TEMPLATE, entries=entries, content=form)

@app.route("/save", methods=["POST"])
def save():
    if not session.get("user"):
        return redirect("/")
    
    db = get_db()
    
    try:
        cur = db.execute("""
            INSERT INTO entries (user_id, date, content) 
            VALUES (?, ?, ?)
        """, (session["user_id"], request.form["date"], request.form["content"]))
        entry_id = cur.lastrowid
        
        files = request.files.getlist("photos")
        saved_count = 0
        
        for file in files:
            if file and file.filename:
                filename = str(uuid.uuid4()) + "_" + secure_filename(file.filename)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                db.execute("INSERT INTO photos (entry_id, filename) VALUES (?,?)",
                          (entry_id, filename))
                saved_count += 1
        
        db.commit()
        
        entries = db.execute("""
            SELECT id, date, 
                   substr(content, 1, 30) as preview 
            FROM entries 
            WHERE user_id = ? 
            ORDER BY date DESC
        """, (session["user_id"],)).fetchall()
        
        success_html = f"""
        <div style="text-align:center;margin-top:50px;">
            <h3 style="color:#48bb78;">✅ Entry saved! {saved_count} photos uploaded</h3>
            <div style="margin-top:20px;">
                <a href='/view/{entry_id}'><button class='primary'>View Entry</button></a>
                <a href='/new'><button class='secondary'>Write Another</button></a>
            </div>
        </div>
        """
        
        return render_template_string(MAIN_TEMPLATE, entries=entries, content=success_html)
    
    except Exception as e:
        db.rollback()
        return render_template_string(MAIN_TEMPLATE, 
                                    message=f"Error: {str(e)}", 
                                    message_type="error")

@app.route("/view/<int:id>")
def view(id):
    if not session.get("user"):
        return redirect("/")
    
    db = get_db()
    
    entry = db.execute("""
        SELECT e.*, u.username 
        FROM entries e
        JOIN users u ON e.user_id = u.id
        WHERE e.id = ?
    """, (id,)).fetchone()
    
    if not entry or (entry["user_id"] != session["user_id"] and not session.get("is_admin")):
        return redirect("/")
    
    photos = db.execute("SELECT filename FROM photos WHERE entry_id = ?", (id,)).fetchall()
    
    entries = db.execute("""
        SELECT id, date, 
               substr(content, 1, 30) as preview 
        FROM entries 
        WHERE user_id = ? 
        ORDER BY date DESC
    """, (session["user_id"],)).fetchall()
    
    photo_html = ""
    if photos:
        photo_html = "<h3 style='color:#333;margin:20px 0 10px;'>📸 Photos</h3><div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;'>"
        for p in photos:
            photo_html += f"""
            <div style="border:1px solid #ddd;border-radius:8px;overflow:hidden;height:120px;">
                <img src='/uploads/{p["filename"]}' style="width:100%;height:100%;object-fit:cover;">
            </div>
            """
        photo_html += "</div>"
    
    html = f"""
    <div style="max-width:800px;margin:0 auto;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <h2 style="color:#333;">📅 {entry["date"]}</h2>
            <a href="/new"><button class="primary">+ New Entry</button></a>
        </div>
        
        <div style="background:#f9f9f9;padding:25px;border-radius:10px;margin-bottom:20px;">
            <p style="white-space:pre-wrap;line-height:1.6;">{entry["content"]}</p>
        </div>
        
        {photo_html}
    </div>
    """
    
    return render_template_string(MAIN_TEMPLATE, entries=entries, content=html)

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)