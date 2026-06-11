from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import pooling
from datetime import datetime
import os
from dotenv import load_dotenv
import logging
import math
from functools import lru_cache

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'fallback-key-change-this')

# Connection pool
pool = None

@app.context_processor
def inject_branch_name():
    branch_name = None
    if session.get('role') in ['owner', 'salesman'] and session.get('branch_id'):
        branch_name = get_branch_name(session.get('branch_id'))
    return dict(branch_name=branch_name)

# Database configuration from environment
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'user': os.getenv('DB_USER', 'store'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'database': os.getenv('DB_NAME', 'first')
}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_number(value, field_name, min_val=0):
    """Validate and convert string to number with proper error handling"""
    try:
        if isinstance(value, str) and value.lower() in ['nan', 'inf', '-inf']:
            raise ValueError(f"Invalid {field_name}: {value}")
        num = float(value)
        if math.isnan(num) or math.isinf(num):
            raise ValueError(f"Invalid {field_name}: {value}")
        if num < min_val:
            raise ValueError(f"{field_name} must be >= {min_val}")
        return num
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid {field_name}: {value}") from e

def validate_int(value, field_name, min_val=0):
    """Validate and convert string to integer with proper error handling"""
    try:
        num = int(value)
        if num < min_val:
            raise ValueError(f"{field_name} must be >= {min_val}")
        return num
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid {field_name}: {value}") from e

def init_pool():
    global pool
    try:
        pool = pooling.MySQLConnectionPool(
            pool_name="inventory_pool",
            pool_size=10,
            pool_reset_session=True,
            **DB_CONFIG
        )
    except mysql.connector.Error as e:
        logger.error(f"Connection pool failed: {e}")
        raise

def get_db_connection():
    try:
        return pool.get_connection() if pool else mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as e:
        logger.error(f"Database connection failed: {e}")
        raise

@lru_cache(maxsize=100)
def get_branch_name(branch_id):
    if not branch_id:
        return "Unknown Branch"
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT branch_name FROM branches WHERE id = %s", (branch_id,))
        result = cursor.fetchone()
        return result[0] if result else "Unknown Branch"
    except mysql.connector.Error:
        return "Unknown Branch"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def init_db():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Use existing database
        cursor.execute("USE first")
        
        # Create branches table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS branches (
                id INT AUTO_INCREMENT PRIMARY KEY,
                branch_name VARCHAR(100) NOT NULL,
                location VARCHAR(255)
            )
        """)
        
        # Insert default branches
        cursor.execute("SELECT COUNT(*) FROM branches")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO branches (branch_name, location) VALUES ('Bashundhara', 'Bashundhara City')")
            cursor.execute("INSERT INTO branches (branch_name, location) VALUES ('Dhanmandi', 'Dhanmandi Area')")
            cursor.execute("INSERT INTO branches (branch_name, location) VALUES ('Mirpur', 'Mirpur Section')")
        else:
            # Update existing branch names if they are still generic
            cursor.execute("UPDATE branches SET branch_name = 'Bashundhara', location = 'Bashundhara City' WHERE id = 1 AND branch_name = 'Branch 1'")
            cursor.execute("UPDATE branches SET branch_name = 'Dhanmandi', location = 'Dhanmandi Area' WHERE id = 2 AND branch_name = 'Branch 2'")
            cursor.execute("UPDATE branches SET branch_name = 'Mirpur', location = 'Mirpur Section' WHERE id = 3 AND branch_name = 'Branch 3'")
            conn.commit()
        
        # Create or modify users table with branch support
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role ENUM('super_admin', 'owner', 'assistant', 'salesman') NOT NULL,
                branch_id INT,
                theme_preference ENUM('light', 'dark') DEFAULT 'light',
                FOREIGN KEY (branch_id) REFERENCES branches(id)
            )
        """)
        
        # Add branch_id to existing users table if not exists
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN branch_id INT")
            cursor.execute("ALTER TABLE users ADD FOREIGN KEY (branch_id) REFERENCES branches(id)")
        except mysql.connector.Error as e:
            logger.info(f"Branch column exists: {e}")
        
        # Add theme_preference column if not exists
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN theme_preference ENUM('light', 'dark') DEFAULT 'light'")
        except mysql.connector.Error as e:
            logger.info(f"Theme preference column exists: {e}")
        
        # Create products table with branch support
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_name VARCHAR(100) NOT NULL,
                description TEXT,
                cost_price DECIMAL(10,2) DEFAULT 0,
                selling_price DECIMAL(10,2) DEFAULT 0,
                branch_id INT DEFAULT 1
            )
        """)
        
        # Add branch_id to existing products table if not exists
        try:
            cursor.execute("ALTER TABLE products ADD COLUMN branch_id INT DEFAULT 1")
        except mysql.connector.Error as e:
            logger.info(f"Products branch column exists: {e}")
        
        # Create inventory_logs table with branch support
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_id INT NOT NULL,
                quantity_change INT NOT NULL,
                cost_price DECIMAL(10,2),
                selling_price DECIMAL(10,2),
                log_type ENUM('sale', 'restock') NOT NULL,
                recorded_by VARCHAR(50) NOT NULL,
                branch_id INT DEFAULT 1,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)
        
        # Add branch_id to existing inventory_logs table if not exists
        try:
            cursor.execute("ALTER TABLE inventory_logs ADD COLUMN branch_id INT DEFAULT 1")
        except mysql.connector.Error as e:
            logger.info(f"Inventory logs branch column exists: {e}")
        
        # Update role enum step by step to avoid data truncation
        try:
            cursor.execute("SHOW COLUMNS FROM users LIKE 'role'")
            result = cursor.fetchone()
            if result and 'super_admin' not in result[1]:
                cursor.execute("ALTER TABLE users MODIFY COLUMN role ENUM('owner', 'assistant', 'salesman', 'super_admin') NOT NULL")
        except mysql.connector.Error as e:
            logger.info(f"Role modification skipped: {e}")
        
        # Create super admin account
        cursor.execute("SELECT * FROM users WHERE username = 'super_admin'")
        if not cursor.fetchone():
            try:
                super_admin_hash = generate_password_hash('super123')
                cursor.execute("INSERT INTO users (username, password_hash, role, branch_id) VALUES (%s, %s, %s, %s)",
                              ('super_admin', super_admin_hash, 'super_admin', None))
            except mysql.connector.Error as e:
                logger.error(f"Could not create super admin: {e}")
        
        # Create branch owners
        for i in range(1, 4):
            cursor.execute(f"SELECT * FROM users WHERE username = 'owner{i}'")
            if not cursor.fetchone():
                try:
                    owner_hash = generate_password_hash(f'admin{i}23')
                    cursor.execute("INSERT INTO users (username, password_hash, role, branch_id) VALUES (%s, %s, %s, %s)",
                                  (f'owner{i}', owner_hash, 'owner', i))
                except mysql.connector.Error as e:
                    logger.error(f"Could not create owner{i}: {e}")
        
        # Create branch salesmen
        for i in range(1, 4):
            cursor.execute(f"SELECT * FROM users WHERE username = 'salesman{i}'")
            if not cursor.fetchone():
                try:
                    salesman_hash = generate_password_hash(f'sales{i}23')
                    cursor.execute("INSERT INTO users (username, password_hash, role, branch_id) VALUES (%s, %s, %s, %s)",
                                  (f'salesman{i}', salesman_hash, 'salesman', i))
                except mysql.connector.Error as e:
                    logger.error(f"Could not create salesman{i}: {e}")
        
        # Create legacy accounts if they don't exist
        cursor.execute("SELECT * FROM users WHERE username = 'owner'")
        if not cursor.fetchone():
            try:
                owner_hash = generate_password_hash('admin123')
                cursor.execute("INSERT INTO users (username, password_hash, role, branch_id) VALUES (%s, %s, %s, %s)",
                              ('owner', owner_hash, 'owner', 1))
            except mysql.connector.Error as e:
                logger.error(f"Could not create legacy owner: {e}")
        
        cursor.execute("SELECT * FROM users WHERE username = 'salesman'")
        if not cursor.fetchone():
            try:
                salesman_hash = generate_password_hash('sales123')
                cursor.execute("INSERT INTO users (username, password_hash, role, branch_id) VALUES (%s, %s, %s, %s)",
                              ('salesman', salesman_hash, 'salesman', 1))
            except mysql.connector.Error as e:
                logger.error(f"Could not create salesman: {e}")
        
        conn.commit()
        
    except mysql.connector.Error as e:
        logger.error(f"Database initialization failed: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session['role'] == 'super_admin':
        return redirect(url_for('super_admin_dashboard'))
    elif session['role'] == 'owner':
        return redirect(url_for('owner_dashboard'))
    elif session['role'] == 'salesman':
        return redirect(url_for('salesman_dashboard'))
    else:
        return redirect(url_for('assistant_dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Username and password are required')
            return render_template('login.html')
        
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, password_hash, role, branch_id, theme_preference FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['role'] = user[3]
                session['branch_id'] = user[4]
                session['theme'] = user[5] or 'light'
                return redirect(url_for('index'))
            else:
                flash('Invalid credentials')
                
        except mysql.connector.Error as e:
            logger.error(f"Login database error: {e}")
            flash('System error. Please try again.')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))



@app.route('/super_admin/return')
def return_to_super_admin():
    if session.get('role') != 'super_admin':
        return redirect(url_for('login'))
    
    # Clear branch context when returning to super admin dashboard
    session.pop('branch_id', None)
    session.pop('super_admin_viewing_branch', None)
    session.pop('current_branch_name', None)
    return redirect(url_for('super_admin_dashboard'))

@app.route('/super_admin/dashboard')
def super_admin_dashboard():
    if session.get('role') != 'super_admin':
        return redirect(url_for('login'))
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all branches data
        cursor.execute("""
            SELECT b.id, b.branch_name, b.location,
                   COALESCE(SUM(ABS(il.quantity_change) * il.selling_price), 0) as today_sales,
                   COUNT(DISTINCT p.id) as total_products
            FROM branches b
            LEFT JOIN products p ON b.id = p.branch_id
            LEFT JOIN inventory_logs il ON p.id = il.product_id AND il.log_type = 'sale' AND DATE(il.timestamp) = CURDATE()
            GROUP BY b.id, b.branch_name, b.location
        """)
        branches_data = cursor.fetchall()
        
        # Get total sales and profit for all branches
        # Today's totals
        cursor.execute("""
            SELECT COALESCE(SUM(ABS(il.quantity_change) * il.selling_price), 0) as total_sales,
                   COALESCE(SUM(ABS(il.quantity_change) * (il.selling_price - CASE WHEN il.log_type = 'restock' THEN il.cost_price ELSE p.cost_price END)), 0) as total_profit
            FROM inventory_logs il
            JOIN products p ON il.product_id = p.id
            WHERE il.log_type = 'sale' AND DATE(il.timestamp) = CURDATE()
        """)
        today_totals = cursor.fetchone()
        
        # Weekly totals
        cursor.execute("""
            SELECT COALESCE(SUM(ABS(il.quantity_change) * il.selling_price), 0) as total_sales,
                   COALESCE(SUM(ABS(il.quantity_change) * (il.selling_price - CASE WHEN il.log_type = 'restock' THEN il.cost_price ELSE p.cost_price END)), 0) as total_profit
            FROM inventory_logs il
            JOIN products p ON il.product_id = p.id
            WHERE il.log_type = 'sale' AND il.timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """)
        weekly_totals = cursor.fetchone()
        
        # Monthly totals
        cursor.execute("""
            SELECT COALESCE(SUM(ABS(il.quantity_change) * il.selling_price), 0) as total_sales,
                   COALESCE(SUM(ABS(il.quantity_change) * (il.selling_price - CASE WHEN il.log_type = 'restock' THEN il.cost_price ELSE p.cost_price END)), 0) as total_profit
            FROM inventory_logs il
            JOIN products p ON il.product_id = p.id
            WHERE il.log_type = 'sale' AND MONTH(il.timestamp) = MONTH(NOW()) AND YEAR(il.timestamp) = YEAR(NOW())
        """)
        monthly_totals = cursor.fetchone()
        
        # Get all users for management
        cursor.execute("""
            SELECT u.id, u.username, u.role, b.branch_name
            FROM users u
            LEFT JOIN branches b ON u.branch_id = b.id
            WHERE u.role != 'super_admin'
            ORDER BY u.role, b.branch_name, u.username
        """)
        users_data = cursor.fetchall()
        
        return render_template('super_admin_dashboard.html', 
                             branches_data=branches_data,
                             today_totals=today_totals,
                             weekly_totals=weekly_totals,
                             monthly_totals=monthly_totals,
                             users_data=users_data)
        
    except mysql.connector.Error as e:
        logger.error(f"Super admin dashboard error: {e}")
        return render_template('super_admin_dashboard.html', branches_data=[])
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/super_admin/create_branch', methods=['GET', 'POST'])
def create_branch():
    if session.get('role') != 'super_admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        conn = None
        cursor = None
        try:
            branch_name = request.form.get('branch_name', '').strip()
            location = request.form.get('location', '').strip()
            
            if not branch_name or not location:
                flash('Branch name and location are required')
                return redirect(url_for('super_admin_dashboard'))
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Create new branch
            cursor.execute("INSERT INTO branches (branch_name, location) VALUES (%s, %s)", (branch_name, location))
            branch_id = cursor.lastrowid
            
            # Get next owner/salesman numbers
            cursor.execute("SELECT MAX(CAST(SUBSTRING(username, 6) AS UNSIGNED)) FROM users WHERE username LIKE 'owner%'")
            max_owner = cursor.fetchone()[0] or 0
            next_owner_num = max_owner + 1
            
            cursor.execute("SELECT MAX(CAST(SUBSTRING(username, 9) AS UNSIGNED)) FROM users WHERE username LIKE 'salesman%'")
            max_salesman = cursor.fetchone()[0] or 0
            next_salesman_num = max_salesman + 1
            
            # Create owner account
            owner_username = f'owner{next_owner_num}'
            owner_password = f'admin{next_owner_num}23'
            owner_hash = generate_password_hash(owner_password)
            cursor.execute("INSERT INTO users (username, password_hash, role, branch_id) VALUES (%s, %s, %s, %s)",
                          (owner_username, owner_hash, 'owner', branch_id))
            
            # Create salesman account
            salesman_username = f'salesman{next_salesman_num}'
            salesman_password = f'sales{next_salesman_num}23'
            salesman_hash = generate_password_hash(salesman_password)
            cursor.execute("INSERT INTO users (username, password_hash, role, branch_id) VALUES (%s, %s, %s, %s)",
                          (salesman_username, salesman_hash, 'salesman', branch_id))
            
            conn.commit()
            flash(f'Branch "{branch_name}" created successfully! Owner: {owner_username}/{owner_password}, Salesman: {salesman_username}/{salesman_password}')
            
        except mysql.connector.Error as e:
            logger.error(f"Create branch error: {e}")
            flash('Error creating branch. Please try again.')
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    return redirect(url_for('super_admin_dashboard'))

@app.route('/super_admin/manage_users', methods=['POST'])
def manage_users():
    if session.get('role') != 'super_admin':
        return redirect(url_for('login'))
    
    conn = None
    cursor = None
    try:
        user_id = request.form.get('user_id')
        new_username = request.form.get('new_username', '').strip()
        new_password = request.form.get('new_password', '').strip()
        
        if not user_id or not new_username or not new_password:
            flash('All fields are required')
            return redirect(url_for('super_admin_dashboard'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if new username already exists (excluding current user)
        cursor.execute("SELECT id FROM users WHERE username = %s AND id != %s", (new_username, user_id))
        if cursor.fetchone():
            flash('Username already exists')
            return redirect(url_for('super_admin_dashboard'))
        
        # Update username and password
        password_hash = generate_password_hash(new_password)
        cursor.execute("UPDATE users SET username = %s, password_hash = %s WHERE id = %s AND role != 'super_admin'", 
                      (new_username, password_hash, user_id))
        
        if cursor.rowcount > 0:
            conn.commit()
            flash(f'User credentials updated successfully! New login: {new_username}/{new_password}')
        else:
            flash('User not found or cannot modify super admin')
            
    except mysql.connector.Error as e:
        logger.error(f"Manage users error: {e}")
        flash('Error updating user credentials')
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
    return redirect(url_for('super_admin_dashboard'))

@app.route('/super_admin/branch/<int:branch_id>')
def view_branch(branch_id):
    if session.get('role') != 'super_admin':
        return redirect(url_for('login'))
    
    # Set branch_id in session for super admin to access branch functions
    session['branch_id'] = branch_id
    session['super_admin_viewing_branch'] = True
    
    # Redirect to owner dashboard with the selected branch context
    return redirect(url_for('owner_dashboard'))

@app.route('/owner/dashboard')
def owner_dashboard():
    if session.get('role') not in ['owner', 'super_admin']:
        return redirect(url_for('login'))
    
    branch_id = session.get('branch_id')
    if not branch_id and session.get('role') != 'super_admin':
        flash('No branch assigned')
        return redirect(url_for('login'))
    elif not branch_id and session.get('role') == 'super_admin':
        return redirect(url_for('super_admin_dashboard'))
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current stock levels for this branch
        cursor.execute("""
            SELECT p.id, p.product_name, 
                   COALESCE(SUM(il.quantity_change), 0) as current_stock,
                   p.cost_price, p.selling_price
            FROM products p
            LEFT JOIN inventory_logs il ON p.id = il.product_id
            WHERE p.branch_id = %s
            GROUP BY p.id, p.product_name, p.cost_price, p.selling_price
        """, (branch_id,))
        stock_data = cursor.fetchall()
        
        # Get today's sales for this branch
        cursor.execute("""
            SELECT COALESCE(SUM(ABS(il.quantity_change) * il.selling_price), 0) as today_sales
            FROM inventory_logs il
            JOIN products p ON il.product_id = p.id
            WHERE il.log_type = 'sale' AND DATE(il.timestamp) = CURDATE() AND p.branch_id = %s
        """, (branch_id,))
        today_sales = cursor.fetchone()[0]
        
        # Get total inventory value for this branch
        cursor.execute("""
            SELECT COALESCE(SUM(
                (SELECT COALESCE(SUM(quantity_change), 0) FROM inventory_logs il WHERE il.product_id = p.id) *
                p.cost_price
            ), 0) as total_value
            FROM products p
            WHERE p.branch_id = %s
        """, (branch_id,))
        total_value = cursor.fetchone()[0]
        
        branch_name = get_branch_name(branch_id)
        session['current_branch_name'] = branch_name
        
        return render_template('owner_dashboard.html', 
                             stock_data=stock_data, 
                             today_sales=today_sales,
                             total_value=total_value,
                             branch_name=branch_name)
                             
    except mysql.connector.Error as e:
        logger.error(f"Owner dashboard database error: {e}")
        flash('Error loading dashboard data')
        return render_template('owner_dashboard.html', stock_data=[], today_sales=0, total_value=0)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/owner/add_product', methods=['POST'])
def add_product():
    if session.get('role') not in ['owner', 'super_admin']:
        return redirect(url_for('login'))
    
    branch_id = session.get('branch_id')
    if not branch_id and session.get('role') != 'super_admin':
        flash('No branch assigned')
        return redirect(url_for('login'))
    elif not branch_id and session.get('role') == 'super_admin':
        return redirect(url_for('super_admin_dashboard'))
    
    conn = None
    cursor = None
    try:
        product_name = request.form.get('product_name', '').strip()
        description = request.form.get('description', '').strip()
        quantity = validate_int(request.form.get('quantity', 0), 'quantity', 1)
        cost_price = validate_number(request.form.get('cost_price', 0), 'cost_price')
        selling_price = validate_number(request.form.get('selling_price', 0), 'selling_price')
        
        if not product_name:
            flash('Product name is required')
            return redirect(url_for('owner_dashboard'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Add product with prices and branch
        cursor.execute("INSERT INTO products (product_name, description, cost_price, selling_price, branch_id) VALUES (%s, %s, %s, %s, %s)",
                      (product_name, description, cost_price, selling_price, branch_id))
        product_id = cursor.lastrowid
        
        # Add initial stock
        cursor.execute("""
            INSERT INTO inventory_logs (product_id, quantity_change, cost_price, selling_price, log_type, recorded_by, branch_id)
            VALUES (%s, %s, %s, %s, 'restock', %s, %s)
        """, (product_id, quantity, cost_price, selling_price, session['username'], branch_id))
        
        conn.commit()
        flash('Product added successfully')
        
    except ValueError as e:
        flash(f'Input error: {str(e)}')
    except mysql.connector.Error as e:
        logger.error(f"Add product database error: {e}")
        flash('Database error. Please try again.')
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
    return redirect(url_for('owner_dashboard'))

@app.route('/owner/restock', methods=['POST'])
def restock():
    if session.get('role') not in ['owner', 'super_admin']:
        return redirect(url_for('login'))
    
    branch_id = session.get('branch_id')
    if not branch_id and session.get('role') != 'super_admin':
        flash('No branch assigned')
        return redirect(url_for('login'))
    elif not branch_id and session.get('role') == 'super_admin':
        return redirect(url_for('super_admin_dashboard'))
    
    conn = None
    cursor = None
    try:
        product_id = validate_int(request.form.get('product_id', 0), 'product_id', 1)
        quantity = validate_int(request.form.get('quantity', 0), 'quantity', 1)
        cost_price = validate_number(request.form.get('cost_price', 0), 'cost_price')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify product belongs to this branch
        cursor.execute("SELECT selling_price FROM products WHERE id = %s AND branch_id = %s", (product_id, branch_id))
        result = cursor.fetchone()
        if not result:
            flash('Product not found in your branch')
            return redirect(url_for('owner_dashboard'))
        
        selling_price = result[0]
        
        cursor.execute("""
            INSERT INTO inventory_logs (product_id, quantity_change, cost_price, selling_price, log_type, recorded_by, branch_id)
            VALUES (%s, %s, %s, %s, 'restock', %s, %s)
        """, (product_id, quantity, cost_price, selling_price, session['username'], branch_id))
        
        conn.commit()
        flash('Stock added successfully')
        
    except ValueError as e:
        flash(f'Input error: {str(e)}')
    except mysql.connector.Error as e:
        logger.error(f"Restock database error: {e}")
        flash('Database error. Please try again.')
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
    return redirect(url_for('owner_dashboard'))

@app.route('/assistant/dashboard')
def assistant_dashboard():
    if session.get('role') not in ['assistant', 'super_admin']:
        return redirect(url_for('login'))
    
    return render_template('assistant_dashboard.html')

@app.route('/assistant/record_sale', methods=['GET', 'POST'])
def record_sale():
    if session.get('role') not in ['assistant', 'super_admin']:
        return redirect(url_for('login'))
    
    branch_id = session.get('branch_id')
    if not branch_id:
        flash('No branch assigned')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        conn = None
        cursor = None
        try:
            product_id = validate_int(request.form.get('product_id', 0), 'product_id', 1)
            quantity = validate_int(request.form.get('quantity', 0), 'quantity', 1)
            selling_price = validate_number(request.form.get('selling_price', 0), 'selling_price')
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check if product belongs to this branch and has enough stock
            cursor.execute("""
                SELECT COALESCE(SUM(il.quantity_change), 0) as current_stock
                FROM inventory_logs il
                JOIN products p ON il.product_id = p.id
                WHERE il.product_id = %s AND p.branch_id = %s
            """, (product_id, branch_id))
            result = cursor.fetchone()
            current_stock = result[0] if result else 0
            
            if current_stock >= quantity:
                cursor.execute("""
                    INSERT INTO inventory_logs (product_id, quantity_change, selling_price, log_type, recorded_by, branch_id)
                    VALUES (%s, %s, %s, 'sale', %s, %s)
                """, (product_id, -quantity, selling_price, session['username'], branch_id))
                conn.commit()
                flash('Sale recorded successfully')
            else:
                flash('Insufficient stock')
                
        except ValueError as e:
            flash(f'Input error: {str(e)}')
        except mysql.connector.Error as e:
            logger.error(f"Record sale database error: {e}")
            flash('Database error. Please try again.')
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
                
        return redirect(url_for('assistant_dashboard'))
    
    # Get products for this branch
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, product_name FROM products WHERE branch_id = %s", (branch_id,))
        products = cursor.fetchall()
        return render_template('record_sale.html', products=products)
    except mysql.connector.Error as e:
        logger.error(f"Get products database error: {e}")
        return render_template('record_sale.html', products=[])
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/assistant/view_stock')
def view_stock():
    if session.get('role') not in ['assistant', 'super_admin']:
        return redirect(url_for('login'))
    
    branch_id = session.get('branch_id')
    if not branch_id:
        flash('No branch assigned')
        return redirect(url_for('login'))
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.product_name, COALESCE(SUM(il.quantity_change), 0) as current_stock
            FROM products p
            LEFT JOIN inventory_logs il ON p.id = il.product_id
            WHERE p.branch_id = %s
            GROUP BY p.id, p.product_name
        """, (branch_id,))
        stock_data = cursor.fetchall()
        
        return render_template('view_stock.html', stock_data=stock_data)
        
    except mysql.connector.Error as e:
        logger.error(f"View stock database error: {e}")
        return render_template('view_stock.html', stock_data=[])
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/owner/logs')
def view_logs():
    if session.get('role') not in ['owner', 'super_admin']:
        return redirect(url_for('login'))
    
    branch_id = session.get('branch_id')
    if not branch_id and session.get('role') != 'super_admin':
        flash('No branch assigned')
        return redirect(url_for('login'))
    elif not branch_id and session.get('role') == 'super_admin':
        return redirect(url_for('super_admin_dashboard'))
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.product_name, il.quantity_change, 
                   CASE WHEN il.log_type = 'restock' THEN il.cost_price ELSE p.cost_price END as cost_price,
                   CASE WHEN il.selling_price IS NULL THEN p.selling_price ELSE il.selling_price END as selling_price,
                   il.log_type, il.recorded_by, il.timestamp
            FROM inventory_logs il
            JOIN products p ON il.product_id = p.id
            WHERE p.branch_id = %s
            ORDER BY il.timestamp DESC
        """, (branch_id,))
        logs = cursor.fetchall()
        
        return render_template('logs.html', logs=logs)
        
    except mysql.connector.Error as e:
        logger.error(f"View logs database error: {e}")
        return render_template('logs.html', logs=[])
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()











@app.route('/salesman/dashboard')
def salesman_dashboard():
    if session.get('role') not in ['salesman', 'super_admin']:
        return redirect(url_for('login'))
    
    branch_id = session.get('branch_id')
    if not branch_id:
        flash('No branch assigned')
        return redirect(url_for('login'))
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get products for this branch with current stock and selling prices only
        cursor.execute("""
            SELECT p.id, p.product_name, p.description,
                   COALESCE(SUM(il.quantity_change), 0) as current_stock,
                   p.selling_price
            FROM products p
            LEFT JOIN inventory_logs il ON p.id = il.product_id
            WHERE p.branch_id = %s
            GROUP BY p.id, p.product_name, p.description, p.selling_price
            HAVING current_stock > 0
        """, (branch_id,))
        raw_products = cursor.fetchall()
        
        # Convert decimal values to float
        products = []
        for p in raw_products:
            products.append((
                p[0], p[1], p[2], p[3], 
                float(p[4]) if p[4] else 0.0
            ))
        
        branch_name = get_branch_name(branch_id)
        
        return render_template('salesman_dashboard.html', products=products, branch_name=branch_name)
        
    except mysql.connector.Error as e:
        logger.error(f"Salesman dashboard database error: {e}")
        return render_template('salesman_dashboard.html', products=[])
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



def process_sale(redirect_route):
    items = []
    total_amount = 0
    conn = None
    cursor = None
    
    branch_id = session.get('branch_id')
    if not branch_id:
        flash('No branch assigned')
        return redirect(url_for('login'))
    
    try:
        discount_percent = validate_number(request.form.get('discount_percent', 0), 'discount_percent')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        branch_name = get_branch_name(branch_id)
        
        for key in request.form:
            if key.startswith('qty_') and request.form[key]:
                product_id = validate_int(key.split('_')[1], 'product_id', 1)
                quantity = validate_int(request.form[key], 'quantity', 1)
                discounted_price = validate_number(request.form[f'price_{product_id}'], 'price')
                
                # Check stock for this branch only
                cursor.execute("""
                    SELECT COALESCE(SUM(il.quantity_change), 0)
                    FROM inventory_logs il
                    JOIN products p ON il.product_id = p.id
                    WHERE il.product_id = %s AND p.branch_id = %s
                """, (product_id, branch_id))
                current_stock = cursor.fetchone()[0]
                
                if current_stock >= quantity:
                    cursor.execute("SELECT product_name, selling_price FROM products WHERE id = %s AND branch_id = %s", (product_id, branch_id))
                    result = cursor.fetchone()
                    if not result:
                        raise ValueError(f'Product {product_id} not found in your branch')
                    
                    cursor.execute("INSERT INTO inventory_logs (product_id, quantity_change, selling_price, log_type, recorded_by, branch_id) VALUES (%s, %s, %s, 'sale', %s, %s)",
                                  (product_id, -quantity, discounted_price, session['username'], branch_id))
                    
                    item_total = quantity * discounted_price
                    total_amount += item_total
                    
                    items.append({
                        'name': result[0],
                        'quantity': quantity,
                        'original_price': float(result[1]),
                        'price': discounted_price,
                        'total': item_total
                    })
                else:
                    raise ValueError(f'Insufficient stock for product ID {product_id}')
        
        conn.commit()
        
        if items:
            subtotal = sum(item['quantity'] * item['original_price'] for item in items)
            discount_amount = subtotal - total_amount
            logger.info(f"Rendering receipt with branch_name: {branch_name}")
            return render_template('receipt.html', items=items, total_amount=total_amount, 
                                 discount_percent=discount_percent, discount_amount=discount_amount, 
                                 subtotal=subtotal, branch_name=branch_name)
        else:
            flash('No items selected for sale')
            return redirect(url_for(redirect_route))
            
    except ValueError as e:
        flash(f'Input error: {str(e)}')
        return redirect(url_for(redirect_route))
    except mysql.connector.Error as e:
        logger.error(f"Make sale error: {e}")
        flash('Database error. Please try again.')
        if conn:
            conn.rollback()
        return redirect(url_for(redirect_route))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/salesman/make_sale', methods=['POST'])
def make_sale():
    if session.get('role') not in ['salesman', 'super_admin']:
        return redirect(url_for('login'))
    
    return process_sale('salesman_dashboard')

@app.route('/salesman/stock')
def salesman_stock():
    if session.get('role') not in ['salesman', 'super_admin']:
        return redirect(url_for('login'))
    
    branch_id = session.get('branch_id')
    if not branch_id:
        flash('No branch assigned')
        return redirect(url_for('login'))
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.product_name, p.description, COALESCE(SUM(il.quantity_change), 0) as current_stock
            FROM products p
            LEFT JOIN inventory_logs il ON p.id = il.product_id
            WHERE p.branch_id = %s
            GROUP BY p.id, p.product_name, p.description
            ORDER BY p.product_name
        """, (branch_id,))
        stock_data = cursor.fetchall()
        
        return render_template('salesman_stock.html', stock_data=stock_data)
        
    except mysql.connector.Error as e:
        logger.error(f"Salesman stock database error: {e}")
        return render_template('salesman_stock.html', stock_data=[])
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/owner/update_prices', methods=['POST'])
def update_prices():
    if session.get('role') not in ['owner', 'super_admin']:
        return redirect(url_for('login'))
    
    branch_id = session.get('branch_id')
    if not branch_id and session.get('role') != 'super_admin':
        flash('No branch assigned')
        return redirect(url_for('login'))
    elif not branch_id and session.get('role') == 'super_admin':
        return redirect(url_for('super_admin_dashboard'))
    
    conn = None
    cursor = None
    try:
        product_id = validate_int(request.form.get('product_id', 0), 'product_id', 1)
        cost_price = validate_number(request.form.get('cost_price', 0), 'cost_price')
        selling_price = validate_number(request.form.get('selling_price', 0), 'selling_price')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify product exists in this branch
        cursor.execute("SELECT id FROM products WHERE id = %s AND branch_id = %s", (product_id, branch_id))
        if not cursor.fetchone():
            flash('Product not found in your branch')
            return redirect(url_for('owner_dashboard'))
        
        cursor.execute("""
            UPDATE products SET cost_price = %s, selling_price = %s WHERE id = %s AND branch_id = %s
        """, (cost_price, selling_price, product_id, branch_id))
        
        conn.commit()
        flash('Prices updated successfully')
        
    except ValueError as e:
        flash(f'Input error: {str(e)}')
    except mysql.connector.Error as e:
        logger.error(f"Update prices database error: {e}")
        flash('Database error. Please try again.')
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
    return redirect(url_for('owner_dashboard'))

@app.route('/owner/today_sales')
def today_sales():
    if session.get('role') not in ['owner', 'super_admin']:
        return redirect(url_for('login'))
    
    branch_id = session.get('branch_id')
    if not branch_id and session.get('role') != 'super_admin':
        flash('No branch assigned')
        return redirect(url_for('login'))
    elif not branch_id and session.get('role') == 'super_admin':
        return redirect(url_for('super_admin_dashboard'))
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.product_name, il.quantity_change, 
                   CASE WHEN il.log_type = 'restock' THEN il.cost_price ELSE p.cost_price END as cost_price,
                   il.selling_price, il.log_type, il.recorded_by, il.timestamp
            FROM inventory_logs il
            JOIN products p ON il.product_id = p.id
            WHERE il.log_type = 'sale' AND DATE(il.timestamp) = CURDATE() AND p.branch_id = %s
            ORDER BY il.timestamp DESC
        """, (branch_id,))
        logs = cursor.fetchall()
        
        return render_template('today_sales.html', logs=logs)
        
    except mysql.connector.Error as e:
        logger.error(f"Today sales database error: {e}")
        return render_template('today_sales.html', logs=[])
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/owner/all_products')
def all_products():
    if session.get('role') not in ['owner', 'super_admin']:
        return redirect(url_for('login'))
    
    branch_id = session.get('branch_id')
    if not branch_id and session.get('role') != 'super_admin':
        flash('No branch assigned')
        return redirect(url_for('login'))
    elif not branch_id and session.get('role') == 'super_admin':
        return redirect(url_for('super_admin_dashboard'))
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.id, p.product_name, p.description, p.cost_price, p.selling_price,
                   COALESCE(SUM(il.quantity_change), 0) as current_stock
            FROM products p
            LEFT JOIN inventory_logs il ON p.id = il.product_id
            WHERE p.branch_id = %s
            GROUP BY p.id, p.product_name, p.description, p.cost_price, p.selling_price
            ORDER BY p.product_name
        """, (branch_id,))
        products = cursor.fetchall()
        
        return render_template('all_products.html', products=products)
        
    except mysql.connector.Error as e:
        logger.error(f"All products database error: {e}")
        return render_template('all_products.html', products=[])
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/owner/weekly_sales')
def weekly_sales():
    if session.get('role') not in ['owner', 'super_admin']:
        return redirect(url_for('login'))
    
    branch_id = session.get('branch_id')
    if not branch_id and session.get('role') != 'super_admin':
        flash('No branch assigned')
        return redirect(url_for('login'))
    elif not branch_id and session.get('role') == 'super_admin':
        return redirect(url_for('super_admin_dashboard'))
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.product_name, il.quantity_change, 
                   CASE WHEN il.log_type = 'restock' THEN il.cost_price ELSE p.cost_price END as cost_price,
                   il.selling_price, il.recorded_by, il.timestamp
            FROM inventory_logs il
            JOIN products p ON il.product_id = p.id
            WHERE il.log_type = 'sale' AND il.timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY) AND p.branch_id = %s
            ORDER BY il.timestamp DESC
        """, (branch_id,))
        logs = cursor.fetchall()
        
        branch_name = get_branch_name(branch_id)
        
        return render_template('weekly_sales.html', logs=logs, branch_name=branch_name)
        
    except mysql.connector.Error as e:
        logger.error(f"Weekly sales database error: {e}")
        return render_template('weekly_sales.html', logs=[], branch_name="Unknown Branch")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/debug_session')
def debug_session():
    return render_template('debug_session.html')

@app.route('/toggle_theme', methods=['POST'])
def toggle_theme():
    if 'username' not in session:
        return jsonify({'success': False})
    
    current_theme = session.get('theme', 'light')
    new_theme = 'dark' if current_theme == 'light' else 'light'
    session['theme'] = new_theme
    
    # Update user preference in database
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET theme_preference = %s WHERE username = %s", 
                      (new_theme, session['username']))
        conn.commit()
        return jsonify({'success': True, 'theme': new_theme})
    except mysql.connector.Error as e:
        logger.error(f"Theme update error: {e}")
        return jsonify({'success': False})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/search')
def search():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    
    # Super admin can search all branches, others only their branch
    branch_filter = ""
    params = []
    
    if session.get('role') != 'super_admin':
        branch_id = session.get('branch_id')
        if not branch_id:
            return jsonify([])
        branch_filter = "AND p.branch_id = %s"
        params.append(branch_id)
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Search by ID or name
        if query.isdigit():
            cursor.execute(f"""
                SELECT p.id, p.product_name, p.description,
                       COALESCE(SUM(il.quantity_change), 0) as current_stock,
                       p.cost_price, p.selling_price
                FROM products p
                LEFT JOIN inventory_logs il ON p.id = il.product_id
                WHERE p.id = %s {branch_filter}
                GROUP BY p.id, p.product_name, p.description, p.cost_price, p.selling_price
            """, [int(query)] + params)
        else:
            cursor.execute(f"""
                SELECT p.id, p.product_name, p.description,
                       COALESCE(SUM(il.quantity_change), 0) as current_stock,
                       p.cost_price, p.selling_price
                FROM products p
                LEFT JOIN inventory_logs il ON p.id = il.product_id
                WHERE p.product_name LIKE %s {branch_filter}
                GROUP BY p.id, p.product_name, p.description, p.cost_price, p.selling_price
            """, [f'%{query}%'] + params)
        
        results = cursor.fetchall()
        
        # Convert to JSON format
        products = []
        for p in results:
            products.append({
                'id': p[0],
                'name': p[1],
                'description': p[2] or '',
                'stock': p[3],
                'cost': float(p[4]) if p[4] else 0.0,
                'price': float(p[5]) if p[5] else 0.0
            })
        
        return jsonify(products)
        
    except mysql.connector.Error as e:
        logger.error(f"Search database error: {e}")
        return jsonify([])
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/api/products')
def get_products_api():
    if session.get('role') not in ['owner', 'super_admin']:
        return jsonify([])
    
    branch_id = session.get('branch_id')
    if not branch_id:
        return jsonify([])
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.id, p.product_name, p.description,
                   COALESCE(SUM(il.quantity_change), 0) as current_stock
            FROM products p
            LEFT JOIN inventory_logs il ON p.id = il.product_id
            WHERE p.branch_id = %s
            GROUP BY p.id, p.product_name, p.description
            ORDER BY p.product_name
        """, (branch_id,))
        products = cursor.fetchall()
        
        return jsonify([{
            'id': p[0],
            'name': p[1],
            'description': p[2] or '',
            'stock': int(p[3])
        } for p in products])
        
    except mysql.connector.Error as e:
        logger.error(f"Get products API error: {e}")
        return jsonify([])
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/owner/monthly_sales')
def monthly_sales():
    if session.get('role') not in ['owner', 'super_admin']:
        return redirect(url_for('login'))
    
    branch_id = session.get('branch_id')
    if not branch_id and session.get('role') != 'super_admin':
        flash('No branch assigned')
        return redirect(url_for('login'))
    elif not branch_id and session.get('role') == 'super_admin':
        return redirect(url_for('super_admin_dashboard'))
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.product_name, il.quantity_change, 
                   CASE WHEN il.log_type = 'restock' THEN il.cost_price ELSE p.cost_price END as cost_price,
                   il.selling_price, il.recorded_by, il.timestamp
            FROM inventory_logs il
            JOIN products p ON il.product_id = p.id
            WHERE il.log_type = 'sale' AND MONTH(il.timestamp) = MONTH(NOW()) AND YEAR(il.timestamp) = YEAR(NOW()) AND p.branch_id = %s
            ORDER BY il.timestamp DESC
        """, (branch_id,))
        logs = cursor.fetchall()
        
        cursor.execute("""
            SELECT DATE(il.timestamp) as sale_date, 
                   SUM(ABS(il.quantity_change) * il.selling_price) as daily_sales
            FROM inventory_logs il
            JOIN products p ON il.product_id = p.id
            WHERE il.log_type = 'sale' AND il.timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY) AND p.branch_id = %s
            GROUP BY DATE(il.timestamp)
            ORDER BY sale_date
        """, (branch_id,))
        chart_data = cursor.fetchall()
        
        branch_name = get_branch_name(branch_id)
        
        return render_template('monthly_sales.html', logs=logs, chart_data=chart_data, branch_name=branch_name)
        
    except mysql.connector.Error as e:
        logger.error(f"Monthly sales database error: {e}")
        return render_template('monthly_sales.html', logs=[], chart_data=[], branch_name="Unknown Branch")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == '__main__':
    init_pool()
    init_db()
    
    print("\n" + "="*70)
    print("🚀 Flask Server Started!")
    print("="*70)
    print("\n📱 Local Access: http://localhost:5000")
    print("\n⚠️  Server is running...\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)