from flask import Flask, render_template_string, request, redirect, session, send_from_directory, g
import sqlite3
import os
import uuid
import random
import smtplib
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from email.mime.text import MIMEText
import os
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'supersecretkey123!@#')

# Configuration for email
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'punitjangir322@gmail.com'
app.config['MAIL_PASSWORD'] = 'sghv tcsj omrp wuum'  # Your app password

# Railway environment - Use persistent volume for database
# Railway provides /data directory for persistent storage
DATABASE = os.path.join('/data', 'diary.db') if os.path.exists('/data') else 'diary.db'
UPLOAD_FOLDER = os.path.join('/data', 'uploads') if os.path.exists('/data') else 'uploads'

# Create directories with proper permissions
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(DATABASE) if os.path.dirname(DATABASE) else '.', exist_ok=True)

# Store OTPs temporarily
otp_storage = {}

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

# ---------------- INIT DATABASE (WITHOUT OVERWRITING) ----------------

def init_db():
    """Initialize database only if it doesn't exist - won't overwrite existing data"""
    db_exists = os.path.exists(DATABASE)
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA foreign_keys = ON")
    
    # Check if tables exist
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    tables_exist = cursor.fetchone() is not None
    
    if not tables_exist:
        print("Creating new database tables...")
        # Create tables
        db.executescript("""
        CREATE TABLE users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE,
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

        # Create admin user only if no users exist
        admin_exists = db.execute("SELECT * FROM users WHERE username = 'admin'").fetchone()
        if not admin_exists:
            db.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
                       ("admin", generate_password_hash("admin123"), "admin@diary.com"))
        
        # Create test user only if no test user exists
        test_exists = db.execute("SELECT * FROM users WHERE username = 'test'").fetchone()
        if not test_exists:
            db.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
                       ("test", generate_password_hash("test123"), "test@example.com"))
        
        db.commit()
        print("Database initialized successfully!")
    else:
        print("Database already exists, skipping initialization...")
        
        # Check if admin exists, if not create it
        admin_exists = db.execute("SELECT * FROM users WHERE username = 'admin'").fetchone()
        if not admin_exists:
            print("Admin user not found, creating...")
            db.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
                       ("admin", generate_password_hash("admin123"), "admin@diary.com"))
            db.commit()
        
        # Check if test user exists, if not create it
        test_exists = db.execute("SELECT * FROM users WHERE username = 'test'").fetchone()
        if not test_exists:
            print("Test user not found, creating...")
            db.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
                       ("test", generate_password_hash("test123"), "test@example.com"))
            db.commit()
    
    db.close()

# Initialize database
init_db()

# ---------------- EMAIL SENDING FUNCTION ----------------

def send_otp_email(to_email, otp):
    """Send OTP via email"""
    try:
        msg = MIMEMultipart()
        msg['From'] = app.config['MAIL_USERNAME']
        msg['To'] = to_email
        msg['Subject'] = "Password Reset OTP - Personal Diary"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #667eea;">Personal Diary - Password Reset</h2>
            <p>Your OTP for password reset is:</p>
            <h1 style="color: #48bb78; font-size: 32px; letter-spacing: 5px;">{otp}</h1>
            <p>This OTP is valid for 10 minutes.</p>
            <p>If you didn't request this, please ignore this email.</p>
            <hr>
            <p style="color: #666; font-size: 12px;">Personal Diary App</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
        server.starttls()
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

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
button.forgot-btn{background:#f6ad55;margin-top:10px;}
.message{padding:12px;border-radius:8px;margin-bottom:20px;text-align:center;}
.success{background:#c6f6d5;color:#22543d;border:1px solid #9ae6b4;}
.error{background:#fed7d7;color:#742a2a;border:1px solid #feb2b2;}
.switch-text{text-align:center;margin-top:20px;color:#666;}
.switch-text span{color:#667eea;cursor:pointer;font-weight:600;}
.switch-text span:hover{text-decoration:underline;}
.info-box{background:#e6f7ff;border:1px solid #91d5ff;padding:10px;border-radius:8px;margin-bottom:20px;text-align:center;color:#0050b3;}
.info-box strong{color:#1890ff;}
.forgot-link{text-align:center;margin-top:15px;}
.forgot-link a{color:#667eea;text-decoration:none;font-size:14px;}
.forgot-link a:hover{text-decoration:underline;}

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
        <div class="forgot-link">
            <a href="/forgot-password">Forgot Password?</a>
        </div>
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
                <label>Email</label>
                <input type="email" name="email" required placeholder="your@email.com">
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

# ---------------- FORGOT PASSWORD PAGE ----------------

FORGOT_PASSWORD_PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>Forgot Password</title>
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

.card {
    background: white;
    border-radius: 20px;
    padding: 40px;
    box-shadow: 0 20px 40px rgba(0,0,0,0.2);
    max-width: 400px;
    width: 100%;
}

.card h2 {
    color: #333;
    margin-bottom: 10px;
    font-size: 24px;
    text-align: center;
}

.card p {
    color: #666;
    margin-bottom: 30px;
    text-align: center;
    font-size: 14px;
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

input {
    width: 100%;
    padding: 12px;
    border: 2px solid #e0e0e0;
    border-radius: 10px;
    font-size: 14px;
    transition: all 0.3s;
}

input:focus {
    outline: none;
    border-color: #667eea;
}

button {
    width: 100%;
    padding: 14px;
    background: #667eea;
    color: white;
    border: none;
    border-radius: 10px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
    margin-bottom: 10px;
}

button:hover {
    background: #5a67d8;
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(102,126,234,0.4);
}

button.secondary {
    background: #48bb78;
}

button.secondary:hover {
    background: #38a169;
}

.back-link {
    text-align: center;
    margin-top: 20px;
}

.back-link a {
    color: #667eea;
    text-decoration: none;
    font-size: 14px;
}

.back-link a:hover {
    text-decoration: underline;
}

.message {
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 20px;
    text-align: center;
}

.success {
    background: #c6f6d5;
    color: #22543d;
    border: 1px solid #9ae6b4;
}

.error {
    background: #fed7d7;
    color: #742a2a;
    border: 1px solid #feb2b2;
}

.otp-input {
    letter-spacing: 8px;
    font-size: 20px;
    text-align: center;
}

.timer {
    text-align: center;
    color: #666;
    font-size: 14px;
    margin-top: 10px;
}
</style>
</head>
<body>

<div class="card">
    <h2>{% if step == 'email' %}🔐 Forgot Password{% elif step == 'otp' %}📨 Enter OTP{% else %}🔄 Reset Password{% endif %}</h2>
    
    {% if message %}
    <div class="message {{message_type}}">{{message}}</div>
    {% endif %}
    
    {% if step == 'email' %}
    <p>Enter your email address to receive OTP</p>
    <form method="post" action="/forgot-password">
        <div class="form-group">
            <label>Email Address</label>
            <input type="email" name="email" required placeholder="your@email.com">
        </div>
        <button type="submit">Send OTP</button>
        <div class="back-link">
            <a href="/">← Back to Login</a>
        </div>
    </form>
    
    {% elif step == 'otp' %}
    <p>Enter the 6-digit OTP sent to {{email}}</p>
    <form method="post" action="/verify-otp">
        <input type="hidden" name="email" value="{{email}}">
        <div class="form-group">
            <label>OTP</label>
            <input type="text" name="otp" class="otp-input" maxlength="6" pattern="\\d{6}" required placeholder="------">
        </div>
        <button type="submit">Verify OTP</button>
        <button type="submit" formaction="/resend-otp" class="secondary">Resend OTP</button>
        <div class="back-link">
            <a href="/">← Back to Login</a>
        </div>
    </form>
    
    {% elif step == 'reset' %}
    <p>Create new password for {{email}}</p>
    <form method="post" action="/reset-password">
        <input type="hidden" name="email" value="{{email}}">
        <div class="form-group">
            <label>New Password</label>
            <input type="password" name="password" required minlength="4" placeholder="••••••••">
        </div>
        <div class="form-group">
            <label>Confirm Password</label>
            <input type="password" name="confirm_password" required minlength="4" placeholder="••••••••">
        </div>
        <button type="submit">Reset Password</button>
        <div class="back-link">
            <a href="/">← Back to Login</a>
        </div>
    </form>
    {% endif %}
</div>

</body>
</html>
"""

# ---------------- CHANGE PASSWORD PAGE ----------------

CHANGE_PASSWORD_PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>Change Password</title>
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
    padding: 30px;
    max-width: 400px;
    margin: 0 auto;
    box-shadow: 0 10px 25px rgba(0,0,0,0.1);
}

.form-container h2 {
    color: #333;
    margin-bottom: 20px;
    font-size: 22px;
    text-align: center;
}

.form-group {
    margin-bottom: 20px;
}

label {
    display: block;
    margin-bottom: 8px;
    color: #555;
    font-weight: 500;
}

input {
    width: 100%;
    padding: 12px;
    border: 2px solid #e0e0e0;
    border-radius: 10px;
    font-size: 14px;
}

input:focus {
    outline: none;
    border-color: #667eea;
}

button {
    width: 100%;
    padding: 14px;
    background: #667eea;
    color: white;
    border: none;
    border-radius: 10px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
    margin-top: 10px;
}

button:hover {
    background: #5a67d8;
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(102,126,234,0.4);
}

.message {
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 20px;
    text-align: center;
}

.success {
    background: #c6f6d5;
    color: #22543d;
    border: 1px solid #9ae6b4;
}

.error {
    background: #fed7d7;
    color: #742a2a;
    border: 1px solid #feb2b2;
}
</style>
</head>
<body>

<div class="header">
    <a href="/entries" class="back-btn">← Back</a>
    <h3>🔐 Change Password</h3>
</div>

<div class="form-container">
    <h2>Change Your Password</h2>
    
    {% if message %}
    <div class="message {{message_type}}">{{message}}</div>
    {% endif %}
    
    <form method="post" action="/change-password">
        <div class="form-group">
            <label>Current Password</label>
            <input type="password" name="current_password" required placeholder="••••••••">
        </div>
        <div class="form-group">
            <label>New Password</label>
            <input type="password" name="new_password" required minlength="4" placeholder="••••••••">
        </div>
        <div class="form-group">
            <label>Confirm New Password</label>
            <input type="password" name="confirm_password" required minlength="4" placeholder="••••••••">
        </div>
        <button type="submit">Update Password</button>
    </form>
</div>

</body>
</html>
"""

# ---------------- ADMIN PANEL PAGE ----------------

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
    flex-wrap: wrap;
}

.user-badge {
    background: #48bb78;
    color: white;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 10px;
    font-weight: 600;
}

.user-email {
    font-size: 12px;
    opacity: 0.8;
    margin-bottom: 4px;
}

.user-meta {
    display: flex;
    gap: 15px;
    font-size: 12px;
    opacity: 0.8;
    flex-wrap: wrap;
}

.user-meta span {
    display: flex;
    align-items: center;
    gap: 4px;
}

.action-buttons {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.login-btn {
    background: #667eea;
    color: white;
    padding: 8px 12px;
    border: none;
    border-radius: 8px;
    font-size: 12px;
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
}

.delete-btn {
    background: #f56565;
    color: white;
    padding: 8px 12px;
    border: none;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    white-space: nowrap;
}

.delete-btn:hover {
    background: #e53e3e;
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
@media(max-width: 768px) {
    .user-card {
        flex-direction: column;
        align-items: flex-start;
        gap: 10px;
    }
    
    .action-buttons {
        width: 100%;
    }
    
    .login-btn, .delete-btn {
        flex: 1;
        text-align: center;
        justify-content: center;
    }
    
    .stats-grid {
        grid-template-columns: 1fr 1fr;
    }
}

@media(max-width: 480px) {
    .user-meta {
        flex-direction: column;
        gap: 5px;
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
        <input type="text" id="searchInput" class="search-box" placeholder="🔍 Search by username or email..." onkeyup="filterUsers()">
    </div>
    
    <div id="usersList">
        {% if users %}
            {% for u in users %}
            <div class="user-card" data-username="{{u.username|lower}}" data-email="{{u.email|lower}}">
                <div class="user-info">
                    <div class="user-name">
                        {{u.username}}
                        {% if u.entry_count > 0 %}
                        <span class="user-badge">{{u.entry_count}} entries</span>
                        {% endif %}
                    </div>
                    {% if u.email %}
                    <div class="user-email">📧 {{u.email}}</div>
                    {% endif %}
                    <div class="user-meta">
                        <span>📝 {{u.entry_count}} entries</span>
                        <span>📸 {{u.photo_count}} photos</span>
                        <span>📅 Joined: {{u.created_at[:10]}}</span>
                    </div>
                </div>
                <div class="action-buttons">
                    <a href="/admin_login/{{u.id}}" class="login-btn">
                        🔑 Login
                    </a>
                    <button onclick="showDeleteModal({{u.id}}, '{{u.username}}')" class="delete-btn">
                        🗑️ Delete
                    </button>
                </div>
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

<!-- Delete Confirmation Modal -->
<div id="deleteModal" class="modal">
    <div class="modal-content">
        <h3>🗑️ Delete User</h3>
        <p id="deleteMessage">Are you sure you want to delete this user? This will delete all their entries and photos.</p>
        <div class="modal-buttons">
            <button onclick="confirmDelete()" class="modal-btn confirm-btn">Yes, Delete</button>
            <button onclick="hideDeleteModal()" class="modal-btn cancel-btn">Cancel</button>
        </div>
    </div>
</div>

<script>
let deleteUserId = null;

function filterUsers() {
    const searchInput = document.getElementById('searchInput').value.toLowerCase();
    const userCards = document.querySelectorAll('.user-card');
    let visibleCount = 0;
    
    userCards.forEach(card => {
        const username = card.getAttribute('data-username');
        const email = card.getAttribute('data-email') || '';
        if (username.includes(searchInput) || email.includes(searchInput)) {
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

function showDeleteModal(userId, username) {
    deleteUserId = userId;
    document.getElementById('deleteMessage').innerHTML = `Are you sure you want to delete user <strong>${username}</strong>? This will delete all their entries and photos.`;
    document.getElementById('deleteModal').style.display = 'flex';
}

function hideDeleteModal() {
    document.getElementById('deleteModal').style.display = 'none';
    deleteUserId = null;
}

function confirmDelete() {
    if (deleteUserId) {
        window.location.href = '/admin_delete/' + deleteUserId;
    }
}

// Live search as you type
document.getElementById('searchInput').addEventListener('keyup', filterUsers);
</script>

</body>
</html>
"""

# ---------------- ENTRIES LIST PAGE ----------------

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

.header-buttons {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
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

.change-password-btn {
    background: #f6ad55;
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
}

/* Mobile Responsive */
@media(max-width: 480px) {
    .header {
        flex-direction: column;
        align-items: flex-start;
    }
    
    .header-buttons {
        width: 100%;
    }
    
    .change-password-btn, .logout-btn, .admin-link {
        flex: 1;
        text-align: center;
    }
}
</style>
</head>
<body>

<div class="header">
    <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
        <h3>📔 {{session['user']}}'s Diary</h3>
        {% if session.get('is_admin') %}
        <span class="user-badge">Admin</span>
        {% endif %}
    </div>
    <div class="header-buttons">
        <a href="/change-password" class="change-password-btn">🔐 Change Password</a>
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

# ---------------- VIEW ENTRY PAGE ----------------

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

# ---------------- DATABASE STATUS PAGE ----------------

@app.route("/db-status")
def db_status():
    """Check database status (only for admin)"""
    if not session.get("is_admin"):
        return "Unauthorized", 403
    
    db = get_db()
    
    # Get database info
    db_path = DATABASE
    db_exists = os.path.exists(db_path)
    db_size = os.path.getsize(db_path) if db_exists else 0
    
    # Get user counts
    user_count = db.execute("SELECT COUNT(*) as count FROM users").fetchone()['count']
    entry_count = db.execute("SELECT COUNT(*) as count FROM entries").fetchone()['count']
    photo_count = db.execute("SELECT COUNT(*) as count FROM photos").fetchone()['count']
    
    # Get upload folder info
    upload_files = len(os.listdir(UPLOAD_FOLDER)) if os.path.exists(UPLOAD_FOLDER) else 0
    upload_size = sum(os.path.getsize(os.path.join(UPLOAD_FOLDER, f)) for f in os.listdir(UPLOAD_FOLDER) if os.path.isfile(os.path.join(UPLOAD_FOLDER, f))) if os.path.exists(UPLOAD_FOLDER) else 0
    
    # Convert to MB for readability
    db_size_mb = db_size / (1024 * 1024)
    upload_size_mb = upload_size / (1024 * 1024)
    
    status_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Database Status</title>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
        <style>
            body {{
                font-family: 'Poppins', sans-serif;
                background: linear-gradient(135deg, #667eea, #764ba2);
                padding: 20px;
                color: white;
            }}
            .container {{
                background: rgba(255,255,255,0.15);
                backdrop-filter: blur(15px);
                border-radius: 20px;
                padding: 30px;
                max-width: 800px;
                margin: 0 auto;
            }}
            h1 {{ margin-bottom: 20px; }}
            .stat-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-bottom: 20px;
            }}
            .stat-card {{
                background: rgba(255,255,255,0.2);
                padding: 20px;
                border-radius: 12px;
            }}
            .stat-value {{ font-size: 24px; font-weight: 600; }}
            .stat-label {{ font-size: 14px; opacity: 0.8; }}
            .info {{ margin-top: 20px; }}
            .info-item {{ margin: 10px 0; }}
            .back-btn {{
                display: inline-block;
                margin-top: 20px;
                padding: 12px 24px;
                background: #667eea;
                color: white;
                text-decoration: none;
                border-radius: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Database Status</h1>
            
            <div class="stat-grid">
                <div class="stat-card">
                    <div class="stat-value">{user_count}</div>
                    <div class="stat-label">Total Users</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{entry_count}</div>
                    <div class="stat-label">Total Entries</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{photo_count}</div>
                    <div class="stat-label">Total Photos</div>
                </div>
            </div>
            
            <div class="info">
                <h3>📁 Storage Info</h3>
                <div class="info-item">📂 Database Path: {db_path}</div>
                <div class="info-item">💾 Database Size: {db_size_mb:.2f} MB</div>
                <div class="info-item">📸 Upload Folder: {UPLOAD_FOLDER}</div>
                <div class="info-item">🖼️ Total Photos Files: {upload_files}</div>
                <div class="info-item">📦 Photos Size: {upload_size_mb:.2f} MB</div>
                <div class="info-item">✅ Database Persistent: {'Yes' if '/data' in db_path else 'No'}</div>
            </div>
            
            <a href="/admin" class="back-btn">← Back to Admin</a>
        </div>
    </body>
    </html>
    """
    
    return status_html

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

@app.route("/admin_delete/<int:id>")
def admin_delete(id):
    if not session.get("user") or not session.get("is_admin"):
        return redirect("/")
    
    db = get_db()
    
    try:
        # Delete user (entries and photos will be deleted automatically due to CASCADE)
        db.execute("DELETE FROM users WHERE id = ? AND username != 'admin'", (id,))
        db.commit()
    except Exception as e:
        print(f"Error deleting user: {e}")
    
    return redirect("/admin")

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
    email = request.form.get("email", "").strip()
    
    if not username or not password or not email:
        return render_template_string(LOGIN_TEMPLATE, 
                                    message="All fields are required", 
                                    message_type="error",
                                    active_tab='signup')
    
    if len(password) < 4:
        return render_template_string(LOGIN_TEMPLATE, 
                                    message="Password must be at least 4 characters", 
                                    message_type="error",
                                    active_tab='signup')
    
    db = get_db()
    try:
        db.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
                   (username, generate_password_hash(password), email))
        db.commit()
        return render_template_string(LOGIN_TEMPLATE, 
                                    message="Account created! Please login.", 
                                    message_type="success",
                                    active_tab='login')
    except sqlite3.IntegrityError as e:
        if "username" in str(e):
            return render_template_string(LOGIN_TEMPLATE, 
                                        message="Username already exists", 
                                        message_type="error",
                                        active_tab='signup')
        else:
            return render_template_string(LOGIN_TEMPLATE, 
                                        message="Email already registered", 
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

@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    if not session.get("user"):
        return redirect("/")
    
    if request.method == "GET":
        return render_template_string(CHANGE_PASSWORD_PAGE)
    
    # POST request
    current_password = request.form["current_password"]
    new_password = request.form["new_password"]
    confirm_password = request.form["confirm_password"]
    
    if new_password != confirm_password:
        return render_template_string(CHANGE_PASSWORD_PAGE,
                                    message="New passwords do not match",
                                    message_type="error")
    
    if len(new_password) < 4:
        return render_template_string(CHANGE_PASSWORD_PAGE,
                                    message="Password must be at least 4 characters",
                                    message_type="error")
    
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    
    if not check_password_hash(user["password"], current_password):
        return render_template_string(CHANGE_PASSWORD_PAGE,
                                    message="Current password is incorrect",
                                    message_type="error")
    
    db.execute("UPDATE users SET password = ? WHERE id = ?",
              (generate_password_hash(new_password), session["user_id"]))
    db.commit()
    
    return render_template_string(CHANGE_PASSWORD_PAGE,
                                message="Password changed successfully!",
                                message_type="success")

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template_string(FORGOT_PASSWORD_PAGE, step='email')
    
    # POST request - send OTP
    email = request.form["email"]
    
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    
    if not user:
        return render_template_string(FORGOT_PASSWORD_PAGE,
                                    step='email',
                                    message="Email not found in our records",
                                    message_type="error")
    
    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))
    
    # Store OTP with timestamp (valid for 10 minutes)
    otp_storage[email] = {
        'otp': otp,
        'timestamp': datetime.now(),
        'user_id': user['id']
    }
    
    # Send OTP via email
    if send_otp_email(email, otp):
        return render_template_string(FORGOT_PASSWORD_PAGE,
                                    step='otp',
                                    email=email,
                                    message=f"OTP sent to {email}",
                                    message_type="success")
    else:
        return render_template_string(FORGOT_PASSWORD_PAGE,
                                    step='email',
                                    message="Failed to send OTP. Please try again.",
                                    message_type="error")

@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    email = request.form["email"]
    entered_otp = request.form["otp"]
    
    if email not in otp_storage:
        return render_template_string(FORGOT_PASSWORD_PAGE,
                                    step='email',
                                    message="OTP expired. Please request again.",
                                    message_type="error")
    
    stored = otp_storage[email]
    
    # Check if OTP is expired (10 minutes)
    if datetime.now() - stored['timestamp'] > timedelta(minutes=10):
        del otp_storage[email]
        return render_template_string(FORGOT_PASSWORD_PAGE,
                                    step='email',
                                    message="OTP expired. Please request again.",
                                    message_type="error")
    
    if stored['otp'] == entered_otp:
        # OTP verified, proceed to reset password
        return render_template_string(FORGOT_PASSWORD_PAGE,
                                    step='reset',
                                    email=email,
                                    message="OTP verified! Set your new password.",
                                    message_type="success")
    else:
        return render_template_string(FORGOT_PASSWORD_PAGE,
                                    step='otp',
                                    email=email,
                                    message="Invalid OTP. Please try again.",
                                    message_type="error")

@app.route("/resend-otp", methods=["POST"])
def resend_otp():
    email = request.form["email"]
    
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    
    if not user:
        return render_template_string(FORGOT_PASSWORD_PAGE,
                                    step='email',
                                    message="Email not found",
                                    message_type="error")
    
    # Generate new OTP
    otp = str(random.randint(100000, 999999))
    
    # Update storage
    otp_storage[email] = {
        'otp': otp,
        'timestamp': datetime.now(),
        'user_id': user['id']
    }
    
    # Send new OTP
    if send_otp_email(email, otp):
        return render_template_string(FORGOT_PASSWORD_PAGE,
                                    step='otp',
                                    email=email,
                                    message="New OTP sent successfully!",
                                    message_type="success")
    else:
        return render_template_string(FORGOT_PASSWORD_PAGE,
                                    step='otp',
                                    email=email,
                                    message="Failed to send OTP. Try again.",
                                    message_type="error")

@app.route("/reset-password", methods=["POST"])
def reset_password():
    email = request.form["email"]
    new_password = request.form["password"]
    confirm_password = request.form["confirm_password"]
    
    if new_password != confirm_password:
        return render_template_string(FORGOT_PASSWORD_PAGE,
                                    step='reset',
                                    email=email,
                                    message="Passwords do not match",
                                    message_type="error")
    
    if len(new_password) < 4:
        return render_template_string(FORGOT_PASSWORD_PAGE,
                                    step='reset',
                                    email=email,
                                    message="Password must be at least 4 characters",
                                    message_type="error")
    
    if email not in otp_storage:
        return render_template_string(FORGOT_PASSWORD_PAGE,
                                    step='email',
                                    message="Session expired. Please try again.",
                                    message_type="error")
    
    user_id = otp_storage[email]['user_id']
    
    db = get_db()
    db.execute("UPDATE users SET password = ? WHERE id = ?",
              (generate_password_hash(new_password), user_id))
    db.commit()
    
    # Clear OTP
    if email in otp_storage:
        del otp_storage[email]
    
    return render_template_string(LOGIN_TEMPLATE,
                                message="Password reset successful! Please login.",
                                message_type="success",
                                active_tab='login')

@app.route("/new")
def new_entry():
    if not session.get("user"):
        return redirect("/")
    
    today = datetime.now().strftime("%Y-%m-%d")
    return render_template_string(NEW_ENTRY_PAGE, today=today)

@app.route("/save", methods=["POST"])
def save_entry():
    if not session.get("user"):
        return redirect("/")
    
    date = request.form["date"]
    content = request.form["content"]
    files = request.files.getlist("photos")
    
    if not date or not content:
        return render_template_string(NEW_ENTRY_PAGE,
                                    message="Date and content are required",
                                    today=datetime.now().strftime("%Y-%m-%d"))
    
    db = get_db()
    
    # Insert entry
    cursor = db.execute(
        "INSERT INTO entries (user_id, date, content) VALUES (?, ?, ?)",
        (session["user_id"], date, content)
    )
    db.commit()
    
    entry_id = cursor.lastrowid
    
    # Save photos
    if files:
        for file in files:
            if file and file.filename:
                # Generate unique filename
                ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'jpg'
                filename = f"{uuid.uuid4().hex}.{ext}"
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                
                db.execute(
                    "INSERT INTO photos (entry_id, filename) VALUES (?, ?)",
                    (entry_id, filename)
                )
        db.commit()
    
    return render_template_string(SUCCESS_PAGE,
                                message="Entry saved successfully!",
                                submessage="Your diary entry has been saved.",
                                entry_id=entry_id)

@app.route("/view/<int:id>")
def view_entry(id):
    if not session.get("user"):
        return redirect("/")
    
    db = get_db()
    
    # Get entry
    entry = db.execute(
        "SELECT * FROM entries WHERE id = ? AND user_id = ?",
        (id, session["user_id"])
    ).fetchone()
    
    if not entry:
        return redirect("/entries")
    
    # Get photos for this entry
    photos = db.execute(
        "SELECT * FROM photos WHERE entry_id = ?",
        (id,)
    ).fetchall()
    
    return render_template_string(VIEW_ENTRY_PAGE, entry=entry, photos=photos)

@app.route("/edit/<int:id>")
def edit_entry(id):
    if not session.get("user"):
        return redirect("/")
    
    db = get_db()
    
    # Get entry
    entry = db.execute(
        "SELECT * FROM entries WHERE id = ? AND user_id = ?",
        (id, session["user_id"])
    ).fetchone()
    
    if not entry:
        return redirect("/entries")
    
    # Get photos
    photos = db.execute(
        "SELECT * FROM photos WHERE entry_id = ?",
        (id,)
    ).fetchall()
    
    return render_template_string(EDIT_ENTRY_PAGE, entry=entry, photos=photos)

@app.route("/update/<int:id>", methods=["POST"])
def update_entry(id):
    if not session.get("user"):
        return redirect("/")
    
    date = request.form["date"]
    content = request.form["content"]
    files = request.files.getlist("photos")
    
    db = get_db()
    
    # Check if entry exists and belongs to user
    entry = db.execute(
        "SELECT * FROM entries WHERE id = ? AND user_id = ?",
        (id, session["user_id"])
    ).fetchone()
    
    if not entry:
        return redirect("/entries")
    
    # Update entry
    db.execute(
        "UPDATE entries SET date = ?, content = ? WHERE id = ?",
        (date, content, id)
    )
    db.commit()
    
    # Save new photos if any
    if files:
        for file in files:
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'jpg'
                filename = f"{uuid.uuid4().hex}.{ext}"
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                
                db.execute(
                    "INSERT INTO photos (entry_id, filename) VALUES (?, ?)",
                    (id, filename)
                )
        db.commit()
    
    return redirect(f"/view/{id}")

@app.route("/delete/<int:id>")
def delete_entry(id):
    if not session.get("user"):
        return redirect("/")
    
    db = get_db()
    
    # Delete entry (photos will be deleted automatically due to CASCADE)
    db.execute(
        "DELETE FROM entries WHERE id = ? AND user_id = ?",
        (id, session["user_id"])
    )
    db.commit()
    
    return redirect("/entries")

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ---------------- RUN APP ----------------

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port, debug=False)