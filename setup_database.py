import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

# Connect without specifying database
conn = mysql.connector.connect(
    host=os.getenv('DB_HOST', '127.0.0.1'),
    user=os.getenv('DB_USER', 'root'),
    password=os.getenv('DB_PASSWORD', '')
)

cursor = conn.cursor()

# Create database if not exists
db_name = os.getenv('DB_NAME', 'first')
cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
print(f"✓ Database '{db_name}' created successfully!")

cursor.close()
conn.close()

print("\nNow run: python app.py")
