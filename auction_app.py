from flask import Flask, render_template, request, redirect, url_for, session, flash, get_flashed_messages
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps # To create reusable login_required decorator
import sqlite3 as sql
import re
import uuid
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = "dev_key"
database = 'nittany_auction.db'

host = 'http://127.0.0.1:5000/'

def get_db_connection():
    conn = sql.connect(database)
    conn.row_factory = sql.Row
    return conn


def parse_money(value):
    if value is None:
        return 0.0
    cleaned = str(value).replace("$", "").replace(",", "").strip()
    if cleaned == "":
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

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

def bidder_only(original_function):
    @wraps(original_function)
    @login_required
    def wrapper(*args, **kwargs):
        role = str(session.get('user_type', '')).strip().lower()
        if role not in ('bidder', 'buyer'):
            flash('Access denied. Bidder access required.', 'danger')
            return redirect(url_for('login'))
        return original_function(*args, **kwargs)
    return wrapper

def seller_only(original_function):
    @wraps(original_function)
    @login_required
    def wrapper(*args, **kwargs):
        role = str(session.get('user_type', '')).strip().lower()
        if role != 'seller':
            flash('Access denied. Seller access required.', 'danger')
            return redirect(url_for('login'))
        return original_function(*args, **kwargs)
    return wrapper

def helpdesk_only(original_function):
    @wraps(original_function)
    @login_required
    def wrapper(*args, **kwargs):
        role = str(session.get('user_type', '')).strip().lower()
        if role != 'helpdesk':
            flash('Access denied. Helpdesk access required.', 'danger')
            return redirect(url_for('login'))
        return original_function(*args, **kwargs)
    return wrapper


def dashboard_endpoint(user_type):
    if user_type is None:
        return 'login'
    t = str(user_type).strip().lower()
    if t in ('bidder'):
        return 'bidder_dashboard'
    return f'{t}_dashboard'


@app.route('/bidder_dashboard')
@bidder_only
def bidder_dashboard():
    return render_template(
        'bidder_dashboard.html',
        email=session.get('email'),
        first_name=session.get('first_name')
    )

@app.route('/bidder/wallet')
@bidder_only
def bidder_wallet():
    user_email = session.get('email')
    
    try:
        with get_db_connection() as conn:
            cards = conn.execute('''
                SELECT credit_card_num, card_type, expire_month, expire_year
                FROM Credit_Cards
                WHERE Owner_email = ?
                ORDER BY card_type, expire_year, expire_month
            ''', (user_email,)).fetchall()
            
            cards_list = []
            for card in cards:
                card_dict = dict(card)
                masked_num = "**** **** **** " + card['credit_card_num'][-4:]
                card_dict['masked_number'] = masked_num
                card_dict['expiry'] = f"{card['expire_month']:02d}/{card['expire_year']}"
                cards_list.append(card_dict)
                
        return render_template('wallet.html', cards=cards_list)
    except Exception as e:
        flash(f'Error loading wallet: {str(e)}', 'danger')
        return redirect(url_for('bidder_dashboard'))


@app.route('/bidder/orders')
@bidder_only
def bidder_orders():
    user_email = session.get('email')
    
    try:
        with get_db_connection() as conn:
            orders = conn.execute('''
                SELECT 
                    t.Transaction_ID,
                    t.Seller_Email,
                    t.Listing_ID,
                    t.Bidder_Email,
                    t.Date,
                    t.Payment,
                    al.Auction_Title,
                    al.Product_Name,
                    al.Status,
                    COALESCE(bidder.first_name, lv.Business_Name, 'Unknown') as Seller_First_Name,
                    COALESCE(bidder.last_name, '') as Seller_Last_Name,
                    (SELECT COUNT(*) FROM Ratings r 
                     WHERE r.Seller_Email = t.Seller_Email 
                     AND r.Bidder_Email = t.Bidder_Email 
                     AND r.Date = t.Date) as has_rated
                FROM Transactions t
                JOIN Auction_Listings al ON t.Seller_Email = al.Seller_Email AND t.Listing_ID = al.Listing_ID
                LEFT JOIN Bidders bidder ON t.Seller_Email = bidder.email
                LEFT JOIN Local_Vendors lv ON t.Seller_Email = lv.Email
                WHERE t.Bidder_Email = ?
                ORDER BY t.Date DESC
            ''', (user_email,)).fetchall()
            
            orders_list = []
            for order in orders:
                order_dict = dict(order)
                order_dict['Payment'] = float(order_dict['Payment']) if order_dict['Payment'] else 0.0
                orders_list.append(order_dict)
                
        return render_template('order_history.html', orders=orders_list)
    except Exception as e:
        flash(f'Error loading order history: {str(e)}', 'danger')
        return redirect(url_for('bidder_dashboard'))


@app.route('/wallet/add_card', methods=['POST'])
@bidder_only
def add_credit_card():
    user_email = session.get('email')
    
    try:
        card_num = request.form.get('card_num', '').strip()
        card_type = request.form.get('card_type', '').strip()
        exp_m = request.form.get('exp_m', '').strip()
        exp_y = request.form.get('exp_y', '').strip()
        cvv = request.form.get('cvv', '').strip()
        
        if not all([card_num, card_type, exp_m, exp_y, cvv]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('bidder_wallet'))
        
        try:
            exp_month = int(exp_m)
            exp_year = int(exp_y)
            if exp_month < 1 or exp_month > 12:
                flash('Invalid expiration month.', 'danger')
                return redirect(url_for('bidder_wallet'))
        except ValueError:
            flash('Invalid expiration date format.', 'danger')
            return redirect(url_for('bidder_wallet'))
        
        with get_db_connection() as conn:
            existing = conn.execute('''
                SELECT 1 FROM Credit_Cards 
                WHERE credit_card_num = ? AND Owner_email = ?
            ''', (card_num, user_email)).fetchone()
            
            if existing:
                flash('This card is already in your wallet.', 'warning')
                return redirect(url_for('bidder_wallet'))
            
            conn.execute('''
                INSERT INTO Credit_Cards (credit_card_num, card_type, expire_month, expire_year, security_code, Owner_email)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (card_num, card_type, exp_month, exp_year, cvv, user_email))
            conn.commit()
            
        flash('Credit card added successfully!', 'success')
        return redirect(url_for('bidder_wallet'))
        
    except Exception as e:
        flash(f'Error adding card: {str(e)}', 'danger')
        import traceback
        traceback.print_exc()
        return redirect(url_for('bidder_wallet'))


@app.route('/wallet/remove_card', methods=['POST'])
@bidder_only
def remove_credit_card():
    user_email = session.get('email')
    card_num = request.form.get('card_num', '').strip()
    
    try:
        with get_db_connection() as conn:
            conn.execute('''
                DELETE FROM Credit_Cards 
                WHERE credit_card_num = ? AND Owner_email = ?
            ''', (card_num, user_email))
            conn.commit()
            
        flash('Credit card removed successfully.', 'success')
        return redirect(url_for('bidder_wallet'))
        
    except Exception as e:
        flash(f'Error removing card: {str(e)}', 'danger')
        return redirect(url_for('bidder_wallet'))


@app.route('/bidder/auction/<seller_email>/<int:listing_id>/payment', methods=['GET', 'POST'])
@bidder_only
def auction_payment(seller_email, listing_id):
    role = str(session.get('user_type', '')).strip().lower()
    bidder_email = session.get('email')
    if role not in ('bidder'):
        flash('Only bidders can complete payment.', 'danger')
        return redirect(url_for('login'))

    with get_db_connection() as conn:
        listing = conn.execute(
            '''
            SELECT Seller_Email, Listing_ID, Auction_Title, Product_Name, Status
            FROM Auction_Listings
            WHERE Seller_Email = ? AND Listing_ID = ?
            ''',
            (seller_email, listing_id)
        ).fetchone()
        if not listing:
            flash('Auction listing not found.', 'danger')
            return redirect(url_for('bidder_dashboard'))

        winning_bid = conn.execute(
            '''
            SELECT Bidder_Email, Bid_Price
            FROM Bids
            WHERE Seller_Email = ? AND Listing_ID = ?
            ORDER BY Bid_Price DESC, Bid_ID DESC
            LIMIT 1
            ''',
            (seller_email, listing_id)
        ).fetchone()

        if not winning_bid or winning_bid['Bidder_Email'] != bidder_email:
            flash('Only the winning bidder can access payment.', 'danger')
            return redirect(url_for('listing', seller_email=seller_email, listing_id=listing_id))

        existing_txn = conn.execute(
            '''
            SELECT Transaction_ID
            FROM Transactions
            WHERE Seller_Email = ? AND Listing_ID = ? AND Bidder_Email = ?
            LIMIT 1
            ''',
            (seller_email, listing_id, bidder_email)
        ).fetchone()

        saved_cards = conn.execute('''
            SELECT credit_card_num, card_type, expire_month, expire_year
            FROM Credit_Cards
            WHERE Owner_email = ?
            ORDER BY card_type, expire_year, expire_month
        ''', (bidder_email,)).fetchall()
        
        cards_list = []
        for card in saved_cards:
            card_dict = dict(card)
            masked_num = "**** **** **** " + card['credit_card_num'][-4:]
            card_dict['masked_number'] = masked_num
            card_dict['card_id'] = f"{card['credit_card_num'][-4:]}_{card['expire_month']}_{card['expire_year']}"
            cards_list.append(card_dict)

        if request.method == 'POST':
            if existing_txn:
                flash('Payment already recorded.', 'info')
                return redirect(url_for('listing', seller_email=seller_email, listing_id=listing_id))

            next_txn_id = conn.execute('SELECT COALESCE(MAX(Transaction_ID), 0) + 1 FROM Transactions').fetchone()[0]
            conn.execute(
                '''
                INSERT INTO Transactions (Transaction_ID, Seller_Email, Listing_ID, Bidder_Email, Date, Payment)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (
                    next_txn_id,
                    seller_email,
                    listing_id,
                    bidder_email,
                    date.today().strftime('%m/%d/%y'),
                    float(winning_bid['Bid_Price'])
                )
            )
            conn.commit()
            return redirect(url_for('listing', seller_email=seller_email, listing_id=listing_id))

        can_r = bool(existing_txn)
        already_r = False
        today = date.today().strftime('%m/%d/%y')
        
        if can_r:
            dup = conn.execute(
                '''
                SELECT 1 FROM Ratings
                WHERE Bidder_Email = ? AND Seller_Email = ? AND Date = ?
                ''',
                (bidder_email, seller_email, today)
            ).fetchone()
            already_r = (dup is not None)

        return render_template(
            'payment.html',
            listing=listing,
            winning_bid=float(winning_bid['Bid_Price']),
            payment_done=bool(existing_txn),
            can_r=can_r,
            already_r=already_r,
            seller_email=seller_email,
            listing_id=listing_id,
            saved_cards=cards_list
        )

@app.route("/helpdesk_dashboard")
@login_required
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
@seller_only
def seller_dashboard():    
    seller_email = session.get('email')
    
    try:
        with get_db_connection() as conn:
            total_balance = conn.execute('''
                SELECT SUM(Payment) as total
                FROM Transactions
                WHERE Seller_Email = ?
            ''', (seller_email,)).fetchone()['total']
            
            if total_balance is None:
                total_balance = 0.0
            else:
                total_balance = float(total_balance)
            
            total_promo_fees = conn.execute('''
                SELECT SUM(al.promotion_fee) as total_fees
                FROM Auction_Listings al
                JOIN Transactions t ON al.Seller_Email = t.Seller_Email AND al.Listing_ID = t.Listing_ID
                WHERE al.Seller_Email = ? AND al.is_promoted = 1
            ''', (seller_email,)).fetchone()['total_fees']
            
            if total_promo_fees is None:
                total_promo_fees = 0.0
            else:
                total_promo_fees = float(total_promo_fees)
            
            actual_balance = total_balance - total_promo_fees
                
    except Exception as e:
        actual_balance = 0.0
        total_sales = 0.0
        total_promo_fees = 0.0
    
    return render_template("seller_dashboard.html", 
                          balance=actual_balance, 
                          total_sales=total_balance, 
                          total_promo_fees=total_promo_fees)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    search_field = request.args.get('search_field', 'all').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()
    
    user_email = session.get('user_id')
    items = []
    
    try:
        with get_db_connection() as conn:
            base_query = '''
                SELECT 
                    al.Seller_Email, 
                    al.Listing_ID, 
                    al.Auction_Title, 
                    al.Product_Name, 
                    al.Max_bids, 
                    al.Status,
                    al.Product_Description as Description,
                    c.category_name as Category_Name,
                    COALESCE((SELECT MAX(b.Bid_price) FROM Bids b WHERE b.Seller_Email = al.Seller_Email AND b.Listing_ID = al.Listing_ID), 0) as current_bid,
                    (SELECT COUNT(*) FROM Bids b WHERE b.Seller_Email = al.Seller_Email AND b.Listing_ID = al.Listing_ID) as bid_count,
                    COALESCE(bidder.first_name, lv.Business_Name, 'Unknown') as Seller_First_Name,
                    COALESCE(bidder.last_name, '') as Seller_Last_Name
                FROM Auction_Listings al
                LEFT JOIN Categories c ON al.Category = c.category_name
                LEFT JOIN Bidders bidder ON al.Seller_Email = bidder.email
                LEFT JOIN Local_Vendors lv ON al.Seller_Email = lv.Email
                WHERE al.Status = 1
            '''
            
            params = []
            conditions = []
            
            if query:
                like_query = f"%{query}%"
                
                if search_field == 'title':
                    conditions.append("al.Auction_Title LIKE ?")
                    params.append(like_query)
                elif search_field == 'product_name':
                    conditions.append("al.Product_Name LIKE ?")
                    params.append(like_query)
                elif search_field == 'description':
                    conditions.append("al.Product_Description LIKE ?")
                    params.append(like_query)
                elif search_field == 'category':
                    conditions.append("COALESCE(c.category_name, '') LIKE ?")
                    params.append(like_query)
                elif search_field == 'seller_name':
                    conditions.append("(COALESCE(bidder.first_name, '') LIKE ? OR COALESCE(bidder.last_name, '') LIKE ? OR COALESCE(lv.Business_Name, '') LIKE ?)")
                    params.extend([like_query, like_query, like_query])
                else:
                    search_conditions = [
                        "al.Auction_Title LIKE ?",
                        "al.Product_Name LIKE ?",
                        "al.Product_Description LIKE ?",
                        "COALESCE(c.category_name, '') LIKE ?",
                        "COALESCE(bidder.first_name, '') LIKE ?",
                        "COALESCE(bidder.last_name, '') LIKE ?",
                        "COALESCE(lv.Business_Name, '') LIKE ?",
                    ]
                    conditions.append("(" + " OR ".join(search_conditions) + ")")
                    params.extend([like_query] * len(search_conditions))
            
            if min_price:
                try:
                    min_val = float(min_price)
                    conditions.append("COALESCE((SELECT MAX(b.Bid_price) FROM Bids b WHERE b.Seller_Email = al.Seller_Email AND b.Listing_ID = al.Listing_ID), 0) >= ?")
                    params.append(min_val)
                except ValueError:
                    pass

            if max_price:
                try:
                    max_val = float(max_price)
                    conditions.append("COALESCE((SELECT MAX(b.Bid_price) FROM Bids b WHERE b.Seller_Email = al.Seller_Email AND b.Listing_ID = al.Listing_ID), 0) <= ?")
                    params.append(max_val)
                except ValueError:
                    pass

            if conditions:
                base_query += " AND " + " AND ".join(conditions)
            
            base_query += "ORDER BY al.is_promoted DESC, al.Listing_ID DESC"
            
            items = conn.execute(base_query, params).fetchall()

            items_list = []
            for item in items:
                item_dict = dict(item)
                
                try:
                    item_dict['current_bid'] = float(item_dict['current_bid']) if item_dict['current_bid'] else 0.0
                except (ValueError, TypeError):
                    item_dict['current_bid'] = 0.0
                
                try:
                    item_dict['bid_count'] = int(item_dict['bid_count']) if item_dict['bid_count'] else 0
                except (ValueError, TypeError):
                    item_dict['bid_count'] = 0
                
                try:
                    item_dict['Max_bids'] = int(item_dict['Max_bids']) if item_dict['Max_bids'] else 0
                except (ValueError, TypeError):
                    item_dict['Max_bids'] = 0
                
                try:
                    item_dict['Status'] = int(item_dict['Status']) if item_dict['Status'] else 0
                except (ValueError, TypeError):
                    item_dict['Status'] = 0
                
                items_list.append(item_dict)
                        
            if user_email:
                watchlist_items = conn.execute('''
                    SELECT Seller_Email, Listing_ID FROM Watchlist WHERE Bidder_Email = ?
                ''', (user_email,)).fetchall()
                
                watchlist_set = {(item['Seller_Email'], item['Listing_ID']) for item in watchlist_items}
                
                items_with_watchlist = []
                for item in items_list:
                    item['in_watchlist'] = (item['Seller_Email'], item['Listing_ID']) in watchlist_set
                    items_with_watchlist.append(item)
                
                items = items_with_watchlist
            else:
                items = items_list
            
    except Exception as e:
        flash(f'Error performing search: {str(e)}', 'danger')
        items = []
    
    return render_template('search.html', 
                        items=items, 
                        query=query,
                        search_field=search_field,
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
                addr_id = str(uuid.uuid4()).replace('-', '')  # Hash the address ID
                cursor.execute(
                    'INSERT INTO Address (address_id, zipcode, street_num, street_name) VALUES (?, ?, ?, ?)',
                    (addr_id, zipcode, street_num, street_name)
                )

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

                    # If student seller, must generate a seller request
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

                    temp_desc = f"Routing:{bank_routing}|Account:{bank_account}|BizName:{business_name}|Phone:{business_phone}|AddrID:{addr_id}"  # 使用哈希的地址ID

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
            SELECT Seller_Email, Listing_ID, Auction_Title, Product_Name, Reserve_Price, Status, is_promoted
            FROM Auction_Listings
            WHERE Category = ? AND Status = 1
            ORDER BY is_promoted DESC, Listing_ID DESC
            ''',
            (name,)
        ).fetchall()
    return render_template('category_detail.html', category_name=name, breadcrumb=bc, subcategories=sc, listings=l)

@app.route('/listing/<seller_email>/<int:listing_id>', methods=['GET', 'POST'])
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
        
        reviews = conn.execute(
                '''
                SELECT Bidder_Email, Date, Rating, Rating_Desc
                FROM Ratings
                WHERE Seller_Email = ?
                ORDER BY Date DESC
                LIMIT 10
                ''',
                (seller_email,)).fetchall()
        
        rb = conn.execute(
            '''
            SELECT Bid_ID, Bidder_Email, Bid_Price
            FROM Bids
            WHERE Seller_Email = ? AND Listing_ID = ?
            ORDER BY Bid_ID DESC
            LIMIT 10
            ''',
            (seller_email, listing_id)).fetchall()

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
        
        can_r = False
        already_r = False
        b_email = session.get("email")
        today = date.today().isoformat()
        
        in_watchlist = False
        if b_email:
            wl_check = conn.execute(
                '''
                SELECT 1 FROM Watchlist 
                WHERE Bidder_Email = ? AND Seller_Email = ? AND Listing_ID = ?
                ''',
                (b_email, seller_email, listing_id)
            ).fetchone()
            in_watchlist = (wl_check is not None)

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
        
        last_bid = conn.execute(
            '''
            SELECT Bidder_Email
            FROM Bids
            WHERE Seller_Email = ? AND Listing_ID = ?
            ORDER BY Bid_ID DESC
            LIMIT 1
            ''',
            (seller_email, listing_id)
        ).fetchone()

        winner = conn.execute(
            '''
            SELECT Bidder_Email, Bid_Price
            FROM Bids
            WHERE Seller_Email = ? AND Listing_ID = ?
            ORDER BY Bid_Price DESC, Bid_ID DESC
            LIMIT 1
            ''',
            (seller_email, listing_id)
        ).fetchone()

        is_winner = bool(winner and b_email and winner['Bidder_Email'] == b_email and int(r['Status']) == 2)

        if request.method == 'POST' and session.get('user_type') == 'bidder' and b_email:
            bid_raw = request.form.get('bid_price', '').strip()
            try:
                bid_price = float(bid_raw)
            except ValueError:
                flash('Invalid bid amount.', 'danger')
                return redirect(url_for('listing', seller_email=seller_email, listing_id=listing_id))

            reserve_price = parse_money(r['Reserve_Price'])

            if int(r['Status']) != 1 or remaining_bids <= 0:
                flash('Bid rejected: auction ended.', 'warning')
                return redirect(url_for('listing', seller_email=seller_email, listing_id=listing_id))

            if bid_price < highest_bid + 1:
                flash(f'Bid rejected: bid must be at least ${highest_bid + 1:.2f}.', 'warning')
                return redirect(url_for('listing', seller_email=seller_email, listing_id=listing_id))

            if last_bid and last_bid['Bidder_Email'] == b_email:
                flash('Bid rejected: you must wait for another bidder.', 'warning')
                return redirect(url_for('listing', seller_email=seller_email, listing_id=listing_id))

            if b_email == seller_email:
                flash('Bid rejected: seller cannot bid on own listing.', 'warning')
                return redirect(url_for('listing', seller_email=seller_email, listing_id=listing_id))

            next_bid_id = conn.execute('SELECT COALESCE(MAX(Bid_ID), 0) + 1 FROM Bids').fetchone()[0]
            conn.execute(
                '''
                INSERT INTO Bids (Bid_ID, Seller_Email, Listing_ID, Bidder_Email, Bid_Price)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (next_bid_id, seller_email, listing_id, b_email, bid_price)
            )

            watchlist_exists = conn.execute('''
                SELECT 1 FROM Watchlist 
                WHERE Bidder_Email = ? AND Seller_Email = ? AND Listing_ID = ?
            ''', (b_email, seller_email, listing_id)).fetchone()
            
            if not watchlist_exists:
                conn.execute('''
                    INSERT INTO Watchlist (Bidder_Email, Seller_Email, Listing_ID)
                    VALUES (?, ?, ?)
                ''', (b_email, seller_email, listing_id))

            updated_stats = conn.execute(
                '''
                SELECT COUNT(*) AS bid_count, MAX(Bid_Price) AS highest_bid
                FROM Bids
                WHERE Seller_Email = ? AND Listing_ID = ?
                ''',
                (seller_email, listing_id)
            ).fetchone()

            updated_bid_count = int(updated_stats['bid_count'] or 0)
            updated_highest_bid = float(updated_stats['highest_bid'] or 0)

            if updated_bid_count >= max_bids:
                if updated_highest_bid >= reserve_price:
                    conn.execute(
                        '''
                        UPDATE Auction_Listings
                        SET Status = 2
                        WHERE Seller_Email = ? AND Listing_ID = ?
                        ''',
                        (seller_email, listing_id)
                    )
                    conn.commit()

                    winning_bid = conn.execute(
                        '''
                        SELECT Bidder_Email, Bid_Price
                        FROM Bids
                        WHERE Seller_Email = ? AND Listing_ID = ?
                        ORDER BY Bid_Price DESC, Bid_ID DESC
                        LIMIT 1
                        ''',
                        (seller_email, listing_id)
                    ).fetchone()

                    if winning_bid and winning_bid['Bidder_Email'] == b_email:
                        flash('Bid accepted. Auction ended and you won. Please complete payment.', 'success')
                        return redirect(url_for('auction_payment', seller_email=seller_email, listing_id=listing_id))

                    flash('Bid accepted. Auction ended.', 'success')
                    return redirect(url_for('listing', seller_email=seller_email, listing_id=listing_id))

                conn.execute(
                    '''
                    UPDATE Auction_Listings
                    SET Status = 0
                    WHERE Seller_Email = ? AND Listing_ID = ?
                    ''',
                    (seller_email, listing_id)
                )
                conn.commit()
                flash('Bid accepted. Auction ended but reserve price not met.', 'warning')
                return redirect(url_for('listing', seller_email=seller_email, listing_id=listing_id))

            conn.commit()
            flash('Bid accepted.', 'success')
            return redirect(url_for('listing', seller_email=seller_email, listing_id=listing_id))
        
        # Check if the winning bidder has completed payment
        payment_completed = False
        if is_winner and b_email:
            payment_record = conn.execute(
                '''
                SELECT 1
                FROM Transactions
                WHERE Seller_Email = ? AND Listing_ID = ? AND Bidder_Email = ?
                ''',
                (seller_email, listing_id, b_email)
            ).fetchone()
            payment_completed = payment_record is not None

    return render_template(
        'item_detail.html',
        listing=r,
        highest_bid=highest_bid,
        bid_count=bid_count,
        remaining_bids=remaining_bids,
        can_place_bid=can_place_bid,
        is_winner=is_winner,
        recent_bids=rb,
        avg_rating=avg_rating,
        num_ratings=num_ratings,
        reviews=reviews,
        can_r=can_r,
        already_r=already_r,
        in_watchlist=in_watchlist,
        payment_completed=payment_completed
    )

@app.route('/rate/<seller_email>/<int:listing_id>', methods=['POST'])
@bidder_only
def rate_seller(seller_email, listing_id):
    if session.get("user_type") != "bidder" or not session.get("email"):
        flash("Only logged-in bidders can rate.", "danger")
        return redirect(url_for("listing", seller_email=seller_email, listing_id=listing_id))

    bidder_email = session["email"]
    today = date.today().strftime('%m/%d/%y')
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

# Watchlist Functions #
@app.route('/watchlist')
@bidder_only
def watchlist():
    from flask import get_flashed_messages
    get_flashed_messages()
    
    user_email = session.get('user_id')
    try:
        with get_db_connection() as conn:
            items = conn.execute('''
                SELECT 
                    al.Seller_Email, 
                    al.Listing_ID, 
                    al.Auction_Title, 
                    al.Product_Name, 
                    al.Reserve_Price, 
                    al.Max_bids, 
                    al.Status,
                    c.category_name as Category_Name,
                    COALESCE((SELECT MAX(b.Bid_price) FROM Bids b WHERE b.Seller_Email = al.Seller_Email AND b.Listing_ID = al.Listing_ID), 0) as current_bid,
                    (SELECT COUNT(*) FROM Bids b WHERE b.Seller_Email = al.Seller_Email AND b.Listing_ID = al.Listing_ID) as bid_count,
                    COALESCE(bidder.first_name, lv.Business_Name, 'Unknown') as Seller_First_Name,
                    COALESCE(bidder.last_name, '') as Seller_Last_Name
                FROM Auction_Listings al
                JOIN Watchlist w ON al.Seller_Email = w.Seller_Email AND al.Listing_ID = w.Listing_ID
                LEFT JOIN Categories c ON al.Category = c.category_name
                LEFT JOIN Bidders bidder ON al.Seller_Email = bidder.email
                LEFT JOIN Local_Vendors lv ON al.Seller_Email = lv.Email
                WHERE w.Bidder_Email = ?
                ORDER BY al.Listing_ID DESC
            ''', (user_email,)).fetchall()
            
            items_list = []
            for item in items:
                item_dict = dict(item)
                item_dict['Reserve_Price'] = parse_money(item_dict['Reserve_Price'])
                
                try:
                    item_dict['current_bid'] = float(item_dict['current_bid']) if item_dict['current_bid'] else 0.0
                except (ValueError, TypeError):
                    item_dict['current_bid'] = 0.0
                
                try:
                    item_dict['bid_count'] = int(item_dict['bid_count']) if item_dict['bid_count'] else 0
                except (ValueError, TypeError):
                    item_dict['bid_count'] = 0
                
                try:
                    item_dict['Max_bids'] = int(item_dict['Max_bids']) if item_dict['Max_bids'] else 0
                except (ValueError, TypeError):
                    item_dict['Max_bids'] = 0
                
                try:
                    item_dict['Status'] = int(item_dict['Status']) if item_dict['Status'] else 0
                except (ValueError, TypeError):
                    item_dict['Status'] = 0
                
                items_list.append(item_dict)
            
        return render_template('watchlist.html', items=items_list)
    except Exception as e:
        flash(f'Error loading watchlist: {str(e)}', 'danger')
        return redirect(url_for('bidder_dashboard'))
# route for page seller_auction.html
@app.route('/seller_auction')
@seller_only
def seller_auction():
    conn = get_db_connection()
    #
    # this part is for create auction
    # Get category selections (fetch all categories)
    email = session.get("email")
    categories = conn.execute("""
    SELECT category_name FROM Categories 
    """).fetchall()

    active_listings = conn.execute("""
    SELECT *, (0.05 * CAST(REPLACE(Reserve_Price, '$', '') AS REAL)) AS promotion_cost FROM Auction_Listings
    WHERE Seller_Email = ? AND Status = 1
""", (email,)).fetchall()

    inactive_listings = conn.execute("""
        SELECT * FROM Auction_Listings
        WHERE Seller_Email = ? AND Status = 0
    """, (email,)).fetchall()

    sold_listings = conn.execute("""
        SELECT * FROM Auction_Listings
        WHERE Seller_Email = ? AND Status = 2
    """, (email,)).fetchall()

    return render_template("seller_auction.html", categories=categories,active_listings=active_listings,inactive_listings=inactive_listings,sold_listings=sold_listings)
# route for creating an auction
@app.route("/create_auction",methods=['POST'])
@seller_only
def create_auction():
    conn = get_db_connection()
    Seller_Email = session.get("email")
    # Listing_ID increase automatically
    Category = request.form['category']
    Auction_Title = request.form['title']
    Product_Name = request.form['name']
    Product_Description = request.form['description']
    Quantity = request.form['quantity']
    Reserve_Price = "$"+request.form['r_price']
    Max_bids = request.form['max_bid']
    Status = 1

    row = conn.execute("""
        SELECT MAX(Listing_ID)
        FROM Auction_Listings
        WHERE Seller_Email = ?
    """, (Seller_Email,)).fetchone()

    if row[0] is None:
        Listing_ID = 1
    else:
        Listing_ID = row[0] + 1

    # generate the SQL statement
    conn.execute("""
        INSERT INTO Auction_Listings (
            Seller_Email,
            Listing_ID,
            Category,
            Auction_Title,
            Product_Name,
            Product_Description,
            Quantity,
            Reserve_Price,
            Max_bids,
            Status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        Seller_Email,
        Listing_ID,
        Category,
        Auction_Title,
        Product_Name,
        Product_Description,
        Quantity,
        Reserve_Price,
        Max_bids,
        Status
    ))    
    conn.commit()

    return redirect(url_for("seller_auction", created="1"))

#for check if auction can edit or not
@app.route('/check_edit_auction', methods=['POST'])
@seller_only
def check_edit_auction():
    conn = get_db_connection()
    seller_email = session.get("email")
    if not seller_email:
        return {"ok": False, "reason": "Please log in first."}

    listing_id = request.form.get("listing_id", type=int)
    if not listing_id:
        return {"ok": False, "reason": "Missing listing ID."}

    listing = conn.execute("""
        SELECT *
        FROM Auction_Listings
        WHERE Seller_Email = ? AND Listing_ID = ?
    """, (seller_email, listing_id)).fetchone()

    bid =  conn.execute("""
        SELECT * 
        FROM Bids 
        WHERE Listing_ID = ?
    """,(listing_id,)).fetchone()

    if bid:
        conn.close()
        print("false")
        return {"ok": False, "reason": "Listing has been bid for at least once."}

    if not listing:
        conn.close()
        print("false")
        return {"ok": False, "reason": "Listing not found."}

    if listing["Status"] == 2:
        conn.close()
        print("false")
        return {"ok": False, "reason": "Sold listings cannot be edited."}

    if listing["Status"] == 1:
        bid_count = conn.execute("""
            SELECT COUNT(*)
            FROM Bids
            WHERE Seller_Email = ? AND Listing_ID = ?
        """, (seller_email, listing_id)).fetchone()[0]

        if bid_count > 0:
            conn.close()
            print("false")
            return {
                "ok": False,
                "reason": "This active listing cannot be updated because bidding has already started."
            }

    data = {
        "listing_id": listing["Listing_ID"],
        "title": listing["Auction_Title"],
        "name": listing["Product_Name"],
        "category": listing["Category"],
        "description": listing["Product_Description"],
        "quantity": listing["Quantity"],
        "reserve_price": listing["Reserve_Price"],
        "max_bids": listing["Max_bids"]
    }

    conn.close()
    print("True")
    return {"ok": True, "listing": data}

# This changes active to inactive, otherwise
@app.route('/toggle_status', methods=['POST'])
@seller_only
def toggle_status():
    conn = get_db_connection()

    try:
        seller_email = session.get("email")
        if not seller_email:
            return redirect(url_for("login"))

        listing_id = request.form.get("listing_id", type=int)
        new_status = request.form.get("status", type=int)

        if listing_id is None or new_status is None:
            return "Invalid request"

        conn.execute("""
            UPDATE Auction_Listings
            SET Status = ?
            WHERE Listing_ID = ? AND Seller_Email = ?
        """, (new_status, listing_id, seller_email))

        conn.commit()

        return redirect(url_for("seller_auction"))

    finally:
        conn.close()

@app.route('/update_auction', methods=['POST'])
@seller_only
def update_auction():
    conn = get_db_connection()
    seller_email = session.get("email")
    if not seller_email:
        return redirect(url_for("login"))

    listing_id = request.form.get("listing_id", type=int)
    category = request.form.get("category", "").strip()
    title = request.form.get("title", "").strip()
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    quantity = request.form.get("quantity", type=int)
    reserve_price = "$"+ request.form.get("r_price", "").strip()
    max_bids = request.form.get("max_bid", type=int)

    if not listing_id:
        return "Missing listing ID."

    if not title or not name or not category or not description:
        return "All fields are required."

    if quantity is None or quantity <= 0:
        return "Quantity must be greater than 0."

    if max_bids is None or max_bids <= 0:
        return "Maximum number of bids must be greater than 0."

    try:
        if float(request.form.get("r_price", "").strip()) <= 0:
            return "Reserve price must be greater than 0."
    except ValueError:
        return "Reserve price must be a valid number."



    listing = conn.execute("""
        SELECT *
        FROM Auction_Listings
        WHERE Seller_Email = ?
          AND Listing_ID = ?
    """, (seller_email, listing_id)).fetchone()

    if not listing:
        conn.close()
        return "Listing not found."

    # double check
    if listing["Status"] == 2:
        conn.close()
        return "Sold listings cannot be edited."

    if listing["Status"] == 1:
        bid_count = conn.execute("""
            SELECT COUNT(*)
            FROM Bids
            WHERE Seller_Email = ?
              AND Listing_ID = ?
        """, (seller_email, listing_id)).fetchone()[0]

        if bid_count > 0:
            conn.close()
            return "This active listing cannot be updated because bidding has already started."

    conn.execute("""
        UPDATE Auction_Listings
        SET Category = ?,
            Auction_Title = ?,
            Product_Name = ?,
            Product_Description = ?,
            Quantity = ?,
            Reserve_Price = ?,
            Max_bids = ?
        WHERE Seller_Email = ?
          AND Listing_ID = ?
    """, (
        category,
        title,
        name,
        description,
        quantity,
        reserve_price,
        max_bids,
        seller_email,
        listing_id
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("seller_auction", updated="1"))

@app.route('/seller_profile')
@seller_only
def seller_profile():
    email = session.get("email")
    if not email:
        return redirect(url_for("login"))

    conn = get_db_connection()

    return render_template("seller_profile.html",email=email,)
@app.route('/seller/sales')
@seller_only
def seller_sales():
    seller_email = session.get('email')
    
    try:
        with get_db_connection() as conn:
            sales = conn.execute('''
                SELECT 
                    t.Transaction_ID,
                    t.Seller_Email,
                    t.Listing_ID,
                    t.Bidder_Email,
                    t.Date,
                    t.Payment,
                    al.Auction_Title,
                    al.Product_Name,
                    COALESCE(b.first_name || ' ' || b.last_name, 'Unknown Bidder') as Bidder_Name,
                    al.Reserve_Price,
                    r.Rating,
                    r.Rating_Desc
                FROM Transactions t
                JOIN Auction_Listings al ON t.Seller_Email = al.Seller_Email AND t.Listing_ID = al.Listing_ID
                LEFT JOIN Bidders b ON t.Bidder_Email = b.email
                LEFT JOIN Ratings r ON t.Bidder_Email = r.Bidder_Email 
                                    AND t.Seller_Email = r.Seller_Email 
                                    AND t.Date = r.Date
                WHERE t.Seller_Email = ? AND al.Status = 2
                ORDER BY t.Date DESC
            ''', (seller_email,)).fetchall()
            
            sales_list = []
            for sale in sales:
                sale_dict = dict(sale)
                sale_dict['Payment'] = float(sale_dict['Payment']) if sale_dict['Payment'] else 0.0
                sale_dict['Reserve_Price'] = parse_money(sale_dict['Reserve_Price'])
                sales_list.append(sale_dict)
                
        return render_template('seller_sales.html', sales=sales_list)
    except Exception as e:
        flash(f'Error loading sales history: {str(e)}', 'danger')
        return redirect(url_for('seller_dashboard'))
    
#this update password
@app.route('/update_password', methods=['POST'])
@login_required
def update_profile():
    conn = get_db_connection()

    try:
        user_type = session.get('user_type')
        email = session.get("email")
        if not email:
            return redirect(url_for("login"))
        user_type = session.get('user_type')
        new_password = request.form.get("password", "").strip()

        # if no new password do not update
        if not new_password:
            return redirect(url_for(f'{user_type}_profile', updated="0"))

        # hash password
        hashed_password = generate_password_hash(new_password)

        # update database
        conn.execute("""
            UPDATE Users
            SET password = ?
            WHERE email = ?
        """, (hashed_password, email))

        conn.commit()

        return redirect(url_for(f'{user_type}_profile', request_sent="1"))
    finally:
        conn.close()


# This update bank account information of seller
@app.route('/update_bank_info', methods=['POST'])
@seller_only
def update_bank_info():
        conn = get_db_connection()

        try:
            email = session.get("email")
            user_type = session.get("user_type")

            if not email:
                return redirect(url_for("login"))

            routing = request.form.get("routing", "").strip()
            account = request.form.get("account", "").strip()


            if routing and account:
                conn.execute("""
                    UPDATE Sellers
                    SET bank_routing_number = ?,
                        bank_account_number = ?
                    WHERE email = ?
                """, (routing, account, email))
            elif routing:
                conn.execute("""
                    UPDATE Sellers
                    SET bank_routing_number = ?,
                    WHERE email = ?
                """, (routing, email))
            elif account:
                conn.execute("""
                    UPDATE Sellers
                    SET bank_account_number = ?
                    WHERE email = ?
                """, (account, email))
            else:
                return redirect(url_for(f'{user_type}_profile', bank_updated="invalid"))


            conn.commit()

            return redirect(url_for(f'{user_type}_profile', bank_updated="1"))

        finally:
            conn.close()

@app.route('/bidder_profile')
@bidder_only
def bidder_profile():
    email = session.get("email")
    if not email:
        return redirect(url_for("login"))

    conn = get_db_connection()

    try:
        bidder = conn.execute("""  
            SELECT 
                B.email,
                B.first_name,
                B.last_name,
                B.major,
                B.home_address_id,
                A.street_num,
                A.street_name,
                A.zipcode
            FROM Bidders B
            LEFT JOIN Address A
                ON B.home_address_id = A.address_id
            WHERE B.email = ?
        """, (email,)).fetchone()

        if not bidder:
            return redirect(url_for("login"))

        return render_template("bidder_profile.html", bidder=bidder)
    finally:
        conn.close()    

# THis part update bidder profile
@app.route('/update_bidder_profile', methods=['POST'])
@bidder_only
def update_bidder_profile():
    email = session.get("email")
    if not email:
        return redirect(url_for("login"))

    conn = get_db_connection()

    try:
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        major = request.form.get("major", "").strip()
        street_num = request.form.get("street_num", type=int)
        street_name = request.form.get("street_name", "").strip()
        zipcode = request.form.get("zipcode", type=int)

        if not first_name or not last_name or not major or not street_name:
            return redirect(url_for("bidder_profile", updated="0"))

        if street_num is None or zipcode is None:
            return redirect(url_for("bidder_profile", updated="0"))

        bidder = conn.execute("""
            SELECT home_address_id
            FROM Bidders
            WHERE email = ?
        """, (email,)).fetchone()

        if not bidder:
            return redirect(url_for("login"))

        address_id = bidder["home_address_id"]

        conn.execute("""
            UPDATE Bidders
            SET first_name = ?,
                last_name = ?,
                major = ?
            WHERE email = ?
        """, (first_name, last_name, major, email))

        conn.execute("""
            UPDATE Address
            SET street_num = ?,
                street_name = ?,
                zipcode = ?
            WHERE address_id = ?
        """, (street_num, street_name, zipcode, address_id))

        conn.commit()

        return redirect(url_for("bidder_profile", updated="1"))

    finally:
        conn.close()

@app.route('/add_watchlist', methods=['POST'])
@bidder_only
def add_watchlist():
    user_email = session.get('user_id')
    seller_email = request.form.get('seller_email')
    listing_id = request.form.get('listing_id')

    try:
        with get_db_connection() as conn:
            exists = conn.execute('''
                SELECT 1 FROM Watchlist 
                WHERE Bidder_Email = ? AND Seller_Email = ? AND Listing_ID = ?
            ''', (user_email, seller_email, listing_id)).fetchone()
            
            if not exists:
                conn.execute('''
                    INSERT INTO Watchlist (Bidder_Email, Seller_Email, Listing_ID)
                    VALUES (?, ?, ?)
                ''', (user_email, seller_email, listing_id))
                conn.commit()
                
        return redirect(request.referrer or url_for('watchlist'))
        
    except Exception as e:
        flash(f'Error adding to watchlist: {str(e)}', 'danger')
        return redirect(url_for('bidder_dashboard'))

@app.route('/remove_watchlist', methods=['POST'])
@bidder_only
def remove_watchlist():
    user_email = session.get('user_id')
    seller_email = request.form.get('seller_email')
    listing_id = request.form.get('listing_id')
    referrer = request.referrer or ''

    try:
        with get_db_connection() as conn:
            conn.execute('''
                DELETE FROM Watchlist 
                WHERE Bidder_Email = ? AND Seller_Email = ? AND Listing_ID = ?
            ''', (user_email, seller_email, listing_id))
            conn.commit()
            
            if '/watchlist' in referrer:
                flash('Removed from watchlist', 'success')
        
        return redirect(referrer or url_for('watchlist'))
    except Exception as e:
        flash(f'Error removing from watchlist: {str(e)}', 'danger')
        return redirect(url_for('bidder_dashboard'))
    
# Place Bid within the Watchlist
@app.route('/place_bid', methods=['POST'])
@bidder_only
def place_bid():
    if session.get('user_type') not in ['bidder']:
        flash('Only bidders can place bids.', 'danger')
        return redirect(url_for('login'))

    bidder_email = session.get('user_id')
    seller_email = request.form.get('seller_email')
    listing_id = request.form.get('listing_id')
    
    try:
        bid_amount = float(request.form.get('bid_amount', 0))
    except (ValueError, TypeError):
        flash('Invalid bid amount.', 'danger')
        return redirect(url_for('watchlist'))

    if bid_amount <= 0:
        flash('Bid amount must be positive.', 'danger')
        return redirect(url_for('watchlist'))

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            auction = cursor.execute('''
                SELECT al.Reserve_Price, al.Max_bids, al.Status,
                       COALESCE((SELECT MAX(b.Bid_price) FROM Bids b WHERE b.Seller_Email = al.Seller_Email AND b.Listing_ID = al.Listing_ID), 0) as current_bid,
                       (SELECT COUNT(*) FROM Bids b WHERE b.Seller_Email = al.Seller_Email AND b.Listing_ID = al.Listing_ID) as bid_count
                FROM Auction_Listings al
                WHERE al.Seller_Email = ? AND al.Listing_ID = ?
            ''', (seller_email, listing_id)).fetchone()
            
            if not auction:
                flash('Auction listing not found.', 'danger')
                return redirect(url_for('watchlist'))
            
            current_bid = float(auction['current_bid']) if auction['current_bid'] else 0.0
            
            reserve_price = parse_money(auction['Reserve_Price'])
            
            max_bids = int(auction['Max_bids']) if auction['Max_bids'] else 0
            bid_count = int(auction['bid_count']) if auction['bid_count'] else 0
            status = int(auction['Status']) if auction['Status'] else 0
            
            if status != 1:
                flash('This auction is not active.', 'danger')
                return redirect(url_for('watchlist'))
            
            if bid_count >= max_bids:
                flash('Maximum number of bids reached for this auction.', 'warning')
                return redirect(url_for('watchlist'))
            
            if bid_amount <= current_bid:
                flash(f'Bid must be higher than current bid (${current_bid:.2f}).', 'danger')
                return redirect(url_for('watchlist'))
            
            last_bid = conn.execute('''
                SELECT Bidder_Email FROM Bids 
                WHERE Seller_Email = ? AND Listing_ID = ? 
                ORDER BY Bid_ID DESC LIMIT 1
            ''', (seller_email, listing_id)).fetchone()
            
            if last_bid and last_bid['Bidder_Email'] == bidder_email:
                flash('Bid rejected: You must wait for another bidder to place a bid first.', 'warning')
                return redirect(url_for('watchlist'))

            if bidder_email == seller_email:
                flash('Bid rejected: Sellers cannot bid on their own listings.', 'warning')
                return redirect(url_for('watchlist'))
            
            cursor.execute('''
                INSERT INTO Bids (Bidder_Email, Seller_Email, Listing_ID, Bid_price)
                VALUES (?, ?, ?, ?)''', 
                (bidder_email, seller_email, listing_id, bid_amount))
            
            conn.commit()
            flash(f'Successfully placed bid of ${bid_amount:.2f}!', 'success')
            
    except Exception as e:
        flash(f'Error placing bid: {str(e)}', 'danger')
        import traceback
        traceback.print_exc()

    return redirect(url_for('watchlist'))

@app.route('/submit_request', methods=['GET', 'POST'])
@login_required
def submit_request():
    if request.method == 'GET':
        return render_template('submit_request.html')
    
    request_type = request.form.get('request_type', '').strip()
    sender_email = session.get('user_id')
    final_desc = ""
    
    try:
        if request_type == 'ChangeID':
            new_email = request.form.get('new_email', '').strip()
            if not new_email:
                flash('New email is required.', 'danger')
                return redirect(url_for('submit_request'))
            final_desc = f"Please change my ID to {new_email}"
            
        elif request_type == 'SellerReg':
            routing = request.form.get('bank_routing', '').strip()
            account = request.form.get('bank_account', '').strip()
            if not routing or not account:
                flash('Bank routing and account numbers are required.', 'danger')
                return redirect(url_for('submit_request'))
            final_desc = f"Routing:{routing}|Account:{account}"
            
        elif request_type == 'AddCategory':
            parent = request.form.get('parent_category', '').strip()
            child = request.form.get('new_category', '').strip()
            if not parent or not child:
                flash('Parent and new category names are required.', 'danger')
                return redirect(url_for('submit_request'))
            final_desc = f"Please add a new category {child} under {parent}"
            
        else:
            # MarketAnalysis or General Question
            general_desc = request.form.get('request_desc', '').strip()
            if not general_desc:
                flash('Description is required for this request type.', 'danger')
                return redirect(url_for('submit_request'))
            final_desc = general_desc

        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO Requests (sender_email, helpdesk_staff_email, request_type, request_desc, request_status)
                VALUES (?, ?, ?, ?, ?)''', 
                (sender_email, 'helpdeskteam@lsu.edu', request_type, final_desc, 0))
            
            conn.commit()
            
        flash('Your request has been submitted successfully! Helpdesk will review it soon.', 'success')
        return redirect(url_for(f'{session.get("user_type")}_dashboard'))
        
    except Exception as e:
        flash(f'Error submitting request: {str(e)}', 'danger')
        import traceback
        traceback.print_exc()
        return redirect(url_for('submit_request'))
    
@app.route('/helpdesk/approve_category/<int:request_id>', methods=['POST'])
@helpdesk_only
def helpdesk_approve_category(request_id):
    try:
        with get_db_connection() as conn:
            req = conn.execute('SELECT * FROM Requests WHERE request_id = ?', (request_id,)).fetchone()
            if not req or req['request_type'] != 'AddCategory':
                flash('Invalid request.', 'danger')
                return redirect(url_for('helpdesk_dashboard'))

            desc = req['request_desc']
            patterns = [
                r"Please add a new category (.+) under (.+)",
                r"Please ad a new category (.+) under (.+)", # To match the exits db wording
            ]

            new_cat = None
            parent_cat = 'Root'
            
            for pattern in patterns:
                match = re.search(pattern, desc)
                if match:
                    new_cat = match.group(1).strip()
                    parent_cat = match.group(2).strip()
                    break
            
            if not match:
                flash('Could not parse category details from request description.', 'danger')
                return redirect(url_for('helpdesk_dashboard'))

            if not new_cat:
                flash('Category name is missing.', 'danger')
                return redirect(url_for('helpdesk_dashboard'))

            exists = conn.execute('SELECT 1 FROM Categories WHERE category_name = ?', (new_cat,)).fetchone()
            if exists:
                flash(f'Category "{new_cat}" already exists.', 'warning')
            else:
                conn.execute('INSERT INTO Categories (parent_category, category_name) VALUES (?, ?)', 
                             (parent_cat, new_cat))
                conn.commit()
                flash(f'Category "{new_cat}" added successfully under "{parent_cat}".', 'success')

            # Mark request as completed
            conn.execute('UPDATE Requests SET request_status = 2, helpdesk_staff_email = ? WHERE request_id = ?', 
                         (session.get('email'), request_id))
            conn.commit()

    except Exception as e:
        flash(f'Error approving category: {str(e)}', 'danger')
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('helpdesk_dashboard'))

@app.route('/helpdesk/complete/<int:request_id>', methods=['POST'])
@helpdesk_only
def helpdesk_complete(request_id):
    if session.get('user_type') != 'helpdesk':
        return redirect(url_for('login'))

    try:
        with get_db_connection() as conn:
            conn.execute('UPDATE Requests SET request_status = 2, helpdesk_staff_email = ? WHERE request_id = ?', 
                         (session.get('email'), request_id))
            conn.commit()
            flash('Request marked as completed.', 'success')
    except Exception as e:
        flash(f'Error completing request: {str(e)}', 'danger')
    
    return redirect(url_for('helpdesk_dashboard'))


@app.route('/helpdesk/reject/<int:request_id>', methods=['POST'])
@helpdesk_only
def helpdesk_reject(request_id):
    if session.get('user_type') != 'helpdesk':
        return redirect(url_for('login'))

    try:
        with get_db_connection() as conn:
            conn.execute('UPDATE Requests SET request_status = 1, helpdesk_staff_email = ? WHERE request_id = ?', 
                         (session.get('email'), request_id))
            conn.commit()
            flash('Request marked as rejected.', 'success')
    except Exception as e:
        flash(f'Error rejecting request: {str(e)}', 'danger')
    
    return redirect(url_for('helpdesk_dashboard'))


@app.route('/helpdesk/claim/<int:request_id>', methods=['POST'])
@helpdesk_only
def helpdesk_claim(request_id):
    if session.get('user_type') != 'helpdesk':
        return redirect(url_for('login'))

    try:
        with get_db_connection() as conn:
            conn.execute('UPDATE Requests SET helpdesk_staff_email = ? WHERE request_id = ?', 
                         (session.get('email'), request_id))
            conn.commit()
            flash('Request claimed successfully.', 'success')
    except Exception as e:
        flash(f'Error claiming request: {str(e)}', 'danger')
    
    return redirect(url_for('helpdesk_dashboard'))

@app.route('/seller/promote/<seller_email>/<int:listing_id>', methods=['POST'])
@seller_only
def promote_auction(seller_email, listing_id):
    current_seller_email = session.get('email')
    if current_seller_email != seller_email:
        flash('Access denied. You can only promote your own listings.', 'danger')
        return redirect(url_for('seller_auction'))

    try:
        with get_db_connection() as conn:
            listing = conn.execute(
                'SELECT Listing_ID, Reserve_Price, Status, Category, is_promoted FROM Auction_Listings WHERE Seller_Email = ? AND Listing_ID = ?',
                (seller_email, listing_id)
            ).fetchone()

            if not listing:
                flash('Auction listing not found.', 'danger')
                return redirect(url_for('seller_auction'))

            is_promoted_value = listing['is_promoted']
            if is_promoted_value is not None and int(is_promoted_value) == 1:
                flash('This auction is already promoted.', 'info')
                return redirect(url_for('seller_auction'))

            status_value = listing['Status']
            if status_value is None or int(status_value) != 1:
                flash('Cannot promote an auction that is not active.', 'danger')
                return redirect(url_for('seller_auction'))

            reserve_price_str = listing['Reserve_Price']
            if reserve_price_str is None:
                flash('Reserve price is not set for this listing.', 'danger')
                return redirect(url_for('seller_auction'))

            reserve_price = parse_money(reserve_price_str)
            promotion_fee = reserve_price * 0.05
            promotion_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute(
                '''UPDATE Auction_Listings 
                   SET is_promoted = 1, promotion_fee = ?, promotion_date = ? 
                   WHERE Seller_Email = ? AND Listing_ID = ?''',
                (promotion_fee, promotion_timestamp, seller_email, listing_id)
            )
            conn.commit()
            flash(f'Auction promoted successfully for ${promotion_fee:.2f}!', 'success')

    except Exception as e:
        flash(f'Unexpected error promoting auction: {str(e)}', 'danger')
        import traceback
        traceback.print_exc()

    return redirect(url_for('seller_auction'))

if __name__ == '__main__':
    #app.run()
    app.run(debug=True)
