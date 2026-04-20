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

def build_bc(conn, c_name):
    bc = []
    current = c_name    
    for _ in range(20):
        r = conn.execute('SELECT parent_category FROM Categories WHERE category_name = ?',(current,)).fetchone()
        if r == None:
            break;
        elif r['parent_category'] == 'Root':
            bc.insert(0, ('All Categories', url_for('categories')))
            break;
        parent = r['parent_category']
        bc.insert(0, (parent, url_for('category_detail', name=parent)))
        current = parent
    return bc



@app.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to their dashboard
    if 'user_id' in session:
        return redirect(url_for(f'{session["user_type"]}_dashboard'))
    
    # Login form submission handling
    if request.method == 'POST':
        input_email = request.form.get('email', '').strip()
        input_password = request.form.get('password', '').strip()

        if not input_email or not input_password:
            flash('Email and password cannot be empty', 'danger')
            return render_template('login.html')

        try:
            with get_db_connection() as conn:
                user = conn.execute('SELECT email, password FROM Users WHERE email = ?', (input_email,)).fetchone()
                
                if not user:
                    flash('This email is not registered.', 'danger')
                    return render_template('login.html')
                
                if not check_password_hash(user['password'], input_password):
                    flash('Invalid password.', 'danger')
                    return render_template('login.html')

                user_type = None
                first_name = "User"
                
                helpdesk = conn.execute('SELECT email FROM Helpdesk WHERE email = ?', (input_email,)).fetchone()
                if helpdesk:
                    user_type = 'helpdesk'
                else:
                    seller = conn.execute('SELECT email FROM Sellers WHERE email = ?', (input_email,)).fetchone()
                    if seller:
                        user_type = 'seller'
                        # first_name = input_email.split('@')[0]
                    else:
                        bidder = conn.execute('SELECT first_name FROM Bidders WHERE email = ?', (input_email,)).fetchone()
                        user_type = 'bidder'
                        first_name = bidder['first_name'] if bidder else "Bidder"

                if not user_type:
                    flash('Error! Please try again later.', 'warning')
                    return render_template('login.html')

               # Save user info in session for later use
                session['user_id'] = user['email']
                session['email'] = user['email']
                session['first_name'] = first_name
                session['user_type'] = user_type

                flash(f'Welcome back, {first_name}!', 'success')
                return redirect(url_for(f'{user_type}_dashboard'))

        except Exception as e:
            flash(f'System error: {str(e)}', 'danger')
            return render_template('login.html')
    
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

def dashboard_endpoint(user_type):
    if user_type is None:
        return 'login'
    t = str(user_type).strip().lower()
    if t in ('bidder', 'buyer'):
        return 'bidder_dashboard'
    return f'{t}_dashboard'


@app.route('/bidder_dashboard')
def bidder_dashboard():
    if 'user_id' not in session:
        flash('Login Required to view this page', 'danger')
        return redirect(url_for('login'))

    role = str(session.get('user_type', '')).strip().lower()
    if role not in ('bidder', 'buyer'):
        flash('Access denied.', 'danger')
        return redirect(url_for('login'))

    return render_template(
        'bidder_dashboard.html',
        email=session.get('email'),
        first_name=session.get('first_name')
    )

@app.route("/helpdesk_dashboard")
def helpdesk_dashboard():
    if not session.get("email"):
        return redirect(url_for("login"))
    return render_template("helpdesk_dashboard.html")

@app.route("/seller_dashboard")
def seller_dashboard():
    if not session.get("email"):
        return redirect(url_for("login"))
    return render_template("seller_dashboard.html")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search')
def search():
    query = request.args.get('q')
    return f"You searched for: {query}. Please login to see results."

@app.route('/register', methods=['GET', 'POST'])
def register():
    pass

@app.route('/account-redirect')
def account_redirect():
    if 'user_id' in session:
        return redirect(url_for(f'{session["user_type"]}_dashboard'))
    return redirect(url_for('login'))





if __name__ == '__main__':
    app.run()
    #app.run(debug=True)