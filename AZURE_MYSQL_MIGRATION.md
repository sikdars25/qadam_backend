# 🚀 Azure MySQL Migration Guide

## Quick Start

Migrate your local MySQL database to Azure Database for MySQL Flexible Server in one command:

```bash
migrate_mysql_to_azure.bat
```

---

## What It Does

The script performs a complete migration:

1. ✅ **Exports** local `qadam_academic` database
2. ✅ **Tests** Azure MySQL connection
3. ✅ **Creates** fresh database in Azure
4. ✅ **Imports** all data to Azure
5. ✅ **Verifies** tables and row counts

---

## Prerequisites

- **Local MySQL:** `D:\MySQL\MySQL Server 8.0`
- **Azure MySQL Server:** `qadam-db.mysql.database.azure.com`
- **Credentials:** Azure username and password
- **Firewall:** Your IP must be allowed in Azure MySQL

---

## Usage

### Run Migration

```bash
migrate_mysql_to_azure.bat
```

### Enter When Prompted

**Local MySQL:**
- Username: `root`
- Password: [Your local password]

**Azure MySQL:**
- Hostname: `qadam-db.mysql.database.azure.com` (default)
- Username: `qaadmin` (default)
- Password: [Your Azure password]
- Database: `qadam_academic` (default)

---

## After Migration

### 1. Update .env File

```bash
MYSQL_HOST=qadam-db.mysql.database.azure.com
MYSQL_PORT=3306
MYSQL_USER=qaadmin
MYSQL_PASSWORD=your_azure_password
MYSQL_DATABASE=qadam_academic
```

### 2. Test Backend

```bash
python app.py
```

Should show: `✓ Connected to MySQL database`

### 3. Configure Azure Function App

```bash
configure_azure_function.bat
```

---

## Troubleshooting

### Connection Failed

**Check:**
- Azure MySQL firewall allows your IP
- Credentials are correct
- Internet connection is stable

**Solution:**
```bash
# Add your IP to firewall in Azure Portal
# MySQL Server → Networking → Add current client IP
```

### Import Failed

**Check:**
- Backup file was created successfully
- Azure MySQL has enough space
- Network is stable during import

**Solution:**
```bash
# Re-run the migration script
migrate_mysql_to_azure.bat
```

---

## Files

- **`migrate_mysql_to_azure.bat`** - Complete migration script
- **`configure_azure_function.bat`** - Configure Function App
- **`AZURE_MYSQL_MIGRATION.md`** - This guide

---

## Support

For detailed Azure deployment information, see:
- `AZURE_DEPLOYMENT_GUIDE.md`
- `README_LOCAL_DEV.md`

---

**Ready to migrate? Run:** `migrate_mysql_to_azure.bat` 🚀
