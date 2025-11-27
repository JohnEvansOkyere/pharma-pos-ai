# Installation Guide for Python 3.13

Since Python 3.13 is very new, some database drivers don't have pre-built wheels yet. This guide shows you the best way to set up PHARMA-POS-AI with Python 3.13.

## ✅ Recommended: Use SQLite (Easiest)

SQLite is built into Python, requires no additional setup, and is **perfect for**:
- ✅ Development
- ✅ Single-pharmacy deployments
- ✅ Offline installations
- ✅ Quick testing
- ✅ Small to medium workloads

### Quick Setup

```bash
# 1. Install core dependencies (from backend directory)
cd backend
uv pip install -r requirements.txt
# OR
pip install -r requirements.txt

# 2. The .env file is already configured for SQLite!
# DATABASE_URL=sqlite:///./pharma_pos.db

# 3. Initialize database
cd ..
bash scripts/init_db.sh

# 4. Start backend
cd backend
python -m app.main

# Done! Backend running on http://localhost:8000
```

---

## 🐘 Optional: Use PostgreSQL

If you need PostgreSQL for production, you have two options:

### Option A: Build from Source (Python 3.13)

Since pre-built wheels aren't available yet for Python 3.13, you'll need to build from source:

```bash
# 1. Install PostgreSQL development libraries
# Ubuntu/Debian:
sudo apt-get update
sudo apt-get install libpq-dev python3-dev gcc

# macOS:
brew install postgresql

# 2. Install psycopg2 from source
pip install psycopg2-binary --no-binary psycopg2-binary

# 3. Update .env
# DATABASE_URL=postgresql://user:password@localhost:5432/pharma_pos
```

### Option B: Use Python 3.12 (Easier)

If you want to use PostgreSQL without building from source:

```bash
# 1. Install Python 3.12
# Ubuntu/Debian:
sudo apt install python3.12 python3.12-venv

# macOS:
brew install python@3.12

# 2. Create new venv with Python 3.12
python3.12 -m venv venv
source venv/bin/activate

# 3. Add psycopg2 to requirements
echo "psycopg2-binary==2.9.9" >> requirements.txt

# 4. Install
pip install -r requirements.txt
```

---

## 📦 What's Installed

With the current `requirements.txt`:

```
✅ FastAPI & Uvicorn      - Web framework
✅ SQLAlchemy             - Database ORM (works with SQLite & PostgreSQL)
✅ Alembic                - Database migrations
✅ Pydantic               - Data validation
✅ JWT & Auth             - Security
✅ APScheduler            - Background tasks
✅ HTTPx & Requests       - HTTP clients
✅ Python-dotenv          - Environment variables
✅ Pandas & Openpyxl      - Excel export
✅ Reportlab              - PDF generation
✅ Email-validator        - Email validation
✅ Pytest                 - Testing
```

**NOT included** (to avoid Python 3.13 compatibility issues):
- ❌ PostgreSQL drivers (install separately if needed)

---

## 🧪 Verify Installation

```bash
# Check Python version
python --version
# Should show: Python 3.13.x

# Check installed packages
pip list

# Test import
python -c "import fastapi, sqlalchemy, pydantic; print('✅ All core packages working!')"

# Start the backend
cd backend
python -m app.main
# Should see: Uvicorn running on http://0.0.0.0:8000
```

---

## 🔄 Database Migration Status

### SQLite (Default)
- ✅ Works perfectly with Python 3.13
- ✅ No additional setup
- ✅ Database file: `backend/pharma_pos.db`

### PostgreSQL
- ⚠️ Requires building from source on Python 3.13
- ✅ Will work once `psycopg2-binary` has Python 3.13 wheels (coming soon)
- ✅ Works out of the box with Python 3.12 and below

---

## 🚀 Quick Start Commands

```bash
# From project root directory

# 1. Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Initialize database (SQLite)
cd ..
bash scripts/init_db.sh

# 3. Start backend
cd backend
python -m app.main

# 4. Frontend setup (new terminal)
cd frontend
npm install
echo "VITE_API_URL=http://localhost:8000/api" > .env.local
npm run dev

# 5. Access at http://localhost:3000
# Login: admin / admin123
```

---

## ❓ Troubleshooting

### "No module named 'fastapi'"
```bash
# Make sure venv is activated
source venv/bin/activate  # Windows: venv\Scripts\activate

# Reinstall
pip install -r requirements.txt
```

### "Could not find a version that satisfies..."
```bash
# You might be using Python 3.14 or higher
python --version

# Use Python 3.13, 3.12, or 3.11
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### PostgreSQL connection errors
```bash
# Switch to SQLite in backend/.env
DATABASE_URL=sqlite:///./pharma_pos.db

# Restart backend
```

---

## 🎯 Recommended Setup

For **most users with Python 3.13**:
1. ✅ Use SQLite (default)
2. ✅ Install dependencies: `pip install -r requirements.txt`
3. ✅ Run migrations: `bash scripts/init_db.sh`
4. ✅ Start backend: `python -m app.main`
5. ✅ Done!

For **production with PostgreSQL**:
1. Use Python 3.12 (easier)
2. Or build psycopg2 from source
3. Or wait for official Python 3.13 wheels

---

## 📝 Summary

| Setup | Python Version | PostgreSQL | Complexity |
|-------|----------------|------------|------------|
| **SQLite (Recommended)** | 3.13 | ❌ Not needed | ⭐ Easy |
| PostgreSQL + Build | 3.13 | ✅ Yes | ⭐⭐⭐ Complex |
| PostgreSQL + Py3.12 | 3.12 | ✅ Yes | ⭐⭐ Medium |

**For quickest setup: Use SQLite with Python 3.13!** 🚀

You can always migrate to PostgreSQL later - SQLAlchemy makes it seamless.
