# 📦 Installation Guide

Complete step-by-step instructions for setting up the ML Learning Assistant on your local machine.

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Python Installation](#python-installation)
3. [Project Setup](#project-setup)
4. [API Keys Setup](#api-keys-setup)
5. [Running the Application](#running-the-application)
6. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum Requirements
- **Operating System**: Windows 10/11, macOS 10.14+, or Linux
- **Python**: 3.8 or higher
- **RAM**: 2GB minimum (4GB recommended)
- **Storage**: 500MB free space
- **Internet**: Active connection for API calls

### Software Dependencies
- Python 3.8+
- pip (comes with Python)
- Modern web browser (Chrome, Firefox, Safari, or Edge)

---

## Python Installation

### Windows

1. **Download Python**
   - Visit [python.org](https://www.python.org/downloads/)
   - Download Python 3.8 or higher
   - Run the installer

2. **Installation Steps**
   - ✅ Check "Add Python to PATH"
   - Click "Install Now"
   - Wait for installation to complete

3. **Verify Installation**
   ```cmd
   python --version
   pip --version
   ```

### macOS

1. **Using Homebrew (Recommended)**
   ```bash
   # Install Homebrew if not installed
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   
   # Install Python
   brew install python@3.11
   ```

2. **Verify Installation**
   ```bash
   python3 --version
   pip3 --version
   ```

### Linux (Ubuntu/Debian)

```bash
# Update package list
sudo apt update

# Install Python and pip
sudo apt install python3 python3-pip python3-venv

# Verify installation
python3 --version
pip3 --version
```

---

## Project Setup

### Step 1: Extract Project Files

Extract the ZIP file to your desired location:
```
C:\Projects\ml_learning_assistant    # Windows
~/Projects/ml_learning_assistant     # macOS/Linux
```

### Step 2: Open Terminal/Command Prompt

**Windows:**
- Press `Win + R`
- Type `cmd` and press Enter
- Navigate to project: `cd C:\Projects\ml_learning_assistant`

**macOS/Linux:**
- Open Terminal
- Navigate to project: `cd ~/Projects/ml_learning_assistant`

### Step 3: Create Virtual Environment

**Why use a virtual environment?**
- Isolates project dependencies
- Prevents conflicts with other Python projects
- Makes it easy to manage packages

**Create virtual environment:**

```bash
# Windows
python -m venv venv

# macOS/Linux
python3 -m venv venv
```

### Step 4: Activate Virtual Environment

**Windows:**
```cmd
venv\Scripts\activate
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

You should see `(venv)` prefix in your terminal.

### Step 5: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- Flask (web framework)
- google-generativeai (NVIDIA NIM API)
- gTTS (text-to-speech)
- And other required packages

**Installation time**: 2-5 minutes depending on internet speed

---

## API Keys Setup

### NVIDIA NIM API Key (Required)

One key covers everything - text, code, audio and image generation all call
the same NVIDIA NIM endpoint, so there is nothing separate to get for images.

1. **Get a key**
   - Go to [https://build.nvidia.com](https://build.nvidia.com)
   - Sign in and click "Get API Key"
   - Copy the generated key (starts `nvapi-`)

2. **Save it to `.env`**
   ```bash
   # Copy example file
   cp .env.example .env

   # Edit .env file
   # Add your key: NVIDIA_API_KEY=nvapi-your_actual_key_here
   ```

That is the only place it is set. There is no per-user key entry in the app -
one key, set once, and every signed-in account shares it against the daily
generation limit.

---

## Running the Application

### Step 1: Start the Server

Make sure your virtual environment is activated, then:

```bash
python app.py
```

You should see output like:
```
 * Running on http://127.0.0.1:5000
 * Running on http://0.0.0.0:5000
```

### Step 2: Open Browser

Open your web browser and navigate to:
```
http://localhost:5000
```

or
```
http://127.0.0.1:5000
```

### Step 3: Start Learning!

Choose any feature:
- **Text Explanation**: Get text-based explanations
- **Code Generation**: Generate Python code
- **Audio Learning**: Create audio lessons
- **Image Visualization**: Generate diagrams

---

## Troubleshooting

### Issue: "Command 'python' not found"

**Solution:**
```bash
# Try python3 instead
python3 app.py

# Or add alias (Linux/macOS)
alias python=python3
```

### Issue: "pip: command not found"

**Solution:**
```bash
# Windows
python -m pip install -r requirements.txt

# macOS/Linux
python3 -m pip install -r requirements.txt
```

### Issue: "Permission denied" on Linux/macOS

**Solution:**
```bash
# Use --user flag
pip install --user -r requirements.txt

# Or use sudo (not recommended)
sudo pip install -r requirements.txt
```

### Issue: "Module not found" errors

**Solution:**
```bash
# Reinstall all dependencies
pip install -r requirements.txt --upgrade --force-reinstall
```

### Issue: "Port 5000 already in use"

**Solution:**

**Option 1: Change port in app.py**
```python
# Edit last line of app.py
app.run(debug=True, host='0.0.0.0', port=5001)
```

**Option 2: Kill process using port 5000**
```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:5000 | xargs kill -9
```

### Issue: "API key invalid" error

**Solution:**
1. Verify your API key is correct
2. Check for extra spaces
3. Ensure you copied the entire key
4. Try regenerating the key
5. Clear browser cache and re-enter

### Issue: Slow image generation

**Solution:**
1. Use NVIDIA NIM backend instead of NVIDIA NIM
2. First request to NVIDIA NIM is always slower (model loading)
3. Subsequent requests will be faster

### Issue: Audio not playing

**Solution:**
1. Check browser audio permissions
2. Try different browser
3. Download MP3 and play locally
4. Verify gTTS is installed: `pip install gTTS --upgrade`

---

## Advanced Configuration

### Running on Different Host/Port

```bash
# Edit app.py, last line:
app.run(debug=True, host='0.0.0.0', port=8080)
```

### Production Deployment

For production use:

1. **Disable debug mode**
   ```python
   app.run(debug=False, host='0.0.0.0', port=5000)
   ```

2. **Use production WSGI server**
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

3. **Set environment variables**
   ```bash
   export FLASK_ENV=production
   ```

### Updating the Application

```bash
# Pull latest changes if using git
git pull

# Upgrade dependencies
pip install -r requirements.txt --upgrade

# Restart the application
python app.py
```

---

## Verifying Installation

Run this checklist:

- [ ] Python 3.8+ installed
- [ ] Virtual environment created and activated
- [ ] Dependencies installed without errors
- [ ] NVIDIA_API_KEY set in .env
- [ ] Application starts without errors
- [ ] Can access http://localhost:5000
- [ ] Chat answers a question

If all checks pass, you're ready to start learning! 🎉

---

## Getting Help

If you're still having issues:

1. Check the error message carefully
2. Search for the error online
3. Review the README.md file
4. Check system requirements
5. Verify all steps were followed correctly

---

## Next Steps

After successful installation:

1. **Explore Features**: Try all four learning modes
2. **Experiment**: Test with different ML topics
3. **Customize**: Adjust complexity levels
4. **Learn**: Use generated content for your studies

---

**Installation complete! Happy learning! 🚀**
