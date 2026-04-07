# Quick Start Guide

Get PHARMA-POS-AI running in 5 minutes!

## 🚀 Prerequisites

- Python 3.9+
- Node.js 18+
- Git

## 📦 Installation

```bash
# 1. Clone repository
git clone <repo-url>
cd pharma-pos-ai

# 2. Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Create .env
cp ../.env backend/.env

# 4. Initialize database
cd ..
bash scripts/init_db.sh

# 5. Start backend (in terminal 1)
cd backend
source venv/bin/activate
python -m app.main

# 6. Frontend setup (in terminal 2)
cd frontend
npm install
echo "VITE_API_URL=http://localhost:8000/api" > .env.local

# 7. Start frontend
npm run dev
```

## 🌐 Access

- Frontend: **http://localhost:3000**
- Backend: **http://localhost:8000**
- API Docs: **http://localhost:8000/docs**

## 🔑 Login

- Username: `admin`
- Password: `admin123`

## ✅ Done!

Start using PHARMA-POS-AI!

For detailed setup, see [SETUP_GUIDE.md](./docs/SETUP_GUIDE.md)
