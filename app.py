from flask import Flask, render_template_string, request, redirect, session, send_from_directory, g, url_for
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
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
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

/* Mobile Responsive */
@media(max-width:480px){
    .login-card{padding:25px;}
    h2{font-size:24px;}
    .tab{padding:8px;}
    button{padding:12px;}
}
</style>
</head>
<body>
<div class="login-card">
    <h2>📔 Personal Diary</h2>
    
    
    
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

# ---------------- ADMIN PANEL PAGE WITH SEARCH ----------------

ADMIN_PANEL_PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>Admin Panel - User Management</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
<style>
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    font-family: 'Poppins', sans-serif;
}

body {
    background: linear-gradient(135deg, #667eea, #764ba2);
    min-height: 100vh;
    padding: 20px;
    padding-bottom: 80px;
}

.header {
    background: rgba(0, 0, 0, 0.7);
    color: white;
    padding: 15px 20px;
    border-radius: 15px;
    margin-bottom: 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
}

.header h3 {
    font-size: 18px;
}

.admin-badge {
    background: #f6ad55;
    color: white;
    padding: 5px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
}

.logout-btn {
    background: #f56565;
    color: white;
    padding: 8px 15px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    text-decoration: none;
    font-size: 14px;
}

.stats-container {
    background: rgba(255, 255, 255, 0.15);
    backdrop-filter: blur(15px);
    border-radius: 15px;
    padding: 20px;
    color: white;
    margin-bottom: 20px;
}

.stats-title {
    margin-bottom: 15px;
    font-size: 20px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 15px;
    margin-bottom: 20px;
}

.stat-card {
    background: rgba(255, 255, 255, 0.2);
    padding: 15px;
    border-radius: 12px;
    text-align: center;
}

.stat-number {
    font-size: 24px;
    font-weight: 600;
    margin-bottom: 5px;
}

.stat-label {
    font-size: 12px;
    opacity: 0.8;
}

.search-container {
    margin-bottom: 20px;
}

.search-box {
    width: 100%;
    padding: 15px;
    border: none;
    border-radius: 12px;
    font-size: 16px;
    background: rgba(255, 255, 255, 0.9);
    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
}

.search-box:focus {
    outline: 2px solid #667eea;
    background: white;
}

.users-container {
    background: rgba(255, 255, 255, 0.15);
    backdrop-filter: blur(15px);
    border-radius: 15px;
    padding: 20px;
    color: white;
}

.users-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 15px;
    flex-wrap: wrap;
    gap: 10px;
}

.users-title {
    font-size: 18px;
    font-weight: 500;
}

.user-count {
    background: rgba(255, 255, 255, 0.2);
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 14px;
}

.user-card {
    background: rgba(255, 255, 255, 0.2);
    padding: 15px;
    border-radius: 12px;
    margin-bottom: 10px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: all 0.3s;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

.user-card:hover {
    background: rgba(255, 255, 255, 0.3);
    transform: translateX(5px);
}

.user-info {
    flex: 1;
}

.user-name {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.user-badge {
    background: #48bb78;
    color: white;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 10px;
    font-weight: 600;
}

.user-meta {
    display: flex;
    gap: 15px;
    font-size: 12px;
    opacity: 0.8;
}

.user-meta span {
    display: flex;
    align-items: center;
    gap: 4px;
}

.login-btn {
    background: #667eea;
    color: white;
    padding: 8px 15px;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    white-space: nowrap;
}

.login-btn:hover {
    background: #5a67d8;
    transform: translateY(-1px);
}

.empty-state {
    text-align: center;
    padding: 40px 20px;
    color: white;
    opacity: 0.8;
}

.empty-state p {
    margin-bottom: 10px;
}

.no-results {
    text-align: center;
    padding: 30px;
    color: white;
    opacity: 0.7;
    font-style: italic;
}

.bottom-nav {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: white;
    padding: 15px;
    display: flex;
    justify-content: space-around;
    box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
    border-top-left-radius: 20px;
    border-top-right-radius: 20px;
}

.nav-btn {
    flex: 1;
    margin: 0 5px;
    padding: 12px;
    border: none;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    text-align: center;
    text-decoration: none;
}

.nav-btn.primary {
    background: #667eea;
    color: white;
}

.nav-btn.secondary {
    background: #48bb78;
    color: white;
}

.nav-btn.active {
    opacity: 1;
    transform: translateY(-2px);
    box-shadow: 0 4px 10px rgba(0,0,0,0.2);
}

/* Loading indicator */
.loading {
    text-align: center;
    padding: 30px;
    color: white;
}

.loading::after {
    content: '';
    display: inline-block;
    width: 20px;
    height: 20px;
    border: 3px solid rgba(255,255,255,0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin-left: 10px;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* Mobile Responsive */
@media(max-width: 480px) {
    .user-meta {
        flex-direction: column;
        gap: 5px;
    }
    
    .user-card {
        flex-direction: column;
        align-items: flex-start;
        gap: 10px;
    }
    
    .login-btn {
        width: 100%;
        justify-content: center;
    }
    
    .stats-grid {
        grid-template-columns: 1fr 1fr;
    }
}
</style>
</head>
<body>

<div class="header">
    <div style="display: flex; align-items: center; gap: 10px;">
        <h3>👑 Admin Panel</h3>
        <span class="admin-badge">Administrator</span>
    </div>
    <a href="/logout" class="logout-btn">Logout</a>
</div>

<div class="stats-container">
    <div class="stats-title">
        <span>📊 Dashboard</span>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-number">{{total_users}}</div>
            <div class="stat-label">Total Users</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{{total_entries}}</div>
            <div class="stat-label">Total Entries</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{{total_photos}}</div>
            <div class="stat-label">Total Photos</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{{new_users_today}}</div>
            <div class="stat-label">New Today</div>
        </div>
    </div>
</div>

<div class="users-container">
    <div class="users-header">
        <div class="users-title">👥 User Management</div>
        <div class="user-count">{{users|length}} users</div>
    </div>
    
    <div class="search-container">
        <input type="text" id="searchInput" class="search-box" placeholder="🔍 Search by username..." onkeyup="filterUsers()">
    </div>
    
    <div id="usersList">
        {% if users %}
            {% for u in users %}
            <div class="user-card" data-username="{{u.username|lower}}">
                <div class="user-info">
                    <div class="user-name">
                        {{u.username}}
                        {% if u.entry_count %}
                        <span class="user-badge">{{u.entry_count}} entries</span>
                        {% endif %}
                    </div>
                    <div class="user-meta">
                        <span>📝 {{u.entry_count}} entries</span>
                        <span>📸 {{u.photo_count}} photos</span>
                        <span>📅 Joined: {{u.created_at[:10]}}</span>
                    </div>
                </div>
                <a href="/admin_login/{{u.id}}" class="login-btn">
                    🔑 Login as {{u.username}}
                </a>
            </div>
            {% endfor %}
        {% else %}
            <div class="empty-state">
                <p>📭 No users found</p>
                <p>Users will appear here when they sign up</p>
            </div>
        {% endif %}
    </div>
    
    <div id="noResults" class="no-results" style="display: none;">
        🔍 No users matching your search
    </div>
</div>

<div class="bottom-nav">
    <a href="/admin" class="nav-btn primary active">👑 Admin</a>
    <a href="/entries" class="nav-btn secondary">📋 My Diary</a>
</div>

<script>
function filterUsers() {
    const searchInput = document.getElementById('searchInput').value.toLowerCase();
    const userCards = document.querySelectorAll('.user-card');
    let visibleCount = 0;
    
    userCards.forEach(card => {
        const username = card.getAttribute('data-username');
        if (username.includes(searchInput)) {
            card.style.display = 'flex';
            visibleCount++;
        } else {
            card.style.display = 'none';
        }
    });
    
    const noResults = document.getElementById('noResults');
    if (visibleCount === 0) {
        noResults.style.display = 'block';
    } else {
        noResults.style.display = 'none';
    }
}

// Live search as you type
document.getElementById('searchInput').addEventListener('keyup', filterUsers);
</script>

</body>
</html>
"""

# ---------------- ENTRIES LIST PAGE (for normal users) ----------------

ENTRIES_PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>My Diary - Entries</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
<style>
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    font-family: 'Poppins', sans-serif;
}

body {
    background: linear-gradient(135deg, #667eea, #764ba2);
    min-height: 100vh;
    padding: 20px;
    padding-bottom: 80px;
}

.header {
    background: rgba(0, 0, 0, 0.7);
    color: white;
    padding: 15px 20px;
    border-radius: 15px;
    margin-bottom: 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
}

.header h3 {
    font-size: 18px;
}

.user-badge {
    background: #48bb78;
    color: white;
    padding: 5px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
}

.logout-btn {
    background: #f56565;
    color: white;
    padding: 8px 15px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    text-decoration: none;
    font-size: 14px;
}

.entries-container {
    background: rgba(255, 255, 255, 0.15);
    backdrop-filter: blur(15px);
    border-radius: 15px;
    padding: 20px;
    color: white;
}

.entries-title {
    margin-bottom: 15px;
    font-size: 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.entry-card {
    background: rgba(255, 255, 255, 0.25);
    padding: 15px;
    border-radius: 12px;
    margin-bottom: 10px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: all 0.3s;
    border: 1px solid rgba(255, 255, 255, 0.1);
    cursor: pointer;
}

.entry-card:active {
    transform: scale(0.98);
    background: rgba(255, 255, 255, 0.35);
}

.entry-info b {
    color: white;
    font-size: 16px;
}

.entry-preview {
    font-size: 12px;
    opacity: 0.8;
    margin-top: 3px;
    color: rgba(255, 255, 255, 0.9);
}

.view-btn {
    background: #48bb78;
    color: white;
    padding: 8px 15px;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    cursor: pointer;
    text-decoration: none;
    pointer-events: none;
}

.empty-state {
    text-align: center;
    padding: 40px 20px;
    color: white;
    opacity: 0.8;
}

.empty-state p {
    margin-bottom: 20px;
}

.bottom-nav {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: white;
    padding: 15px;
    display: flex;
    justify-content: space-around;
    box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
    border-top-left-radius: 20px;
    border-top-right-radius: 20px;
}

.nav-btn {
    flex: 1;
    margin: 0 5px;
    padding: 12px;
    border: none;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    text-align: center;
    text-decoration: none;
}

.nav-btn.primary {
    background: #667eea;
    color: white;
}

.nav-btn.secondary {
    background: #48bb78;
    color: white;
}

.nav-btn.active {
    opacity: 1;
    transform: translateY(-2px);
    box-shadow: 0 4px 10px rgba(0,0,0,0.2);
}

/* Admin link for normal users */
.admin-link {
    background: #f6ad55;
    color: white;
    padding: 8px 15px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    text-decoration: none;
    font-size: 14px;
    margin-left: 10px;
}
</style>
</head>
<body>

<div class="header">
    <div style="display: flex; align-items: center; gap: 10px;">
        <h3>📔 {{session['user']}}'s Diary</h3>
        {% if session.get('is_admin') %}
        <span class="user-badge">Admin</span>
        {% endif %}
    </div>
    <div>
        {% if session.get('is_admin') %}
        <a href="/admin" class="admin-link">👑 Admin Panel</a>
        {% endif %}
        <a href="/logout" class="logout-btn">Logout</a>
    </div>
</div>

<div class="entries-container">
    <div class="entries-title">
        <span>📝 Your Entries ({{entries|length}})</span>
        <a href="/new" style="text-decoration: none;">
            <button class="nav-btn secondary" style="padding: 8px 15px;">+ New</button>
        </a>
    </div>
    
    {% if entries %}
        {% for e in entries %}
        <div class="entry-card" onclick="window.location.href='/view/{{e.id}}'">
            <div class="entry-info">
                <b>{{e.date}}</b>
                {% if e.preview %}
                <div class="entry-preview">{{e.preview[:30]}}...</div>
                {% endif %}
            </div>
            <span class="view-btn">View →</span>
        </div>
        {% endfor %}
    {% else %}
        <div class="empty-state">
            <p>📭 No entries yet</p>
            <p>Create your first diary entry!</p>
            <a href="/new"><button class="nav-btn secondary">+ Create Entry</button></a>
        </div>
    {% endif %}
</div>

<div class="bottom-nav">
    <a href="/entries" class="nav-btn primary active">📋 Entries</a>
    <a href="/new" class="nav-btn secondary">➕ New</a>
</div>

</body>
</html>
"""

# ---------------- NEW ENTRY PAGE ----------------

NEW_ENTRY_PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>New Entry</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
<style>
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    font-family: 'Poppins', sans-serif;
}

body {
    background: linear-gradient(135deg, #667eea, #764ba2);
    min-height: 100vh;
    padding: 20px;
    padding-bottom: 80px;
}

.header {
    background: rgba(0, 0, 0, 0.7);
    color: white;
    padding: 15px 20px;
    border-radius: 15px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 15px;
}

.back-btn {
    background: #667eea;
    color: white;
    padding: 8px 15px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    text-decoration: none;
    font-size: 14px;
}

.header h3 {
    font-size: 18px;
    flex: 1;
}

.form-container {
    background: white;
    border-radius: 15px;
    padding: 25px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.1);
}

.form-container h2 {
    color: #333;
    margin-bottom: 20px;
    font-size: 22px;
}

.form-group {
    margin-bottom: 20px;
}

label {
    display: block;
    margin-bottom: 8px;
    color: #555;
    font-weight: 500;
    font-size: 14px;
}

input[type="date"] {
    width: 100%;
    padding: 12px;
    border: 2px solid #e0e0e0;
    border-radius: 10px;
    font-size: 14px;
}

textarea {
    width: 100%;
    padding: 12px;
    border: 2px solid #e0e0e0;
    border-radius: 10px;
    min-height: 150px;
    font-size: 14px;
}

input[type="file"] {
    width: 100%;
    padding: 10px;
    border: 2px dashed #e0e0e0;
    border-radius: 10px;
    margin-bottom: 5px;
}

small {
    display: block;
    color: #666;
    font-size: 12px;
    margin-top: 5px;
}

.button-group {
    display: flex;
    gap: 10px;
    margin-top: 20px;
}

.btn {
    flex: 1;
    padding: 14px;
    border: none;
    border-radius: 10px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    text-align: center;
    text-decoration: none;
}

.btn.primary {
    background: #667eea;
    color: white;
}

.btn.secondary {
    background: #48bb78;
    color: white;
}

.btn.danger {
    background: #f56565;
    color: white;
}

.bottom-nav {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: white;
    padding: 15px;
    display: flex;
    justify-content: space-around;
    box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
    border-top-left-radius: 20px;
    border-top-right-radius: 20px;
}

.nav-btn {
    flex: 1;
    margin: 0 5px;
    padding: 12px;
    border: none;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    text-align: center;
    text-decoration: none;
}

.nav-btn.primary {
    background: #667eea;
    color: white;
}

.nav-btn.secondary {
    background: #48bb78;
    color: white;
}

.nav-btn.active {
    background: #48bb78;
    color: white;
    opacity: 1;
}

.flash-message {
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 20px;
    text-align: center;
}

.flash-message.error {
    background: #fed7d7;
    color: #742a2a;
    border: 1px solid #feb2b2;
}
</style>
</head>
<body>

<div class="header">
    <a href="/entries" class="back-btn">← Back</a>
    <h3>📝 New Entry</h3>
</div>

<div class="form-container">
    <h2>Write Your Diary Entry</h2>
    
    {% if message %}
    <div class="flash-message error">{{message}}</div>
    {% endif %}
    
    <form method="post" action="/save" enctype="multipart/form-data">
        <div class="form-group">
            <label>📅 Date</label>
            <input type="date" name="date" value="{{today}}" required>
        </div>
        
        <div class="form-group">
            <label>📝 Your Thoughts</label>
            <textarea name="content" placeholder="What's on your mind today?" required></textarea>
        </div>
        
        <div class="form-group">
            <label>📸 Photos (Optional)</label>
            <input type="file" name="photos" multiple accept="image/*">
            <small>You can select multiple photos</small>
        </div>
        
        <div class="button-group">
            <button type="submit" class="btn primary">💾 Save</button>
            <a href="/entries" class="btn danger">Cancel</a>
        </div>
    </form>
</div>

<div class="bottom-nav">
    <a href="/entries" class="nav-btn primary">📋 Entries</a>
    <a href="/new" class="nav-btn secondary active">➕ New</a>
</div>

</body>
</html>
"""

# ---------------- EDIT ENTRY PAGE ----------------

EDIT_ENTRY_PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>Edit Entry</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
<style>
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    font-family: 'Poppins', sans-serif;
}

body {
    background: linear-gradient(135deg, #667eea, #764ba2);
    min-height: 100vh;
    padding: 20px;
    padding-bottom: 80px;
}

.header {
    background: rgba(0, 0, 0, 0.7);
    color: white;
    padding: 15px 20px;
    border-radius: 15px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 15px;
}

.back-btn {
    background: #667eea;
    color: white;
    padding: 8px 15px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    text-decoration: none;
    font-size: 14px;
}

.header h3 {
    font-size: 18px;
    flex: 1;
}

.form-container {
    background: white;
    border-radius: 15px;
    padding: 25px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.1);
}

.form-container h2 {
    color: #333;
    margin-bottom: 20px;
    font-size: 22px;
}

.form-group {
    margin-bottom: 20px;
}

label {
    display: block;
    margin-bottom: 8px;
    color: #555;
    font-weight: 500;
    font-size: 14px;
}

input[type="date"] {
    width: 100%;
    padding: 12px;
    border: 2px solid #e0e0e0;
    border-radius: 10px;
    font-size: 14px;
}

textarea {
    width: 100%;
    padding: 12px;
    border: 2px solid #e0e0e0;
    border-radius: 10px;
    min-height: 150px;
    font-size: 14px;
}

input[type="file"] {
    width: 100%;
    padding: 10px;
    border: 2px dashed #e0e0e0;
    border-radius: 10px;
    margin-bottom: 5px;
}

small {
    display: block;
    color: #666;
    font-size: 12px;
    margin-top: 5px;
}

.current-photos {
    margin-bottom: 20px;
}

.current-photos h4 {
    color: #555;
    margin-bottom: 10px;
    font-size: 16px;
}

.photo-list {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
}

.photo-item {
    width: 80px;
    height: 80px;
    border-radius: 8px;
    overflow: hidden;
    border: 2px solid #e0e0e0;
}

.photo-item img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.button-group {
    display: flex;
    gap: 10px;
    margin-top: 20px;
}

.btn {
    flex: 1;
    padding: 14px;
    border: none;
    border-radius: 10px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    text-align: center;
    text-decoration: none;
}

.btn.primary {
    background: #667eea;
    color: white;
}

.btn.secondary {
    background: #48bb78;
    color: white;
}

.btn.danger {
    background: #f56565;
    color: white;
}

.btn.edit {
    background: #f6ad55;
    color: white;
}

.flash-message {
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 20px;
    text-align: center;
}

.flash-message.error {
    background: #fed7d7;
    color: #742a2a;
    border: 1px solid #feb2b2;
}
</style>
</head>
<body>

<div class="header">
    <a href="/view/{{entry.id}}" class="back-btn">← Back</a>
    <h3>✏️ Edit Entry</h3>
</div>

<div class="form-container">
    <h2>Edit Your Diary Entry</h2>
    
    {% if message %}
    <div class="flash-message error">{{message}}</div>
    {% endif %}
    
    <form method="post" action="/update/{{entry.id}}" enctype="multipart/form-data">
        <div class="form-group">
            <label>📅 Date</label>
            <input type="date" name="date" value="{{entry.date}}" required>
        </div>
        
        <div class="form-group">
            <label>📝 Your Thoughts</label>
            <textarea name="content" placeholder="What's on your mind today?" required>{{entry.content}}</textarea>
        </div>
        
        {% if photos %}
        <div class="current-photos">
            <h4>Current Photos:</h4>
            <div class="photo-list">
                {% for p in photos %}
                <div class="photo-item">
                    <img src="/uploads/{{p.filename}}" alt="Photo">
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}
        
        <div class="form-group">
            <label>📸 Add More Photos (Optional)</label>
            <input type="file" name="photos" multiple accept="image/*">
            <small>You can select multiple photos</small>
        </div>
        
        <div class="button-group">
            <button type="submit" class="btn primary">💾 Update</button>
            <a href="/view/{{entry.id}}" class="btn danger">Cancel</a>
        </div>
    </form>
</div>

</body>
</html>
"""

# ---------------- VIEW ENTRY PAGE WITH EDIT & DELETE ----------------

VIEW_ENTRY_PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>View Entry</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
<style>
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    font-family: 'Poppins', sans-serif;
}

body {
    background: linear-gradient(135deg, #667eea, #764ba2);
    min-height: 100vh;
    padding: 20px;
    padding-bottom: 80px;
}

.header {
    background: rgba(0, 0, 0, 0.7);
    color: white;
    padding: 15px 20px;
    border-radius: 15px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 15px;
}

.back-btn {
    background: #667eea;
    color: white;
    padding: 8px 15px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    text-decoration: none;
    font-size: 14px;
}

.header h3 {
    font-size: 18px;
    flex: 1;
}

.entry-container {
    background: white;
    border-radius: 15px;
    padding: 25px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.1);
}

.entry-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 15px;
    border-bottom: 2px solid #f0f0f0;
    flex-wrap: wrap;
    gap: 10px;
}

.entry-date h2 {
    color: #333;
    font-size: 20px;
}

.action-buttons {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
}

.action-btn {
    padding: 8px 15px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    text-decoration: none;
    font-size: 14px;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 5px;
}

.edit-btn {
    background: #f6ad55;
    color: white;
}

.delete-btn {
    background: #f56565;
    color: white;
}

.new-btn {
    background: #667eea;
    color: white;
    padding: 8px 15px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    text-decoration: none;
    font-size: 14px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
}

.entry-content {
    background: #f9f9f9;
    padding: 20px;
    border-radius: 12px;
    line-height: 1.6;
    color: #333;
    white-space: pre-wrap;
    margin-bottom: 20px;
}

.photos-section {
    margin-top: 20px;
}

.photos-section h3 {
    color: #333;
    margin-bottom: 15px;
    font-size: 18px;
}

.photos-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 10px;
}

.photos-grid img {
    width: 100%;
    height: 120px;
    object-fit: cover;
    border-radius: 10px;
    border: 2px solid #f0f0f0;
}

.bottom-nav {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: white;
    padding: 15px;
    display: flex;
    justify-content: space-around;
    box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
    border-top-left-radius: 20px;
    border-top-right-radius: 20px;
}

.nav-btn {
    flex: 1;
    margin: 0 5px;
    padding: 12px;
    border: none;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    text-align: center;
    text-decoration: none;
}

.nav-btn.primary {
    background: #667eea;
    color: white;
}

.nav-btn.secondary {
    background: #48bb78;
    color: white;
}

/* Delete Confirmation Modal */
.modal {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.5);
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.modal-content {
    background: white;
    padding: 30px;
    border-radius: 20px;
    max-width: 300px;
    text-align: center;
}

.modal-content h3 {
    color: #333;
    margin-bottom: 10px;
}

.modal-content p {
    color: #666;
    margin-bottom: 20px;
}

.modal-buttons {
    display: flex;
    gap: 10px;
}

.modal-btn {
    flex: 1;
    padding: 12px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 600;
}

.confirm-btn {
    background: #f56565;
    color: white;
}

.cancel-btn {
    background: #e0e0e0;
    color: #333;
}

/* Mobile Responsive */
@media(max-width: 480px) {
    .entry-header {
        flex-direction: column;
        align-items: flex-start;
    }
    
    .action-buttons {
        width: 100%;
    }
    
    .action-btn {
        flex: 1;
        text-align: center;
        justify-content: center;
    }
}
</style>
</head>
<body>

<div class="header">
    <a href="/entries" class="back-btn">← Back</a>
    <h3>📖 View Entry</h3>
</div>

<div class="entry-container">
    <div class="entry-header">
        <div class="entry-date">
            <h2>📅 {{entry.date}}</h2>
        </div>
        <div class="action-buttons">
            <a href="/edit/{{entry.id}}" class="action-btn edit-btn">✏️ Edit</a>
            <button onclick="showDeleteModal()" class="action-btn delete-btn">🗑️ Delete</button>
            <a href="/new" class="new-btn">+ New</a>
        </div>
    </div>
    
    <div class="entry-content">
        {{entry.content}}
    </div>
    
    {% if photos %}
    <div class="photos-section">
        <h3>📸 Photos</h3>
        <div class="photos-grid">
            {% for p in photos %}
            <img src="/uploads/{{p.filename}}" alt="Entry photo">
            {% endfor %}
        </div>
    </div>
    {% endif %}
</div>

<div class="bottom-nav">
    <a href="/entries" class="nav-btn primary">📋 Entries</a>
    <a href="/new" class="nav-btn secondary">➕ New</a>
</div>

<!-- Delete Confirmation Modal -->
<div id="deleteModal" class="modal">
    <div class="modal-content">
        <h3>🗑️ Delete Entry</h3>
        <p>Are you sure you want to delete this entry? This action cannot be undone.</p>
        <div class="modal-buttons">
            <button onclick="deleteEntry()" class="modal-btn confirm-btn">Yes, Delete</button>
            <button onclick="hideDeleteModal()" class="modal-btn cancel-btn">Cancel</button>
        </div>
    </div>
</div>

<script>
function showDeleteModal() {
    document.getElementById('deleteModal').style.display = 'flex';
}

function hideDeleteModal() {
    document.getElementById('deleteModal').style.display = 'none';
}

function deleteEntry() {
    window.location.href = '/delete/{{entry.id}}';
}
</script>

</body>
</html>
"""

# ---------------- SUCCESS PAGE ----------------

SUCCESS_PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>Success</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
<style>
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    font-family: 'Poppins', sans-serif;
}

body {
    background: linear-gradient(135deg, #667eea, #764ba2);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
}

.success-card {
    background: white;
    border-radius: 20px;
    padding: 40px 30px;
    text-align: center;
    box-shadow: 0 20px 40px rgba(0,0,0,0.2);
    max-width: 400px;
    width: 100%;
}

.success-icon {
    font-size: 60px;
    margin-bottom: 20px;
}

.success-card h2 {
    color: #48bb78;
    margin-bottom: 10px;
    font-size: 24px;
}

.success-card p {
    color: #666;
    margin-bottom: 30px;
    font-size: 16px;
}

.button-group {
    display: flex;
    gap: 10px;
    flex-direction: column;
}

.btn {
    padding: 14px;
    border: none;
    border-radius: 10px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    text-align: center;
    text-decoration: none;
}

.btn.primary {
    background: #667eea;
    color: white;
}

.btn.secondary {
    background: #48bb78;
    color: white;
}

.btn.edit {
    background: #f6ad55;
    color: white;
}
</style>
</head>
<body>

<div class="success-card">
    <div class="success-icon">✅</div>
    <h2>{{message}}</h2>
    <p>{{submessage}}</p>
    
    <div class="button-group">
        <a href="/view/{{entry_id}}" class="btn primary">View Entry</a>
        <a href="/new" class="btn secondary">Write Another</a>
        <a href="/entries" class="btn edit">Back to Entries</a>
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
    
    # Redirect to appropriate page based on user role
    if session.get("is_admin"):
        return redirect("/admin")
    return redirect("/entries")

@app.route("/admin")
def admin_panel():
    if not session.get("user") or not session.get("is_admin"):
        return redirect("/")
    
    db = get_db()
    
    # Get all users except admin
    users = db.execute("""
        SELECT u.*, 
               (SELECT COUNT(*) FROM entries WHERE user_id = u.id) as entry_count,
               (SELECT COUNT(*) FROM photos p JOIN entries e ON p.entry_id = e.id WHERE e.user_id = u.id) as photo_count
        FROM users u 
        WHERE u.username != 'admin' 
        ORDER BY u.created_at DESC
    """).fetchall()
    
    # Get statistics
    total_users = db.execute("SELECT COUNT(*) as count FROM users WHERE username != 'admin'").fetchone()['count']
    total_entries = db.execute("SELECT COUNT(*) as count FROM entries").fetchone()['count']
    total_photos = db.execute("SELECT COUNT(*) as count FROM photos").fetchone()['count']
    
    # New users today
    today = datetime.now().strftime("%Y-%m-%d")
    new_users_today = db.execute("""
        SELECT COUNT(*) as count FROM users 
        WHERE date(created_at) = date('now') AND username != 'admin'
    """).fetchone()['count']
    
    return render_template_string(ADMIN_PANEL_PAGE, 
                                users=users,
                                total_users=total_users,
                                total_entries=total_entries,
                                total_photos=total_photos,
                                new_users_today=new_users_today)

@app.route("/entries")
def entries_list():
    if not session.get("user"):
        return redirect("/")
    
    db = get_db()
    
    # Get entries for the user
    entries = db.execute("""
        SELECT id, date, 
               substr(content, 1, 40) as preview 
        FROM entries 
        WHERE user_id = ? 
        ORDER BY date DESC, created_at DESC
    """, (session["user_id"],)).fetchall()
    
    return render_template_string(ENTRIES_PAGE, entries=entries)

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
        
        # Redirect admin to admin panel, others to entries
        if user["username"] == "admin":
            return redirect("/admin")
        return redirect("/entries")
    
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
        session["is_admin"] = False  # Demote to normal user
        return redirect("/entries")
    
    return redirect("/admin")

@app.route("/new")
def new():
    if not session.get("user"):
        return redirect("/")
    
    today = datetime.now().strftime("%Y-%m-%d")
    return render_template_string(NEW_ENTRY_PAGE, today=today)

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
        
        message = "Entry saved successfully!"
        submessage = f"{saved_count} photo(s) uploaded"
        
        return render_template_string(SUCCESS_PAGE, 
                                    message=message,
                                    submessage=submessage,
                                    entry_id=entry_id)
    
    except Exception as e:
        db.rollback()
        return render_template_string(NEW_ENTRY_PAGE, 
                                    today=datetime.now().strftime("%Y-%m-%d"),
                                    message=f"Error: {str(e)}", 
                                    message_type="error")

@app.route("/view/<int:id>")
def view(id):
    if not session.get("user"):
        return redirect("/")
    
    db = get_db()
    
    entry = db.execute("""
        SELECT * FROM entries 
        WHERE id = ? AND user_id = ?
    """, (id, session["user_id"])).fetchone()
    
    if not entry:
        return redirect("/entries")
    
    photos = db.execute("SELECT filename FROM photos WHERE entry_id = ?", (id,)).fetchall()
    
    return render_template_string(VIEW_ENTRY_PAGE, entry=entry, photos=photos)

@app.route("/edit/<int:id>")
def edit(id):
    if not session.get("user"):
        return redirect("/")
    
    db = get_db()
    
    entry = db.execute("""
        SELECT * FROM entries 
        WHERE id = ? AND user_id = ?
    """, (id, session["user_id"])).fetchone()
    
    if not entry:
        return redirect("/entries")
    
    photos = db.execute("SELECT filename FROM photos WHERE entry_id = ?", (id,)).fetchall()
    
    return render_template_string(EDIT_ENTRY_PAGE, entry=entry, photos=photos)

@app.route("/update/<int:id>", methods=["POST"])
def update(id):
    if not session.get("user"):
        return redirect("/")
    
    db = get_db()
    
    try:
        # Update entry
        db.execute("""
            UPDATE entries 
            SET date = ?, content = ? 
            WHERE id = ? AND user_id = ?
        """, (request.form["date"], request.form["content"], id, session["user_id"]))
        
        # Save new photos
        files = request.files.getlist("photos")
        saved_count = 0
        
        for file in files:
            if file and file.filename:
                filename = str(uuid.uuid4()) + "_" + secure_filename(file.filename)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                db.execute("INSERT INTO photos (entry_id, filename) VALUES (?,?)",
                          (id, filename))
                saved_count += 1
        
        db.commit()
        
        message = "Entry updated successfully!"
        submessage = f"{saved_count} new photo(s) added"
        
        return render_template_string(SUCCESS_PAGE, 
                                    message=message,
                                    submessage=submessage,
                                    entry_id=id)
    
    except Exception as e:
        db.rollback()
        return render_template_string(EDIT_ENTRY_PAGE,
                                    entry=entry,
                                    message=f"Error: {str(e)}",
                                    message_type="error")

@app.route("/delete/<int:id>")
def delete(id):
    if not session.get("user"):
        return redirect("/")
    
    db = get_db()
    
    try:
        # Delete entry (photos will be deleted automatically due to CASCADE)
        db.execute("DELETE FROM entries WHERE id = ? AND user_id = ?", 
                  (id, session["user_id"]))
        db.commit()
        
        return redirect("/entries")
    
    except Exception as e:
        return redirect("/entries")

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)