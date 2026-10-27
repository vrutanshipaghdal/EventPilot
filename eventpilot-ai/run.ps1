Set-Location -Path "$PSScriptRoot"
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  Starting EventPilot Booking & AI Platform   " -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

if (Test-Path ".\.venv\Scripts\streamlit.exe") {
    & ".\.venv\Scripts\streamlit.exe" run app.py
} else {
    Write-Error "[ERROR] Virtual environment not found in .venv!"
}
