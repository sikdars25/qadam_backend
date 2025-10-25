# 🏠 Local Development Setup

## Quick Start Guide for Running Backend Locally

This guide helps you run the backend on your local machine with MySQL database.

---

## ✅ Prerequisites

- ✅ Python 3.8 or higher installed
- ✅ MySQL installed (XAMPP or MySQL Server)
- ✅ Git (optional, for cloning)

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Install MySQL

**Option A: XAMPP (Easiest)**
1. Download from: https://www.apachefriends.org/
2. Install with default settings
3. Open XAMPP Control Panel
4. Click "Start" next to MySQL

**Option B: MySQL Server**
1. Download from: https://dev.mysql.com/downloads/mysql/
2. Install and set root password
3. Start MySQL service

### Step 2: Set Up Backend

```bash
# Navigate to backend folder
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file from example
copy .env.example .env

# Edit .env file and add your Groq API key
# For XAMPP with no password, you can leave MySQL settings as defaults
```

### Step 3: Initialize Database

```bash
# Test MySQL connection
python test_mysql_connection.py

# Initialize database tables
python database.py
```

### Step 4: Start Backend

```bash
# Start Flask server
python app.py
```

**Or use the quick start script:**
```bash
start_local.bat
```

---

## 📝 Configuration

### Minimal .env for Local Development (XAMPP)

```bash
# Groq API Key (Required)
GROQ_API_KEY=your_groq_api_key_here

# Frontend URL (for CORS)
FRONTEND_URL=http://localhost:3000

# Secret Key
SECRET_KEY=dev-secret-key

# MySQL uses defaults (localhost, root, no password)
# No need to specify MYSQL_* variables!
```

### Full .env for Local Development (MySQL with password)

```bash
# Groq API Key (Required)
GROQ_API_KEY=your_groq_api_key_here

# Frontend URL (for CORS)
FRONTEND_URL=http://localhost:3000

# Secret Key
SECRET_KEY=dev-secret-key

# MySQL Configuration
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=qadam_academic

# Email (Optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password
```

---

## 🔧 Backend Code Configuration

### Already Configured for Local Development ✓

The backend code is **already set up** to work with local MySQL:

**db_config.py:**
```python
MYSQL_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),      # ✓ Default: localhost
    'port': int(os.getenv('MYSQL_PORT', 3306)),        # ✓ Default: 3306
    'user': os.getenv('MYSQL_USER', 'root'),           # ✓ Default: root
    'password': os.getenv('MYSQL_PASSWORD', ''),       # ✓ Default: empty
    'database': os.getenv('MYSQL_DATABASE', 'qadam_academic'),  # ✓ Default: qadam_academic
}
```

**What this means:**
- ✅ Works with default XAMPP installation (no configuration needed)
- ✅ Works with MySQL Server (just set password in .env)
- ✅ Automatically uses localhost if no .env variables set
- ✅ **No code changes needed!**

---

## 🧪 Testing

### Test MySQL Connection

```bash
python test_mysql_connection.py
```

**Expected Output:**
```
✅ Connected to MySQL database!
ℹ️  MySQL Version: 8.0.30
ℹ️  Current Database: qadam_academic
✅ Found 5 tables in database:
  📋 users
  📋 uploaded_papers
  📋 textbooks
  📋 parsed_questions
  📋 sample_questions
```

### Test Backend API

```bash
# Start backend
python app.py

# In another terminal or browser, test:
curl http://localhost:5000/api/health

# Expected response:
# {"status": "healthy", "message": "Backend is running"}
```

---

## 🔍 Troubleshooting

### Issue: "Can't connect to MySQL server"

**Solution:**
1. Check if MySQL is running:
   - XAMPP: Open Control Panel, click "Start" for MySQL
   - MySQL Service: Run `net start MySQL80`
2. Check if port 3306 is free: `netstat -ano | findstr :3306`

### Issue: "Access denied for user 'root'"

**Solution:**
1. For XAMPP: Default has no password, leave `MYSQL_PASSWORD` empty
2. For MySQL Server: Set correct password in `.env` file

### Issue: "Unknown database 'qadam_academic'"

**Solution:**
```bash
# Create database manually
mysql -u root -p
CREATE DATABASE qadam_academic;
exit;

# Or run database.py
python database.py
```

### Issue: "mysql.connector module not found"

**Solution:**
```bash
pip install mysql-connector-python
# Or
pip install -r requirements.txt
```

---

## 📂 Project Structure

```
backend/
├── app.py                      # Main Flask application
├── database.py                 # Database initialization
├── db_config.py               # Database configuration
├── test_mysql_connection.py   # Connection test script
├── start_local.bat            # Quick start script
├── .env                       # Environment variables (create from .env.example)
├── .env.example               # Environment variables template
├── requirements.txt           # Python dependencies
└── README_LOCAL_DEV.md        # This file
```

---

## 🎯 Development Workflow

### Daily Development

```bash
# 1. Start MySQL (if not running)
# XAMPP: Open Control Panel → Start MySQL

# 2. Activate virtual environment
venv\Scripts\activate

# 3. Start backend
python app.py

# 4. In another terminal, start frontend
cd ..\frontend
npm start
```

### Quick Start Script

```bash
# Use the automated script
start_local.bat

# This will:
# - Activate virtual environment
# - Test MySQL connection
# - Initialize database if needed
# - Start Flask backend
```

---

## 🔄 Switching Between Local and Azure

The backend automatically detects the environment based on `.env` variables:

**Local Development:**
```bash
# .env
MYSQL_HOST=localhost
# Uses local MySQL
```

**Azure Production:**
```bash
# Azure Function App Configuration
MYSQL_HOST=qadam-mysql-server.mysql.database.azure.com
# Uses Azure MySQL
```

**No code changes needed!** Just update environment variables.

---

## 📚 Useful Commands

### Database Management

```bash
# Initialize database
python database.py

# Test connection
python test_mysql_connection.py

# Access MySQL command line
mysql -u root -p

# Backup database
mysqldump -u root -p qadam_academic > backup.sql

# Restore database
mysql -u root -p qadam_academic < backup.sql
```

### Backend Management

```bash
# Start backend
python app.py

# Start with debug mode
python app.py --debug

# Check Python version
python --version

# List installed packages
pip list

# Update dependencies
pip install -r requirements.txt --upgrade
```

---

## 🎓 Learning Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [MySQL Documentation](https://dev.mysql.com/doc/)
- [XAMPP Guide](https://www.apachefriends.org/docs/)
- [Python Virtual Environments](https://docs.python.org/3/tutorial/venv.html)

---

## ✅ Checklist

Before starting development, ensure:

- [ ] MySQL installed and running
- [ ] Python 3.8+ installed
- [ ] Virtual environment created (`python -m venv venv`)
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created and configured
- [ ] Database initialized (`python database.py`)
- [ ] Connection test passes (`python test_mysql_connection.py`)
- [ ] Backend starts successfully (`python app.py`)

---

## 🆘 Need Help?

1. **Check logs:** Backend prints detailed error messages
2. **Test connection:** Run `python test_mysql_connection.py`
3. **Check MySQL:** Verify MySQL is running in XAMPP/Services
4. **Review .env:** Ensure all required variables are set
5. **Check documentation:** See `LOCAL_MYSQL_SETUP.md` for detailed guide

---

**Happy Coding! 🚀**
