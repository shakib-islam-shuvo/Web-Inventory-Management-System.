import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

conn = mysql.connector.connect(
    host=os.getenv('DB_HOST', '127.0.0.1'),
    user=os.getenv('DB_USER', 'root'),
    password=os.getenv('DB_PASSWORD', ''),
    database=os.getenv('DB_NAME', 'first')
)

cursor = conn.cursor()

# Check if users table exists
cursor.execute("SHOW TABLES LIKE 'users'")
if cursor.fetchone():
    print("✓ Users table exists")
    
    # Show all users
    cursor.execute("SELECT username, role FROM users")
    users = cursor.fetchall()
    
    if users:
        print("\n📋 Existing users:")
        for user in users:
            print(f"  - {user[0]} ({user[1]})")
    else:
        print("\n⚠️ No users found in database!")
        print("Run the app once to create default users: python app.py")
else:
    print("❌ Users table doesn't exist!")
    print("Run the app once to initialize: python app.py")

cursor.close()
conn.close()
