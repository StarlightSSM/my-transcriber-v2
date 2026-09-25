$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

Write-Host ""
Write-Host "my-transcriber 실행 중..." -ForegroundColor Cyan
Write-Host "브라우저: http://127.0.0.1:5000"
Write-Host ""
& ".venv\Scripts\python.exe" app.py
