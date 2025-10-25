import sqlite3
import os
from werkzeug.security import generate_password_hash

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'qadam.db')

def create_admin():
    """Create admin user and add is_admin column"""
    print("=" * 50)
    print("Creating Admin User")
    print("=" * 50)
    print()
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Check if users table exists, create if not
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✓ Users table ready")
    
    # Add email column if it doesn't exist
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN email TEXT')
        print("✓ Added email column to users table")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e).lower():
            print("• email column already exists")
    
    # Add phone column if it doesn't exist
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN phone TEXT')
        print("✓ Added phone column to users table")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e).lower():
            print("• phone column already exists")
    
    # Add is_active column if it doesn't exist
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1')
        print("✓ Added is_active column to users table")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e).lower():
            print("• is_active column already exists")
    
    # Add activation_token column if it doesn't exist
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN activation_token TEXT')
        print("✓ Added activation_token column to users table")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e).lower():
            print("• activation_token column already exists")
    
    # Add is_admin column if it doesn't exist
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0')
        print("✓ Added is_admin column to users table")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e).lower():
            print("• is_admin column already exists")
        else:
            print(f"✗ Error adding is_admin column: {e}")
    
    conn.commit()
    
    # Admin credentials
    admin_email = 'sikdar.moving@gmail.com'
    admin_username = 'admin'
    admin_password = 'admin123'  # Change this after first login!
    admin_full_name = 'System Administrator'
    
    # Check if admin already exists
    existing_admin = cursor.execute(
        'SELECT id FROM users WHERE email = ? OR username = ?',
        (admin_email, admin_username)
    ).fetchone()
    
    if existing_admin:
        # Update existing user to admin
        cursor.execute(
            'UPDATE users SET is_admin = 1, is_active = 1 WHERE email = ? OR username = ?',
            (admin_email, admin_username)
        )
        print(f"✓ Updated existing user to admin: {admin_username}")
    else:
        # Create new admin user
        hashed_password = generate_password_hash(admin_password)
        cursor.execute(
            '''INSERT INTO users (username, password, full_name, email, is_active, is_admin, activation_token) 
               VALUES (?, ?, ?, ?, 1, 1, NULL)''',
            (admin_username, hashed_password, admin_full_name, admin_email)
        )
        print(f"✓ Created new admin user: {admin_username}")
    
    conn.commit()
    
    # Display current schema
    print()
    print("Current users table schema:")
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
    
    conn.close()
    
    print()
    print("=" * 50)
    print("Admin User Created!")
    print("=" * 50)
    print()
    print("Admin Login Credentials:")
    print(f"  Email: {admin_email}")
    print(f"  Username: {admin_username}")
    print(f"  Password: {admin_password}")
    print()
    print("⚠️  IMPORTANT: Change the admin password after first login!")
    print()

if __name__ == '__main__':
    create_admin()
