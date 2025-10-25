# 🔧 Fix: Admin Login "Failed to load users" Error

## Problem

When logging into the admin dashboard, you see:
```
Failed to load users
```

## Root Cause

The backend is trying to connect to a database that doesn't have the `users` table. This happens because:

1. ✅ Backend is running
2. ❌ Database connection works BUT tables don't exist
3. ❌ Query fails: `SELECT * FROM users` → Table doesn't exist

---

## ✅ Solution: Complete Migration to Azure

### Step 1: Run the Migration Script

```bash
migrate_mysql_to_azure.bat
```

**Enter when prompted:**
- Local MySQL username: `root`
- Local MySQL password: [your local password]
- Azure hostname: `qadam-db.mysql.database.azure.com`
- Azure username: `qaadmin`
- Azure password: `Academic@2025`
- Database name: `qadam_academic`

**This will:**
- Export local database with all tables
- Create fresh database in Azure
- Import all tables and data
- Verify migration succeeded

---

### Step 2: Update .env File

After successful migration, update your `.env` file:

```bash
# Azure MySQL Configuration
MYSQL_HOST=qadam-db.mysql.database.azure.com
MYSQL_PORT=3306
MYSQL_USER=qaadmin
MYSQL_PASSWORD=Academic@2025
MYSQL_DATABASE=qadam_academic
```

**Important:** Change `MYSQL_HOST` from `localhost` to Azure hostname!

---

### Step 3: Restart Backend

```bash
# Stop current backend (Ctrl+C)

# Start backend again
python app.py
```

**Expected output:**
```
✓ Connected to MySQL database
* Running on http://127.0.0.1:5000
```

---

### Step 4: Test Admin Login

1. Open browser: `http://localhost:3000`
2. Login with admin credentials
3. Go to User Management
4. Should now load users successfully!

---

## 🔍 Verify Migration

Before updating `.env`, verify tables exist in Azure:

```bash
"D:\MySQL\MySQL Server 8.0\bin\mysql.exe" ^
  -h qadam-db.mysql.database.azure.com ^
  -u qaadmin ^
  -pAcademic@2025 ^
  qadam_academic ^
  -e "SHOW TABLES;"
```

**Expected output:**
```
+---------------------------+
| Tables_in_qadam_academic  |
+---------------------------+
| ai_search_results         |
| parsed_questions          |
| question_bank             |
| sample_questions          |
| textbooks                 |
| uploaded_papers           |
| usage_logs                |
| users                     | ← This table is needed!
+---------------------------+
```

---

## 🎯 Quick Fix Steps

```bash
# 1. Migrate database
migrate_mysql_to_azure.bat

# 2. Update .env file
# Change MYSQL_HOST=localhost to MYSQL_HOST=qadam-db.mysql.database.azure.com

# 3. Restart backend
python app.py

# 4. Refresh admin page
# Should now work!
```

---

## 🆘 Alternative: Use Local Database

If you want to use local MySQL instead of Azure:

### Verify .env is set to localhost:

```bash
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_local_password
MYSQL_DATABASE=qadam_academic
```

### Verify local database has tables:

```bash
"D:\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p qadam_academic -e "SHOW TABLES;"
```

### Restart backend:

```bash
python app.py
```

---

## 📋 Checklist

- [ ] Run `migrate_mysql_to_azure.bat`
- [ ] Verify tables exist in Azure
- [ ] Update `.env` file with Azure credentials
- [ ] Restart backend (`python app.py`)
- [ ] Test admin login
- [ ] User management page loads successfully

---

## 💡 Why This Happened

Your `.env` file configuration determines which database the backend connects to:

**Current (not working):**
```
MYSQL_HOST=localhost  ← Points to local MySQL
```

**But:** Local MySQL might not have tables, or you want to use Azure.

**Solution:** Either:
1. Use Azure MySQL (recommended) - Update `.env` to Azure
2. Use Local MySQL - Ensure local database has tables

---

## 🎯 Recommended Action

**Use Azure MySQL:**

1. Run migration: `migrate_mysql_to_azure.bat`
2. Update `.env` to Azure
3. Restart backend
4. Admin login will work!

---

**After migration, your admin dashboard will load users successfully!** 🚀
