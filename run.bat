@echo off
cd /d "%~dp0eventpilot-ai"
echo ==============================================
echo   Starting EventPilot Booking ^& AI Platform
echo ==============================================
if exist ".venv\Scripts\streamlit.exe" (
    ".venv\Scripts\streamlit.exe" run app.py
) else (
    echo [ERROR] Virtual environment not found in eventpilot-ai\.venv!
    pause
)
