# Directory Structure

Complete file tree of PHARMA-POS-AI project.

```
pharma-pos-ai/
├── README.md                          # Main documentation
├── QUICKSTART.md                      # 5-minute setup guide
├── PROJECT_SUMMARY.md                 # Project overview
├── DIRECTORY_STRUCTURE.md             # This file
├── .env.example                       # Example environment variables
├── .env                               # Environment configuration
├── .gitignore                         # Git ignore rules
│
├── backend/                           # Backend FastAPI application
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI application entry point
│   │   │
│   │   ├── core/                      # Core configuration
│   │   │   ├── config.py              # Settings & environment variables
│   │   │   └── security.py            # JWT & password hashing
│   │   │
│   │   ├── db/                        # Database configuration
│   │   │   └── base.py                # SQLAlchemy session & base
│   │   │
│   │   ├── models/                    # SQLAlchemy models
│   │   │   ├── __init__.py            # Model exports
│   │   │   ├── user.py                # User model (3 roles)
│   │   │   ├── category.py            # Product categories
│   │   │   ├── supplier.py            # Supplier/vendor model
│   │   │   ├── product.py             # Product & ProductBatch
│   │   │   ├── sale.py                # Sale & SaleItem
│   │   │   ├── notification.py        # Notification model
│   │   │   ├── activity_log.py        # Audit trail
│   │   │   └── stock_adjustment.py    # Inventory adjustments
│   │   │
│   │   ├── schemas/                   # Pydantic schemas
│   │   │   ├── __init__.py            # Schema exports
│   │   │   ├── user.py                # User schemas & Token
│   │   │   ├── category.py            # Category schemas
│   │   │   ├── supplier.py            # Supplier schemas
│   │   │   ├── product.py             # Product & Batch schemas
│   │   │   ├── sale.py                # Sale schemas
│   │   │   └── notification.py        # Notification schemas
│   │   │
│   │   ├── api/                       # API routes
│   │   │   ├── __init__.py            # API router aggregation
│   │   │   │
│   │   │   ├── dependencies/          # FastAPI dependencies
│   │   │   │   ├── __init__.py
│   │   │   │   └── auth.py            # Auth dependencies
│   │   │   │
│   │   │   └── endpoints/             # API endpoint handlers
│   │   │       ├── auth.py            # Login and session endpoints
│   │   │       ├── products.py        # Product CRUD, search, batches
│   │   │       ├── categories.py      # Category management
│   │   │       ├── suppliers.py       # Supplier management
│   │   │       ├── sales.py           # POS & sales
│   │   │       ├── notifications.py   # Notification management
│   │   │       ├── dashboard.py       # Dashboard KPIs & analytics
│   │   │       └── insights.py        # Operational insights endpoints
│   │   │
│   │   └── services/                  # Business logic services
│   │       ├── notification_service.py # Notification creation & webhooks
│   │       ├── ai_insights.py         # Rule-based operational analytics
│   │       └── scheduler.py           # Background task scheduler
│   │
│   ├── alembic/                       # Database migrations
│   │   ├── env.py                     # Alembic environment
│   │   ├── script.py.mako             # Migration template
│   │   └── versions/                  # Migration files (auto-generated)
│   │
│   ├── alembic.ini                    # Alembic configuration
│   ├── requirements.txt               # Python dependencies
│   └── .env                           # Backend environment (copy from root)
│
├── frontend/                          # Frontend React application
│   ├── public/                        # Static assets
│   │
│   ├── src/
│   │   ├── main.tsx                   # React entry point
│   │   ├── App.tsx                    # Main app with routing
│   │   │
│   │   ├── components/                # React components
│   │   │   ├── layout/
│   │   │   │   ├── MainLayout.tsx     # Main layout wrapper
│   │   │   │   ├── Sidebar.tsx        # Navigation sidebar
│   │   │   │   └── Header.tsx         # Top header with user menu
│   │   │   │
│   │   │   └── common/                # Reusable components (future)
│   │   │
│   │   ├── pages/                     # Page components
│   │   │   ├── LoginPage.tsx          # Login screen
│   │   │   ├── DashboardPage.tsx      # Dashboard with KPIs & charts
│   │   │   ├── ProductsPage.tsx       # Product management
│   │   │   ├── POSPage.tsx            # Point of Sale interface
│   │   │   ├── SalesPage.tsx          # Sales history
│   │   │   ├── SuppliersPage.tsx      # Supplier management
│   │   │   └── NotificationsPage.tsx  # Notifications center
│   │   │
│   │   ├── services/                  # API & external services
│   │   │   └── api.ts                 # Axios API client
│   │   │
│   │   ├── stores/                    # Zustand state management
│   │   │   ├── authStore.ts           # Authentication state
│   │   │   ├── cartStore.ts           # Shopping cart state
│   │   │   └── themeStore.ts          # Dark/light theme
│   │   │
│   │   ├── styles/                    # CSS & styling
│   │   │   └── index.css              # Tailwind & custom styles
│   │   │
│   │   ├── hooks/                     # Custom React hooks (future)
│   │   ├── utils/                     # Utility functions (future)
│   │   └── assets/                    # Images, icons (future)
│   │
│   ├── index.html                     # HTML template
│   ├── package.json                   # Node.js dependencies
│   ├── tsconfig.json                  # TypeScript configuration
│   ├── tsconfig.node.json             # TypeScript for Node (Vite)
│   ├── vite.config.ts                 # Vite build configuration
│   ├── tailwind.config.js             # Tailwind CSS config
│   ├── postcss.config.js              # PostCSS config
│   └── .env.local                     # Frontend environment
│
├── scripts/                           # Utility scripts
│   ├── seed_data.py                   # Database seed script
│   └── init_db.sh                     # Database initialization
│
├── docs/                              # Documentation
│   ├── SETUP_GUIDE.md                 # Detailed setup instructions
│   └── OFFLINE_INSTALLATION.md        # Offline deployment guide
│
├── logs/                              # Application logs (created at runtime)
│   └── app.log
│
├── uploads/                           # File uploads (created at runtime)
│   └── .gitkeep
│
└── installer-builds/                  # Build outputs for installers
    └── (created during build process)
```

## 📊 File Count by Type

### Backend
- **Python Files:** 30+
  - Models: 9
  - Schemas: 6
  - API Endpoints: 8
  - Services: 3
  - Core: 2
  - Other: 2+

### Frontend
- **TypeScript/React Files:** 25+
  - Pages: 6
  - Components: 3
  - Stores: 3
  - Services: 1
  - Configuration: 5+
  - Other: 7+

### Documentation
- **Markdown Files:** 5
- **Configuration Files:** 10+
- **Scripts:** 2+

### Total Files Created
**70+ files** across the entire project

---

## 🗂️ Key Directories

### `/backend/app/`
Core backend application with API, models, and business logic.

### `/frontend/src/`
React application with pages, components, and state management.

### `/docs/`
Comprehensive documentation for setup and deployment.

### `/scripts/`
Automation scripts for database and deployment tasks.

---

## 🚀 Getting Started

1. Review `QUICKSTART.md` for 5-minute setup
2. See `docs/SETUP_GUIDE.md` for detailed installation
3. Check `README.md` for feature overview
4. Explore `docs/OFFLINE_INSTALLATION.md` for deployment

---

## 📝 Notes

- **Configuration:** Environment files (`.env`) are gitignored
- **Dependencies:** Listed in `requirements.txt` (backend) and `package.json` (frontend)
- **Migrations:** Alembic handles database schema changes
- **Build Output:** Goes to `frontend/dist/` and `installer-builds/`

---

For more details, see the main [README.md](./README.md)
