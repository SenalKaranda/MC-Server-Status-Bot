@echo off
setlocal ENABLEDELAYEDEXPANSION

echo.
echo [*] Using docker-compose.yml in %cd%
if not exist ".env" (
  echo [!] .env not found. Copying from .env.example...
  copy /Y ".env.example" ".env" >nul
  echo [!] Edit the .env file and set WEBHOOK_URL before starting.
)

echo.
echo [*] Building and starting containers...
docker compose up -d --build
if errorlevel 1 (
  echo [x] Failed to start. Check Docker is running.
  exit /b 1
)

echo.
echo [ok] Running.
echo     Banner:   http://localhost:8080/banner.png
echo     Discord:  refreshes every INTERVAL seconds via webhook edits.
