# MinerU Document Extraction App - Setup & Run Script
# This script installs dependencies and launches the Streamlit app

Write-Host "================================" -ForegroundColor Cyan
Write-Host "MinerU Document Extraction App" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Check Python installation
Write-Host "Checking Python installation..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($pythonVersion -match "Python") {
    Write-Host "✓ $pythonVersion found" -ForegroundColor Green
} else {
    Write-Host "✗ Python not found! Please install Python 3.9+" -ForegroundColor Red
    exit 1
}

# Check model weights
Write-Host ""
Write-Host "Checking model weights..." -ForegroundColor Yellow
if (Test-Path "./MinerU2.5-Pro-2605-1.2B/model.safetensors") {
    Write-Host "✓ Model weights found at ./MinerU2.5-Pro-2605-1.2B" -ForegroundColor Green
} else {
    Write-Host "✗ Model weights not found!" -ForegroundColor Red
    Write-Host "   Expected location: ./MinerU2.5-Pro-2605-1.2B/model.safetensors" -ForegroundColor Red
    exit 1
}

# Ask user if they want to install dependencies
Write-Host ""
Write-Host "Ready to install dependencies? This may take 5-10 minutes..." -ForegroundColor Yellow
$response = Read-Host "Continue? (y/n)"
if ($response -ne "y") {
    Write-Host "Skipping installation..." -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Yellow
    pip install -r requirements.txt
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Dependencies installed successfully" -ForegroundColor Green
    } else {
        Write-Host "✗ Dependency installation failed" -ForegroundColor Red
        exit 1
    }
}

# Launch Streamlit app
Write-Host ""
Write-Host "================================" -ForegroundColor Green
Write-Host "🚀 Launching Streamlit App..." -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host ""
Write-Host "Server will start at: http://localhost:8501" -ForegroundColor Cyan
Write-Host "Your browser will open automatically" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Run Streamlit
& ".\.venv\Scripts\python.exe" -m streamlit run app.py --client.showErrorDetails=false
