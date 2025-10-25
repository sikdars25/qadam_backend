@echo off
echo ========================================
echo Installing OCR Support for Scanned PDFs
echo ========================================
echo.
echo This will install:
echo - pytesseract (OCR library)
echo - Pillow (Image processing)
echo - pdf2image (PDF to image conversion)
echo.
echo NOTE: You also need to install Tesseract-OCR separately!
echo Download from: https://github.com/UB-Mannheim/tesseract/wiki
echo.
pause

echo.
echo Step 1: Installing Python packages...
pip install pytesseract
pip install Pillow
pip install pdf2image
pip install paddleocr
pip install paddlepaddle

echo.
echo Step 2: Verifying installation...
python -c "import pytesseract; from PIL import Image; print('✓ Python packages installed')"
python -c "import paddleocr; print('✓ PaddleOCR installed')"
python -c "import paddlepaddle; print('✓ PaddlePaddle installed')"

echo.
echo ========================================
echo Python Packages Installed!
echo ========================================
echo.
echo IMPORTANT: You still need to install Tesseract-OCR:
echo.
echo 1. Download from: https://github.com/UB-Mannheim/tesseract/wiki
echo 2. Install the .exe file
echo 3. Add to PATH or configure pytesseract
echo.
echo After installing Tesseract, restart backend: python app.py
echo.
pause
