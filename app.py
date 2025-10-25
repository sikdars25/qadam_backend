from flask import Flask, request, jsonify, send_file, session
from flask_cors import CORS
from database import init_db, get_db_connection
from db_config import convert_query
import os
import json
import mysql.connector
from mysql.connector import Error as MySQLError
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from datetime import datetime

# Try to import AI service, but don't fail if dependencies aren't installed yet
try:
    from ai_service import (
        analyze_question_paper,
        generate_solution,
        extract_chapters_from_textbook,
        map_questions_to_chapters,
        solve_question_with_llm
    )
    AI_ENABLED = True
except ImportError as e:
    print(f"AI features disabled: {e}")
    print("Install AI dependencies: pip install -r requirements-ai.txt")
    print("Or run: install_all_ai.bat")
    AI_ENABLED = False
except Exception as e:
    print(f"AI features disabled due to error: {e}")
    import traceback
    traceback.print_exc()
    AI_ENABLED = False

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here-change-in-production')

# CORS Configuration for Azure
# Get frontend URL from environment variable
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')

ALLOWED_ORIGINS = [
    'https://nice-plant-017975e1e.3.azurestaticapps.net',
    FRONTEND_URL,  # Azure Static Web App (production)
    'http://localhost:3000',  # Local React development
    'http://localhost:5000',  # Local Flask testing
    'http://127.0.0.1:3000',  # Alternative localhost
    'http://127.0.0.1:5000',  # Alternative localhost
]

# Configure CORS with specific settings for Azure
CORS(app, 
     origins=ALLOWED_ORIGINS,
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization', 'X-Requested-With'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
     expose_headers=['Content-Type', 'Authorization'])


# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize database
init_db()

@app.route('/api/login', methods=['POST'])
def login():
    """Login endpoint"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get user by username first
    try:
        cursor.execute(
            'SELECT id, username, password, full_name, is_active, is_admin FROM users WHERE username = %s',
            (username,)
        )
        user = cursor.fetchone()
    except MySQLError:
        # Fallback for older schema without is_active/is_admin
        cursor.execute(
            'SELECT id, username, password, full_name FROM users WHERE username = %s',
            (username,)
        )
        user = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    # Debug logging
    print(f"🔍 Login attempt: username={username}")
    
    # Verify password
    if not user:
        print(f"❌ User not found: {username}")
        return jsonify({'error': 'Invalid credentials'}), 401
    
    print(f"✓ User found: {user['username']}")
    stored_password = user['password']
    print(f"🔑 Password type: {'hashed' if stored_password.startswith(('pbkdf2:', 'scrypt:', '$2b$', '$2a$', '$2y$')) else 'plain'}")
    
    # Check if password is hashed (starts with pbkdf2, scrypt, or bcrypt)
    if stored_password.startswith(('pbkdf2:', 'scrypt:', '$2b$', '$2a$', '$2y$')):
        # Hashed password - use check_password_hash
        if not check_password_hash(stored_password, password):
            print(f"❌ Hashed password verification failed")
            return jsonify({'error': 'Invalid credentials'}), 401
        print(f"✅ Hashed password verified")
    else:
        # Plain text password (old users) - direct comparison
        if stored_password != password:
            print(f"❌ Plain text password mismatch")
            return jsonify({'error': 'Invalid credentials'}), 401
        print(f"✅ Plain text password matched")
    
    if user:
        # Check if account is activated (if column exists)
        if 'is_active' in user.keys() and not user['is_active']:
            return jsonify({'error': 'Please activate your account. Check your email for activation link.'}), 403
        
        # Set session for authenticated user
        session['user_id'] = user['id']
        session['username'] = user['username']
        
        # Check if user is admin
        is_admin = user['is_admin'] if 'is_admin' in user.keys() else 0
        
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'full_name': user['full_name'],
                'is_admin': bool(is_admin)
            }
        })
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout endpoint"""
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

# OTP storage (in-memory for demo - use Redis in production)
otp_storage = {}

@app.route('/api/send-otp', methods=['POST'])
def send_otp():
    """Send OTP to phone number"""
    import random
    data = request.get_json()
    phone = data.get('phone')
    
    if not phone or len(phone) != 10:
        return jsonify({'error': 'Valid 10-digit phone number required'}), 400
    
    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))
    
    # Store OTP with timestamp (for expiry check)
    from datetime import datetime, timedelta
    otp_storage[phone] = {
        'otp': otp,
        'expires_at': datetime.now() + timedelta(minutes=5)
    }
    
    # Try to send SMS for Indian numbers
    sms_sent = False
    try:
        # For Indian numbers, try SMS gateway
        if phone.startswith(('6', '7', '8', '9')):  # Indian mobile numbers
            sms_sent = send_sms_india(phone, otp)
    except Exception as e:
        print(f"SMS sending failed: {e}")
    
    # Always print to console for demo/testing
    print(f"📱 OTP for +91-{phone}: {otp}")
    
    return jsonify({
        'success': True,
        'message': f'OTP sent successfully{" via SMS" if sms_sent else " (check console)"}',
        'otp': otp,  # For demo - shows OTP in response
        'sms_sent': sms_sent
    })

def send_sms_india(phone, otp):
    """Send SMS to Indian phone number using SMS gateway"""
    # Option 1: Fast2SMS (Free tier available)
    # Option 2: MSG91
    # Option 3: Twilio
    
    # For now, using Fast2SMS (requires API key)
    import os
    api_key = os.getenv('FAST2SMS_API_KEY', '')
    
    if not api_key:
        print("⚠️  No SMS API key configured. Set FAST2SMS_API_KEY in .env")
        return False
    
    try:
        import requests
        url = "https://www.fast2sms.com/dev/bulkV2"
        
        payload = {
            "route": "v3",
            "sender_id": "QADAM",
            "message": f"Your QAdam verification code is: {otp}. Valid for 5 minutes.",
            "language": "english",
            "flash": 0,
            "numbers": phone
        }
        
        headers = {
            'authorization': api_key,
            'Content-Type': "application/x-www-form-urlencoded",
            'Cache-Control': "no-cache"
        }
        
        response = requests.post(url, data=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('return'):
                print(f"✅ SMS sent successfully to +91-{phone}")
                return True
        
        print(f"⚠️  SMS sending failed: {response.text}")
        return False
        
    except Exception as e:
        print(f"❌ SMS error: {e}")
        return False

@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    """Verify OTP for phone number"""
    from datetime import datetime
    data = request.get_json()
    phone = data.get('phone')
    otp = data.get('otp')
    
    if not phone or not otp:
        return jsonify({'error': 'Phone and OTP required'}), 400
    
    stored_data = otp_storage.get(phone)
    
    if not stored_data:
        return jsonify({'error': 'OTP expired or not found'}), 400
    
    # Check if OTP is expired
    if datetime.now() > stored_data['expires_at']:
        otp_storage.pop(phone, None)
        return jsonify({'error': 'OTP has expired. Please request a new one.'}), 400
    
    if stored_data['otp'] == otp:
        # OTP verified successfully - don't delete yet, might be needed for login
        return jsonify({'success': True, 'message': 'Phone verified successfully'})
    else:
        return jsonify({'error': 'Invalid OTP'}), 401

@app.route('/api/login-otp', methods=['POST'])
def login_otp():
    """Login with phone and OTP"""
    from datetime import datetime
    data = request.get_json()
    phone = data.get('phone')
    otp = data.get('otp')
    
    if not phone or not otp:
        return jsonify({'error': 'Phone and OTP required'}), 400
    
    # Verify OTP
    stored_data = otp_storage.get(phone)
    if not stored_data:
        return jsonify({'error': 'OTP expired or not found'}), 401
    
    # Check expiry
    if datetime.now() > stored_data['expires_at']:
        otp_storage.pop(phone, None)
        return jsonify({'error': 'OTP has expired'}), 401
    
    if stored_data['otp'] != otp:
        return jsonify({'error': 'Invalid OTP'}), 401
    
    # Find user by phone
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        'SELECT id, username, full_name FROM users WHERE phone = %s',
        (phone,)
    )
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if user:
        # Clear OTP after successful login
        otp_storage.pop(phone, None)
        
        # Set session
        session['user_id'] = user['id']
        session['username'] = user['username']
        
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'full_name': user['full_name']
            }
        })
    else:
        return jsonify({'error': 'No account found with this phone number'}), 404

@app.route('/api/register', methods=['POST'])
def register():
    """Register new user"""
    data = request.get_json()
    full_name = data.get('fullName')
    username = data.get('username')
    email = data.get('email')
    phone = data.get('phone')
    password = data.get('password')
    
    # Validate required fields (phone is optional)
    if not all([full_name, username, email, password]):
        return jsonify({'error': 'Full name, username, email, and password are required'}), 400
    
    # Validate email format
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return jsonify({'error': 'Invalid email address'}), 400
    
    # Validate phone if provided
    if phone and len(phone) != 10:
        return jsonify({'error': 'Valid 10-digit phone number required'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Check if username already exists
    cursor.execute(
        'SELECT id FROM users WHERE username = %s',
        (username,)
    )
    existing_user = cursor.fetchone()
    
    if existing_user:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Username already exists'}), 409
    
    # Check if email already exists
    cursor.execute(
        'SELECT id FROM users WHERE email = %s',
        (email,)
    )
    existing_email = cursor.fetchone()
    
    if existing_email:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Email already registered'}), 409
    
    # Check if phone already exists (only if phone is provided)
    if phone:
        cursor.execute(
            'SELECT id FROM users WHERE phone = %s',
            (phone,)
        )
        existing_phone = cursor.fetchone()
        
        if existing_phone:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Phone number already registered'}), 409
    
    # Generate activation token
    import secrets
    activation_token = secrets.token_urlsafe(32)
    
    # Insert new user (inactive by default)
    try:
        # Try with email and phone columns
        try:
            cursor.execute(
                '''INSERT INTO users (username, password, full_name, email, phone, is_active, activation_token) 
                   VALUES (%s, %s, %s, %s, %s, 0, %s)''',
                (username, password, full_name, email, phone, activation_token)
            )
        except Exception as db_error:
            # Fallback for older database schema
            if 'no column named' in str(db_error).lower():
                print("Using fallback insert (older schema)")
                cursor.execute(
                    'INSERT INTO users (username, password, full_name) VALUES (%s, %s, %s)',
                    (username, password, full_name)
                )
                activation_token = None  # No activation for old schema
            else:
                raise db_error
        
        conn.commit()
        user_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        # Send activation email
        if activation_token:
            activation_sent, activation_link = send_activation_email(email, full_name, activation_token)
            
            if not activation_sent:
                # Email not configured - return activation link in response
                return jsonify({
                    'success': True,
                    'message': 'Registration successful! Email not configured.',
                    'activation_required': True,
                    'activation_link': activation_link,
                    'user': {
                        'id': user_id,
                        'username': username,
                        'full_name': full_name,
                        'email': email
                    }
                })
            else:
                # Email sent successfully
                return jsonify({
                    'success': True,
                    'message': 'Registration successful! Please check your email to activate your account.',
                    'activation_required': True,
                    'email_sent': True,
                    'user': {
                        'id': user_id,
                        'username': username,
                        'full_name': full_name,
                        'email': email
                    }
                })
        
        # Fallback for old schema without activation
        return jsonify({
            'success': True,
            'message': 'Registration successful!',
            'activation_required': False,
            'user': {
                'id': user_id,
                'username': username,
                'full_name': full_name,
                'email': email
            }
        })
    except Exception as e:
        conn.close()
        error_msg = str(e)
        print(f"❌ Registration error: {error_msg}")  # Log the actual error
        
        # Provide helpful error messages
        if 'no column named email' in error_msg.lower():
            return jsonify({
                'error': 'Database not updated. Please run: python migrate_database.py',
                'details': 'Email column missing from database'
            }), 500
        elif 'no column named is_active' in error_msg.lower():
            return jsonify({
                'error': 'Database not updated. Please run: python migrate_database.py',
                'details': 'Activation columns missing from database'
            }), 500
        else:
            return jsonify({'error': f'Registration failed: {error_msg}'}), 500

@app.route('/api/activate/<token>', methods=['GET'])
def activate_account(token):
    """Activate user account with token"""
    conn = get_db_connection()
    
    print(f"🔍 Activation attempt with token: {token[:10]}...")
    
    # Find user with this activation token
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        'SELECT id, username, email, is_active FROM users WHERE activation_token = %s',
        (token,)
    )
    user = cursor.fetchone()
    
    if not user:
        print(f"❌ No user found with this activation token")
        cursor.close()
        conn.close()
        return jsonify({'error': 'Invalid activation token. This link may have already been used or expired.'}), 400
    
    if user['is_active']:
        print(f"✓ Account already activated: {user['username']}")
        cursor.close()
        conn.close()
        return jsonify({
            'success': True,
            'message': 'Account already activated! You can login now.',
            'username': user['username']
        }), 200
    
    # Activate the account
    print(f"✅ Activating account: {user['username']}")
    cursor.execute(
        'UPDATE users SET is_active = 1, activation_token = NULL WHERE id = %s',
        (user['id'],)
    )
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ Account activated successfully: {user['username']}")
    
    return jsonify({
        'success': True,
        'message': 'Account activated successfully! You can now login.',
        'username': user['username']
    })

def send_activation_email(email, full_name, activation_token):
    """Send activation email to user using SMTP (Yahoo)"""
    import os
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    # Create activation link
    activation_link = f"http://localhost:3000/activate?token={activation_token}"
    
    # Get SMTP configuration from environment
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.mail.yahoo.com')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER', '')
    smtp_password = os.getenv('SMTP_PASSWORD', '')
    
    if not smtp_user or not smtp_password:
        print("⚠️  Email not configured. Set SMTP_USER and SMTP_PASSWORD in .env")
        print(f"📧 Activation link for {email}:")
        print(f"   {activation_link}")
        return False, activation_link
    
    print(f"🔄 Attempting to send email to {email}...")
    print(f"   SMTP Server: {smtp_server}:{smtp_port}")
    print(f"   From: {smtp_user}")
    
    try:
        # Create email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = '🎓 Activate Your QAdam Account'
        msg['From'] = f'QAdam Academic Portal <{smtp_user}>'
        msg['To'] = email
        
        # Email HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html>
          <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
          </head>
          <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f4f4; padding: 20px;">
              <tr>
                <td align="center">
                  <table width="600" cellpadding="0" cellspacing="0" style="background-color: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                      <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; text-align: center;">
                        <h1 style="color: white; margin: 0; font-size: 32px;">🎓 QAdam</h1>
                        <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0; font-size: 16px;">Academic Portal</p>
                      </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                      <td style="padding: 40px 30px;">
                        <h2 style="color: #333; margin: 0 0 20px 0; font-size: 24px;">Welcome, {full_name}! 👋</h2>
                        <p style="color: #666; line-height: 1.6; margin: 0 0 20px 0; font-size: 16px;">
                          Thank you for registering with QAdam Academic Portal. We're excited to have you join our learning community!
                        </p>
                        <p style="color: #666; line-height: 1.6; margin: 0 0 30px 0; font-size: 16px;">
                          To complete your registration and activate your account, please click the button below:
                        </p>
                        
                        <!-- Button -->
                        <table width="100%" cellpadding="0" cellspacing="0">
                          <tr>
                            <td align="center" style="padding: 20px 0;">
                              <a href="{activation_link}" 
                                 style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                        color: white;
                                        padding: 16px 40px;
                                        text-decoration: none;
                                        border-radius: 8px;
                                        font-weight: 600;
                                        font-size: 16px;
                                        display: inline-block;
                                        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);">
                                Activate My Account
                              </a>
                            </td>
                          </tr>
                        </table>
                        
                        <p style="color: #999; font-size: 14px; line-height: 1.6; margin: 30px 0 0 0;">
                          Or copy and paste this link in your browser:<br>
                          <a href="{activation_link}" style="color: #667eea; word-break: break-all;">{activation_link}</a>
                        </p>
                        
                        <div style="background-color: #f8f9fa; border-left: 4px solid #667eea; padding: 15px; margin: 30px 0;">
                          <p style="color: #666; font-size: 14px; margin: 0; line-height: 1.5;">
                            <strong>Security Note:</strong> This link will expire once used. If you didn't create this account, please ignore this email.
                          </p>
                        </div>
                      </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                      <td style="background-color: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #e0e0e0;">
                        <p style="color: #999; font-size: 12px; margin: 0 0 10px 0;">
                          QAdam Academic Portal - CBSE Senior School
                        </p>
                        <p style="color: #999; font-size: 12px; margin: 0;">
                          This is an automated email. Please do not reply.
                        </p>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </body>
        </html>
        """
        
        # Attach HTML content
        msg.attach(MIMEText(html_content, 'html'))
        
        # Send email via SMTP
        print(f"🔌 Connecting to SMTP server...")
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            print(f"🔐 Starting TLS...")
            server.starttls()
            print(f"🔑 Logging in...")
            server.login(smtp_user, smtp_password)
            print(f"📤 Sending message...")
            server.send_message(msg)
        
        print(f"✅ Activation email sent to {email} via Gmail SMTP")
        return True, activation_link
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication Error: {e}")
        print(f"   Check your Gmail app password")
        print(f"📧 Activation link for {email}:")
        print(f"   {activation_link}")
        return False, activation_link
    except smtplib.SMTPException as e:
        print(f"❌ SMTP Error: {e}")
        print(f"📧 Activation link for {email}:")
        print(f"   {activation_link}")
        return False, activation_link
    except Exception as e:
        print(f"❌ Email error: {type(e).__name__}: {e}")
        print(f"📧 Activation link for {email}:")
        print(f"   {activation_link}")
        return False, activation_link

@app.route('/api/sample-questions', methods=['GET'])
def get_sample_questions():
    """Get all sample questions"""
    subject = request.args.get('subject')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if subject:
        cursor.execute(
            'SELECT * FROM sample_questions WHERE subject = %s ORDER BY created_at DESC',
            (subject,)
        )
    else:
        cursor.execute(
            'SELECT * FROM sample_questions ORDER BY created_at DESC'
        )
    
    questions = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return jsonify(questions)

@app.route('/api/subjects', methods=['GET'])
def get_subjects():
    """Get all unique subjects"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        'SELECT DISTINCT subject FROM sample_questions ORDER BY subject'
    )
    subjects = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return jsonify([s['subject'] for s in subjects])

@app.route('/api/upload-paper', methods=['POST'])
def upload_paper():
    """Upload a paper"""
    try:
        print("📤 Upload request received")
        
        if 'file' not in request.files:
            print("❌ No file in request")
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        title = request.form.get('title')
        subject = request.form.get('subject')
        user_id = request.form.get('user_id')
        
        print(f"📝 Title: {title}, Subject: {subject}, User: {user_id}")
        print(f"📄 Filename: {file.filename}")
        
        if not title or not subject:
            print("❌ Missing title or subject")
            return jsonify({'error': 'Title and subject required'}), 400
        
        if file.filename == '':
            print("❌ Empty filename")
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            print(f"❌ Invalid file type: {file.filename}")
            return jsonify({'error': 'Invalid file type. Allowed: PDF, DOC, DOCX, TXT'}), 400
        
        # Ensure upload folder exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        print(f"✓ Upload folder ready: {app.config['UPLOAD_FOLDER']}")
        
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        print(f"💾 Saving to: {filepath}")
        file.save(filepath)
        print(f"✓ File saved successfully")
        
        # Verify file exists
        if not os.path.exists(filepath):
            print(f"❌ File not found after save: {filepath}")
            return jsonify({'error': 'Failed to save file'}), 500
        
        file_size = os.path.getsize(filepath)
        print(f"✓ File size: {file_size} bytes")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO uploaded_papers (title, subject, file_path, user_id) VALUES (%s, %s, %s, %s)',
            (title, subject, filepath, user_id)
        )
        conn.commit()
        paper_id = cursor.lastrowid
        conn.close()
        
        print(f"✓ Paper saved to database with ID: {paper_id}")
        
        return jsonify({
            'success': True,
            'message': 'Paper uploaded successfully',
            'paper_id': paper_id,
            'filename': filename
        })
        
    except Exception as e:
        print(f"❌ Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/api/uploaded-papers', methods=['GET'])
def get_uploaded_papers():
    """Get all uploaded papers"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT p.*, u.full_name as uploaded_by_name 
        FROM uploaded_papers p
        LEFT JOIN users u ON p.user_id = u.id
        ORDER BY p.created_at DESC
    ''')
    papers = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return jsonify(papers)

@app.route('/api/delete-paper/<int:paper_id>', methods=['DELETE'])
def delete_paper(paper_id):
    """Delete a question paper and its associated data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get paper info
        cursor.execute(
            'SELECT file_path FROM uploaded_papers WHERE id = %s',
            (paper_id,)
        )
        paper = cursor.fetchone()
        
        if not paper:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Paper not found'}), 404
        
        # Delete the physical file
        if os.path.exists(paper['file_path']):
            os.remove(paper['file_path'])
            print(f"✓ Deleted file: {paper['file_path']}")
        
        # Delete parsed questions
        cursor.execute('DELETE FROM parsed_questions WHERE paper_id = %s', (paper_id,))
        print(f"✓ Deleted parsed questions for paper {paper_id}")
        
        # Delete FAISS index if exists
        faiss_index_path = f"./vector_db/paper_{paper_id}_questions.index"
        if os.path.exists(faiss_index_path):
            os.remove(faiss_index_path)
            print(f"✓ Deleted FAISS index")
        
        # Delete the paper record
        cursor.execute('DELETE FROM uploaded_papers WHERE id = %s', (paper_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Paper deleted successfully'
        })
    except Exception as e:
        print(f"Error deleting paper: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload-textbook', methods=['POST'])
def upload_textbook():
    """Upload a textbook"""
    try:
        print("📚 Textbook upload request received")
        
        if 'file' not in request.files:
            print("❌ No file in request")
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        title = request.form.get('title')
        subject = request.form.get('subject')
        author = request.form.get('author', '')
        user_id = request.form.get('user_id')
        
        print(f"📝 Title: {title}, Subject: {subject}, Author: {author}, User: {user_id}")
        print(f"📄 Filename: {file.filename}")
        
        if not title or not subject:
            print("❌ Missing title or subject")
            return jsonify({'error': 'Title and subject required'}), 400
        
        if file.filename == '':
            print("❌ Empty filename")
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            print(f"❌ Invalid file type: {file.filename}")
            return jsonify({'error': 'Invalid file type. Allowed: PDF, DOC, DOCX, TXT'}), 400
        
        # Ensure upload folder exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        print(f"✓ Upload folder ready: {app.config['UPLOAD_FOLDER']}")
        
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"textbook_{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        print(f"💾 Saving to: {filepath}")
        file.save(filepath)
        print(f"✓ File saved successfully")
        
        # Verify file exists
        if not os.path.exists(filepath):
            print(f"❌ File not found after save: {filepath}")
            return jsonify({'error': 'Failed to save file'}), 500
        
        file_size = os.path.getsize(filepath)
        print(f"✓ File size: {file_size} bytes")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO textbooks (title, subject, file_path, user_id) VALUES (%s, %s, %s, %s)',
            (title, subject, author, filepath, user_id)
        )
        conn.commit()
        textbook_id = cursor.lastrowid
        conn.close()
        
        print(f"✓ Textbook saved to database with ID: {textbook_id}")
        
        return jsonify({
            'success': True,
            'message': 'Textbook uploaded successfully',
            'textbook_id': textbook_id,
            'filename': filename
        })
        
    except Exception as e:
        print(f"❌ Textbook upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/api/textbooks', methods=['GET'])
def get_textbooks():
    """Get all textbooks"""
    subject = request.args.get('subject')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if subject:
        cursor.execute('''
            SELECT t.*, u.full_name as uploaded_by_name 
            FROM textbooks t
            LEFT JOIN users u ON t.user_id = u.id
            WHERE t.subject = %s
            ORDER BY t.created_at DESC
        ''', (subject,))
    else:
        cursor.execute('''
            SELECT t.*, u.full_name as uploaded_by_name 
            FROM textbooks t
            LEFT JOIN users u ON t.user_id = u.id
            ORDER BY t.created_at DESC
        ''')
    
    textbooks = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Debug: Log textbook IDs
    if textbooks:
        print(f"📚 Returning {len(textbooks)} textbooks")
        for tb in textbooks:
            print(f"   - {tb.get('title', 'Unknown')}: ID={tb.get('id', 'MISSING')}")
    
    return jsonify(textbooks)

@app.route('/api/textbook-pdf/<int:textbook_id>', methods=['GET'])
def serve_textbook_pdf(textbook_id):
    """Serve textbook PDF file"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            'SELECT file_path, title FROM textbooks WHERE id = %s',
            (textbook_id,)
        )
        textbook = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not textbook:
            return jsonify({'error': 'Textbook not found'}), 404
        
        file_path = textbook['file_path']
        if not os.path.exists(file_path):
            return jsonify({'error': 'Textbook file not found'}), 404
        
        return send_file(
            file_path,
            mimetype='application/pdf',
            as_attachment=False,
            download_name=f"{textbook['title']}.pdf"
        )
    except Exception as e:
        print(f"Error serving textbook PDF: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/textbook-page-image/<int:textbook_id>/<int:page_number>', methods=['GET'])
def serve_textbook_page_image(textbook_id, page_number):
    """Serve textbook page as image (requires PDF to image conversion)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            'SELECT file_path FROM textbooks WHERE id = %s',
            (textbook_id,)
        )
        textbook = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not textbook:
            return jsonify({'error': 'Textbook not found'}), 404
        
        # This would require PDF to image conversion
        # For now, return an error suggesting to use PDF viewer
        return jsonify({
            'error': 'Page image conversion not yet implemented',
            'message': 'Please use the PDF Viewer option to view textbook pages'
        }), 501
        
    except Exception as e:
        print(f"Error serving page image: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/map-questions-to-chapters', methods=['POST'])
def map_questions_to_chapters_endpoint():
    """Map questions to textbook chapters using semantic search"""
    try:
        if not AI_ENABLED:
            return jsonify({'error': 'AI features not available'}), 503
        
        data = request.json
        print(f"📥 Received data: {type(data)}")
        print(f"   Keys: {data.keys() if data else 'None'}")
        
        questions = data.get('questions', []) if data else []
        textbook_id = data.get('textbook_id') if data else None
        
        print(f"   Questions: {len(questions) if questions else 0}")
        print(f"   Textbook ID: {textbook_id}")
        
        if not questions or not textbook_id:
            print(f"❌ Missing data - questions: {len(questions) if questions else 0}, textbook_id: {textbook_id}")
            return jsonify({
                'error': 'Missing questions or textbook_id',
                'received': {
                    'questions_count': len(questions) if questions else 0,
                    'textbook_id': textbook_id,
                    'data_keys': list(data.keys()) if data else []
                }
            }), 400
        
        print(f"📚 Mapping {len(questions)} questions to chapters for textbook {textbook_id}")
        
        # Use the AI service function
        result = map_questions_to_chapters(questions, textbook_id)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in map_questions_to_chapters_endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete-textbook/<int:textbook_id>', methods=['DELETE'])
def delete_textbook(textbook_id):
    """Delete a textbook"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get textbook info
        cursor.execute(
            'SELECT file_path FROM textbooks WHERE id = %s',
            (textbook_id,)
        )
        textbook = cursor.fetchone()
        
        if not textbook:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Textbook not found'}), 404
        
        # Delete the physical file
        if os.path.exists(textbook['file_path']):
            os.remove(textbook['file_path'])
            print(f"✓ Deleted file: {textbook['file_path']}")
        
        # Delete the textbook record
        cursor.execute('DELETE FROM textbooks WHERE id = %s', (textbook_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Textbook deleted successfully'
        })
    except Exception as e:
        print(f"Error deleting textbook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/textbook-file/<int:textbook_id>', methods=['GET'])
def get_textbook_file(textbook_id):
    """Get textbook file info"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        'SELECT * FROM textbooks WHERE id = %s',
        (textbook_id,)
    )
    textbook = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not textbook:
        return jsonify({'error': 'Textbook not found'}), 404
    
    file_path = textbook['file_path']
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    file_ext = file_path.rsplit('.', 1)[1].lower()
    
    return jsonify({
        'success': True,
        'file_type': file_ext,
        'file_name': os.path.basename(file_path),
        'title': textbook['title'],
        'subject': textbook['subject'],
        'author': textbook['author']
    })

@app.route('/api/download-textbook/<int:textbook_id>', methods=['GET'])
@app.route('/api/textbooks/<int:textbook_id>', methods=['GET'])
def download_textbook(textbook_id):
    """Serve textbook file"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        'SELECT * FROM textbooks WHERE id = %s',
        (textbook_id,)
    )
    textbook = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not textbook:
        return jsonify({'error': 'Textbook not found'}), 404
    
    file_path = textbook['file_path']
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(file_path, mimetype='application/pdf' if file_path.endswith('.pdf') else None)

@app.route('/api/paper-file/<int:paper_id>', methods=['GET'])
def get_paper_file(paper_id):
    """Get paper file for viewing"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        'SELECT * FROM uploaded_papers WHERE id = %s',
        (paper_id,)
    )
    paper = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not paper:
        return jsonify({'error': 'Paper not found'}), 404
    
    file_path = paper['file_path']
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    # Get file extension
    file_ext = file_path.rsplit('.', 1)[1].lower()
    
    return jsonify({
        'success': True,
        'file_type': file_ext,
        'file_name': os.path.basename(file_path),
        'title': paper['title'],
        'subject': paper['subject']
    })

@app.route('/api/download-paper/<int:paper_id>', methods=['GET'])
def download_paper(paper_id):
    """Download or serve paper file"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        'SELECT * FROM uploaded_papers WHERE id = %s',
        (paper_id,)
    )
    paper = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not paper:
        return jsonify({'error': 'Paper not found'}), 404
    
    file_path = paper['file_path']
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    # Serve the file with proper MIME type
    return send_file(file_path, mimetype='application/pdf' if file_path.endswith('.pdf') else None)

@app.route('/api/analyze-paper', methods=['POST'])
def analyze_paper():
    """Analyze question paper against textbook"""
    if not AI_ENABLED:
        return jsonify({
            'error': 'AI features not available. Please install dependencies: pip install PyMuPDF sentence-transformers chromadb openai python-dotenv'
        }), 503
    
    try:
        data = request.json
        paper_id = data.get('paper_id')
        textbook_id = data.get('textbook_id')
        
        if not paper_id or not textbook_id:
            return jsonify({'error': 'paper_id and textbook_id required'}), 400
        
        # Get paper and textbook paths
        conn = get_db_connection()
        
        paper = conn.execute(
            'SELECT * FROM uploaded_papers WHERE id = %s',
            (paper_id,)
        ).fetchone()
        
        textbook = conn.execute(
            'SELECT * FROM textbooks WHERE id = %s',
            (textbook_id,)
        ).fetchone()
        
        conn.close()
        
        if not paper or not textbook:
            return jsonify({'error': 'Paper or textbook not found'}), 404
        
        # Perform analysis
        result = analyze_question_paper(
            paper_id,
            paper['file_path'],
            textbook_id,
            textbook['file_path']
        )
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-solution', methods=['POST'])
def get_solution():
    """Generate solution for a question"""
    if not AI_ENABLED:
        return jsonify({
            'error': 'AI features not available. Please install dependencies first.'
        }), 503
    
    try:
        data = request.json
        question_text = data.get('question_text')
        context = data.get('context', '')
        
        if not question_text:
            return jsonify({'error': 'question_text required'}), 400
        
        result = generate_solution(question_text, context)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/index-textbook/<int:textbook_id>', methods=['POST'])
def index_textbook(textbook_id):
    """Index a textbook for semantic search"""
    if not AI_ENABLED:
        return jsonify({
            'error': 'AI features not available. Please install dependencies first.'
        }), 503
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            'SELECT * FROM textbooks WHERE id = %s',
            (textbook_id,)
        )
        textbook = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not textbook:
            return jsonify({'error': 'Textbook not found'}), 404
        
        result = extract_chapters_from_textbook(
            textbook['file_path'],
            textbook_id
        )
        
        # If extraction was successful, mark textbook as indexed
        if result and 'error' not in result:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE textbooks SET chapters_extracted = 1 WHERE id = %s',
                (textbook_id,)
            )
            conn.commit()
            cursor.close()
            conn.close()
            print(f"✓ Marked textbook {textbook_id} as indexed")
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/parse-questions/<int:paper_id>', methods=['POST'])
def parse_questions(paper_id):
    """Parse questions from a paper using OCR + Groq AI"""
    try:
        from question_parser import parse_question_paper_fixed as parse_question_paper
        import json
        import faiss
        import numpy as np
        
        # Get paper details
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            'SELECT * FROM uploaded_papers WHERE id = %s',
            (paper_id,)
        )
        paper = cursor.fetchone()
        
        if not paper:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Paper not found'}), 404
        
        file_path = paper['file_path']
        
        if not os.path.exists(file_path):
            cursor.close()
            conn.close()
            return jsonify({'error': 'File not found'}), 404
        
        # CLEAN DATABASE: Delete existing parsed questions for this paper
        print(f"🧹 Cleaning existing parsed questions for paper {paper_id}...")
        cursor.execute(
            'DELETE FROM parsed_questions WHERE paper_id = %s',
            (paper_id,)
        )
        conn.commit()
        print(f"✓ Deleted {deleted.rowcount} old questions")
        
        # Delete old FAISS index if exists
        faiss_index_path = f"./vector_db/paper_{paper_id}_questions.index"
        if os.path.exists(faiss_index_path):
            os.remove(faiss_index_path)
            print(f"✓ Deleted old FAISS index")
        
        # Parse the question paper
        result = parse_question_paper(file_path)
        
        if not result or result is None:
            return jsonify({'error': 'Failed to parse question paper'}), 500
        
        questions = result.get('questions', [])
        
        # Store in FAISS vector database
        # CLEANUP: Delete existing questions for this paper
        print(f"\n🗑️ Cleaning up existing questions for paper_id={paper_id}...")
        cursor = conn.execute('SELECT COUNT(*) FROM parsed_questions WHERE paper_id = ?', (paper_id,))
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 0:
            print(f"  Found {existing_count} existing questions - deleting...")
            conn.execute('DELETE FROM parsed_questions WHERE paper_id = %s', (paper_id,))
            conn.commit()
            
            # Verify deletion
            cursor = conn.execute('SELECT COUNT(*) FROM parsed_questions WHERE paper_id = ?', (paper_id,))
            remaining = cursor.fetchone()[0]
            if remaining == 0:
                print(f"  ✓ Deleted {existing_count} old questions (verified: 0 remaining)")
            else:
                print(f"  ⚠ Warning: {remaining} questions still remain after deletion!")
            
            # Delete old FAISS index if it exists
            old_index_path = f"./vector_db/paper_{paper_id}_questions.index"
            if os.path.exists(old_index_path):
                try:
                    os.remove(old_index_path)
                    print(f"  ✓ Deleted old FAISS index")
                except:
                    pass
        else:
            print(f"  No existing questions found")
        
        if AI_ENABLED:
            try:
                from ai_service import get_embedding_model
                model = get_embedding_model()
                
                # Create embeddings for questions
                question_texts = [q['question_text'] for q in questions]
                embeddings = model.encode(question_texts, show_progress_bar=False)
                embeddings_np = np.array(embeddings).astype('float32')
                
                # Create FAISS index
                dimension = embeddings_np.shape[1]
                index = faiss.IndexFlatL2(dimension)
                index.add(embeddings_np)
                
                # Save FAISS index
                index_path = f"./vector_db/paper_{paper_id}_questions.index"
                os.makedirs("./vector_db", exist_ok=True)
                faiss.write_index(index, index_path)
                
                print(f"✓ Stored {len(questions)} questions in FAISS")
            except Exception as e:
                print(f"⚠ FAISS storage failed: {e}")
        
        # Store in SQLite database
        print(f"\n💾 Storing {len(questions)} NEW questions in database...")
        for idx, q in enumerate(questions):
            q_num = q.get('question_number', str(idx + 1))
            q_text_preview = q.get('question_text', '')[:80]
            
            # Debug: Show first 5 questions
            if idx < 5:
                print(f"  Q{q_num}: {q_text_preview}...")
            
            # Store diagram files as JSON
            diagram_files = json.dumps(q.get('diagram_files', []))
            
            conn.execute('''
                INSERT INTO parsed_questions 
                (paper_id, question_number, question_text, question_type, 
                 sub_parts, has_diagram, marks, embedding_id, parsed_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                paper_id,
                q_num,
                q.get('question_text', ''),
                q.get('question_type', 'unknown'),
                json.dumps(q.get('sub_parts', [])),
                1 if q.get('has_diagram', False) else 0,
                q.get('marks'),
                idx,
                json.dumps(q)  # This includes diagram_files
            ))
        
        print(f"✓ Stored all questions in database")
        
        conn.commit()
        
        # Final verification - show what's in database
        cursor = conn.execute('SELECT COUNT(*) FROM parsed_questions WHERE paper_id = ?', (paper_id,))
        final_count = cursor.fetchone()[0]
        print(f"\n✅ FINAL: Database now has {final_count} questions for paper_id={paper_id}")
        
        conn.close()
        
        return jsonify({
            'success': True,
            'total_questions': len(questions),
            'questions': questions,
            'diagrams_extracted': len(result.get('diagrams', []))
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/parsed-questions', methods=['GET'])
def get_parsed_questions():
    """Get all parsed questions"""
    paper_id = request.args.get('paper_id')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if paper_id:
        print(f"📖 Fetching parsed questions for paper_id={paper_id}")
        cursor.execute('''
            SELECT pq.*, up.title as paper_title, up.subject
            FROM parsed_questions pq
            JOIN uploaded_papers up ON pq.paper_id = up.id
            WHERE pq.paper_id = %s
            ORDER BY CAST(pq.question_number AS UNSIGNED)
        ''', (paper_id,))
        questions = cursor.fetchall()
        print(f"  Found {len(questions)} questions in database")
    else:
        cursor.execute('''
            SELECT pq.*, up.title as paper_title, up.subject
            FROM parsed_questions pq
            JOIN uploaded_papers up ON pq.paper_id = up.id
            ORDER BY pq.created_at DESC
            LIMIT 100
        ''')
        questions = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    print(f"📖 Returning {len(questions)} parsed questions for paper_id={paper_id if paper_id else 'all'}")
    
    return jsonify(questions)

@app.route('/api/diagram/<int:paper_id>/<filename>', methods=['GET'])
def get_diagram(paper_id, filename):
    """Serve diagram file"""
    try:
        # Get paper to find its directory
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            'SELECT file_path FROM uploaded_papers WHERE id = %s',
            (paper_id,)
        )
        paper = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not paper:
            return jsonify({'error': 'Paper not found'}), 404
        
        # Construct diagram path
        paper_dir = os.path.dirname(paper['file_path'])
        diagram_path = os.path.join(paper_dir, 'diagrams', filename)
        
        if not os.path.exists(diagram_path):
            return jsonify({'error': 'Diagram not found'}), 404
        
        # Serve the diagram file
        return send_file(diagram_path, mimetype='image/png')
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clean-duplicates', methods=['POST'])
def clean_duplicates():
    """Remove duplicate parsed questions from database"""
    try:
        conn = get_db_connection()
        
        # Find duplicates (same paper_id and question_number)
        duplicates = conn.execute('''
            SELECT paper_id, question_number, COUNT(*) as count
            FROM parsed_questions
            GROUP BY paper_id, question_number
            HAVING count > 1
        ''').fetchall()
        
        total_removed = 0
        
        for dup in duplicates:
            paper_id = dup['paper_id']
            question_number = dup['question_number']
            
            # Keep only the most recent one, delete others
            conn.execute('''
                DELETE FROM parsed_questions
                WHERE id NOT IN (
                    SELECT MAX(id)
                    FROM parsed_questions
                    WHERE paper_id = ? AND question_number = ?
                )
                AND paper_id = ? AND question_number = ?
            ''', (paper_id, question_number, paper_id, question_number))
            
            total_removed += dup['count'] - 1
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'duplicates_found': len(duplicates),
            'questions_removed': total_removed,
            'message': f'Removed {total_removed} duplicate questions'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/parse-single-question', methods=['POST'])
def parse_single_question():
    """Parse a single question from text, image, or document"""
    try:
        import question_parser
        
        # Import with error handling
        try:
            import pytesseract
        except ImportError:
            return jsonify({'error': 'pytesseract not installed. Run: pip install pytesseract'}), 500
        
        try:
            from PIL import Image
        except ImportError:
            return jsonify({'error': 'Pillow not installed. Run: pip install Pillow'}), 500
        
        try:
            import fitz  # PyMuPDF
        except ImportError:
            return jsonify({'error': 'PyMuPDF not installed. Run: pip install PyMuPDF'}), 500
        
        try:
            from docx import Document
        except ImportError:
            return jsonify({'error': 'python-docx not installed. Run: pip install python-docx'}), 500
        
        input_type = request.form.get('input_type')
        question_text = None
        
        if input_type == 'text':
            # Direct text input
            question_text = request.form.get('question_text', '').strip()
            if not question_text:
                return jsonify({'error': 'No question text provided'}), 400
                
        elif input_type == 'file':
            # File upload
            if 'file' not in request.files:
                return jsonify({'error': 'No file uploaded'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            file_type = request.form.get('file_type', '').lower()
            
            # Save file temporarily
            temp_filename = secure_filename(f"temp_question_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_type}")
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
            file.save(temp_path)
            
            try:
                # Extract text based on file type
                if file_type in ['jpg', 'jpeg', 'png']:
                    # OCR for images
                    image = Image.open(temp_path)
                    question_text = pytesseract.image_to_string(image)
                    
                elif file_type == 'pdf':
                    # Extract from PDF
                    doc = fitz.open(temp_path)
                    question_text = ""
                    for page in doc:
                        question_text += page.get_text()
                    doc.close()
                    
                elif file_type == 'docx':
                    # Extract from DOCX
                    doc = Document(temp_path)
                    question_text = "\n".join([para.text for para in doc.paragraphs])
                    
                elif file_type == 'txt':
                    # Read text file
                    with open(temp_path, 'r', encoding='utf-8') as f:
                        question_text = f.read()
                        
                else:
                    return jsonify({'error': f'Unsupported file type: {file_type}'}), 400
                    
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        
        else:
            return jsonify({'error': 'Invalid input type'}), 400
        
        if not question_text or not question_text.strip():
            return jsonify({'error': 'Could not extract text from input'}), 400
        
        # Parse the question using Groq AI
        print(f"Parsing single question: {question_text[:100]}...")
        
        # Create a simple question block
        question_block = {
            'block_number': 1,
            'raw_text': question_text.strip(),
            'instruction': None
        }
        
        # Use the existing Groq parser
        parsed_questions = question_parser.parse_with_groq_fixed([question_block])
        
        if parsed_questions and len(parsed_questions) > 0:
            parsed_question = parsed_questions[0]
            
            return jsonify({
                'success': True,
                'question': parsed_question,
                'extracted_text': question_text[:500]  # First 500 chars for reference
            })
        else:
            return jsonify({'error': 'Failed to parse question'}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/save-ai-search-results', methods=['POST'])
def save_ai_search_results():
    """Save AI search results to database"""
    import json  # Explicit import to avoid scope issues
    try:
        data = request.get_json()
        paper_id = data.get('paper_id')
        textbook_id = data.get('textbook_id')
        search_results = data.get('search_results')
        
        if not paper_id or not textbook_id or not search_results:
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Calculate stats
        total_chapters = len(search_results)
        total_questions = sum(len(data['questions']) for data in search_results.values())
        unmatched_count = len(search_results.get('Unmatched Questions', {}).get('questions', []))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete old results for this paper-textbook combination
        cursor.execute('''
            DELETE FROM ai_search_results 
            WHERE paper_id = %s AND textbook_id = %s
        ''', (paper_id, textbook_id))
        
        # Insert new results
        cursor.execute('''
            INSERT INTO ai_search_results 
            (paper_id, textbook_id, search_results, total_chapters, total_questions, unmatched_count)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            paper_id,
            textbook_id,
            json.dumps(search_results),
            total_chapters,
            total_questions,
            unmatched_count
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Search results saved successfully'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-last-ai-search', methods=['GET'])
def get_last_ai_search():
    """Get last AI search results for a paper-textbook combination"""
    import json  # Explicit import to avoid scope issues
    try:
        paper_id = request.args.get('paper_id')
        textbook_id = request.args.get('textbook_id')
        
        if not paper_id or not textbook_id:
            return jsonify({'error': 'Missing paper_id or textbook_id'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT search_results, total_chapters, total_questions, unmatched_count, created_at
            FROM ai_search_results
            WHERE paper_id = %s AND textbook_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        ''', (paper_id, textbook_id))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return jsonify({
                'success': True,
                'search_results': json.loads(result['search_results']),
                'total_chapters': result['total_chapters'],
                'total_questions': result['total_questions'],
                'unmatched_count': result['unmatched_count'],
                'created_at': result['created_at']
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No previous search results found'
            }), 404
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/solve-question', methods=['POST'])
def solve_question():
    """Solve a question using LLM with detailed step-by-step solution"""
    if not AI_ENABLED:
        return jsonify({'error': 'AI features are not enabled'}), 503
    
    try:
        data = request.json
        question_text = data.get('question_text')
        question_type = data.get('question_type', 'unknown')
        subject = data.get('subject')
        chapter_context = data.get('chapter_context')
        
        if not question_text:
            return jsonify({'error': 'question_text is required'}), 400
        
        print(f"🎓 Solving question: {question_text[:60]}...")
        
        result = solve_question_with_llm(
            question_text=question_text,
            question_type=question_type,
            subject=subject,
            chapter_context=chapter_context
        )
        
        if 'error' in result:
            return jsonify(result), 500
        
        # Log token usage
        if result.get('tokens_used'):
            user_id = session.get('user_id')
            if user_id:
                try:
                    conn = get_db_connection()
                    conn.execute('''
                        INSERT INTO usage_logs (user_id, action_type, tokens_used, model_name, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (user_id, 'solve_question', result.get('tokens_used'), result.get('model'), datetime.now().isoformat()))
                    conn.commit()
                    conn.close()
                    print(f"📊 Logged {result.get('tokens_used')} tokens for user {user_id}")
                except Exception as log_err:
                    print(f"Warning: Failed to log token usage: {log_err}")
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/save-solved-question', methods=['POST'])
def save_solved_question():
    """Save a solved question to the Question Bank"""
    try:
        data = request.json
        question_text = data.get('question_text')
        solution = data.get('solution')
        source = data.get('source', 'unknown')
        subject = data.get('subject')  # Subject from Solve One Question
        timestamp = data.get('timestamp')
        paper_id = data.get('paper_id')  # Optional: from Answer Chapterwise
        textbook_id = data.get('textbook_id')  # Optional: from Answer Chapterwise
        chapter_name = data.get('chapter_name')  # Optional: from Answer Chapterwise
        
        if not question_text or not solution:
            return jsonify({'error': 'question_text and solution are required'}), 400
        
        # Get current user from session
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Save to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO question_bank (question_text, solution, source, subject, paper_id, textbook_id, chapter_name, user_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (question_text, solution, source, subject, paper_id, textbook_id, chapter_name, user_id, timestamp or datetime.now().isoformat()))
        
        conn.commit()
        question_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        log_msg = f"✅ Saved question {question_id} to Question Bank from {source}"
        if subject:
            log_msg += f" (Subject: {subject})"
        if paper_id:
            log_msg += f" (Paper ID: {paper_id})"
        if textbook_id:
            log_msg += f" (Textbook ID: {textbook_id})"
        if chapter_name:
            log_msg += f" (Chapter: {chapter_name})"
        print(log_msg)
        
        return jsonify({
            'success': True,
            'question_id': question_id,
            'message': 'Question saved to Question Bank'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/question-bank', methods=['GET'])
def get_question_bank():
    """Get all questions from Question Bank for current user"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('''
            SELECT qb.id, qb.question_text, qb.solution, qb.source, qb.subject, qb.created_at,
                   qb.paper_id, qb.textbook_id, qb.chapter_name,
                   up.title as paper_title, tb.title as textbook_title
            FROM question_bank qb
            LEFT JOIN uploaded_papers up ON qb.paper_id = up.id
            LEFT JOIN textbooks tb ON qb.textbook_id = tb.id
            WHERE qb.user_id = %s
            ORDER BY qb.created_at DESC
        ''', (user_id,))
        
        questions = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'questions': questions,
            'count': len(questions)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/question-bank/<int:question_id>', methods=['DELETE'])
def delete_question_from_bank(question_id):
    """Delete a question from Question Bank"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Verify ownership before deleting
        cursor.execute('''
            SELECT id FROM question_bank
            WHERE id = %s AND user_id = %s
        ''', (question_id, user_id))
        
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Question not found or unauthorized'}), 404
        
        cursor.execute('DELETE FROM question_bank WHERE id = %s', (question_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"🗑️ Deleted question {question_id} from Question Bank")
        
        return jsonify({
            'success': True,
            'message': 'Question deleted successfully'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'Backend is running'})

# ============================================
# ADMIN USER MANAGEMENT ENDPOINTS
# ============================================

@app.route('/api/admin/users', methods=['GET'])
def get_all_users():
    """Get all users (admin only)"""
    # TODO: Add proper admin authentication check
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            '''SELECT id, username, full_name, email, phone, is_active, is_admin, created_at 
               FROM users ORDER BY created_at DESC'''
        )
        users = cursor.fetchall()
        
        users_list = []
        for user in users:
            users_list.append({
                'id': user['id'],
                'username': user['username'],
                'full_name': user['full_name'],
                'email': user['email'],
                'phone': user['phone'],
                'is_active': bool(user['is_active']),
                'is_admin': bool(user['is_admin']),
                'created_at': user['created_at']
            })
        
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'users': users_list})
        
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/users/<int:user_id>/toggle-active', methods=['POST'])
def toggle_user_active(user_id):
    """Activate or deactivate a user (admin only)"""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get current status
        cursor.execute(
            'SELECT id, username, is_active FROM users WHERE id = %s',
            (user_id,)
        )
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        
        # Toggle status
        new_status = 0 if user['is_active'] else 1
        
        cursor.execute(
            'UPDATE users SET is_active = %s WHERE id = %s',
            (new_status, user_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        status_text = "activated" if new_status else "deactivated"
        print(f"✅ Admin {status_text} user: {user['username']}")
        
        return jsonify({
            'success': True,
            'message': f'User {status_text} successfully',
            'is_active': bool(new_status)
        })
        
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Delete a user account (admin only)"""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Check if user exists
        cursor.execute(
            'SELECT id, username, is_admin FROM users WHERE id = %s',
            (user_id,)
        )
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        
        # Prevent deleting admin accounts
        if user['is_admin']:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Cannot delete admin accounts'}), 403
        
        # Delete user
        cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"🗑️ Admin deleted user: {user['username']}")
        
        return jsonify({
            'success': True,
            'message': 'User deleted successfully'
        })
        
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/usage-analytics', methods=['GET'])
def get_usage_analytics():
    """Get usage analytics including token usage and questions solved by each user (admin only)"""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get questions solved by each user from question_bank
        cursor.execute('''
            SELECT 
                u.id as user_id,
                u.username,
                u.full_name,
                COUNT(qb.id) as questions_solved,
                COUNT(CASE WHEN qb.source = 'solve_one' THEN 1 END) as solve_one_count,
                COUNT(CASE WHEN qb.source = 'answer_chapterwise' THEN 1 END) as chapterwise_count,
                COUNT(CASE WHEN qb.source = 'all_questions' THEN 1 END) as all_questions_count,
                COUNT(DISTINCT qb.subject) as subjects_covered,
                MIN(qb.created_at) as first_question_date,
                MAX(qb.created_at) as last_question_date
            FROM users u
            LEFT JOIN question_bank qb ON u.id = qb.user_id
            GROUP BY u.id, u.username, u.full_name
            ORDER BY questions_solved DESC
        ''')
        questions_by_user = cursor.fetchall()
        
        # Get token usage by user from usage_logs (if any logs exist)
        cursor.execute('''
            SELECT 
                u.id as user_id,
                u.username,
                u.full_name,
                COALESCE(SUM(ul.tokens_used), 0) as total_tokens,
                COUNT(ul.id) as api_calls,
                ul.model_name
            FROM users u
            LEFT JOIN usage_logs ul ON u.id = ul.user_id
            GROUP BY u.id, u.username, u.full_name, ul.model_name
            HAVING total_tokens > 0
            ORDER BY total_tokens DESC
        ''')
        token_usage = cursor.fetchall()
        
        # Get overall statistics
        cursor.execute('''
            SELECT 
                COUNT(DISTINCT user_id) as active_users,
                COUNT(*) as total_questions_solved,
                COUNT(DISTINCT subject) as total_subjects
            FROM question_bank
        ''')
        overall_stats = cursor.fetchone()
        
        # Format user analytics
        user_analytics = []
        for row in questions_by_user:
            user_analytics.append({
                'user_id': row['user_id'],
                'username': row['username'],
                'full_name': row['full_name'],
                'questions_solved': row['questions_solved'],
                'solve_one_count': row['solve_one_count'],
                'chapterwise_count': row['chapterwise_count'],
                'all_questions_count': row['all_questions_count'],
                'subjects_covered': row['subjects_covered'],
                'first_question_date': row['first_question_date'],
                'last_question_date': row['last_question_date']
            })
        
        # Format token usage
        token_analytics = []
        for row in token_usage:
            token_analytics.append({
                'user_id': row['user_id'],
                'username': row['username'],
                'full_name': row['full_name'],
                'total_tokens': row['total_tokens'],
                'api_calls': row['api_calls'],
                'model_name': row['model_name'] or 'N/A'
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'user_analytics': user_analytics,
            'token_analytics': token_analytics,
            'overall_stats': {
                'active_users': overall_stats['active_users'] if overall_stats else 0,
                'total_questions_solved': overall_stats['total_questions_solved'] if overall_stats else 0,
                'total_subjects': overall_stats['total_subjects'] if overall_stats else 0
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        conn.close()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
