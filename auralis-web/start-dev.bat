@echo off
REM Auralis Web Development Launcher for Windows
REM Starts both backend and frontend in development mode

echo 🚀 Starting Auralis Web Development Environment...

REM Start backend in new window
echo 📡 Starting FastAPI backend...
start "Auralis Backend" cmd /k "cd backend && python main.py"

REM Wait for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend in new window
echo 🎨 Starting React frontend...
cd frontend

REM Check if node_modules exists
if not exist "node_modules" (
    echo 📦 Installing frontend dependencies...
    pnpm install
)

start "Auralis Frontend" cmd /k "pnpm run dev"

echo.
echo ✅ Development environment started!
echo.
echo 🌐 Frontend: http://localhost:3000
echo 📡 Backend:  http://localhost:8765
echo 📖 API Docs: http://localhost:8765/api/docs
echo.
echo Press any key to exit...
pause >nul