"""
Quick Database Connection Checker
Checks which database the backend is connecting to and if tables exist
"""

import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

print("=" * 60)
print("Database Connection Checker")
print("=" * 60)
print()

# Get configuration from .env
host = os.getenv('MYSQL_HOST', 'localhost')
port = int(os.getenv('MYSQL_PORT', 3306))
user = os.getenv('MYSQL_USER', 'root')
password = os.getenv('MYSQL_PASSWORD', '')
database = os.getenv('MYSQL_DATABASE', 'qadam_academic')

print("Configuration from .env:")
print(f"  Host: {host}")
print(f"  Port: {port}")
print(f"  User: {user}")
print(f"  Database: {database}")
print()

# Determine if local or Azure
if 'azure' in host.lower() or 'qadam-db' in host.lower():
    print("Target: AZURE MySQL")
else:
    print("Target: LOCAL MySQL")
print()

# Try to connect
try:
    print("Connecting...")
    conn = mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database
    )
    
    if conn.is_connected():
        print("SUCCESS: Connected to database!")
        print()
        
        cursor = conn.cursor()
        
        # Get MySQL version
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()[0]
        print(f"MySQL Version: {version}")
        print()
        
        # Check tables
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        if tables:
            print(f"SUCCESS: Found {len(tables)} table(s):")
            print()
            for table in tables:
                table_name = table[0]
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
                count = cursor.fetchone()[0]
                print(f"  - {table_name}: {count} rows")
            print()
            print("Database is ready!")
            print("Admin login should work.")
        else:
            print("ERROR: No tables found!")
            print()
            print("This is why admin login fails.")
            print()
            print("Solution:")
            print("  1. Run: migrate_mysql_to_azure.bat")
            print("  2. Update .env with Azure credentials")
            print("  3. Restart backend: python app.py")
        
        cursor.close()
        conn.close()
        
except mysql.connector.Error as e:
    print(f"ERROR: {e}")
    print()
    if "Access denied" in str(e):
        print("Wrong username or password in .env file")
    elif "Unknown database" in str(e):
        print(f"Database '{database}' does not exist")
        print()
        print("Solution:")
        print("  1. Run: migrate_mysql_to_azure.bat")
    elif "Can't connect" in str(e):
        print("Cannot connect to database server")
        print()
        print("Check:")
        print("  1. MySQL server is running")
        print("  2. Host/port are correct in .env")
        print("  3. Firewall allows connection (if Azure)")

print()
print("=" * 60)
