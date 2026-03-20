CREATE TABLE Zipcode_Info (
    zipcode TEXT,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    PRIMARY KEY (zipcode)
);

CREATE TABLE Users (
    user_id INTEGER,
    email TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    user_type TEXT NOT NULL,
    phone TEXT,
    zipcode TEXT NOT NULL,
    PRIMARY KEY (user_id),
    UNIQUE (email),
    FOREIGN KEY (zipcode) REFERENCES Zipcode_Info(zipcode),
    CHECK (user_type IN ('bidder', 'seller', 'helpdesk'))
);

CREATE TABLE Address (
    address_id INTEGER,
    user_id INTEGER NOT NULL,
    street_address TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    zipcode TEXT NOT NULL,
    address_type TEXT,
    PRIMARY KEY (address_id),
    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    FOREIGN KEY (zipcode) REFERENCES Zipcode_Info(zipcode),
    CHECK (address_type IN ('billing', 'shipping'))
);

CREATE TABLE Credit_Cards (
    card_id INTEGER,
    user_id INTEGER NOT NULL,
    card_number TEXT NOT NULL,
    cardholder_name TEXT NOT NULL,
    expiration_date TEXT NOT NULL,
    cvv TEXT NOT NULL,
    billing_address_id INTEGER NOT NULL,
    PRIMARY KEY (card_id),
    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    FOREIGN KEY (billing_address_id) REFERENCES Address(address_id)
);

CREATE TABLE Categories (
    category_id INTEGER,
    category_name TEXT NOT NULL,
    parent_category_id INTEGER,
    description TEXT,
    PRIMARY KEY (category_id),
    FOREIGN KEY (parent_category_id) REFERENCES Categories(category_id)
);

CREATE TABLE Local_Vendors (
    vendor_id INTEGER,
    business_name TEXT NOT NULL,
    business_description TEXT,
    rating_avg REAL,
    PRIMARY KEY (vendor_id),
    FOREIGN KEY (vendor_id) REFERENCES Users(user_id),
    CHECK (rating_avg BETWEEN 0 AND 5)
);

CREATE TABLE Sellers (
    seller_id INTEGER,
    is_verified INTEGER DEFAULT 0,
    total_listings INTEGER DEFAULT 0,
    PRIMARY KEY (seller_id),
    FOREIGN KEY (seller_id) REFERENCES Users(user_id),
    CHECK (is_verified IN (0, 1))
);

CREATE TABLE Auction_Listings (
    listing_id INTEGER,
    seller_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    start_price REAL NOT NULL,
    current_price REAL NOT NULL DEFAULT 0,
    start_time DATE NOT NULL,
    end_time DATE NOT NULL,
    is_active INTEGER DEFAULT 1,
    max_bids INTEGER,
    item_condition TEXT,
    PRIMARY KEY (listing_id),
    FOREIGN KEY (seller_id) REFERENCES Sellers(seller_id),
    FOREIGN KEY (category_id) REFERENCES Categories(category_id),
    CHECK (start_price >= 0),
    CHECK (current_price >= 0),
    CHECK (is_active IN (0, 1)),
    CHECK (item_condition IN ('new', 'used_like_new', 'used_good', 'used_fair'))
);

CREATE TABLE Bidders (
    bidder_id INTEGER,
    total_bids INTEGER DEFAULT 0,
    total_wins INTEGER DEFAULT 0,
    PRIMARY KEY (bidder_id),
    FOREIGN KEY (bidder_id) REFERENCES Users(user_id)
);

CREATE TABLE Bids (
    bid_id INTEGER,
    listing_id INTEGER NOT NULL,
    bidder_id INTEGER NOT NULL,
    bid_amount REAL NOT NULL,
    bid_time DATE NOT NULL,
    is_winning_bid INTEGER DEFAULT 0,
    PRIMARY KEY (bid_id),
    FOREIGN KEY (listing_id) REFERENCES Auction_Listings(listing_id),
    FOREIGN KEY (bidder_id) REFERENCES Bidders(bidder_id),
    UNIQUE (listing_id, bidder_id, bid_time),
    CHECK (bid_amount >= 0),
    CHECK (is_winning_bid IN (0, 1))
);

CREATE TABLE Transactions (
    transaction_id INTEGER,
    listing_id INTEGER NOT NULL,
    winning_bid_id INTEGER NOT NULL,
    buyer_id INTEGER NOT NULL,
    seller_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    transaction_time DATE NOT NULL,
    payment_method TEXT NOT NULL,
    card_id INTEGER,
    status TEXT NOT NULL,
    PRIMARY KEY (transaction_id),
    FOREIGN KEY (listing_id) REFERENCES Auction_Listings(listing_id),
    FOREIGN KEY (winning_bid_id) REFERENCES Bids(bid_id),
    FOREIGN KEY (buyer_id) REFERENCES Bidders(bidder_id),
    FOREIGN KEY (seller_id) REFERENCES Sellers(seller_id),
    FOREIGN KEY (card_id) REFERENCES Credit_Cards(card_id),
    CHECK (amount >= 0),
    CHECK (status IN ('completed', 'pending', 'cancelled'))
);

CREATE TABLE Ratings (
    rating_id INTEGER,
    transaction_id INTEGER NOT NULL,
    seller_id INTEGER NOT NULL,
    bidder_id INTEGER NOT NULL,
    rating_value INTEGER NOT NULL,
    review_text TEXT,
    review_time DATE NOT NULL,
    PRIMARY KEY (rating_id),
    UNIQUE (transaction_id),
    FOREIGN KEY (transaction_id) REFERENCES Transactions(transaction_id),
    FOREIGN KEY (seller_id) REFERENCES Sellers(seller_id),
    FOREIGN KEY (bidder_id) REFERENCES Bidders(bidder_id),
    CHECK (rating_value BETWEEN 1 AND 5)
);

CREATE TABLE Requests (
    request_id INTEGER,
    user_id INTEGER NOT NULL,
    request_type TEXT NOT NULL,
    request_details TEXT,
    submission_time DATE NOT NULL,
    status TEXT DEFAULT 'pending',
    admin_notes TEXT,
    PRIMARY KEY (request_id),
    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    CHECK (status IN ('pending', 'approved', 'rejected'))
);

CREATE TABLE Helpdesk (
    ticket_id INTEGER,
    user_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    description TEXT NOT NULL,
    submission_time DATE NOT NULL,
    status TEXT DEFAULT 'open',
    assigned_support_id INTEGER,
    resolution TEXT,
    PRIMARY KEY (ticket_id),
    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    FOREIGN KEY (assigned_support_id) REFERENCES Users(user_id),
    CHECK (status IN ('open', 'in_progress', 'resolved', 'closed'))
);