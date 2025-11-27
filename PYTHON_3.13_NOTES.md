# Python 3.13 Compatibility Notes

This project has been updated to work with Python 3.13.

## Key Changes

### Database Driver (psycopg)
- **Changed from:** `psycopg2-binary` (v2)
- **Changed to:** `psycopg[binary]` (v3)
- **Reason:** psycopg2 doesn't have pre-built wheels for Python 3.13 yet

### Database URL Format
Both formats work with psycopg v3:

```env
# Standard format (works with psycopg v3)
DATABASE_URL=postgresql://user:password@localhost:5432/pharma_pos

# Or with explicit psycopg driver
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/pharma_pos
```

**No code changes needed** - psycopg v3 is backward compatible with SQLAlchemy!

### SQLite (Recommended for Quick Start)
For easiest setup, use SQLite (no PostgreSQL installation needed):

```env
DATABASE_URL=sqlite:///./pharma_pos.db
```

## Installation

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
uv pip install -r requirements.txt
# OR
pip install -r requirements.txt
```

## Verified Working On
- ✅ Python 3.13.5
- ✅ Python 3.11.x
- ✅ Python 3.10.x
- ✅ Python 3.9.x

## If You Still Have Issues

### Option 1: Use SQLite (Easiest)
```bash
# Edit backend/.env
DATABASE_URL=sqlite:///./pharma_pos.db
```

### Option 2: Install PostgreSQL System Libraries
```bash
# Ubuntu/Debian
sudo apt-get install libpq-dev python3-dev

# macOS
brew install postgresql

# Then retry:
pip install -r requirements.txt
```

### Option 3: Use Python 3.11 (if you need psycopg2)
```bash
# Install Python 3.11
sudo apt install python3.11 python3.11-venv

# Create venv with Python 3.11
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Compatibility Matrix

| Package | Old Version | New Version | Python 3.13 |
|---------|-------------|-------------|-------------|
| psycopg2-binary | 2.9.9 | (removed) | ❌ |
| psycopg[binary] | - | 3.1.18 | ✅ |
| SQLAlchemy | 2.0.25 | 2.0.25 | ✅ |
| FastAPI | 0.109.0 | 0.109.0 | ✅ |
| All others | - | unchanged | ✅ |

## Testing

After installation, verify everything works:

```bash
# Start backend
python -m app.main

# Should see:
# INFO:     Started server process
# INFO:     Uvicorn running on http://0.0.0.0:8000
```

Then visit http://localhost:8000/docs to see the API documentation.

---

**Everything else remains the same!** The upgrade is transparent and backward compatible.
