@echo off
echo ========================================
echo Setting Up Virtual Environment
echo ========================================
echo.
echo This will create a clean Python environment
echo to avoid conflicts with user-installed packages
echo.
pause

echo.
echo Step 1: Creating virtual environment...
python -m venv venv

echo.
echo Step 2: Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Step 3: Upgrading pip...
python -m pip install --upgrade pip

echo.
echo Step 4: Installing basic dependencies...
pip install Flask==2.3.3
pip install Flask-CORS==4.0.0
pip install Werkzeug==2.3.7

echo.
echo Step 5: Installing AI dependencies (this may take 5-10 minutes)...
echo Installing PyMuPDF and dotenv...
pip install PyMuPDF==1.23.8
pip install python-dotenv==1.0.0

echo.
echo Installing PyTorch (large download ~2GB)...
pip install torch --index-url https://download.pytorch.org/whl/cpu

echo.
echo Installing transformers and sentence-transformers...
pip install transformers
pip install sentence-transformers

echo.
echo Installing ChromaDB...
pip install chromadb

echo.
echo Installing OpenAI client...
pip install openai

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo To use the virtual environment:
echo 1. Run: venv\Scripts\activate.bat
echo 2. Then: python app.py
echo.
echo To deactivate: deactivate
echo.
pause
