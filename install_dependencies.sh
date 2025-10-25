#!/bin/bash

echo "========================================"
echo "Installing Required Dependencies"
echo "========================================"
echo ""

echo "Installing python-docx..."
pip install python-docx==1.1.0

echo ""
echo "Installing PyMuPDF..."
pip install PyMuPDF==1.23.8

echo ""
echo "Installing pytesseract..."
pip install pytesseract==0.3.10

echo ""
echo "Installing Pillow..."
pip install Pillow==10.2.0

echo ""
echo "Installing python-dotenv..."
pip install python-dotenv==1.0.0

echo ""
echo "Installing requests..."
pip install requests==2.31.0

echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo ""
echo "Note: For pytesseract to work, you also need to install Tesseract OCR:"
echo "Ubuntu/Debian: sudo apt-get install tesseract-ocr"
echo "macOS: brew install tesseract"
echo ""
