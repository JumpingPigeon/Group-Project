import sqlite3
from werkzeug.security import generate_password_hash

def hash_existing_passwords():
    conn = sqlite3.connect('nittany_auction.db')
    cursor = conn.cursor()

    cursor.execute("SELECT email, password FROM Users")
    users = cursor.fetchall()

    print(f"Converting {len(users)} users...")

    for email, plain_password in users:
        hashed_password = generate_password_hash(plain_password)
        
        cursor.execute(
            "UPDATE Users SET password = ? WHERE email = ?", 
            (hashed_password, email)
        )

    conn.commit()
    conn.close()
    print("Conversion completed successfully.")

if __name__ == '__main__':
    hash_existing_passwords()