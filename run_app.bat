@echo off
REM MinerU Document Extraction App - Quick Start Batch Script
REM For Windows users who prefer .bat over PowerShell

title MinerU Document Extraction App
color 0A

echo ================================
echo MinerU Document Extraction App
echo ================================
echo.

REM Check Python
echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found! Please install Python 3.9+
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo ✓ %%i found

REM Check model weights
echo.
echo Checking model weights...
if exist "MinerU2.5-Pro-2605-1.2B\model.safetensors" (
    echo ✓ Model weights found at .\MinerU2.5-Pro-2605-1.2B
) else (
    echo ERROR: Model weights not found!
    echo Expected: .\MinerU2.5-Pro-2605-1.2B\model.safetensors
    pause
    exit /b 1
)

REM Install dependencies
echo.
echo Installing dependencies from requirements.txt...
echo This may take 5-10 minutes on first run...
echo.
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed
    pause
    exit /b 1
)

REM Launch app
echo.
echo ================================
echo 🚀 Launching Streamlit App...
echo ================================
echo.
echo Server will start at: http://localhost:8501
echo Your browser will open automatically
echo.
echo Press Ctrl+C to stop the server
echo.

".\.venv\Scripts\python.exe" -m streamlit run app.py --client.showErrorDetails=false

pause
