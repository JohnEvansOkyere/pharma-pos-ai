# Offline Installation Guide for Clients

This guide provides **multiple strategies** for packaging and deploying PHARMA-POS-AI to client computers **without internet access**.

---

## 📦 Installation Methods

1. **Portable Python + Node Package** (Easiest)
2. **Electron Desktop App** (Most User-Friendly)
3. **Docker Offline Package** (Most Reliable)
4. **Windows Installer (NSIS)** (Most Professional)

---

## Method 1: Portable Python + Node Package ⭐ RECOMMENDED

This method bundles Python, Node.js, and all dependencies into a single portable package.

### A. Creating the Package (On Development Machine)

#### Step 1: Install Dependencies

```bash
# Install pyinstaller for Python bundling
pip install pyinstaller

# Install pkg for Node.js bundling (optional)
npm install -g pkg
```

#### Step 2: Create Portable Backend

```bash
cd pharma-pos-ai

# Create a build script
cat > build_portable.sh << 'EOF'
#!/bin/bash

echo "Building Portable PHARMA-POS-AI..."

# Create dist directory
mkdir -p dist/pharma-pos-portable

# Backend: Bundle with dependencies
cd backend
pip install -r requirements.txt --target ../dist/pharma-pos-portable/backend_libs
cp -r app ../dist/pharma-pos-portable/
cp -r alembic ../dist/pharma-pos-portable/
cp alembic.ini ../dist/pharma-pos-portable/
cp requirements.txt ../dist/pharma-pos-portable/

# Create backend launcher
cat > ../dist/pharma-pos-portable/run_backend.bat << 'BACKEND'
@echo off
set PYTHONPATH=%CD%\backend_libs;%PYTHONPATH%
python -m app.main
pause
BACKEND

cat > ../dist/pharma-pos-portable/run_backend.sh << 'BACKEND'
#!/bin/bash
export PYTHONPATH="$PWD/backend_libs:$PYTHONPATH"
python3 -m app.main
BACKEND

chmod +x ../dist/pharma-pos-portable/run_backend.sh

cd ..

# Frontend: Build production bundle
cd frontend
npm install
npm run build

# Copy frontend build to dist
cp -r dist ../dist/pharma-pos-portable/frontend_build/

# Create frontend server (using Python)
cat > ../dist/pharma-pos-portable/run_frontend.py << 'FRONTEND'
import http.server
import socketserver
import os

PORT = 3000
DIRECTORY = "frontend_build"

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
    print(f"Frontend server running at http://localhost:{PORT}")
    httpd.serve_forever()
FRONTEND

cat > ../dist/pharma-pos-portable/run_frontend.bat << 'FRONTEND'
@echo off
python run_frontend.py
pause
FRONTEND

cat > ../dist/pharma-pos-portable/run_frontend.sh << 'FRONTEND'
#!/bin/bash
python3 run_frontend.py
FRONTEND

chmod +x ../dist/pharma-pos-portable/run_frontend.sh

cd ..

# Create main launcher
cat > dist/pharma-pos-portable/START_PHARMA_POS.bat << 'MAIN'
@echo off
echo Starting PHARMA-POS-AI...
echo.
echo Starting Backend Server...
start "Backend" cmd /k run_backend.bat

timeout /t 3

echo Starting Frontend Server...
start "Frontend" cmd /k run_frontend.bat

timeout /t 2

echo Opening Browser...
start http://localhost:3000

echo.
echo PHARMA-POS-AI is running!
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo.
pause
MAIN

cat > dist/pharma-pos-portable/START_PHARMA_POS.sh << 'MAIN'
#!/bin/bash
echo "Starting PHARMA-POS-AI..."
echo ""

echo "Starting Backend Server..."
./run_backend.sh &
BACKEND_PID=$!

sleep 3

echo "Starting Frontend Server..."
./run_frontend.sh &
FRONTEND_PID=$!

sleep 2

echo "Opening Browser..."
xdg-open http://localhost:3000 || open http://localhost:3000

echo ""
echo "PHARMA-POS-AI is running!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop..."

wait
MAIN

chmod +x dist/pharma-pos-portable/START_PHARMA_POS.sh

# Create .env file
cp .env.example dist/pharma-pos-portable/.env

# Create README
cat > dist/pharma-pos-portable/README.txt << 'README'
PHARMA-POS-AI - Portable Installation
======================================

REQUIREMENTS:
- Python 3.9 or higher
- No internet connection needed

INSTALLATION:
1. Ensure Python 3.9+ is installed
2. Run START_PHARMA_POS.bat (Windows) or START_PHARMA_POS.sh (Linux/Mac)
3. Wait for both servers to start
4. Browser will open automatically at http://localhost:3000

DEFAULT LOGIN:
Username: admin
Password: admin123

FIRST RUN:
The database will be created automatically on first run.

TROUBLESHOOTING:
- If ports 8000 or 3000 are in use, close other applications
- Check that Python is in your system PATH
- Run run_backend.bat and run_frontend.bat separately to see errors

For support, contact your system administrator.
README

echo "Build complete! Package located at: dist/pharma-pos-portable"
echo "Archive this folder and copy to client computers."
EOF

chmod +x build_portable.sh
bash build_portable.sh
```

#### Step 3: Package for Distribution

```bash
# Create compressed archive
cd dist
tar -czf pharma-pos-portable.tar.gz pharma-pos-portable/

# Or for Windows ZIP:
# zip -r pharma-pos-portable.zip pharma-pos-portable/
```

### B. Installing on Client Computer

1. **Copy** the `pharma-pos-portable.tar.gz` to client computer
2. **Extract**: `tar -xzf pharma-pos-portable.tar.gz`
3. **Ensure Python 3.9+** is installed
4. **Double-click** `START_PHARMA_POS.bat` (Windows) or run `./START_PHARMA_POS.sh` (Linux)
5. **Browser opens** automatically at http://localhost:3000

---

## Method 2: Electron Desktop App

Package as a native desktop application using Electron.

### A. Setup Electron Wrapper

```bash
cd frontend

# Create electron directory
mkdir electron
cd electron

# Initialize package.json
npm init -y

# Install Electron
npm install electron electron-builder

# Create main.js
cat > main.js << 'EOF'
const { app, BrowserWindow } = require('electron')
const path = require('path')
const { spawn } = require('child_process')

let backendProcess = null
let mainWindow = null

function startBackend() {
  const backendPath = path.join(__dirname, '../../backend/app/main.py')
  backendProcess = spawn('python', [backendPath])

  backendProcess.stdout.on('data', (data) => {
    console.log(`Backend: ${data}`)
  })

  backendProcess.stderr.on('data', (data) => {
    console.error(`Backend Error: ${data}`)
  })
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
    icon: path.join(__dirname, 'icon.png')
  })

  // Wait for backend to start
  setTimeout(() => {
    mainWindow.loadURL('http://localhost:8000')
  }, 3000)

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

app.on('ready', () => {
  startBackend()
  createWindow()
})

app.on('window-all-closed', () => {
  if (backendProcess) {
    backendProcess.kill()
  }
  app.quit()
})

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow()
  }
})
EOF

# Update package.json
cat > package.json << 'EOF'
{
  "name": "pharma-pos-ai",
  "version": "1.0.0",
  "main": "main.js",
  "scripts": {
    "start": "electron .",
    "build:win": "electron-builder --win --x64",
    "build:mac": "electron-builder --mac",
    "build:linux": "electron-builder --linux"
  },
  "build": {
    "appId": "com.pharmapos.app",
    "productName": "PHARMA-POS-AI",
    "directories": {
      "output": "dist"
    },
    "files": [
      "**/*",
      "../../backend/**/*",
      "../../frontend/dist/**/*"
    ],
    "win": {
      "target": "nsis",
      "icon": "icon.ico"
    },
    "mac": {
      "target": "dmg",
      "icon": "icon.icns"
    },
    "linux": {
      "target": ["AppImage", "deb"],
      "icon": "icon.png"
    }
  },
  "dependencies": {
    "electron": "^27.0.0"
  },
  "devDependencies": {
    "electron-builder": "^24.6.4"
  }
}
EOF
```

### B. Build Electron App

```bash
# Build for Windows
npm run build:win

# Build for macOS
npm run build:mac

# Build for Linux
npm run build:linux

# Output will be in electron/dist/
```

### C. Install on Client

1. Copy the installer (`.exe`, `.dmg`, or `.AppImage`) to client
2. Run installer
3. Launch "PHARMA-POS-AI" from Start Menu/Applications

---

## Method 3: Docker Offline Package

Package everything in Docker containers for maximum reliability.

### A. Create Docker Images

```bash
# Build images
docker build -t pharma-pos-backend:1.0 ./backend
docker build -t pharma-pos-frontend:1.0 ./frontend

# Save images to tar files
docker save pharma-pos-backend:1.0 > pharma-backend.tar
docker save pharma-pos-frontend:1.0 > pharma-frontend.tar
docker save postgres:15 > postgres.tar

# Create installation script
cat > install_docker.sh << 'EOF'
#!/bin/bash

echo "Installing PHARMA-POS-AI via Docker..."

# Load images
docker load < pharma-backend.tar
docker load < pharma-frontend.tar
docker load < postgres.tar

# Create docker-compose.yml
cat > docker-compose.yml << 'COMPOSE'
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: pharma_pos
      POSTGRES_USER: pharma
      POSTGRES_PASSWORD: pharma123
    volumes:
      - pharma_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  backend:
    image: pharma-pos-backend:1.0
    environment:
      DATABASE_URL: postgresql://pharma:pharma123@db:5432/pharma_pos
    ports:
      - "8000:8000"
    depends_on:
      - db

  frontend:
    image: pharma-pos-frontend:1.0
    ports:
      - "3000:80"
    depends_on:
      - backend

volumes:
  pharma_data:
COMPOSE

# Start services
docker-compose up -d

echo "PHARMA-POS-AI is now running!"
echo "Access at: http://localhost:3000"
EOF

chmod +x install_docker.sh
```

### B. Package for Distribution

```bash
# Create package
mkdir pharma-docker-package
mv pharma-backend.tar pharma-docker-package/
mv pharma-frontend.tar pharma-docker-package/
mv postgres.tar pharma-docker-package/
mv install_docker.sh pharma-docker-package/

# Create README
cat > pharma-docker-package/README.txt << 'EOF'
PHARMA-POS-AI - Docker Installation
====================================

REQUIREMENTS:
- Docker Engine installed
- Docker Compose installed

INSTALLATION:
1. Run: ./install_docker.sh
2. Wait for containers to start
3. Access at http://localhost:3000

LOGIN:
Username: admin
Password: admin123

MANAGEMENT:
- Stop: docker-compose down
- Start: docker-compose up -d
- Logs: docker-compose logs -f

For support, contact your administrator.
EOF

# Archive
tar -czf pharma-docker-package.tar.gz pharma-docker-package/
```

---

## Method 4: Windows Installer (NSIS)

Create professional Windows installer using NSIS.

### A. Install NSIS

Download from: https://nsis.sourceforge.io/

### B. Create Installer Script

```nsis
; PHARMA-POS-AI Installer Script
; Save as: installer.nsi

!define APP_NAME "PHARMA-POS-AI"
!define APP_VERSION "1.0.0"
!define PUBLISHER "Your Company"

Name "${APP_NAME}"
OutFile "PHARMA-POS-AI-Setup.exe"
InstallDir "$PROGRAMFILES\${APP_NAME}"

Page directory
Page instfiles

Section "Install"
  SetOutPath "$INSTDIR"

  ; Copy files
  File /r "dist\pharma-pos-portable\*.*"

  ; Create shortcuts
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\PHARMA-POS-AI.lnk" \
    "$INSTDIR\START_PHARMA_POS.bat"
  CreateShortcut "$DESKTOP\PHARMA-POS-AI.lnk" \
    "$INSTDIR\START_PHARMA_POS.bat"

  ; Create uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Registry entries
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
    "DisplayName" "${APP_NAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
    "UninstallString" "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
  ; Remove files
  RMDir /r "$INSTDIR"

  ; Remove shortcuts
  Delete "$SMPROGRAMS\${APP_NAME}\PHARMA-POS-AI.lnk"
  RMDir "$SMPROGRAMS\${APP_NAME}"
  Delete "$DESKTOP\PHARMA-POS-AI.lnk"

  ; Remove registry entries
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
SectionEnd
```

### C. Build Installer

```bash
# Compile with NSIS
makensis installer.nsi

# Output: PHARMA-POS-AI-Setup.exe
```

---

## 🎯 Recommended Approach

For **most clients**, use **Method 1: Portable Package** because:
- ✅ No complex installation
- ✅ Works on any OS
- ✅ Easy to update
- ✅ Minimal dependencies
- ✅ Easy to troubleshoot

For **enterprise deployments**, use **Method 3: Docker** because:
- ✅ Guaranteed consistency
- ✅ Easy backup/restore
- ✅ Professional deployment
- ✅ Scalable

---

## 📋 Pre-Installation Checklist for Clients

Before deploying to client:
- [ ] Python 3.9+ installed (for Method 1)
- [ ] Docker installed (for Method 3)
- [ ] Ports 8000 and 3000 available
- [ ] Sufficient disk space (500MB+)
- [ ] Windows Defender/Antivirus exclusions set
- [ ] Backup strategy in place

---

## 🔧 Post-Installation Configuration

After installation:

1. **Change default passwords**
2. **Configure backup schedule**
3. **Set up printer (if needed)**
4. **Configure barcode scanner**
5. **Import initial inventory**
6. **Train staff on system**

---

## 💾 Database Backup & Restore

### SQLite Backup
```bash
# Backup
cp pharma_pos.db pharma_pos_backup_$(date +%Y%m%d).db

# Restore
cp pharma_pos_backup_20240101.db pharma_pos.db
```

### PostgreSQL Backup
```bash
# Backup
pg_dump pharma_pos > pharma_pos_backup_$(date +%Y%m%d).sql

# Restore
psql pharma_pos < pharma_pos_backup_20240101.sql
```

---

## 🆘 Troubleshooting

### Common Issues

**Port Already in Use**
```bash
# Find process using port 8000
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Kill process
kill <PID>  # Linux/Mac
taskkill /PID <PID> /F  # Windows
```

**Python Not Found**
- Ensure Python is installed
- Add Python to system PATH
- Use full path to python executable

**Database Connection Error**
- Check PostgreSQL is running
- Verify DATABASE_URL in .env
- Check firewall settings

---

## ✅ Success Checklist

Installation is successful when:
- [ ] Backend starts without errors
- [ ] Frontend loads in browser
- [ ] Login works with default credentials
- [ ] Can create a test product
- [ ] Can process a test sale
- [ ] Dashboard shows data

---

For additional support, refer to the main README.md
