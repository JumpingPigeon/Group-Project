from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps # To create reusable login_required decorator
import sqlite3 as sql

app = Flask(__name__)
app.secret_key = "dev_key"
database = 'nittany_auction.db'

host = 'http://127.0.0.1:5000/'

def get_db_connection():
    conn = sql.connect(database)
    conn.row_factory = sql.Row
    return conn

@app.route("/")
def home():
    return "Server running. Go to /helpdesk_dashboard"

@app.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to their dashboard; otherwise, show login page
    if 'user_id' in session:
        return redirect(url_for(f'{session["user_type"]}_dashboard'))

    # Process login form submission
    if request.method == 'POST':
        input_email = request.form.get('email', '').strip()
        input_password = request.form.get('password', '').strip()

        if not input_email or not input_password:
            flash('Email and password cannot be empty', 'danger')
            return render_template('login.html')

        try:
            with get_db_connection() as conn:
                user = conn.execute('SELECT user_id, email, password_hash, first_name, user_type FROM Users WHERE email = ?', (input_email,)).fetchone()
        except Exception as e:
            flash(f'System exception, please try again: {str(e)}', 'danger')
            return render_template('login.html')

        # Check if user exists
        if not user:
            flash('This email is not registered, please register an account first', 'danger')
            return render_template('login.html')
        
        # Hash password verification
        if not check_password_hash(user['password_hash'], input_password):
            flash('Invalid password, please try again', 'danger')
            return render_template('login.html')

        # Save user info in session (login state)
        session['user_id'] = user['user_id']
        session['email'] = user['email']
        session['first_name'] = user['first_name']
        session['user_type'] = user['user_type']

        # Redirect to respective dashboard based on user type
        flash(f'Welcome back, {user["first_name"]}!', 'success')
        return redirect(url_for(f'{user["user_type"]}_dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Successfully logged out', 'success')
    return redirect(url_for('login'))

# Resuable login_required decorator for all routes that require authentication
def login_required(original_function):
    @wraps(original_function)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Login Required to view this page', 'danger')
            return redirect(url_for('login'))
        return original_function(*args, **kwargs) # If already logged in
    return wrapper

@app.route("/helpdesk_dashboard")
def helpdesk_dashboard():
    if not session.get("user_email"):
        return redirect(url_for("login"))
    return render_template("helpdesk_dashboard.html")

@app.route('/')
def index():
    # If user is already logged in, redirect to their dashboard; otherwise, go to login page
    if 'user_id' in session:
        return redirect(url_for(f'{session["user_type"]}_dashboard'))
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run()
    #app.run(debug=True)