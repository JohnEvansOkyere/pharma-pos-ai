# PHARMA-POS-AI 🏥💊

**Offline-Capable Pharmaceutical Point-of-Sale System with AI Insights**

A modern, production-grade POS system built specifically for pharmacies, featuring complete offline functionality, real-time inventory management, AI-powered insights, and comprehensive reporting.

---

## 🌟 Features

### Core Functionality
- ✅ **Inventory Management** - Track products, batches, categories, and expiry dates
- ✅ **Point of Sale (POS)** - Fast, intuitive sales interface with barcode support
- ✅ **Sales Tracking** - Complete transaction history and daily summaries
- ✅ **Supplier Management** - Manage vendors and purchase orders
- ✅ **User Management** - Role-based access (Admin, Manager, Cashier)
- ✅ **Notifications** - Automated alerts for expiry and low stock

### Advanced Features
- 🤖 **AI Insights** - Rule-based analytics for:
  - Dead stock detection
  - Reorder quantity suggestions
  - Sales pattern analysis
  - Profit margin analysis
- 📊 **Dashboard Analytics** - KPIs, charts, and trends
- 📱 **Responsive UI** - Works on desktop, tablet, and mobile
- 🌙 **Dark Mode** - Eye-friendly interface
- 📴 **Offline Support** - Service Workers for offline caching
- 🔐 **Security** - JWT authentication with role-based permissions
- 🔔 **Background Scheduler** - Automated daily checks

---

## 🏗️ Architecture

### Backend Stack
- **FastAPI** - Modern Python web framework
- **PostgreSQL / SQLite** - Flexible database options
- **SQLAlchemy** - ORM for database operations
- **Alembic** - Database migrations
- **APScheduler** - Background task scheduling
- **JWT** - Secure authentication

### Frontend Stack
- **React 18** - Modern UI framework
- **TypeScript** - Type-safe development
- **Vite** - Lightning-fast build tool
- **TailwindCSS** - Utility-first styling
- **Zustand** - State management
- **Recharts** - Data visualization
- **React Hot Toast** - Notifications
- **PWA** - Progressive Web App support

---

## 📁 Project Structure

```
pharma-pos-ai/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── endpoints/     # API route handlers
│   │   │   │   ├── auth.py
│   │   │   │   ├── products.py
│   │   │   │   ├── sales.py
│   │   │   │   ├── dashboard.py
│   │   │   │   ├── notifications.py
│   │   │   │   └── insights.py
│   │   │   └── dependencies/  # Auth & permissions
│   │   ├── core/              # Config & security
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   │   ├── notification_service.py
│   │   │   ├── ai_insights.py
│   │   │   └── scheduler.py
│   │   ├── db/                # Database config
│   │   └── main.py            # FastAPI app
│   ├── alembic/               # Database migrations
│   ├── requirements.txt
│   └── alembic.ini
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/        # Layout components
│   │   │   └── common/        # Reusable components
│   │   ├── pages/             # Page components
│   │   ├── services/          # API client
│   │   ├── stores/            # Zustand stores
│   │   ├── styles/            # CSS files
│   │   └── main.tsx           # Entry point
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
├── scripts/                   # Utility scripts
│   ├── seed_data.py
│   └── init_db.sh
└── docs/                      # Documentation
```

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.9+**
- **Node.js 18+**
- **PostgreSQL 13+** (or SQLite for development)

### 1. Clone Repository
```bash
git clone <your-repo-url>
cd pharma-pos-ai
```

### 2. Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp ../.env.example .env
# Edit .env with your configuration

# Initialize database
cd ..
bash scripts/init_db.sh

# Or manually:
cd backend
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
python ../scripts/seed_data.py

# Run backend
python -m app.main
# Or with uvicorn:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will run at: **http://localhost:8000**
API Documentation: **http://localhost:8000/docs**

### 3. Frontend Setup

```bash
# Open new terminal
cd frontend

# Install dependencies
npm install

# Create environment file
echo "VITE_API_URL=http://localhost:8000/api" > .env.local

# Run development server
npm run dev
```

Frontend will run at: **http://localhost:3000**

### 4. Login

Default credentials:
- **Admin**: `admin` / `admin123`
- **Manager**: `manager` / `manager123`
- **Cashier**: `cashier` / `cashier123`

---

## 📖 Usage Guide

### POS Workflow
1. Navigate to **POS** page
2. Search for products by name, SKU, or barcode
3. Click products to add to cart
4. Adjust quantities if needed
5. Enter customer info (optional)
6. Select payment method
7. Enter amount paid
8. Click "Complete Sale"
9. Invoice is generated automatically

### Inventory Management
1. Go to **Products** page
2. View all products with stock levels
3. Add new products with batches
4. Track expiry dates
5. Receive low stock alerts

### Dashboard Insights
- View today's sales and profit
- Monitor inventory value
- Track fast/slow-moving products
- View sales trends (charts)
- Check staff performance

---

## 🛠️ Configuration

### Environment Variables

#### Backend (.env)
```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/pharma_pos
# Or for SQLite: sqlite:///./pharma_pos.db

# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# App Settings
DEBUG=False
ENVIRONMENT=production

# Notifications
ENABLE_EMAIL_NOTIFICATIONS=False
N8N_WEBHOOK_URL=http://localhost:5678/webhook/notifications

# Scheduler
ENABLE_BACKGROUND_SCHEDULER=True
EXPIRY_CHECK_HOUR=9
LOW_STOCK_CHECK_HOUR=10

# Business Rules
LOW_STOCK_THRESHOLD=10
EXPIRY_WARNING_DAYS=30
DEAD_STOCK_DAYS=90
```

#### Frontend (.env.local)
```env
VITE_API_URL=http://localhost:8000/api
```

---

## 🐳 Docker Deployment (Optional)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: pharma_pos
      POSTGRES_USER: pharma
      POSTGRES_PASSWORD: changeme
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://pharma:changeme@db:5432/pharma_pos
    ports:
      - "8000:8000"
    depends_on:
      - db
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

volumes:
  postgres_data:
```

Run:
```bash
docker-compose up -d
```

---

## 📦 Offline Installation for Clients

See [OFFLINE_INSTALLATION.md](./docs/OFFLINE_INSTALLATION.md) for detailed guides on:

1. **Python + Node Bundled Installer**
2. **Electron Desktop App**
3. **Docker Offline Package**
4. **Windows Installer (NSIS)**

---

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest
```

### Frontend Tests
```bash
cd frontend
npm run test
```

---

## 📚 API Documentation

Once the backend is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

#### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/register` - User registration
- `GET /api/auth/me` - Get current user

#### Products
- `GET /api/products` - List products
- `POST /api/products` - Create product
- `GET /api/products/search?q={query}` - Search products
- `GET /api/products/low-stock` - Low stock items

#### Sales
- `POST /api/sales` - Create sale
- `GET /api/sales` - List sales
- `GET /api/sales/summary/today` - Today's summary

#### Dashboard
- `GET /api/dashboard/kpis` - Dashboard KPIs
- `GET /api/dashboard/sales-trend` - Sales trend data
- `GET /api/dashboard/fast-moving-products` - Top products

#### AI Insights
- `GET /api/insights/dead-stock` - Dead stock items
- `GET /api/insights/reorder-suggestion/{id}` - Reorder suggestions
- `GET /api/insights/profit-margin-analysis` - Profit analysis

---

## 🔐 Security Best Practices

1. **Change default SECRET_KEY** in production
2. **Use strong passwords** for default users
3. **Enable HTTPS** in production
4. **Configure CORS** properly
5. **Use environment variables** for sensitive data
6. **Regular database backups**
7. **Update dependencies** regularly

---

## 🤝 Contributing

This is a complete, production-ready system. For enhancements:

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

---

## 📄 License

This project is licensed under the MIT License.

---

## 🆘 Support

For issues and questions:
- Open an issue on GitHub
- Check API docs at `/docs`
- Review this README

---

## 🎯 Roadmap

- [ ] Barcode scanner integration
- [ ] Receipt printer support
- [ ] Multi-store management
- [ ] Advanced reporting (PDF/Excel)
- [ ] Email notifications
- [ ] SMS alerts
- [ ] Batch printing
- [ ] Mobile apps (React Native)

---

## ✨ Credits

Built with modern technologies for the pharmaceutical industry.

**Version**: 1.0.0
**Status**: Production Ready ✅
