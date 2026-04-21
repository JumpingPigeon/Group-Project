from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps # To create reusable login_required decorator
import sqlite3 as sql
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


@app.route('/bidder/auctions')
@login_required
def bidder_auctions():
    role = str(session.get('user_type', '')).strip().lower()
    if role not in ('bidder', 'buyer'):
        flash('Only bidders can place bids.', 'danger')
        return redirect(url_for('login'))

    with get_db_connection() as conn:
        listings = conn.execute(
            '''
            SELECT Seller_Email, Listing_ID, Category, Auction_Title, Product_Name,
                   Product_Description, Max_bids, Status
            FROM Auction_Listings
            WHERE Status = 1
            ORDER BY Listing_ID DESC
            '''
        ).fetchall()

        listing_dicts = []
        for listing in listings:
            bid_stats = conn.execute(
                '''
                SELECT COUNT(*) AS bid_count, MAX(Bid_Price) AS highest_bid
                FROM Bids
                WHERE Seller_Email = ? AND Listing_ID = ?
                ''',
                (listing['Seller_Email'], listing['Listing_ID'])
            ).fetchone()
            bid_count = int(bid_stats['bid_count'] or 0)
            remaining_bids = max(int(listing['Max_bids']) - bid_count, 0)
            listing_dicts.append({
                'seller_email': listing['Seller_Email'],
                'listing_id': listing['Listing_ID'],
                'category': listing['Category'],
                'auction_title': listing['Auction_Title'],
                'product_name': listing['Product_Name'],
                'product_description': listing['Product_Description'],
                'highest_bid': float(bid_stats['highest_bid'] or 0),
                'max_bids': int(listing['Max_bids']),
                'remaining_bids': remaining_bids
            })

    return render_template('active_listings.html', listings=listing_dicts)


@app.route('/bidder/auction/<seller_email>/<int:listing_id>', methods=['GET', 'POST'])
@login_required
def bidder_auction_detail(seller_email, listing_id):
    role = str(session.get('user_type', '')).strip().lower()
    bidder_email = session.get('email')
    if role not in ('bidder', 'buyer'):
        flash('Only bidders can place bids.', 'danger')
        return redirect(url_for('login'))

    with get_db_connection() as conn:
        listing = conn.execute(
            '''
            SELECT Seller_Email, Listing_ID, Category, Auction_Title, Product_Name,
                   Product_Description, Reserve_Price, Max_bids, Status
            FROM Auction_Listings
            WHERE Seller_Email = ? AND Listing_ID = ?
            ''',
            (seller_email, listing_id)
        ).fetchone()

        if not listing:
            flash('Auction listing not found.', 'danger')
            return redirect(url_for('bidder_auctions'))

        bid_stats = conn.execute(
            '''
            SELECT COUNT(*) AS bid_count, MAX(Bid_Price) AS highest_bid
            FROM Bids
            WHERE Seller_Email = ? AND Listing_ID = ?
            ''',
            (seller_email, listing_id)
        ).fetchone()

        bid_count = int(bid_stats['bid_count'] or 0)
        highest_bid = float(bid_stats['highest_bid'] or 0)
        max_bids = int(listing['Max_bids'])
        remaining_bids = max(max_bids - bid_count, 0)
        reserve_price = parse_money(listing['Reserve_Price'])

        recent_bids = conn.execute(
            '''
            SELECT Bid_ID, Bidder_Email, Bid_Price
            FROM Bids
            WHERE Seller_Email = ? AND Listing_ID = ?
            ORDER BY Bid_ID DESC
            LIMIT 10
            ''',
            (seller_email, listing_id)
        ).fetchall()

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

        can_place_bid = (int(listing['Status']) == 1 and remaining_bids > 0)

        if request.method == 'POST':
            bid_raw = request.form.get('bid_price', '').strip()
            try:
                bid_price = float(bid_raw)
            except ValueError:
                flash('Invalid bid amount.', 'danger')
                return redirect(url_for('bidder_auction_detail', seller_email=seller_email, listing_id=listing_id))

            if int(listing['Status']) != 1 or remaining_bids <= 0:
                flash('Bid rejected: auction ended.', 'warning')
                return redirect(url_for('bidder_auction_detail', seller_email=seller_email, listing_id=listing_id))

            if bid_price < highest_bid + 1:
                flash(f'Bid rejected: bid must be at least ${highest_bid + 1:.2f}.', 'warning')
                return redirect(url_for('bidder_auction_detail', seller_email=seller_email, listing_id=listing_id))

            if last_bid and last_bid['Bidder_Email'] == bidder_email:
                flash('Bid rejected: you must wait for another bidder.', 'warning')
                return redirect(url_for('bidder_auction_detail', seller_email=seller_email, listing_id=listing_id))

            if bidder_email == seller_email:
                flash('Bid rejected: seller cannot bid on own listing.', 'warning')
                return redirect(url_for('bidder_auction_detail', seller_email=seller_email, listing_id=listing_id))

            next_bid_id = conn.execute('SELECT COALESCE(MAX(Bid_ID), 0) + 1 FROM Bids').fetchone()[0]
            conn.execute(
                '''
                INSERT INTO Bids (Bid_ID, Seller_Email, Listing_ID, Bidder_Email, Bid_Price)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (next_bid_id, seller_email, listing_id, bidder_email, bid_price)
            )

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

                    if winning_bid and winning_bid['Bidder_Email'] == bidder_email:
                        flash('Bid accepted. Auction ended and you won. Please complete payment.', 'success')
                        return redirect(url_for('auction_payment', seller_email=seller_email, listing_id=listing_id))

                    flash('Bid accepted. Auction ended.', 'success')
                    return redirect(url_for('bidder_auction_detail', seller_email=seller_email, listing_id=listing_id))

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
                return redirect(url_for('bidder_auction_detail', seller_email=seller_email, listing_id=listing_id))

            conn.commit()
            flash('Bid accepted.', 'success')
            return redirect(url_for('bidder_auction_detail', seller_email=seller_email, listing_id=listing_id))

        is_winner = bool(winner and winner['Bidder_Email'] == bidder_email and int(listing['Status']) == 2)
        return render_template(
            'item_detail.html',
            listing=listing,
            recent_bids=recent_bids,
            bid_count=bid_count,
            highest_bid=highest_bid,
            remaining_bids=remaining_bids,
            can_place_bid=can_place_bid,
            is_winner=is_winner
        )


@app.route('/bidder/auction/<seller_email>/<int:listing_id>/payment', methods=['GET', 'POST'])
@login_required
def auction_payment(seller_email, listing_id):
    role = str(session.get('user_type', '')).strip().lower()
    bidder_email = session.get('email')
    if role not in ('bidder', 'buyer'):
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
            return redirect(url_for('bidder_auctions'))

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
            return redirect(url_for('bidder_auction_detail', seller_email=seller_email, listing_id=listing_id))

        existing_txn = conn.execute(
            '''
            SELECT Transaction_ID
            FROM Transactions
            WHERE Seller_Email = ? AND Listing_ID = ? AND Bidder_Email = ?
            LIMIT 1
            ''',
            (seller_email, listing_id, bidder_email)
        ).fetchone()

        if request.method == 'POST':
            if existing_txn:
                flash('Payment already recorded.', 'info')
                return redirect(url_for('bidder_auction_detail', seller_email=seller_email, listing_id=listing_id))

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
                    datetime.now().strftime('%m/%d/%y'),
                    float(winning_bid['Bid_Price'])
                )
            )
            conn.commit()
            flash('Payment completed and transaction recorded.', 'success')
            return redirect(url_for('bidder_auction_detail', seller_email=seller_email, listing_id=listing_id))

        return render_template(
            'payment.html',
            listing=listing,
            winning_bid=float(winning_bid['Bid_Price']),
            payment_done=bool(existing_txn)
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
    return render_template('category_detail.html', category_name=name, breadcrumb=bc, subcategories=sc, listings=l)

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

# route for page seller_auction.html
@app.route('/seller_auction')
def seller_auction():
    conn = get_db_connection()
    if not session.get("email"):
        return redirect(url_for("login"))

    #
    # this part is for create auction
    # Get category selections (fetch all categories)
    email = session.get("email")
    categories = conn.execute("""
    SELECT category_name FROM Categories 
    """).fetchall()

    active_listings = conn.execute("""
    SELECT * FROM Auction_Listings
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
def seller_profile():
    email = session.get("email")
    if not email:
        return redirect(url_for("login"))

    conn = get_db_connection()

    return render_template("seller_profile.html",email=email,)


@app.route('/request_change_email', methods=['POST'])
def request_change_email():
    conn = get_db_connection()

    try:
        sender_email = session.get("email")
        if not sender_email:
            return redirect(url_for("login"))

        new_email = request.form.get("new_email", "").strip()

        if not new_email:
            return redirect(url_for(f'{user_type}_profile', request_sent="0"))

        if new_email == sender_email:
            return redirect(url_for(f'{user_type}_profile', request_sent="same"))

        # generate max id+1
        row = conn.execute("""
            SELECT MAX(request_id) FROM Requests
        """).fetchone()

        # if empty table start from 1
        max_id = row[0] if row[0] is not None else 0
        request_id = max_id + 1

        helpdesk_email = "helpdeskteam@lsu.edu"
        request_type = "ChangeID"
        request_desc = f"Please change my ID from {sender_email} to {new_email}."
        request_status = 0

        conn.execute("""
            INSERT INTO Requests (
                request_id,
                sender_email,
                helpdesk_staff_email,
                request_type,
                request_desc,
                request_status
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            request_id,
            sender_email,
            helpdesk_email,
            request_type,
            request_desc,
            request_status
        ))

        conn.commit()

        # redirect back to profile
        return redirect(url_for(f'{user_type}_profile', request_sent="1"))

    finally:
        conn.close()

#this update password
@app.route('/update_password', methods=['POST'])
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


if __name__ == '__main__':
    app.run()
    #app.run(debug=True)
