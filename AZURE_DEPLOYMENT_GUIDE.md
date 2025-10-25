# Azure Deployment - Connecting Frontend to Backend

## 🎯 Overview

**Your Setup:**
- **Frontend:** React app on Azure Static Web Apps
- **Backend:** Python Flask API on Azure Function App

**Goal:** Connect them securely with proper CORS and environment configuration.

---

## 📋 Step 1: Get Your Azure URLs

### Backend (Function App)
1. Go to Azure Portal → Function App
2. Click on your Function App name
3. Copy the **URL** (looks like):
   ```
   https://qadam-backend.azurewebsites.net
   ```

### Frontend (Static Web App)
1. Go to Azure Portal → Static Web Apps
2. Click on your Static Web App name
3. Copy the **URL** (looks like):
   ```
   https://happy-ocean-12345.azurestaticapps.net
   ```

---

## 🔧 Step 2: Configure CORS on Function App

### Option 1: Via Azure Portal (Easiest)

1. **Go to Function App → CORS**
   - Azure Portal → Your Function App
   - Left sidebar → API → CORS

2. **Add Allowed Origins:**
   ```
   https://happy-ocean-12345.azurestaticapps.net
   ```
   (Replace with YOUR Static Web App URL)

3. **Additional Settings:**
   - ✅ Enable "Enable Access-Control-Allow-Credentials"
   - ✅ Add `http://localhost:3000` for local development

4. **Click "Save"**

### Option 2: Via Code (app.py)

Update your `app.py`:

```python
from flask import Flask
from flask_cors import CORS

app = Flask(__name__)

# CORS Configuration for Azure
ALLOWED_ORIGINS = [
    'https://happy-ocean-12345.azurestaticapps.net',  # Your Static Web App
    'http://localhost:3000',  # Local development
    'http://localhost:5000'   # Local backend testing
]

CORS(app, 
     origins=ALLOWED_ORIGINS,
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])

# Rest of your code...
```

---

## 🌐 Step 3: Update Frontend Environment Variables

### Create Environment Files

**For Production (Azure):**

Create `.env.production` in your React app root:

```bash
# Azure Backend URL
REACT_APP_API_URL=https://qadam-backend.azurewebsites.net

# Other production settings
REACT_APP_ENV=production
```

**For Development (Local):**

Create `.env.development`:

```bash
# Local Backend URL
REACT_APP_API_URL=http://localhost:5000

# Development settings
REACT_APP_ENV=development
```

### Update API Calls in React

**Before (Hardcoded):**
```javascript
const response = await axios.get('http://localhost:5000/api/papers');
```

**After (Environment Variable):**
```javascript
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

const response = await axios.get(`${API_URL}/api/papers`);
```

### Create API Configuration File

**src/config/api.js:**
```javascript
// API Configuration
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

export const API_ENDPOINTS = {
  // Papers
  PAPERS: `${API_URL}/api/papers`,
  UPLOAD_PAPER: `${API_URL}/api/upload-paper`,
  DELETE_PAPER: `${API_URL}/api/delete-paper`,
  
  // Questions
  PARSE_QUESTIONS: `${API_URL}/api/parse-questions`,
  PARSE_SINGLE_QUESTION: `${API_URL}/api/parse-single-question`,
  
  // Textbooks
  TEXTBOOKS: `${API_URL}/api/textbooks`,
  UPLOAD_TEXTBOOK: `${API_URL}/api/upload-textbook`,
  TEXTBOOK_PDF: (id) => `${API_URL}/api/textbook-pdf/${id}`,
  
  // AI Services
  MAP_QUESTIONS: `${API_URL}/api/map-questions-to-chapters`,
  GENERATE_SOLUTION: `${API_URL}/api/generate-solution`,
  
  // Auth
  LOGIN: `${API_URL}/api/login`,
  REGISTER: `${API_URL}/api/register`,
  LOGOUT: `${API_URL}/api/logout`,
};

export default API_URL;
```

**Usage in Components:**
```javascript
import { API_ENDPOINTS } from './config/api';

// Instead of hardcoded URLs
const response = await axios.get(API_ENDPOINTS.PAPERS);
```

---

## 🔐 Step 4: Configure Static Web App Settings

### Add Environment Variables to Static Web App

1. **Go to Azure Portal → Static Web Apps**
2. **Click "Configuration"** (left sidebar)
3. **Add Application Settings:**

   | Name | Value |
   |------|-------|
   | `REACT_APP_API_URL` | `https://qadam-backend.azurewebsites.net` |
   | `REACT_APP_ENV` | `production` |

4. **Click "Save"**

5. **Redeploy** your Static Web App (triggers automatic rebuild)

---

## 🚀 Step 5: Update Backend Configuration

### Function App Settings

1. **Go to Azure Portal → Function App**
2. **Click "Configuration"** (left sidebar)
3. **Add Application Settings:**

   | Name | Value |
   |------|-------|
   | `ALLOWED_ORIGINS` | `https://happy-ocean-12345.azurestaticapps.net` |
   | `GROQ_API_KEY` | `your_groq_api_key` |
   | `SMTP_SERVER` | `smtp.gmail.com` |
   | `SMTP_PORT` | `587` |
   | `SMTP_USER` | `your_email@gmail.com` |
   | `SMTP_PASSWORD` | `your_app_password` |

4. **Click "Save"**
5. **Restart** Function App

---

## 🗄️ Step 6: Set Up Azure Database for MySQL

### A. Create MySQL Flexible Server

1. **Go to Azure Portal** → "+ Create a resource"
2. **Search for:** "Azure Database for MySQL Flexible Server"
3. **Click "Create"**

### B. Configure MySQL Server

**Basics Tab:**
```
Resource Group: qadam-resources (same as Function App)
Server Name: qadam-mysql-server
Region: Same as your Function App
MySQL Version: 8.0
Workload Type: Development (for testing) or Production
```

**Compute + Storage:**
```
Compute Tier: Burstable (cheapest)
Compute Size: B1ms (1 vCore, 2 GiB RAM)
Storage: 20 GiB
Storage Auto-growth: Enabled
```

**Authentication:**
```
Authentication Method: MySQL authentication only
Admin Username: adminuser
Password: [Create strong password]
Confirm Password: [Same password]
```

**Networking Tab:**
```
Connectivity Method: Public access (0.0.0.0/0) and selected networks
Firewall Rules:
  ✅ Allow public access from any Azure service
  ✅ Add current client IP address
  ✅ Add your Function App's outbound IPs (see below)
```

**Review + Create:**
- Review settings
- Click "Create"
- Wait 5-10 minutes for deployment

### C. Get Function App Outbound IPs

1. **Go to Function App** → Settings → Properties
2. **Scroll to "Outbound IP addresses"**
3. **Copy all IP addresses** (comma-separated list)
4. **Example:**
   ```
   20.62.134.1, 20.62.134.2, 20.62.134.3
   ```

### D. Add Function App IPs to MySQL Firewall

1. **Go to MySQL Server** → Networking
2. **Under Firewall rules**, click "+ Add firewall rule"
3. **Add each Function App IP:**
   ```
   Rule Name: FunctionApp-IP-1
   Start IP: 20.62.134.1
   End IP: 20.62.134.1
   ```
4. **Repeat for all outbound IPs**
5. **Click "Save"**

### E. Create Database

**Option 1: Azure Cloud Shell**
```bash
# Open Cloud Shell in Azure Portal
mysql -h qadam-mysql-server.mysql.database.azure.com -u adminuser -p

# Enter password when prompted
CREATE DATABASE qadam_academic;
SHOW DATABASES;
exit;
```

**Option 2: MySQL Workbench**
```
Host: qadam-mysql-server.mysql.database.azure.com
Port: 3306
Username: adminuser
Password: [your password]

# Then run:
CREATE DATABASE qadam_academic;
```

### F. Configure Function App with MySQL Connection

1. **Go to Function App** → Configuration → Application settings
2. **Add MySQL settings:**

| Name | Value | Example |
|------|-------|---------|
| `MYSQL_HOST` | MySQL server hostname | `qadam-mysql-server.mysql.database.azure.com` |
| `MYSQL_PORT` | MySQL port | `3306` |
| `MYSQL_USER` | Admin username | `adminuser` |
| `MYSQL_PASSWORD` | Admin password | `your_secure_password` |
| `MYSQL_DATABASE` | Database name | `qadam_academic` |

3. **Click "Save"**
4. **Restart Function App**

### G. Initialize Database Tables

**Option 1: Run from Local Machine**
```bash
# Update your local .env with Azure MySQL credentials
MYSQL_HOST=qadam-mysql-server.mysql.database.azure.com
MYSQL_PORT=3306
MYSQL_USER=adminuser
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=qadam_academic

# Run initialization script
python database.py
```

**Option 2: Use Azure Function**
- Deploy your Function App with database.py
- Trigger initialization via HTTP endpoint
- Or use Azure Cloud Shell to run the script

### H. Verify Connection

**Test from Function App:**
```bash
# Check Function App logs
# Should see: "✓ Connected to MySQL database"
```

**Test from Cloud Shell:**
```bash
mysql -h qadam-mysql-server.mysql.database.azure.com -u adminuser -p qadam_academic

# List tables
SHOW TABLES;

# Should see: users, papers, parsed_questions, textbooks, etc.
```

### I. Security Best Practices

**1. Enable SSL/TLS (Recommended):**
```python
# In db_config.py or database.py
MYSQL_CONFIG = {
    'host': os.getenv('MYSQL_HOST'),
    'user': os.getenv('MYSQL_USER'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DATABASE'),
    'ssl_disabled': False,  # Enable SSL
}
```

**2. Restrict Firewall Rules:**
- Remove "Allow from any Azure service" after testing
- Only allow specific Function App IPs
- Don't allow 0.0.0.0/0 in production

**3. Use Private Endpoint (Advanced):**
- For production, consider Azure Private Link
- Connects Function App to MySQL via private network
- No public internet exposure

**4. Enable Backups:**
- Azure Portal → MySQL Server → Backup
- Automated backups: Enabled (default)
- Retention: 7-35 days
- Geo-redundant backup: Optional

### J. Cost Optimization

**Development/Testing:**
```
Tier: Burstable B1ms
Storage: 20 GiB
Cost: ~$15-20/month
```

**Production:**
```
Tier: General Purpose D2ds_v4
Storage: 32-64 GiB
Cost: ~$100-150/month
```

**Cost-Saving Tips:**
- Start with Burstable tier
- Monitor storage usage
- Set up cost alerts
- Use reserved capacity for long-term (1-3 years)
- Stop server when not in use (dev only)

---

## 🧪 Step 7: Test the Connection

### Test Backend Directly

```bash
# Test if backend is accessible
curl https://qadam-backend.azurewebsites.net/api/papers

# Should return JSON response
```

### Test from Frontend

**Create a test component:**

```javascript
// src/components/ConnectionTest.js
import React, { useState } from 'react';
import axios from 'axios';
import { API_ENDPOINTS } from '../config/api';

function ConnectionTest() {
  const [status, setStatus] = useState('Not tested');
  const [data, setData] = useState(null);

  const testConnection = async () => {
    try {
      setStatus('Testing...');
      const response = await axios.get(API_ENDPOINTS.PAPERS);
      setStatus('✅ Connected!');
      setData(response.data);
    } catch (error) {
      setStatus('❌ Failed: ' + error.message);
      console.error(error);
    }
  };

  return (
    <div style={{ padding: '20px' }}>
      <h2>Backend Connection Test</h2>
      <button onClick={testConnection}>Test Connection</button>
      <p>Status: {status}</p>
      {data && <pre>{JSON.stringify(data, null, 2)}</pre>}
    </div>
  );
}

export default ConnectionTest;
```

---

## 🔍 Troubleshooting

### Issue 1: CORS Error

**Error:**
```
Access to XMLHttpRequest has been blocked by CORS policy
```

**Solution:**
1. Verify CORS settings in Function App
2. Ensure Static Web App URL is in allowed origins
3. Check for typos in URLs (https vs http)
4. Restart Function App after CORS changes

### Issue 2: 404 Not Found

**Error:**
```
GET https://qadam-backend.azurewebsites.net/api/papers 404
```

**Solution:**
1. Verify Function App is deployed correctly
2. Check function routes in `app.py`
3. Ensure Function App is running (not stopped)
4. Check deployment logs in Azure Portal

### Issue 3: Environment Variables Not Working

**Error:**
```
process.env.REACT_APP_API_URL is undefined
```

**Solution:**
1. Ensure variable starts with `REACT_APP_`
2. Rebuild Static Web App after adding variables
3. Check Configuration in Azure Portal
4. Clear browser cache

### Issue 4: Authentication Issues

**Error:**
```
401 Unauthorized
```

**Solution:**
1. Check if credentials are being sent
2. Verify CORS allows credentials
3. Check session/token configuration
4. Ensure cookies are allowed

### Issue 5: MySQL Connection Failed

**Error:**
```
Can't connect to MySQL server on 'qadam-mysql-server.mysql.database.azure.com'
```

**Solution:**
1. **Check Firewall Rules:**
   - Go to MySQL Server → Networking
   - Verify Function App IPs are in firewall rules
   - Ensure "Allow Azure services" is enabled

2. **Verify Credentials:**
   - Check MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD in Function App config
   - Test connection from Azure Cloud Shell
   - Ensure database name is correct

3. **Check Function App Logs:**
   ```bash
   # Azure Portal → Function App → Log Stream
   # Look for MySQL connection errors
   ```

4. **Test from Cloud Shell:**
   ```bash
   mysql -h qadam-mysql-server.mysql.database.azure.com -u adminuser -p
   # If this fails, issue is with MySQL server/firewall
   ```

### Issue 6: Database Tables Not Created

**Error:**
```
Table 'qadam_academic.users' doesn't exist
```

**Solution:**
1. **Run database initialization:**
   ```bash
   # Update .env with Azure MySQL credentials
   python database.py
   ```

2. **Verify tables exist:**
   ```bash
   mysql -h qadam-mysql-server.mysql.database.azure.com -u adminuser -p qadam_academic
   SHOW TABLES;
   ```

3. **Check initialization logs:**
   - Should see "✓ Connected to MySQL database"
   - Should see table creation messages

### Issue 7: SSL/TLS Connection Error

**Error:**
```
SSL connection error: SSL is required
```

**Solution:**
1. **Enable SSL in connection:**
   ```python
   MYSQL_CONFIG = {
       'host': os.getenv('MYSQL_HOST'),
       'user': os.getenv('MYSQL_USER'),
       'password': os.getenv('MYSQL_PASSWORD'),
       'database': os.getenv('MYSQL_DATABASE'),
       'ssl_disabled': False
   }
   ```

2. **Or temporarily disable SSL requirement:**
   - Azure Portal → MySQL Server → Server parameters
   - Search for "require_secure_transport"
   - Set to "OFF" (not recommended for production)

---

## 📝 Complete Example

### Backend (app.py)

```python
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)

# Get allowed origins from environment
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
ALLOWED_ORIGINS = [
    FRONTEND_URL,
    'http://localhost:3000',
    'http://localhost:5000'
]

CORS(app, 
     origins=ALLOWED_ORIGINS,
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'message': 'Backend is running',
        'environment': os.getenv('ENVIRONMENT', 'development')
    })

@app.route('/api/papers', methods=['GET'])
def get_papers():
    # Your existing code
    return jsonify({'papers': []})

if __name__ == '__main__':
    app.run()
```

### Frontend (src/config/api.js)

```javascript
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

export const API_ENDPOINTS = {
  HEALTH: `${API_URL}/api/health`,
  PAPERS: `${API_URL}/api/papers`,
  // ... other endpoints
};

export default API_URL;
```

### Frontend (src/App.js)

```javascript
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API_ENDPOINTS } from './config/api';

function App() {
  const [backendStatus, setBackendStatus] = useState('Checking...');

  useEffect(() => {
    // Check backend connection on mount
    axios.get(API_ENDPOINTS.HEALTH)
      .then(response => {
        setBackendStatus('✅ Connected to backend');
        console.log('Backend:', response.data);
      })
      .catch(error => {
        setBackendStatus('❌ Backend connection failed');
        console.error('Backend error:', error);
      });
  }, []);

  return (
    <div>
      <p>Backend Status: {backendStatus}</p>
      {/* Rest of your app */}
    </div>
  );
}

export default App;
```

---

## 🎯 Deployment Checklist

### Backend (Function App)
- [ ] CORS configured with Static Web App URL
- [ ] Environment variables set (API keys, SMTP, etc.)
- [ ] MySQL environment variables configured
- [ ] Function App is running (not stopped)
- [ ] Health check endpoint works
- [ ] Logs show no errors
- [ ] MySQL connection successful

### Database (Azure MySQL Flexible Server)
- [ ] MySQL Flexible Server created
- [ ] Database `qadam_academic` created
- [ ] Firewall rules configured with Function App IPs
- [ ] "Allow Azure services" enabled
- [ ] Admin credentials saved securely
- [ ] Database tables initialized (`python database.py`)
- [ ] Connection tested from Cloud Shell
- [ ] SSL/TLS configured (optional but recommended)
- [ ] Automated backups enabled
- [ ] Cost alerts set up

### Frontend (Static Web App)
- [ ] `.env.production` created with backend URL
- [ ] Environment variables added in Azure Portal
- [ ] All API calls use `process.env.REACT_APP_API_URL`
- [ ] Static Web App redeployed after config changes
- [ ] Browser console shows no CORS errors

### Testing
- [ ] Backend health check accessible
- [ ] Frontend can fetch data from backend
- [ ] MySQL connection works from Function App
- [ ] Database queries execute successfully
- [ ] File uploads work
- [ ] Authentication works
- [ ] All API endpoints tested
- [ ] No errors in Function App logs
- [ ] No errors in MySQL slow query log

---

## 🔗 Quick Reference

### Your URLs (Replace with actual)
```bash
# Frontend
https://happy-ocean-12345.azurestaticapps.net

# Backend
https://qadam-backend.azurewebsites.net

# MySQL Server
qadam-mysql-server.mysql.database.azure.com

# Health Check
https://qadam-backend.azurewebsites.net/api/health
```

### Environment Variables

**Static Web App:**
```
REACT_APP_API_URL=https://qadam-backend.azurewebsites.net
REACT_APP_ENV=production
```

**Function App:**
```
# Frontend & CORS
FRONTEND_URL=https://happy-ocean-12345.azurestaticapps.net
SECRET_KEY=your-random-secret-key

# API Keys
GROQ_API_KEY=your_groq_api_key

# Email (Optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password

# MySQL Database
MYSQL_HOST=qadam-mysql-server.mysql.database.azure.com
MYSQL_PORT=3306
MYSQL_USER=adminuser
MYSQL_PASSWORD=your_secure_password
MYSQL_DATABASE=qadam_academic
```

**MySQL Server:**
```
Server Name: qadam-mysql-server.mysql.database.azure.com
Port: 3306
Admin Username: adminuser
Database: qadam_academic
```

---

## 🚀 Next Steps

1. **Set up custom domain** (optional)
2. **Enable HTTPS** (automatic with Azure)
3. **Set up monitoring** (Application Insights)
4. **Configure auto-scaling**
5. **Set up CI/CD** (GitHub Actions)

---

**Need help?** Check Azure Portal logs or contact support.
