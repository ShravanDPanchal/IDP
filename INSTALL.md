# MinerU Streamlit App - Complete Installation Guide

## Overview

This guide will walk you through setting up the MinerU Document Extraction web app on your Windows machine.

**Total time:** 10-20 minutes (including dependency installation)

---

## Prerequisites Check

Before starting, verify you have:

### 1. Python 3.9+
```powershell
python --version
```
Should show: `Python 3.x.x`

If not installed, download from: https://www.python.org/downloads/

### 2. Model Weights Downloaded
```powershell
ls "D:\REDEL\MinerU download\MinerU2.5-Pro-2605-1.2B"
```
Should show files including: `model.safetensors`, `config.json`, `tokenizer.json`, etc.

### 3. ~50GB Free Disk Space
For dependencies and temporary files during processing.

### 4. Optional: NVIDIA GPU with CUDA 11.8+
For faster processing (10-100x faster). If you have an NVIDIA GPU, install:
- NVIDIA CUDA Toolkit 11.8+: https://developer.nvidia.com/cuda-11-8-0-download-archive
- NVIDIA cuDNN: https://developer.nvidia.com/cudnn

---

## Step-by-Step Installation

### Step 1: Open PowerShell

1. Click the Windows Start button
2. Search for "PowerShell" 
3. Right-click and select "Run as Administrator"
4. Or press `Win + X` then select "Windows Terminal (Admin)"

### Step 2: Navigate to Project Directory

```powershell
cd "D:\REDEL\MinerU download"
```

Verify you're in the right place:
```powershell
ls -la
```

Should show:
```
    Directory: D:\REDEL\MinerU download

Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
d-----         8/12/2026  12:00 PM                MinerU2.5-Pro-2605-1.2B
-a---          8/12/2026  12:01 PM            5234 app.py
-a---          8/12/2026  12:01 PM             892 requirements.txt
-a---          8/12/2026  12:01 PM            4500 README.md
```

### Step 3: Create Virtual Environment (Recommended)

```powershell
# Create virtual environment
python -m venv venv

# Activate it
.\venv\Scripts\Activate.ps1
```

You should see `(venv)` in your prompt now.

**Troubleshooting:** If you get a PowerShell execution error:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try activating again.

### Step 4: Install Dependencies

```powershell
# Upgrade pip, setuptools, wheel
pip install --upgrade pip setuptools wheel

# Install requirements (takes 5-10 minutes)
pip install -r requirements.txt
```

**Note:** This downloads ~5GB of dependencies. Please wait for completion.

Expected output at end:
```
Successfully installed streamlit-1.41.1 mineru-0.4.0 ... (many packages)
```

### Step 5: Verify Installation

```powershell
# Check Streamlit
streamlit --version
# Should show: Streamlit, version 1.41.1

# Check MinerU
python -c "from mineru.core import MinerUPipeline; print('✓ MinerU OK')"
# Should show: ✓ MinerU OK

# Check model path
ls "./MinerU2.5-Pro-2605-1.2B/model.safetensors"
# Should show file info, not "not found"
```

---

## Running the App

### Option A: Simple Run (Easiest)

```powershell
cd "D:\REDEL\MinerU download"
streamlit run app.py
```

✅ Browser opens automatically to http://localhost:8501

### Option B: Using PowerShell Launcher

```powershell
cd "D:\REDEL\MinerU download"
.\run_app.ps1
```

### Option C: Using Batch File (Fastest)

Simply double-click: `run_app.bat`

### Option D: With GPU Optimization (If you have NVIDIA GPU)

```powershell
cd "D:\REDEL\MinerU download"
.\run_with_gpu.ps1
```

---

## First Run Walkthrough

### 1. App Opens
You'll see the Streamlit interface with 3 columns:
- **Left:** Controls & Status Log
- **Middle:** Document Preview
- **Right:** Results (4 tabs)

### 2. Upload a Test File
- Click "Upload Document" in left panel
- Select a small PDF or image file (~5MB, 1-3 pages)
- Click Open

### 3. Configure Settings
- **Backend:** Keep as "pipeline" (fastest)
- **Max Pages:** Set to 5 (for faster first test)
- Leave other defaults

### 4. Click "Convert"
- Status log starts showing real updates:
  - `[12:34:56] Preparing to process: test.pdf`
  - `[12:34:57] Initializing MinerU pipeline...`
  - `[12:34:58] ✓ Pipeline initialized with pipeline backend`
  - `[12:35:01] Submitting to pipeline...`
  - `[12:35:05] Running MinerU extraction pipeline...`
  - `[12:35:45] ✓ Document parsing completed successfully`
  - `[12:35:45] Build outputs complete`
  - `[12:35:45] ✓ Done - Results ready for viewing`

### 5. View Results
Right panel shows extracted content in tabs:
- **Markdown Rendering:** Formatted view of document
- **Markdown Text:** Raw markdown code
- **JSON Content:** Structured JSON data
- **Download:** Download as ZIP or individual files

### 6. Download Results
Click "Download as ZIP" to get:
- `filename_output.md` - Full markdown
- `filename_text.txt` - Raw text
- `filename_content.json` - Structured data
- `filename_metadata.json` - Processing metadata

### 7. Try More Files
Click "Clear" and upload another document to test!

---

## Stopping the App

In the PowerShell terminal:
```powershell
Ctrl + C
```

Choose `y` when asked to terminate batch job.

---

## Troubleshooting

### Issue: "Python not found"
**Solution:** Install Python 3.9+ from https://www.python.org/downloads/

### Issue: "ModuleNotFoundError: No module named 'mineru'"
**Solution:**
```powershell
pip install -U "mineru[core]"
```

### Issue: Port 8501 Already in Use
**Solution:**
```powershell
streamlit run app.py --server.port 8502
```
Use 8502, 8503, etc.

### Issue: Out of Memory
**Solution:**
- Reduce max-pages slider to 5
- Close other applications
- Restart the app

### Issue: Model not found
**Solution:**
Verify model exists:
```powershell
ls ".\MinerU2.5-Pro-2605-1.2B\model.safetensors"
```

If missing, check your download path in `app.py` line 30:
```python
MODEL_PATH = Path("./MinerU2.5-Pro-2605-1.2B")
```

### Issue: Slow Processing
**Solution:**
- Install GPU drivers (NVIDIA CUDA 11.8+)
- Run: `.\run_with_gpu.ps1`
- Or use "pipeline" backend (fastest)

### Issue: "Permission denied" on .ps1 files
**Solution:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## Advanced Configuration

### Using GPU
Create file `run_gpu.ps1`:
```powershell
$env:CUDA_VISIBLE_DEVICES = "0"
streamlit run app.py
```

### Changing Model Path
Edit `app.py` line 30:
```python
MODEL_PATH = Path("C:/Your/Custom/Path/MinerU2.5-Pro-2605-1.2B")
```

### Custom Port
```powershell
streamlit run app.py --server.port 8888
```

### Debug Mode
```powershell
streamlit run app.py --logger.level=debug
```

---

## Verify Everything Works

### Quick Verification Checklist
```powershell
# 1. Check Python
python --version
# ✓ Python 3.9+

# 2. Check Streamlit
streamlit version
# ✓ Streamlit 1.41.1

# 3. Check MinerU
python -c "from mineru.core import MinerUPipeline; print('✓')"
# ✓ (output shown)

# 4. Check Model
ls "./MinerU2.5-Pro-2605-1.2B/model.safetensors"
# ✓ File listed

# 5. Check App File
ls "./app.py"
# ✓ File exists

# All green? Ready to run!
streamlit run app.py
```

---

## File Structure

After setup, your folder should look like:
```
D:\REDEL\MinerU download\
├── app.py                          ← Main Streamlit app
├── requirements.txt                ← Dependencies
├── README.md                       ← Full documentation
├── QUICKSTART.md                   ← Quick reference
├── INSTALL.md                      ← This file
├── run_app.ps1                     ← PowerShell launcher
├── run_app.bat                     ← Batch launcher
├── run_with_gpu.ps1                ← GPU launcher
│
├── .streamlit/
│   └── config.toml                 ← Streamlit settings
│
├── venv/                           ← Virtual environment (after setup)
│   ├── Scripts/
│   ├── Lib/
│   └── ...
│
└── MinerU2.5-Pro-2605-1.2B/        ← Your model weights
    ├── model.safetensors           ← Main model file (~1.2GB)
    ├── config.json
    ├── tokenizer.json
    ├── vocab.json
    └── ... (other model files)
```

---

## Next Steps

1. **Verify Prerequisites:**
   ```powershell
   python --version
   ls ".\MinerU2.5-Pro-2605-1.2B\model.safetensors"
   ```

2. **Install Dependencies (one time):**
   ```powershell
   cd "D:\REDEL\MinerU download"
   pip install -r requirements.txt
   ```

3. **Run the App:**
   ```powershell
   streamlit run app.py
   ```

4. **Upload & Extract:**
   - Click "Upload Document"
   - Click "Convert"
   - View results in right panel

---

## Getting Help

- **Questions?** Check `README.md` for detailed docs
- **Error messages?** Check the Status Log (left panel)
- **Performance issues?** See "Troubleshooting" section above
- **Model weights missing?** Verify path: `.\MinerU2.5-Pro-2605-1.2B`

---

## Performance Expectations

| File Type | Size | Time | Backend |
|-----------|------|------|---------|
| Simple PDF | 5MB | 30-60s | pipeline |
| Text PDF | 20MB | 1-2 min | pipeline |
| Image PDF | 50MB | 3-5 min | hybrid-engine |
| DOCX | 10MB | 20-40s | pipeline |
| PPTX | 30MB | 1-2 min | pipeline |
| With GPU | Same | 5-10x faster | Any |

**Times vary based on:** document complexity, OCR difficulty, table density, system specs.

---

## Ready? Let's Go!

```powershell
cd "D:\REDEL\MinerU download"
streamlit run app.py
```

Your browser will open automatically in ~3 seconds! 🎉

---

**Installation complete? Move to `QUICKSTART.md` for usage instructions.**
