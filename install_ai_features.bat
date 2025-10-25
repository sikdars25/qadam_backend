@echo off
echo ========================================
echo AI Features Installation
echo ========================================
echo.
echo This will install ALL AI dependencies:
echo - PyMuPDF (PDF processing)
echo - sentence-transformers (AI embeddings)
echo - FAISS (vector database)
echo - Groq API client (for AI solutions)
echo - python-dotenv (environment variables)
echo - All required dependencies
echo.
echo Download size: ~500MB (first time)
echo Installation time: 5-10 minutes
echo.
echo NOTE: Make sure you have a Groq API key ready!
echo Get one free at: https://console.groq.com
echo.
pause

echo.
echo Step 1: Upgrading pip...
python -m pip install --upgrade pip

echo.
echo Step 2: Installing core dependencies...
pip install PyMuPDF==1.23.8
pip install python-dotenv==1.0.0

echo.
echo Step 3: Installing numpy...
pip install numpy

echo.
echo Step 4: Installing FAISS vector database...
pip install faiss-cpu

echo.
echo Step 5: Installing pydantic...
pip install pydantic

echo.
echo Step 6: Installing Groq API client...
pip install groq

echo.
echo Step 7: Installing sentence-transformers (large download)...
pip install sentence-transformers

echo.
echo Step 8: Verifying installation...
python -c "import fitz; print('✓ PyMuPDF')"
python -c "import numpy; print('✓ NumPy')"
python -c "import faiss; print('✓ FAISS')"
python -c "import pydantic; print('✓ Pydantic')"
python -c "import groq; print('✓ Groq')"
python -c "from sentence_transformers import SentenceTransformer; print('✓ Sentence Transformers')"

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo All AI dependencies are now installed!
echo.
echo Next steps:
echo 1. Create .env file with: GROQ_API_KEY=your_key_here
echo 2. Restart backend: python app.py
echo 3. Look for: "AI features enabled ✓"
echo 4. Test features in frontend
echo.
pause
