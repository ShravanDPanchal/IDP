# MinerU Streamlit App - Quick Start Guide

## ⚡ 30-Second Startup

### Option 1: PowerShell (Recommended)
```powershell
cd "D:\REDEL\MinerU download"
streamlit run app.py
```

### Option 2: Using Setup Script
```powershell
cd "D:\REDEL\MinerU download"
.\run_app.ps1
```

### Option 3: Batch File (Windows)
```
Double-click: run_app.bat
```

---

## 📋 Installation Checklist

Before running, complete these steps once:

### 1. Verify Python
```powershell
python --version
```
✓ Should show Python 3.9 or higher

### 2. Verify Model Weights
```powershell
ls ".\MinerU2.5-Pro-2605-1.2B\model.safetensors"
```
✓ File should exist and be ~1.2GB

### 3. Install Dependencies (First Time Only)
```powershell
cd "D:\REDEL\MinerU download"
pip install -r requirements.txt
```
⏱️ Takes 5-10 minutes on first install

---

## 🚀 Run the App

### One-Liner (After Dependencies Installed)
```powershell
cd "D:\REDEL\MinerU download"; streamlit run app.py
```

### What Happens Next
1. Terminal shows: `Local URL: http://localhost:8501`
2. Browser opens automatically to the app
3. Status shows: "⚙️ Controls | 👁️ Document Preview | 📊 Extraction Results"
4. You're ready to upload documents!

---

## 🎯 Common Commands

### Run and Keep Running
```powershell
streamlit run app.py
```

### Run on Different Port
```powershell
streamlit run app.py --server.port 8502
```

### Run with Debug Output
```powershell
streamlit run app.py --logger.level=debug
```

### Stop the App
```
Press Ctrl+C in the terminal
```

### Clear Cache
```powershell
streamlit cache clear
```

---

## 📊 First Test Run

1. **Open the app**
   ```powershell
   cd "D:\REDEL\MinerU download"
   streamlit run app.py
   ```

2. **Upload a test PDF** (~5MB, 1-3 pages)

3. **Click Convert**
   - Watch status log update in real-time
   - Processing takes 30-120 seconds depending on file

4. **View Results**
   - Click tabs to see markdown, JSON, raw text
   - Download as ZIP or individual files

5. **Success!** 🎉

---

## 🛠️ Troubleshooting

### "ModuleNotFoundError: No module named 'mineru'"
```powershell
pip install -U "mineru[core]"
```

### "Failed to initialize pipeline"
```powershell
pip install --upgrade torch transformers
```

### App Crashes on Upload
- Use a smaller PDF (< 20 pages)
- Reduce max-pages slider to 5
- Restart: `streamlit run app.py`

### Slow Processing
- Use GPU: Install CUDA 11.8+
- Reduce file size or page count
- Switch backend to "pipeline" (fastest)

### Port Already in Use
```powershell
streamlit run app.py --server.port 8502
```
Use a different port (8502, 8503, etc.)

---

## 💾 File Locations

Your app files are here:
```
D:\REDEL\MinerU download\
├── app.py                    ← Main app (DO NOT EDIT unless you know Python)
├── requirements.txt          ← Dependencies
├── README.md                 ← Full documentation
├── QUICKSTART.md             ← This file
├── run_app.ps1              ← PowerShell launcher
├── run_app.bat              ← Batch file launcher
└── MinerU2.5-Pro-2605-1.2B/  ← Your model weights
```

---

## 🎮 Using the App

### Left Panel
- **Upload File** - Click to select PDF/DOCX/PPTX/XLSX/PNG/JPG
- **Backend** - Choose: pipeline (fast) | hybrid-engine | vlm (accurate)
- **Max Pages** - Slider 1-500, default 10
- **Convert** - Click to start extraction
- **Clear** - Reset session
- **Status Log** - Watch processing updates

### Middle Panel
- File info (name, size)
- Document preview (images, PDF thumbnails)

### Right Panel (4 Tabs)
1. **Markdown Rendering** - Formatted view of extracted content
2. **Markdown Text** - Raw markdown code
3. **JSON Content** - Structured data as JSON
4. **Download** - Get results as ZIP or individual files

---

## ✅ You're Ready!

### To start immediately:
```powershell
cd "D:\REDEL\MinerU download"
streamlit run app.py
```

The browser will open in ~3 seconds!

### Need help?
- Check `README.md` for detailed documentation
- Check status log (left panel) for error messages
- Verify model path: `ls "./MinerU2.5-Pro-2605-1.2B"`

---

**Happy extracting! 🎉**
