# Docker Deployment Guide - Pharma POS AI

This guide will help you deploy the Pharma POS AI application using Docker and Docker Compose.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Environment Configuration](#environment-configuration)
4. [Database Schema](#database-schema)
5. [Building and Running](#building-and-running)
6. [Accessing the Application](#accessing-the-application)
7. [Managing the Application](#managing-the-application)
8. [Production Deployment](#production-deployment)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, ensure you have the following installed:

- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher
- **Git**: For cloning the repository

### Installing Docker

**Ubuntu/Debian:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker
```

**macOS:**
```bash
brew install --cask docker
```

**Windows:**
Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### Verify Installation

```bash
docker --version
docker-compose --version
```

---

## Quick Start

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd pharma-pos-ai
```

### 2. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit the .env file with your settings
nano .env  # or use your preferred editor
```

**Important:** Update these values in `.env`:
- `POSTGRES_PASSWORD`: Set a strong password
- `SECRET_KEY`: Generate using `openssl rand -hex 32`
- `VITE_API_URL`: Update for production deployment

### 3. Build and Start Services

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

### 4. Access the Application

- **Frontend**: http://localhost
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432

Provision the first administrator after deployment using the site-specific admin provisioning workflow. Do not ship or rely on shared default credentials.

---

## Environment Configuration

### Required Environment Variables

```bash
# Database
POSTGRES_DB=pharma_pos
POSTGRES_USER=pharma_user
POSTGRES_PASSWORD=<set-a-strong-site-specific-password>

# Backend
SECRET_KEY=YOUR_SECRET_KEY_MINIMUM_32_CHARACTERS
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Frontend
VITE_API_URL=http://localhost:8000
```

### Generating Secure Keys

```bash
# Generate a secure SECRET_KEY
openssl rand -hex 32

# Generate a secure password
openssl rand -base64 32
```

---

## Database Schema

The database is automatically initialized with:

### Tables Created:
- `users` - User accounts with role-based access
- `categories` - Product categories
- `suppliers` - Supplier information
- `products` - Product catalog
- `product_batches` - Batch tracking with expiry dates
- `sales` - Sales transactions
- `sale_items` - Individual items in sales
- `stock_adjustments` - Stock movement tracking
- `notifications` - System notifications
- `activity_logs` - Audit trail

### Seed Data Included:
- schema objects only unless you intentionally load site data
- no release default users should be shipped to customer environments

### Database Views:
- `low_stock_products` - Products below threshold
- `expiring_products` - Products expiring within 3 months
- `sales_summary` - Daily sales aggregation

---

## Building and Running

### Build Services

```bash
# Build all services
docker-compose build

# Build specific service
docker-compose build backend
docker-compose build frontend
```

### Start Services

```bash
# Start all services in detached mode
docker-compose up -d

# Start specific services
docker-compose up -d db backend

# Start with build
docker-compose up -d --build
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ deletes database data)
docker-compose down -v

# Stop specific service
docker-compose stop backend
```

---

## Accessing the Application

### Frontend (React)
```
URL: http://localhost
Port: 80
```

### Backend API (FastAPI)
```
URL: http://localhost:8000
API Docs: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc
Health Check: http://localhost:8000/health
```

### PostgreSQL Database
```
Host: localhost
Port: 5432
Database: pharma_pos
User: pharma_user
Password: (from .env file)
```

#### Connecting to PostgreSQL

```bash
# Using docker-compose
docker-compose exec db psql -U pharma_user -d pharma_pos

# Using psql client directly
psql -h localhost -p 5432 -U pharma_user -d pharma_pos
```

---

## Managing the Application

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f db

# Last 100 lines
docker-compose logs --tail=100 backend
```

### Check Service Status

```bash
# List running containers
docker-compose ps

# Check health status
docker-compose ps --format table
```

### Execute Commands in Containers

```bash
# Backend container
docker-compose exec backend bash

# Database container
docker-compose exec db bash

# Run migrations (if needed)
docker-compose exec backend alembic upgrade head
```

### Restart Services

```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart backend
```

### Update Services

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose up -d --build
```

---

## Production Deployment

### 1. Update Environment Variables

```bash
# Production .env settings
ENVIRONMENT=production
DEBUG=false
POSTGRES_PASSWORD=<strong-password>
SECRET_KEY=<strong-secret-key>
VITE_API_URL=https://api.yourdomain.com
```

### 2. Use Production Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  db:
    restart: always
    
  backend:
    restart: always
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    
  frontend:
    restart: always
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./ssl:/etc/nginx/ssl:ro

  # Add nginx reverse proxy for SSL
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - frontend
      - backend
```

### 3. Deploy

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 4. Set Up SSL/TLS

```bash
# Using Let's Encrypt with Certbot
docker run -it --rm \
  -v /etc/letsencrypt:/etc/letsencrypt \
  -p 80:80 \
  certbot/certbot certonly --standalone \
  -d yourdomain.com -d www.yourdomain.com
```

### 5. Security Checklist

- [ ] Change all default passwords
- [ ] Generate new SECRET_KEY
- [ ] Enable HTTPS/SSL
- [ ] Configure firewall rules
- [ ] Set up database backups
- [ ] Enable application logging
- [ ] Configure CORS properly
- [ ] Set up monitoring and alerts

---

## Troubleshooting

### Common Issues

#### 1. Port Already in Use

```bash
# Check what's using the port
sudo lsof -i :8000
sudo lsof -i :5432

# Kill the process
sudo kill -9 <PID>
```

#### 2. Database Connection Failed

```bash
# Check database logs
docker-compose logs db

# Verify database is running
docker-compose ps db

# Test connection
docker-compose exec backend python -c "from app.db.base import engine; engine.connect()"
```

#### 3. Frontend Can't Connect to Backend

```bash
# Check VITE_API_URL in .env
cat .env | grep VITE_API_URL

# Rebuild frontend
docker-compose build --no-cache frontend
docker-compose up -d frontend
```

#### 4. Permission Denied Errors

```bash
# Fix permissions
sudo chown -R $USER:$USER .

# For specific directories
sudo chmod -R 755 backend
sudo chmod -R 755 frontend
```

#### 5. Out of Memory

```bash
# Increase Docker memory limit
# On Docker Desktop: Settings > Resources > Memory

# Clean up Docker system
docker system prune -a
docker volume prune
```

### Reset Everything

```bash
# ⚠️ WARNING: This deletes ALL data!

# Stop and remove containers, networks, volumes
docker-compose down -v

# Remove images
docker-compose down --rmi all

# Clean Docker system
docker system prune -a --volumes

# Start fresh
docker-compose up -d --build
```

### Database Backup

```bash
# Backup database
docker-compose exec db pg_dump -U pharma_user pharma_pos > backup_$(date +%Y%m%d).sql

# Restore database
docker-compose exec -T db psql -U pharma_user pharma_pos < backup_20240101.sql
```

### View Container Resource Usage

```bash
docker stats
```

### Debug Mode

```bash
# Run services without detaching
docker-compose up

# Run with verbose logging
docker-compose --verbose up
```

---

## Maintenance Commands

### Database Maintenance

```bash
# Vacuum database
docker-compose exec db psql -U pharma_user -d pharma_pos -c "VACUUM ANALYZE;"

# Check database size
docker-compose exec db psql -U pharma_user -d pharma_pos -c "\l+"

# List all tables
docker-compose exec db psql -U pharma_user -d pharma_pos -c "\dt"
```

### Monitor Logs

```bash
# Follow logs with timestamps
docker-compose logs -f --timestamps

# Filter logs
docker-compose logs -f backend | grep ERROR
```

---

## Additional Resources

- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **React Documentation**: https://react.dev/
- **PostgreSQL Documentation**: https://www.postgresql.org/docs/
- **Docker Documentation**: https://docs.docker.com/
- **Nginx Documentation**: https://nginx.org/en/docs/

---

## Support

For issues and questions:
1. Check the logs: `docker-compose logs -f`
2. Review this troubleshooting guide
3. Check GitHub issues
4. Contact support

---

**Last Updated**: November 2024
**Version**: 1.0.0
