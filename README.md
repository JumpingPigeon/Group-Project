# 431W Nitanny Auction Project
Group Members: Hao Wang, Sirui Lim, Jinyang Liu, Xuan Liu

# Overview
This is a comprehensive online auction platform built with Flask, featuring three distinct user roles: **Bidders**, **Sellers**, and **Helpdesk Staff**. The system supports complete auction lifecycle management including user registration, category hierarchy, auction listing creation, bidding, payment processing, and helpdesk support.

# Progress Tracking/Feature List
1. Data population - Hao
    - DB Browser for SQLite is used for Data Population
    - Intruction:
        - Open the tool
        - Open the database
        - choose import data from csv files
2. User Login
    1. Login Page - Hao
    2. Helpdesk - Xuan
    3. Seller - Sirui
    4. Bidder - Jinyang
3. Category Hierarchy - Xuan
    - View all categories and subcategories
4. Auction Listing Management (Seller) - Sirui
    - Create a new auction listing
    - Edit an existing auction listing

5. AuctionBidding (Bidder) - Jinyang
    -
6. UserRegistration - Jinyang
7. UserProfileUpdate - Sirui
8. Product Search - Hao

9. Extra Credit 1 - Helpdesk Support - Hao
    - Allow helpdesk to claim request, view and manage their requests, and mark as complete once completed.
    - For Demo Purpose, we only implment Adding a new catrgory fucntion
10. Extra Credit 2 - AuctionPromotion (Seller) - Hao
    - Allow seller to create a promotion for their auction
11. Extra Credit 3 - Wishlist - Hao
    - Allow bidder to add an item to their wishlist
    - Able to place bid in the wishlist

## Organization
1. All webpage design in located at the templates folder.

## Instructions
1. Open the code folder in VS code
2. Run **pip install flask**
3. Run **python app.py**
4. Click ***http://127.0.0.1:5000/*** in terminal

## Reference
- [Flask Documentation](https://flask.palletsprojects.com/en/stable/#user-s-guide)
- [Bootstrap Documentation](https://getbootstrap.com/docs/5.3/getting-started/introduction/)
- [SQLite Documentation] (https://www.sqlitetutorial.net/)
- [HTML Tutorial] (https://www.w3schools.com/html/)
- [CSS Tutorial] (https://www.w3schools.com/css/)