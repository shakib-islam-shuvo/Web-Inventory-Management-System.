# Trust-Verification Inventory & Sales Tracking System

A secure, self-hosted web application for multi-branch inventory management with role-based access control.

## 🌟 Features

### Super Admin:
- Manage multiple branches
- Create new branches with auto-generated accounts
- View consolidated sales data across all branches
- Manage user accounts and credentials

### Owner (Branch Manager):
- Complete dashboard with sales statistics and inventory value
- Add new products with initial stock
- Restock existing products
- Update product prices
- View all transaction logs with timestamps
- Low stock alerts
- Daily, weekly, and monthly sales reports

### Salesman:
- Record sales with automatic stock deduction
- View current stock levels
- Generate printable receipts
- Apply discounts

### Assistant:
- Simple interface for basic operations
- Record sales
- View stock levels (no financial data)

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Setup Database
- Install MySQL Server or XAMPP
- Start MySQL service
- Create database named `first` (or update in .env)

### 3. Configure Environment
```bash
cp .env.example .env
```
Edit `.env` with your database credentials.

### 4. Run Application

**Option A: Simple (Local only)**
```bash
python app.py
```
Access at: `http://localhost:5000`

**Option B: With ngrok (Internet access)**
```bash
python launch.py
```
This will:
- Start Flask server
- Start ngrok tunnel automatically
- Display public URL in terminal

## 🔐 Default Login Credentials

### Super Admin (Access all branches)
- Username: `super_admin`
- Password: `super123`

### Branch 1 - Bashundhara
- Owner: `owner1` / `admin123`
- Salesman: `salesman1` / `sales123`

### Branch 2 - Dhanmondi
- Owner: `owner2` / `admin223`
- Salesman: `salesman2` / `sales223`

### Branch 3 - Mirpur
- Owner: `owner3` / `admin323`
- Salesman: `salesman3` / `sales323`

## 📁 Project Structure

```
Chatbot/
├── app.py                    # Main application
├── launch.py                 # Launcher with ngrok support
├── requirements.txt          # Python dependencies
├── .env.example             # Environment variables template
├── README.md                # This file
├── check_users.py           # Database user checker
├── setup_database.py        # Database setup helper
├── setup_database.sql       # SQL initialization script
├── static/
│   ├── logo.png            # Application logo
│   └── theme.css           # Styling
└── templates/              # HTML templates
    ├── base.html
    ├── login.html
    ├── super_admin_dashboard.html
    ├── owner_dashboard.html
    ├── salesman_dashboard.html
    └── ... (other templates)
```

## 🌐 Access from Different Networks

### Method 1: ngrok (Recommended)
1. Install ngrok: https://ngrok.com/download
2. Authenticate: `ngrok config add-authtoken YOUR_TOKEN`
3. Run: `python launch.py`
4. Share the public URL displayed in terminal

### Method 2: Manual
**Terminal 1:**
```bash
python app.py
```

**Terminal 2:**
```bash
grok http 5000
```
Copy the `https://` URL from ngrok.

## 🔧 Database Configuration

Update `.env` file:
```env
DB_HOST=127.0.0.1
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=first
SECRET_KEY=your-secret-key-change-this
```

## 🛡️ Security Features

- Session-based authentication
- Password hashing with Werkzeug
- Role-based access control (RBAC)
- Branch isolation (users can only access their branch)
- Immutable transaction logs
- Stock validation for sales
- SQL injection protection

## 📊 Database Schema

### branches
- id, branch_name, location

### users
- id, username, password_hash, role, branch_id, theme_preference

### products
- id, product_name, description, cost_price, selling_price, branch_id

### inventory_logs
- id, product_id, quantity_change, cost_price, selling_price, log_type, recorded_by, branch_id, timestamp

## 🎯 Usage

### For Super Admin:
1. Login with super admin credentials
2. View all branches performance
3. Create new branches
4. Manage user accounts
5. Access any branch dashboard

### For Owners:
1. Login with owner credentials
2. Add products and initial stock
3. Monitor sales and inventory
4. View detailed transaction logs
5. Update prices and restock
6. Generate sales reports

### For Salesmen:
1. Login with salesman credentials
2. Select products and quantities
3. Apply discounts if needed
4. Generate receipts
5. Check stock availability

## 🔍 Utility Scripts

**Check database users:**
```bash
python check_users.py
```

**Setup database:**
```bash
python setup_database.py
```

## ⚠️ Important Notes

- All transactions are logged with timestamps and user information
- Stock levels are calculated in real-time from transaction logs
- Low stock alerts appear when quantity < 10 units
- The system prevents overselling by validating stock before sales
- Branch data is isolated - users can only see their branch data
- Super admin can view all branches but owners/salesmen are restricted

## 🤝 Contributing

Feel free to fork this project and submit pull requests!

## 📝 License

MIT License - feel free to use for personal or commercial projects.

## 🐛 Troubleshooting

### MySQL Connection Error
- Ensure MySQL/XAMPP is running
- Check database credentials in `.env`
- Verify database `first` exists

### ngrok URL not showing
- Open `http://localhost:4040` in browser
- Manually run: `ngrok http 5000`
- Check if ngrok is authenticated

### Port 5000 already in use
- Close other Flask applications
- Change port in `app.py` and `launch.py`

## 📧 Support

For issues and questions, please open a GitHub issue.