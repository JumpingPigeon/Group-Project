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
        selected_role = request.form.get('role', '').strip()

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

                is_authorized = False # Flag to check if user belongs to the selected role
                first_name = "User" # Default name

            # Role-based authorization checks
                # 1. Helpdesk
                if selected_role == 'helpdesk':
                    # Check if user is in Helpdesk and if so, get their position for dashboard display
                    role_data = conn.execute('SELECT email, position FROM Helpdesk WHERE email = ?', (input_email,)).fetchone()
                    if role_data:
                        is_authorized = True
                        
                        # Get name from bidder table (assume they are student bidder), else use email prefix as name
                        bidder_info = conn.execute('SELECT first_name FROM Bidders WHERE email = ?', (input_email,)).fetchone()
                        if bidder_info:
                            first_name = bidder_info['first_name']
                        else:
                            first_name = input_email.split('@')[0]
                        session['position'] = role_data['position']

                elif selected_role == 'seller':
                    # Seller: Student / Local Vendor
                    role_data = conn.execute('SELECT email FROM Sellers WHERE email = ?', (input_email,)).fetchone()
                    if role_data:
                        is_authorized = True
                        
                        bidder_info = conn.execute('SELECT first_name FROM Bidders WHERE email = ?', (input_email,)).fetchone()
                        vendor_info = conn.execute('SELECT Business_Name FROM Local_Vendors WHERE Email = ?', (input_email,)).fetchone()
                        
                        if bidder_info:
                            first_name = bidder_info['first_name']
                        elif vendor_info:
                            first_name = vendor_info['Business_Name']
                        else:
                            first_name = "Null"

                elif selected_role == 'bidder':
                    role_data = conn.execute('SELECT first_name FROM Bidders WHERE email = ?', (input_email,)).fetchone()
                    if role_data:
                        is_authorized = True
                        first_name = role_data['first_name']

                if not is_authorized:
                    flash(f'Access Denied: You do not have permissions to access, please contact support.', 'warning')
                    return render_template('login.html')

                # Save user info in session and redirect to appropriate dashboard
                session['user_id'] = user['email']
                session['email'] = user['email']
                session['first_name'] = first_name
                session['user_type'] = selected_role

                flash(f'Welcome back, {first_name}!', 'success')
                return redirect(url_for(f'{selected_role}_dashboard'))

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
    
    if session.get('user_type') != 'helpdesk':
        flash('Access denied.', 'danger')
        return redirect(url_for('login'))

    try:
        with get_db_connection() as conn:
            helpdesk_email = session.get('email')
            all_requests = conn.execute('''
                SELECT request_id, sender_email, helpdesk_staff_email, request_type, request_desc, request_status 
                FROM Requests
                WHERE request_status = 0
                ORDER BY request_id ASC
            ''').fetchall()
            
            # Categorize requests into unassigned(pesudo email) and assigned to current user
            unassigned = [i for i in all_requests if i['helpdesk_staff_email'] == 'helpdeskteam@lsu.edu']
            my_assigned = [n for n in all_requests if n['helpdesk_staff_email'] == helpdesk_email]

    except Exception as e:
        unassigned, my_assigned = [], []

    return render_template("helpdesk_dashboard.html", 
                           unassigned = unassigned, 
                           my_assigned = my_assigned)

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
    query = request.args.get('q', '').strip() # Get keyword search query
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()
    
    user_email = session.get('user_id')
    
    try:
        with get_db_connection() as conn:
            base_query = '''
                SELECT 
                    al.Seller_Email, 
                    al.Listing_ID, 
                    al.Auction_Title, 
                    al.Product_Name, 
                    al.Reserve_Price, 
                    al.Max_bids, 
                    al.Status,
                    al.Description,
                    c.category_name as Category_Name,
                    COALESCE((SELECT MAX(b.Bid_price) FROM Bids b WHERE b.Seller_Email = al.Seller_Email AND b.Listing_ID = al.Listing_ID), 0) as current_bid,
                    (SELECT COUNT(*) FROM Bids b WHERE b.Seller_Email = al.Seller_Email AND b.Listing_ID = al.Listing_ID) as bid_count,
                    COALESCE(bidder.first_name, lv.Business_Name, 'Unknown') as Seller_First_Name,
                    COALESCE(bidder.last_name, '') as Seller_Last_Name
                FROM Auction_Listings al
                LEFT JOIN Categories c ON al.Category_Name = c.category_name
                LEFT JOIN Bidders bidder ON al.Seller_Email = bidder.email
                LEFT JOIN Local_Vendors lv ON al.Seller_Email = lv.Email
                WHERE al.Status = 1
            '''
            
            params = []
            conditions = []
            
            # Keyword search across multiple fields
            if query:
                search_conditions = [
                    "al.Auction_Title LIKE ?",
                    "al.Product_Name LIKE ?",
                    "al.Description LIKE ?",
                    "c.category_name LIKE ?",
                    "bidder.first_name LIKE ?",
                    "bidder.last_name LIKE ?",
                    "lv.Business_Name LIKE ?",
                    "al.Seller_Email LIKE ?"
                ]
                
                like_query = f"%{query}%" # partial match
                conditions.append("(" + " OR ".join(search_conditions) + ")")
                params.extend([like_query] * len(search_conditions)) # Add the same like_query for each search condition
            
            if min_price:
                try:
                    min_val = float(min_price)
                    conditions.append("al.Reserve_Price >= ?")
                    params.append(min_val)
                except ValueError: # If not a number than ignore the min price filter
                    pass

            if max_price:
                try:
                    max_val = float(max_price)
                    conditions.append("al.Reserve_Price <= ?")
                    params.append(max_val)
                except ValueError: # If not a number than ignore the max price filter
                    pass

            if conditions:
                base_query += " AND " + " AND ".join(conditions) # Combine all addtional conditions with AND
            
            base_query += " ORDER BY al.Listing_ID DESC" # Show newest listings first
            
            items = conn.execute(base_query, params).fetchall() # Get all matching items
            
            # Find all watchlist items for the user in one query to avoid N+1 problem
            if user_email:
                watchlist_items = conn.execute('''
                    SELECT Seller_Email, Listing_ID FROM Watchlist WHERE Bidder_Email = ?
                ''', (user_email,)).fetchall()
                
                watchlist_set = {(item['Seller_Email'], item['Listing_ID']) for item in watchlist_items}
                
                items_with_watchlist = []
                for item in items:
                    item_dict = dict(item)
                    # Make query result into a dict so we can add the in_watchlist key without affecting the original SQL Row object
                    item_dict['in_watchlist'] = (item['Seller_Email'], item['Listing_ID']) in watchlist_set
                    items_with_watchlist.append(item_dict) # Create a new list of dicts that includes the in_watchlist key for each item
                
                items = items_with_watchlist
            
    except Exception as e:
        flash(f'Error performing search: {str(e)}', 'danger')
        items = []
    
    # Return the search results along with the original query and price filters to repopulate the search form
    return render_template('search.html', 
                         items=items, 
                         query=query,
                         min_price=min_price,
                         max_price=max_price)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for(f'{session.get("user_type")}_dashboard'))

    if request.method == 'POST':
        # Get information from form
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        user_type = request.form.get('user_type', '').strip() # 'bidder', 'seller', 'helpdesk'
        seller_sub_type = request.form.get('seller_sub_type', '').strip() # 'student' or 'vendor'

        if not email or not password or not user_type:
            flash('Please fill all required fields.', 'danger')
            return render_template('register.html')

        if user_type == 'helpdesk':
            flash('Contact System Administrators to create a HelpDesk account.', 'danger')
            return render_template('register.html')

        street_num = request.form.get('street_num', '').strip()
        street_name = request.form.get('street_name', '').strip()
        zipcode = request.form.get('zipcode', '').strip()

        pwd_hash = generate_password_hash(password)

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                # 1. Insert into Users table
                cursor.execute('INSERT INTO Users (email, password) VALUES (?, ?)', (email, pwd_hash))

                # 2. Insert into Address table and get the primary key
                cursor.execute(
                    'INSERT INTO Address (zipcode, street_num, street_name) VALUES (?, ?, ?)',
                    (zipcode, street_num, street_name)
                )

                addr_id = cursor.lastrowid

                # 3. Depending on user type, insert into corresponding tables

                # A. Bidder/Student Seller
                if user_type == 'bidder' or (user_type == 'seller' and seller_sub_type == 'student'):
                    first_name = request.form.get('firstname', '').strip()
                    last_name = request.form.get('lastname', '').strip()
                    age = request.form.get('age', '').strip()
                    major = request.form.get('major', '').strip()

                    cursor.execute('''
                        INSERT INTO Bidders (email, first_name, last_name, age, home_address_id, major)
                        VALUES (?, ?, ?, ?, ?, ?)''', 
                    (email, first_name, last_name, age, addr_id, major))

                    # Credit Card Info
                    card_num = request.form.get('card_num', '').strip()
                    card_type = request.form.get('card_type', '').strip()
                    exp_m = request.form.get('exp_m', '').strip()
                    exp_y = request.form.get('exp_y', '').strip()
                    cvv = request.form.get('cvv', '').strip()

                    if card_num:
                        cursor.execute('''
                            INSERT INTO Credit_Cards (credit_card_num, card_type, expire_month, expire_year, security_code, Owner_email)
                            VALUES (?, ?, ?, ?, ?, ?)''', 
                        (card_num, card_type, exp_m, exp_y, cvv, email))

                    # If student seller, must generate a seller request (This will not work for Prototype Demo b/c it is not required))
                    if user_type == 'seller' and seller_sub_type == 'student':
                        bank_routing = request.form.get('bank_routing', '').strip()
                        bank_account = request.form.get('bank_account', '').strip()
                        
                        bank_info_desc = f"Routing:{bank_routing}|Account:{bank_account}"

                        cursor.execute('''
                            INSERT INTO Requests (sender_email, helpdesk_staff_email, request_type, request_desc, request_status)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (email, 'helpdeskteam@lsu.edu', 'SellerReg', bank_info_desc, 0))

                # B. Local Vendor
                elif user_type == 'seller' and seller_sub_type == 'vendor':
                    bank_routing = request.form.get('bank_routing', '').strip()
                    bank_account = request.form.get('bank_account', '').strip()
                    business_name = request.form.get('business_name', '').strip()
                    business_phone = request.form.get('business_phone', '').strip()

                    temp_desc = f"Routing:{bank_routing}|Account:{bank_account}|BizName:{business_name}|Phone:{business_phone}|AddrID:{addr_id}"

                    cursor.execute('''
                        INSERT INTO Requests (sender_email, helpdesk_staff_email, request_type, request_desc, request_status)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (email, 'helpdeskteam@lsu.edu', 'SellerReg', temp_desc, 0))

                conn.commit()
                
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            flash(f'Email may already exist. Error: {str(e)}', 'danger')
            return render_template('register.html')
        
    return render_template('register.html')

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
    return render_template('categories.html',category_name=name,breadcrumb=bc,subcategories=sc,listings=l)

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
        

        #test
        # recent bids
        rb = conn.execute(
            '''
            SELECT Bid_ID, Bidder_Email, Bid_Price
            FROM Bids
            WHERE Seller_Email = ? AND Listing_ID = ?
            ORDER BY Bid_ID DESC
            LIMIT 10
            ''',
            (seller_email, listing_id)).fetchall()

        # count + highest bid
        row = conn.execute(
            '''
            SELECT COUNT(*) AS bid_count, MAX(Bid_Price) AS highest_bid
            FROM Bids
            WHERE Seller_Email = ? AND Listing_ID = ?
            ''',
            (seller_email, listing_id)).fetchone()

        if row:
            bid_count = row["bid_count"]
            if row["highest_bid"] != None:
                highest_bid = row["highest_bid"]
            else:
                highest_bid = 0.0
        else:
            bid_count = 0
            highest_bid = 0.0
        max_bids = int(r["Max_bids"] or 0)
        remaining_bids = max_bids - int(bid_count)
        if remaining_bids < 0:
            remaining_bids = 0
        if r["Status"] == 1 and remaining_bids > 0:
            can_place_bid = True
        else:
            can_place_bid = False
        #test
        
        
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
        highest_bid=highest_bid,
        bid_count=bid_count,
        remaining_bids=remaining_bids,
        can_place_bid=can_place_bid,
        is_winner=False,
        recent_bids=rb,
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
    rating_val = request.form.get("rating", "").strip()
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