from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps # To create reusable login_required decorator
import sqlite3 as sql
from datetime import date

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

@app.route('/categories')
def categories():
    with get_db_connection() as conn:
        cats = conn.execute(
            'SELECT category_name FROM Categories WHERE parent_category = ?', ('Root',)
        ).fetchall()
    return render_template('categories.html', categories=cats)

@app.route('/categories/<path:name>')
def category_detail(name):
    with get_db_connection() as conn:
        bc = build_bc(conn, name)
        sc = conn.execute(
            'SELECT category_name FROM Categories WHERE parent_category = ?',
            (name,)
        ).fetchall()
        l = conn.execute(
            '''
            SELECT Seller_Email, Listing_ID, Auction_Title, Product_Name, Reserve_Price, Status
            FROM Auction_Listings
            WHERE Category = ? AND Status = 1
            ''',
            (name,)
        ).fetchall()
    return render_template('category_detail.html',category_name=name,breadcrumb=bc,subcategories=sc,listings=l)

@app.route('/listing/<seller_email>/<int:listing_id>')
def listing(seller_email, listing_id):
    with get_db_connection() as conn:
        r = conn.execute(
            '''
            SELECT * FROM Auction_Listings
            WHERE Seller_Email = ? AND Listing_ID = ?
            ''', 
            (seller_email, listing_id)).fetchone()
        if r == None:
            return "Listing not found", 404
        #seller avg rating + count
        s = conn.execute(
                '''
                SELECT ROUND(AVG(Rating), 1) AS avg_rating, COUNT(*) AS num_ratings
                FROM Ratings
                WHERE Seller_Email = ?
                ''',
                (seller_email,)).fetchone()
        if s:
            avg_rating = s["avg_rating"] if s["avg_rating"] is not None else None
            num_ratings = s["num_ratings"]
        else:
            avg_rating = None
            num_ratings = 0
        #last 10 reviews
        reviews = conn.execute(
                '''
                SELECT Bidder_Email, Date, Rating, Rating_Desc
                FROM Ratings
                WHERE Seller_Email = ?
                ORDER BY Date DESC
                LIMIT 10
                ''',
                (seller_email,)).fetchall()
        #eligibility + duplicate today
        can_r = False
        already_r = False
        b_email = session.get("email")
        today = date.today().isoformat()
        if b_email and session.get("user_type") == "bidder":
            p = conn.execute(
                '''
                SELECT 1
                FROM Transactions
                WHERE Seller_Email = ?
                    AND Listing_ID = ?
                    AND Bidder_Email = ?
                    AND Payment > 0
                ''',
                (seller_email, listing_id, b_email)).fetchone()
            if p:
                can_r = True
                dup = conn.execute(
                    '''
                    SELECT 1
                    FROM Ratings
                    WHERE Bidder_Email = ? AND Seller_Email = ? AND Date = ?
                    ''',
                    (b_email, seller_email, today)).fetchone()
                already_r = (dup is not None)
    return render_template(
        'item_detail.html',
        listing=r,
        avg_rating=avg_rating,
        num_ratings=num_ratings,
        reviews=reviews,
        can_r=can_r,
        already_r=already_r
    )

@app.route('/rate/<seller_email>/<int:listing_id>', methods=['POST'])
def rate_seller(seller_email, listing_id):
    if session.get("user_type") != "bidder" or not session.get("email"):
        flash("Only logged-in bidders can rate.", "danger")
        return redirect(url_for("listing", seller_email=seller_email, listing_id=listing_id))

    bidder_email = session["email"]
    today = date.today().isoformat()
    try:
        rating_val = int(rating_val)
    except:
        flash("Rating must be a number from 1 to 5.", "danger")
        return redirect(url_for("listing", seller_email=seller_email, listing_id=listing_id))
    if rating_val < 1 or rating_val > 5:
        flash("Rating must be between 1 and 5.", "danger")
        return redirect(url_for("listing", seller_email=seller_email, listing_id=listing_id))

    rating_desc = request.form.get("rating_desc", "").strip()
    with get_db_connection() as conn:
        paid = conn.execute(
            '''
            SELECT 1
            FROM Transactions
            WHERE Seller_Email = ?
              AND Listing_ID = ?
              AND Bidder_Email = ?
              AND Payment > 0
            ''',
            (seller_email, listing_id, bidder_email)).fetchone()

        if not paid:
            flash("You can only rate after a successful paid purchase for this listing.", "danger")
            return redirect(url_for("listing", seller_email=seller_email, listing_id=listing_id))
        dup = conn.execute(
            '''
            SELECT 1
            FROM Ratings
            WHERE Bidder_Email = ? AND Seller_Email = ? AND Date = ?
            ''',
            (bidder_email, seller_email, today)).fetchone()
        if dup:
            flash("You already rated this seller today.", "warning")
            return redirect(url_for("listing", seller_email=seller_email, listing_id=listing_id))
        conn.execute(
            '''
            INSERT INTO Ratings (Bidder_Email, Seller_Email, Date, Rating, Rating_Desc)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (bidder_email, seller_email, today, rating_val, rating_desc or None))
        conn.commit()
    flash("Rating submitted!", "success")
    return redirect(url_for("listing", seller_email=seller_email, listing_id=listing_id))









if __name__ == '__main__':
    app.run()
    #app.run(debug=True)