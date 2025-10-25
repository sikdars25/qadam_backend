import mysql.connector
from mysql.connector import Error
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# MySQL configuration
MYSQL_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', ''),
    'database': os.getenv('MYSQL_DATABASE', 'qadam_academic'),
}

def init_db():
    """Initialize the MySQL database with required tables"""
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        print("✓ Connected to MySQL database")
    except Error as e:
        print(f"❌ Error connecting to MySQL: {e}")
        return
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            full_name VARCHAR(255) NOT NULL,
            email VARCHAR(255),
            phone VARCHAR(20) UNIQUE,
            is_active BOOLEAN DEFAULT TRUE,
            is_admin BOOLEAN DEFAULT FALSE,
            activation_token VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✓ Users table ready")
    
    # Sample questions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sample_questions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            subject VARCHAR(100) NOT NULL,
            question TEXT NOT NULL,
            answer TEXT,
            difficulty VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✓ Sample questions table ready")
    
    # Uploaded papers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uploaded_papers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            subject VARCHAR(100) NOT NULL,
            file_path VARCHAR(500) NOT NULL,
            user_id INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        )
    ''')
    print("✓ Uploaded papers table ready")
    
    # Textbooks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS textbooks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            subject VARCHAR(100) NOT NULL,
            file_path VARCHAR(500) NOT NULL,
            user_id INT,
            chapters_extracted BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        )
    ''')
    print("✓ Textbooks table ready")
    
    # Parsed questions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parsed_questions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            paper_id INT NOT NULL,
            question_number VARCHAR(50) NOT NULL,
            question_text TEXT NOT NULL,
            question_type VARCHAR(50),
            marks INT,
            subject VARCHAR(100),
            has_diagram BOOLEAN DEFAULT FALSE,
            diagram_description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (paper_id) REFERENCES uploaded_papers (id) ON DELETE CASCADE
        )
    ''')
    print("✓ Parsed questions table ready")
    
    # AI Search Results table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_search_results (
            id INT AUTO_INCREMENT PRIMARY KEY,
            paper_id INT NOT NULL,
            textbook_id INT NOT NULL,
            search_results JSON NOT NULL,
            total_chapters INT,
            total_questions INT,
            unmatched_count INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (paper_id) REFERENCES uploaded_papers (id) ON DELETE CASCADE,
            FOREIGN KEY (textbook_id) REFERENCES textbooks (id) ON DELETE CASCADE
        )
    ''')
    print("✓ AI search results table ready")
    
    # Question Bank table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS question_bank (
            id INT AUTO_INCREMENT PRIMARY KEY,
            question_text TEXT NOT NULL,
            solution TEXT NOT NULL,
            source VARCHAR(100),
            subject VARCHAR(100),
            paper_id INT,
            textbook_id INT,
            chapter_name VARCHAR(255),
            user_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (paper_id) REFERENCES uploaded_papers(id) ON DELETE SET NULL,
            FOREIGN KEY (textbook_id) REFERENCES textbooks(id) ON DELETE SET NULL
        )
    ''')
    print("✓ Question bank table ready")
    
    # Usage logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            action_type VARCHAR(100) NOT NULL,
            tokens_used INT DEFAULT 0,
            model_name VARCHAR(100),
            question_id INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    print("✓ Usage logs table ready")
    
    # Note: Default users and sample questions should be migrated from SQLite
    # Run: python migrate_users_only.py and python migrate_sample_questions_only.py
    
    conn.commit()
    cursor.close()
    conn.close()
    print("\n✅ MySQL database initialized successfully!")
    print("💡 Run migration scripts to import data from SQLite if needed")

def get_db_connection():
    """Get a MySQL database connection"""
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        return conn
    except Error as e:
        print(f"❌ Error connecting to MySQL: {e}")
        raise

if __name__ == '__main__':
    init_db()
