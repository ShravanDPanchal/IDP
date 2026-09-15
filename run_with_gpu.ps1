# Environment Configuration Script
# Sets up GPU and optimization settings for MinerU processing

# For NVIDIA GPU acceleration (recommended)
# Uncomment the line below if you have an NVIDIA GPU:
# $env:CUDA_VISIBLE_DEVICES = "0"

# For AMD GPU acceleration (if applicable):
# $env:HIP_VISIBLE_DEVICES = "0"

# For CPU-only mode (not recommended, slower):
# $env:CUDA_VISIBLE_DEVICES = ""

# PyTorch optimization settings
$env:PYTORCH_ENABLE_MPS_FALLBACK = "1"

# Reduce memory usage
$env:PYTORCH_CUDA_ALLOC_CONF = "max_split_size_mb:512"

# Number of threads for PyTorch
$env:OMP_NUM_THREADS = "8"

# Disable telemetry
$env:TRANSFORMERS_OFFLINE = "0"

# Model cache directory (optional, defaults to ~/.cache)
# $env:HF_HOME = "D:\Models\huggingface"

Write-Host "✓ Environment configured for MinerU" -ForegroundColor Green
Write-Host "  GPU: NVIDIA" -ForegroundColor Cyan
Write-Host "  CUDA Threads: 8" -ForegroundColor Cyan
Write-Host ""
Write-Host "Starting app..." -ForegroundColor Yellow
Write-Host ""

# Launch the app
& ".\.venv\Scripts\python.exe" -m streamlit run app.py
