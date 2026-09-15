# Generate demo sample invoices, then run the automated test suite.
Set-Location -Path (Join-Path $PSScriptRoot "..")

Write-Host "[1/2] Generating sample invoices..."
python scripts/make_sample_invoices.py

Write-Host "[2/2] Running tests..."
python -m pytest tests -q