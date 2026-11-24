$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Membuat virtual environment Python..." -ForegroundColor Cyan
    python -m venv .venv
    .\.venv\Scripts\pip.exe install -r requirements.txt
}

Write-Host "Menjalankan Karyawan Assistant Intelligent..." -ForegroundColor Green
Write-Host "  Laptop : http://127.0.0.1:8000" -ForegroundColor Cyan
$lanIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.InterfaceAlias -match 'Wi-Fi|Ethernet' } | Select-Object -First 1 -ExpandProperty IPAddress)
if ($lanIp) {
    Write-Host "  HP/WiFi: http://${lanIp}:8000" -ForegroundColor Yellow
}
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
