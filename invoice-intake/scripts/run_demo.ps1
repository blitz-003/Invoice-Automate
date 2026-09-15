# Install dependencies and launch the API for a local demo.
param(
    [string]$Port = "8000"
)

Set-Location -Path (Join-Path $PSScriptRoot "..")

Write-Host "[1/2] Installing Python dependencies..."
python -m pip install -r requirements.txt

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

Write-Host "[2/2] Starting Invoice Intake API on http://127.0.0.1:$Port"
python run.py --host 127.0.0.1 --port $Port