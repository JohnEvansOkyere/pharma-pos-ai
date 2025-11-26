# Complete Setup Guide

This guide walks you through setting up PHARMA-POS-AI from scratch on a fresh system.

---

## 🖥️ System Requirements

### Minimum Requirements
- **CPU**: Dual-core processor
- **RAM**: 4GB
- **Storage**: 2GB free space
- **OS**: Windows 10+, Ubuntu 20.04+, macOS 11+

### Recommended Requirements
- **CPU**: Quad-core processor
- **RAM**: 8GB
- **Storage**: 10GB SSD
- **OS**: Windows 11, Ubuntu 22.04, macOS 13+

---

## 📥 Installation

### Step 1: Install Prerequisites

#### Windows

1. **Install Python 3.9+**
   ```powershell
   # Download from python.org
   # Or use winget:
   winget install Python.Python.3.11
   ```

2. **Install Node.js 18+**
   ```powershell
   # Download from nodejs.org
   # Or use winget:
   winget install OpenJS.NodeJS
   ```

3. **Install PostgreSQL 15** (Optional)
   ```powershell
   winget install PostgreSQL.PostgreSQL
   ```

4. **Install Git**
   ```powershell
   winget install Git.Git
   ```

#### Linux (Ubuntu/Debian)

```bash
# Update package list
sudo apt update

# Install Python 3.9+
sudo apt install python3.11 python3.11-venv python3-pip -y

# Install Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install nodejs -y

# Install PostgreSQL 15 (Optional)
sudo apt install postgresql postgresql-contrib -y

# Install Git
sudo apt install git -y
```

#### macOS

```bash
# Install Homebrew if not installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.9+
brew install python@3.11

# Install Node.js 18+
brew install node@18

# Install PostgreSQL 15 (Optional)
brew install postgresql@15

# Install Git
brew install git
```

### Step 2: Clone Repository

```bash
git clone <your-repo-url>
cd pharma-pos-ai
```

### Step 3: Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### Step 4: Database Configuration

#### Option A: SQLite (Development/Small Deployments)

```bash
# Create .env file
cd ..  # Back to root
cp .env.example backend/.env

# Edit backend/.env
# Set DATABASE_URL=sqlite:///./pharma_pos.db
```

#### Option B: PostgreSQL (Production)

```bash
# Create database
# Windows (PowerShell as postgres user):
psql -U postgres
CREATE DATABASE pharma_pos;
CREATE USER pharma_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE pharma_pos TO pharma_user;
\q

# Linux/Mac:
sudo -u postgres psql
CREATE DATABASE pharma_pos;
CREATE USER pharma_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE pharma_pos TO pharma_user;
\q

# Edit backend/.env
# Set DATABASE_URL=postgresql://pharma_user:your_password@localhost:5432/pharma_pos
```

### Step 5: Initialize Database

```bash
cd backend

# Create initial migration
alembic revision --autogenerate -m "Initial migration"

# Run migrations
alembic upgrade head

# Seed database with sample data
cd ..
python scripts/seed_data.py
```

### Step 6: Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env.local
echo "VITE_API_URL=http://localhost:8000/api" > .env.local
```

### Step 7: Run Application

#### Terminal 1: Backend
```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
python -m app.main

# Or with uvicorn:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Terminal 2: Frontend
```bash
cd frontend
npm run dev
```

### Step 8: Access Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### Step 9: Login

Use default credentials:
- **Username**: `admin`
- **Password**: `admin123`

---

## 🔧 Configuration

### Backend Configuration (backend/.env)

```env
# Application
APP_NAME=PHARMA-POS-AI
APP_VERSION=1.0.0
DEBUG=False
ENVIRONMENT=production

# Database
DATABASE_URL=postgresql://pharma_user:password@localhost:5432/pharma_pos
# Or for SQLite: sqlite:///./pharma_pos.db

# Security
SECRET_KEY=generate-a-secure-random-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS (frontend URLs)
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]

# Notifications
ENABLE_EMAIL_NOTIFICATIONS=False
N8N_WEBHOOK_URL=

# Background Scheduler
ENABLE_BACKGROUND_SCHEDULER=True
EXPIRY_CHECK_HOUR=9
LOW_STOCK_CHECK_HOUR=10

# Business Rules
LOW_STOCK_THRESHOLD=10
EXPIRY_WARNING_DAYS=30
DEAD_STOCK_DAYS=90

# File Storage
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE=5242880

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/app.log
```

### Generate Secure SECRET_KEY

```python
# Run in Python
import secrets
print(secrets.token_urlsafe(32))
```

### Frontend Configuration (frontend/.env.local)

```env
VITE_API_URL=http://localhost:8000/api
```

---

## 🏗️ Production Deployment

### Option 1: Traditional Server

#### 1. Prepare Server
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install python3.11 python3.11-venv nginx postgresql -y
```

#### 2. Deploy Backend
```bash
# Create app directory
sudo mkdir -p /var/www/pharma-pos
sudo chown $USER:$USER /var/www/pharma-pos
cd /var/www/pharma-pos

# Clone repository
git clone <repo-url> .

# Setup virtual environment
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp ../.env.example .env
nano .env  # Edit with production values

# Run migrations
alembic upgrade head

# Create systemd service
sudo nano /etc/systemd/system/pharma-pos-backend.service
```

**Service file content:**
```ini
[Unit]
Description=PHARMA-POS-AI Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/pharma-pos/backend
Environment="PATH=/var/www/pharma-pos/backend/venv/bin"
ExecStart=/var/www/pharma-pos/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Start service
sudo systemctl daemon-reload
sudo systemctl start pharma-pos-backend
sudo systemctl enable pharma-pos-backend
```

#### 3. Deploy Frontend
```bash
cd /var/www/pharma-pos/frontend

# Build for production
npm install
npm run build

# Configure Nginx
sudo nano /etc/nginx/sites-available/pharma-pos
```

**Nginx configuration:**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Frontend
    location / {
        root /var/www/pharma-pos/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8000/api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/pharma-pos /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Option 2: Docker

See `docker-compose.yml` in project root.

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

---

## 🔐 Security Hardening

### 1. Change Default Credentials

```bash
# Login as admin and change password immediately
# Or use the backend to create new admin user
```

### 2. Configure Firewall

```bash
# Ubuntu/Debian
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

### 3. Enable HTTPS

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo certbot renew --dry-run
```

### 4. Secure Database

```bash
# PostgreSQL: Edit pg_hba.conf to restrict connections
sudo nano /etc/postgresql/15/main/pg_hba.conf

# Change from 'trust' to 'md5' or 'scram-sha-256'
```

### 5. Regular Updates

```bash
# Backend dependencies
cd backend
source venv/bin/activate
pip install --upgrade -r requirements.txt

# Frontend dependencies
cd frontend
npm update
```

---

## 📊 Monitoring & Logs

### Backend Logs

```bash
# Using systemd
sudo journalctl -u pharma-pos-backend -f

# Application logs
tail -f backend/logs/app.log
```

### Database Monitoring

```bash
# PostgreSQL
sudo -u postgres psql
SELECT * FROM pg_stat_activity;
```

### Performance Monitoring

Consider installing:
- **Prometheus** for metrics
- **Grafana** for dashboards
- **Sentry** for error tracking

---

## 💾 Backup Strategy

### Automated Daily Backups

```bash
# Create backup script
sudo nano /usr/local/bin/backup-pharma-pos.sh
```

**Script content:**
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/pharma-pos"

mkdir -p $BACKUP_DIR

# Backup database
pg_dump pharma_pos > $BACKUP_DIR/db_$DATE.sql

# Backup uploads
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz /var/www/pharma-pos/backend/uploads

# Keep only last 30 days
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed: $DATE"
```

```bash
# Make executable
sudo chmod +x /usr/local/bin/backup-pharma-pos.sh

# Add to crontab (daily at 2 AM)
sudo crontab -e
0 2 * * * /usr/local/bin/backup-pharma-pos.sh
```

---

## 🧪 Testing

### Backend Tests
```bash
cd backend
source venv/bin/activate
pytest

# With coverage
pytest --cov=app tests/
```

### Frontend Tests
```bash
cd frontend
npm run test
```

### Manual Testing Checklist
- [ ] User login/logout
- [ ] Create product
- [ ] Add product to cart
- [ ] Complete sale
- [ ] View dashboard
- [ ] Check notifications
- [ ] Test offline mode
- [ ] Print receipt (if applicable)

---

## 🔄 Updating the Application

### Update Backend
```bash
cd backend
git pull
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart pharma-pos-backend
```

### Update Frontend
```bash
cd frontend
git pull
npm install
npm run build
sudo systemctl restart nginx
```

---

## 🆘 Troubleshooting

### Backend Won't Start

1. Check logs:
   ```bash
   sudo journalctl -u pharma-pos-backend -n 50
   ```

2. Verify database connection:
   ```bash
   psql -U pharma_user -d pharma_pos -h localhost
   ```

3. Check port availability:
   ```bash
   sudo lsof -i :8000
   ```

### Frontend Not Loading

1. Clear browser cache
2. Check Nginx configuration:
   ```bash
   sudo nginx -t
   ```
3. View Nginx logs:
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```

### Database Issues

1. Check PostgreSQL status:
   ```bash
   sudo systemctl status postgresql
   ```

2. View PostgreSQL logs:
   ```bash
   sudo tail -f /var/log/postgresql/postgresql-15-main.log
   ```

---

## 📞 Support

For issues:
1. Check logs
2. Review this guide
3. Check API documentation at `/docs`
4. Open GitHub issue

---

## ✅ Post-Installation Checklist

After installation:
- [ ] Change all default passwords
- [ ] Configure backup schedule
- [ ] Set up monitoring
- [ ] Enable HTTPS
- [ ] Configure firewall
- [ ] Test all features
- [ ] Train users
- [ ] Document custom configurations

---

**Installation complete! 🎉**

Access your PHARMA-POS-AI system and start managing your pharmacy efficiently!
