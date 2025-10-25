"""
Database Configuration Module
Configured for MySQL database only
"""
import mysql.connector
from mysql.connector import Error
import os
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

def get_db_connection():
    """
    Get MySQL database connection
    Returns a connection object
    """
    try:
        conn = mysql.connector.connect(
            host=MYSQL_CONFIG['host'],
            port=MYSQL_CONFIG['port'],
            user=MYSQL_CONFIG['user'],
            password=MYSQL_CONFIG['password'],
            database=MYSQL_CONFIG['database']
        )
        
        if conn.is_connected():
            return conn
        else:
            raise Error("Failed to connect to MySQL database")
            
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        raise

def execute_query(query, params=None, fetch=False):
    """
    Execute a query with automatic connection handling
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch:
            result = cursor.fetchall()
            cursor.close()
            conn.close()
            return result
        else:
            conn.commit()
            last_id = cursor.lastrowid
            cursor.close()
            conn.close()
            return last_id
            
    except Exception as e:
        cursor.close()
        conn.close()
        raise e

def get_placeholder():
    """
    Get the correct placeholder for MySQL
    MySQL uses %s
    """
    return '%s'

def convert_query(query):
    """
    Convert SQLite query syntax (?) to MySQL syntax (%s)
    """
    return query.replace('?', '%s')
