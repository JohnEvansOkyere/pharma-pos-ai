# 🚀 Quick Start Guide - Pharma POS AI

Get your Pharma POS AI application running in minutes!

## 📋 Prerequisites

- Docker (20.10+)
- Docker Compose (2.0+)

## ⚡ Quick Deploy (3 Steps)

### Step 1: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Generate a secure secret key
openssl rand -hex 32

# Edit .env and update:
# - POSTGRES_PASSWORD (change from default)
# - SECRET_KEY (paste generated key above)
# - VITE_API_URL (if deploying remotely)
nano .env
```

### Step 2: Deploy Application

**Option A: Using deployment script (Recommended)**
```bash
./deploy.sh
# Select option 1: Deploy application
```

**Option B: Manual deployment**
```bash
docker-compose up -d --build
```

### Step 3: Access Application

- **Frontend**: http://localhost / http://localhost:8080
- **Backend API**: http://localhost:8000/docs
- **Database**: localhost:5432

## 🔑 Default Login Credentials

| Role | Username | Password |
|------|----------|----------|
| Admin | admin | password123 | 
| Manager | manager1 | password123 |
| Cashier | cashier1 | password123 |

⚠️ **Change these immediately after first login!**
 
## 📊 Database Information

The database is automatically initialized with:
- ✅ Complete schema (users, products, sales, etc.)
- ✅ 4 test users
- ✅ 12 product categories
- ✅ 5 suppliers
- ✅ 15 sample products with batches
- ✅ Sample notifications

## 🔧 Common Commands

```bash
# View logs
docker-compose logs -f

# Stop application
docker-compose down

# Restart application
docker-compose restart

# Check status
docker-compose ps

# Access database
docker-compose exec db psql -U pharma_user -d pharma_pos

# Backup database
docker-compose exec db pg_dump -U pharma_user pharma_pos > backup.sql

# View backend logs only
docker-compose logs -f backend

# Reset everything (⚠️ deletes all data!)
docker-compose down -v
```

## 🛠️ Troubleshooting

### Port Already in Use

```bash
# Check what's using port 8000
sudo lsof -i :8000

# Check what's using port 80
sudo lsof -i :80

# Kill the process
sudo kill -9 <PID>
```

### Backend Can't Connect to Database

```bash
# Check database is running
docker-compose ps db

# View database logs
docker-compose logs db

# Restart database
docker-compose restart db
```

### Frontend Shows "Network Error"

```bash
# Check VITE_API_URL in .env
cat .env | grep VITE_API_URL

# Should be: VITE_API_URL=http://localhost:8000

# Rebuild frontend
docker-compose build --no-cache frontend
docker-compose up -d frontend
```

## 📂 Project Structure

```
pharma-pos-ai/
├── backend/              # FastAPI backend
│   ├── Dockerfile
│   └── app/
├── frontend/             # React frontend
│   ├── Dockerfile
│   ├── nginx.conf
│   └── src/
├── database/             # Database schema & seeds
│   ├── init.sql
│   ├── seed.sql
│   └── README.md
├── docker-compose.yml    # Docker orchestration
├── .env.example          # Environment template
├── deploy.sh             # Deployment script
└── DOCKER_DEPLOYMENT.md  # Full documentation
```

## 🔐 Security Checklist

Before deploying to production:

- [ ] Change all default passwords
- [ ] Generate new SECRET_KEY
- [ ] Set strong POSTGRES_PASSWORD
- [ ] Update VITE_API_URL to production domain
- [ ] Set ENVIRONMENT=production
- [ ] Set DEBUG=false
- [ ] Enable HTTPS/SSL
- [ ] Configure firewall
- [ ] Set up database backups
- [ ] Review CORS settings

## 📚 Documentation

- **Full Deployment Guide**: [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)
- **Database Documentation**: [database/README.md](database/README.md)
- **Files Summary**: [DOCKER_FILES_SUMMARY.md](DOCKER_FILES_SUMMARY.md)

## 🆘 Need Help?

1. Check logs: `docker-compose logs -f`
2. Review [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)
3. Check service status: `docker-compose ps`
4. Verify .env file settings

## 🎯 Next Steps

After deployment:

1. ✅ Login with admin credentials
2. ✅ Change all default passwords
3. ✅ Add your categories and suppliers
4. ✅ Import your products
5. ✅ Create user accounts for your staff
6. ✅ Configure system settings
7. ✅ Start selling! 🎉

---

**Happy Selling! 💊💰**
