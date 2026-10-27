@echo off
cd /d "%~dp0"
echo ==============================================
echo   Starting EventPilot Booking ^& AI Platform
echo ==============================================
if exist ".venv\Scripts\streamlit.exe" (
    ".venv\Scripts\streamlit.exe" run app.py
) else (
    echo [ERROR] Virtual environment not found in .venv!
    pause
)
