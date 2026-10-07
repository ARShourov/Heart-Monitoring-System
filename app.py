from flask import Flask, render_template, request, redirect, url_for, session
from firebase_client import signup_user, login_user
import system_core

app = Flask(__name__)
app.secret_key = "super_secret_key"

# ===== Home Route =====
@app.route('/')
def home():
    return redirect(url_for('login'))

# ===== Login =====
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = login_user(email, password)
        if user:
            session['user'] = email
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid email or password"
    return render_template('login.html', error=error)

# ===== Signup =====
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = signup_user(email, password)
        if user:
            session['user'] = email
            return redirect(url_for('dashboard'))
        else:
            error = "Signup failed. Try again."
    return render_template('signup.html', error=error)

# ===== Logout =====
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# ===== Dashboard =====
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    user_email = session['user']
    return render_template('dashboard.html', user_email=user_email)

# ===== Run Commands =====
@app.route('/run/<cmd>')
def run_command(cmd):
    if 'user' not in session:
        return "Unauthorized", 401
    user_email = session['user']

    if cmd == 'enroll':
        result = system_core.enroll_fingerprint(user_email)
    elif cmd == 'verify':
        result = system_core.verify_and_monitor(user_email)
    elif cmd == 'delete':
        result = system_core.delete_fingerprint(user_email)
    elif cmd == 'pulse':
        result = system_core.pulse_check(user_email)
    else:
        result = "Invalid command"

    return str(result)

# ===== Run App =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
