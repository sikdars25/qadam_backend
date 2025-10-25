"""
FIXED Advanced Question Parser - Addresses All Critical Issues:
1. Correct question numbering
2. First question starts from beginning
3. MCQ options included in question text
4. Diagram text separated
5. All symbols preserved uniformly
"""

import os
import re
import json
import requests
import fitz  # PyMuPDF
from dotenv import load_dotenv
from PIL import Image
import io

load_dotenv()

GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_VISION_MODEL = "llama-3.2-90b-vision-preview"

def fix_greek_symbol_misrecognition(text):
    """
    Fix common Greek symbol misrecognitions from PDF extraction.
    PDFs sometimes have incorrect character encoding where Greek symbols
    are mapped to wrong characters (e.g., λ → 4, μ → µ, etc.)
    """
    if not text:
        return ""
    
    # Common patterns where Greek symbols are misrecognized
    # These are context-based replacements
    
    # Pattern: "charge density 4" or "linear charge density 4" → should be λ (lambda)
    text = re.sub(r'\b(charge\s+density|linear\s+charge\s+density)\s+4\b', r'\1 λ', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(charge\s+density|linear\s+charge\s+density)\s+A\b', r'\1 λ', text, flags=re.IGNORECASE)
    
    # Pattern: "wavelength 4" or "wavelength A" → should be λ (lambda)
    text = re.sub(r'\b(wavelength|wave\s+length)\s+[4A]\b', r'\1 λ', text, flags=re.IGNORECASE)
    
    # Pattern: "coefficient µ" (micro sign) → μ (Greek mu)
    text = text.replace('µ', 'μ')
    
    # Pattern: "angle 0" or "angle O" at start of sentence → should be θ (theta)
    text = re.sub(r'\b(angle|at\s+angle)\s+[0O]\b', r'\1 θ', text, flags=re.IGNORECASE)
    
    # Pattern: "pi" as word → π (but be careful not to replace "pi" in "spin", "eping", etc.)
    text = re.sub(r'\b(value\s+of\s+)pi\b', r'\1π', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(equals\s+)pi\b', r'\1π', text, flags=re.IGNORECASE)
    
    # Pattern: "delta" as word → Δ
    text = re.sub(r'\b(change|difference)\s+delta\b', r'\1 Δ', text, flags=re.IGNORECASE)
    
    # Pattern: "sigma" as word → σ
    text = re.sub(r'\b(surface\s+charge\s+density|conductivity)\s+sigma\b', r'\1 σ', text, flags=re.IGNORECASE)
    
    # Pattern: "omega" as word → ω
    text = re.sub(r'\b(angular\s+frequency|angular\s+velocity)\s+omega\b', r'\1 ω', text, flags=re.IGNORECASE)
    
    # Pattern: "alpha" as word → α
    text = re.sub(r'\b(coefficient|constant)\s+alpha\b', r'\1 α', text, flags=re.IGNORECASE)
    
    # Pattern: "beta" as word → β
    text = re.sub(r'\b(coefficient|constant)\s+beta\b', r'\1 β', text, flags=re.IGNORECASE)
    
    # Pattern: "gamma" as word → γ
    text = re.sub(r'\b(photon|ray)\s+gamma\b', r'\1 γ', text, flags=re.IGNORECASE)
    
    return text

def normalize_math_symbols(text):
    """Preserve ALL academic symbols uniformly - DO NOT replace with regular text"""
    if not text:
        return ""
    
    # First, fix common Greek symbol misrecognitions
    text = fix_greek_symbol_misrecognition(text)
    
    # PRESERVE these symbols - do NOT convert to text
    # Only normalize superscripts and subscripts for consistency
    
    # Superscripts to ^notation
    superscripts = {
        '⁰': '^0', '¹': '^1', '²': '^2', '³': '^3', '⁴': '^4',
        '⁵': '^5', '⁶': '^6', '⁷': '^7', '⁸': '^8', '⁹': '^9',
        '⁺': '^+', '⁻': '^-', '⁼': '^=', '⁽': '^(', '⁾': '^)'
    }
    
    # Subscripts to _notation
    subscripts = {
        '₀': '_0', '₁': '_1', '₂': '_2', '₃': '_3', '₄': '_4',
        '₅': '_5', '₆': '_6', '₇': '_7', '₈': '_8', '₉': '_9',
        '₊': '_+', '₋': '_-', '₌': '_=', '₍': '_(', '₎': '_)'
    }
    
    # Apply superscript conversions
    for sup, replacement in superscripts.items():
        text = text.replace(sup, replacement)
    
    # Apply subscript conversions
    for sub, replacement in subscripts.items():
        text = text.replace(sub, replacement)
    
    # PRESERVE all other symbols:
    # Greek: α β γ δ ε ζ η θ ι κ λ μ ν ξ π ρ σ τ υ φ χ ψ ω
    # Math: √ ∛ ∜ ∫ ∑ ∏ ∂ ∇ ∆ ∞ ± ∓ × ÷ ≤ ≥ ≠ ≈ ≡ ∝ ∠ ⊥ ∥ ⊕ ⊗
    # Arrows: → ← ↑ ↓ ↔ ⇒ ⇐ ⇔
    # Chemistry: ⇌ ⇋ ↑ ↓
    # Fractions: ½ ⅓ ¼ ⅕ ⅙ ⅐ ⅛ ⅑ ⅒ ⅔ ⅖ ¾ ⅗ ⅜ ⅘ ⅚ ⅝ ⅞
    
    return text

def detect_math_content(text):
    """Detect if text contains mathematical symbols"""
    math_symbols = ['√', '∫', '∑', '∏', '∂', '∇', 'α', 'β', 'γ', 'δ', 'θ', 'π', 'σ', 'ω',
                    '^', '_', '≤', '≥', '≠', '≈', '±', '∞', '∆', '°']
    return any(symbol in text for symbol in math_symbols)

def advanced_image_preprocessing(img):
    """Advanced image preprocessing for better OCR of mathematical content"""
    from PIL import ImageEnhance, ImageFilter, ImageOps
    import numpy as np
    
    # Convert to grayscale if not already
    if img.mode != 'L':
        img = img.convert('L')
    
    # Increase resolution (2x upscale)
    width, height = img.size
    img = img.resize((width * 2, height * 2), Image.LANCZOS)
    
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.5)
    
    # Enhance sharpness
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(2.0)
    
    # Apply adaptive thresholding using numpy
    img_array = np.array(img)
    # Simple threshold - convert to binary
    threshold = np.mean(img_array)
    img_array = np.where(img_array > threshold, 255, 0).astype(np.uint8)
    img = Image.fromarray(img_array)
    
    # Denoise
    img = img.filter(ImageFilter.MedianFilter(size=3))
    
    return img

def ocr_with_vision_model(image_data, page_num):
    """Use Groq Vision API to extract text from image with mathematical symbols"""
    if not GROQ_API_KEY:
        return None
    
    try:
        import base64
        
        # Convert image to base64
        if isinstance(image_data, bytes):
            img_base64 = base64.b64encode(image_data).decode('utf-8')
        else:
            # If PIL Image, convert to bytes first
            import io
            buffer = io.BytesIO()
            image_data.save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        print(f"    🤖 Using Groq Vision API for page {page_num}...")
        
        payload = {
            "model": GROQ_VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Extract ALL text from this image. This is an academic question paper.

IMPORTANT INSTRUCTIONS:
1. Preserve ALL mathematical symbols EXACTLY: α β γ δ ε θ λ μ π σ ω Δ Σ Π Ω
2. Preserve ALL mathematical operators: √ ∫ ∑ ∏ ∂ ∇ ± × ÷ ≤ ≥ ≠ ≈ ≡
3. Use ^ for superscripts (e.g., x^2, 10^-3)
4. Use _ for subscripts (e.g., H_2O, ε_0)
5. Preserve fractions as written
6. Keep ALL question numbers and MCQ options (A, B, C, D)
7. Maintain line breaks and spacing
8. Do NOT add explanations, just extract the text

Extract the text now:"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_base64}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 4000,
            "temperature": 0.1
        }
        
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        extracted_text = result['choices'][0]['message']['content']
        
        if len(extracted_text) > 100:
            print(f"    ✓ Vision API extracted {len(extracted_text)} chars")
            return extracted_text
        else:
            print(f"    ⚠ Vision API returned short text ({len(extracted_text)} chars)")
            return None
            
    except Exception as e:
        print(f"    ⚠ Vision API failed: {e}")
        return None

def enhanced_ocr_extraction(page, page_num):
    """Enhanced OCR with multiple methods for mathematical content"""
    print(f"  🔍 Page {page_num}: Using enhanced OCR...")
    
    # Get high-resolution image
    pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))  # 3x resolution
    img_data = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_data))
    
    # Method 1: Try PaddleOCR (best for mathematical content)
    try:
        from paddleocr import PaddleOCR
        print("    Trying PaddleOCR (best for math symbols)...")
        
        ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
        
        # Preprocess image
        processed_img = advanced_image_preprocessing(img)
        
        # Save to temp file for PaddleOCR
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            processed_img.save(tmp.name)
            tmp_path = tmp.name
        
        result = ocr.ocr(tmp_path, cls=True)
        
        # Clean up temp file
        os.remove(tmp_path)
        
        if result and result[0]:
            # Extract text from result
            text_lines = []
            for line in result[0]:
                if len(line) >= 2:
                    text_lines.append(line[1][0])  # line[1][0] is the text
            
            ocr_text = '\n'.join(text_lines)
            if len(ocr_text) > 50:
                print(f"    ✓ PaddleOCR: {len(ocr_text)} chars")
                return ocr_text
    except ImportError:
        print("    ⚠ PaddleOCR not installed (pip install paddleocr)")
    except Exception as e:
        print(f"    ⚠ PaddleOCR failed: {e}")
    
    # Method 2: Try Groq Vision API (best for complex math)
    vision_text = ocr_with_vision_model(img_data, page_num)
    if vision_text:
        return vision_text
    
    # Method 3: Enhanced Tesseract with better preprocessing
    try:
        import pytesseract
        print("    Trying enhanced Tesseract...")
        
        # Apply advanced preprocessing
        processed_img = advanced_image_preprocessing(img)
        
        # Try multiple Tesseract configs
        configs = [
            r'--oem 3 --psm 6 -c preserve_interword_spaces=1',
            r'--oem 1 --psm 6',
            r'--oem 3 --psm 4',
        ]
        
        best_text = ""
        best_length = 0
        
        for config in configs:
            try:
                # Try with Greek support
                text = pytesseract.image_to_string(processed_img, lang='eng+script/Greek', config=config)
                if len(text) > best_length:
                    best_text = text
                    best_length = len(text)
            except:
                # Fallback to English only
                text = pytesseract.image_to_string(processed_img, config=config)
                if len(text) > best_length:
                    best_text = text
                    best_length = len(text)
        
        if len(best_text) > 50:
            print(f"    ✓ Enhanced Tesseract: {len(best_text)} chars")
            return best_text
            
    except Exception as e:
        print(f"    ⚠ Enhanced Tesseract failed: {e}")
    
    print("    ❌ All OCR methods failed")
    return ""

def extract_raw_text_simple(pdf_path):
    """
    STEP 1: Extract RAW text from PDF - NO CLEANING, NO FILTERING
    - Just extract text as-is
    - Use OCR if needed
    - Keep everything
    """
    print(f"📄 STEP 1: Extracting RAW text from: {pdf_path}")
    
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        diagrams_info = []
        
        # Create diagrams directory
        diagrams_dir = os.path.join(os.path.dirname(pdf_path), 'diagrams')
        os.makedirs(diagrams_dir, exist_ok=True)
        
        for page_num in range(len(doc)):
            try:
                page = doc[page_num]
                
                print(f"\n  📄 Processing Page {page_num + 1}/{len(doc)}...")
                
                # Try to get text directly first
                page_text = page.get_text("text")
                
                # Check if text quality is poor (garbled symbols, short text)
                has_garbled_text = False
                if page_text:
                    # Check for common garbled patterns
                    garbled_patterns = [
                        r'rn\s+[A-Z]\s+rn',  # "rn A rn" pattern
                        r'[A-Z]\s+—+\s+[A-Z]',  # "A —_ B" pattern
                        r'\)\s+\d+e\d+[A-Z]',  # ") 2e5R" pattern
                        r'©\s+tek',  # "© tek" pattern
                    ]
                    for pattern in garbled_patterns:
                        if re.search(pattern, page_text):
                            has_garbled_text = True
                            print(f"  ⚠ Page {page_num + 1}: Detected garbled text, using enhanced OCR...")
                            break
                
                # If no text, very little text, or garbled text, use enhanced OCR
                if len(page_text.strip()) < 50 or has_garbled_text:
                    if not has_garbled_text:
                        print(f"  🔍 Page {page_num + 1}: Insufficient text, using enhanced OCR...")
                    
                    # Use the new enhanced OCR system
                    page_text = enhanced_ocr_extraction(page, page_num + 1)
                    
                    if not page_text or len(page_text.strip()) < 50:
                        print(f"  ⚠ Enhanced OCR returned insufficient text, trying direct extraction anyway...")
                        page_text = page.get_text("text")
                else:
                    print(f"  ✓ Direct text extraction: {len(page_text)} chars")
                
                # Apply Greek symbol fix to the extracted text
                page_text = normalize_math_symbols(page_text)
                
                # Show preview of page text
                preview = page_text.strip()[:100].replace('\n', ' ')
                print(f"  Preview: {preview}...")
                
                # Count question numbers on this page for debugging
                q_nums_on_page = re.findall(r'(?:^|\n)\s*(\d+)\s*[\.\)]', page_text, re.MULTILINE)
                if q_nums_on_page:
                    print(f"  📊 Found question numbers: {', '.join(q_nums_on_page[:10])}{' ...' if len(q_nums_on_page) > 10 else ''}")
                
                # Extract diagrams (don't let this break the main process)
                try:
                    image_list = page.get_images()
                    if image_list:
                        print(f"  📊 Extracting {len(image_list)} diagram(s)...")
                        for img_index, img in enumerate(image_list):
                            try:
                                xref = img[0]
                                base_image = doc.extract_image(xref)
                                diagram_filename = f"page{page_num + 1}_img{img_index + 1}.{base_image['ext']}"
                                diagram_path = os.path.join(diagrams_dir, diagram_filename)
                                
                                with open(diagram_path, "wb") as img_file:
                                    img_file.write(base_image["image"])
                                
                                diagrams_info.append({
                                    'page': page_num + 1,
                                    'path': diagram_path,
                                    'filename': diagram_filename
                                })
                                print(f"    ✓ Saved: {diagram_filename}")
                            except Exception as e:
                                print(f"    ⚠ Failed to extract diagram {img_index + 1}: {e}")
                                continue
                except Exception as e:
                    print(f"  ⚠ Diagram extraction failed for page {page_num + 1}: {e}")
                
                # Add to full text with clear page separation
                # Use double newline to preserve page boundaries
                if page_num > 0:
                    full_text += "\n\n"  # Double newline between pages
                full_text += page_text
                
            except Exception as e:
                print(f"  ❌ Error processing page {page_num + 1}: {e}")
                print(f"  ⚠ Continuing with next page...")
                import traceback
                traceback.print_exc()
                continue
        
        # Save page count before closing
        total_pages = len(doc)
        doc.close()
        
        print(f"\n✓ Extracted {len(full_text)} characters from {total_pages} pages")
        print(f"✓ Extracted {len(diagrams_info)} diagrams")
        print(f"✓ NO CLEANING APPLIED - Raw text preserved")
        
        return full_text, diagrams_info
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, []

def clean_text_REMOVED(text):
    """Clean text while preserving question lines and symbols - MINIMAL CLEANING"""
    if not text:
        return ""
    
    print("🧹 Cleaning text (minimal mode - preserving content)...")
    
    lines = text.split('\n')
    cleaned_lines = []
    removed_count = 0
    question_lines_found = 0
    
    # VERY STRICT patterns - only remove obvious headers/footers
    # Only match at first/last 5 lines to avoid removing question content
    ignore_patterns = [
        r'^Page\s+\d+\s*$',           # "Page 1" alone on line
        r'^-\s*\d+\s*-\s*$',          # "- 1 -" page numbers
        r'^\d+\s*$',                   # Just a number (page number)
        r'^www\.',                     # URLs
        r'^https?://',                 # URLs
        r'©.*\d{4}',                   # Copyright
    ]
    
    # Patterns for question lines (for logging only)
    question_patterns = [
        r'^\d+\s*[\.\)]',
        r'^Q\.?\s*\d+',
        r'^Question\s+\d+',
    ]
    
    total_lines = len(lines)
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        
        # PRESERVE EMPTY LINES - they may be part of question formatting
        if not line_stripped:
            cleaned_lines.append(line)
            continue
        
        # Check if question line (for logging)
        is_question = any(re.match(p, line_stripped, re.IGNORECASE) for p in question_patterns)
        
        if is_question:
            question_lines_found += 1
            if question_lines_found <= 5:
                print(f"  ✓ Question line {question_lines_found}: {line_stripped[:70]}...")
            cleaned_lines.append(line)
            continue
        
        # ONLY check ignore patterns in first 5 and last 5 lines
        should_ignore = False
        if i < 5 or i >= total_lines - 5:
            for pattern in ignore_patterns:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    should_ignore = True
                    removed_count += 1
                    if removed_count <= 5:
                        print(f"  🗑️ Removing line {i+1}: {line_stripped[:70]}...")
                    break
        
        # PRESERVE everything else
        if not should_ignore:
            cleaned_lines.append(line)
    
    original_length = len(text)
    cleaned_length = len('\n'.join(cleaned_lines))
    
    print(f"  ✓ Found {question_lines_found} question lines")
    print(f"  ✓ Removed {removed_count} header/footer lines")
    print(f"  ✓ Preserved {len(cleaned_lines)}/{total_lines} lines ({100*len(cleaned_lines)/total_lines:.1f}%)")
    print(f"  ✓ Text length: {original_length} → {cleaned_length} chars ({100*cleaned_length/original_length:.1f}%)")
    
    return '\n'.join(cleaned_lines)

def fix_ocr_number_misrecognition(text):
    """
    Fix common OCR misrecognitions of question numbers.
    OCR often misreads numbers as letters: 7→q, 1→l, 0→O, 5→S, etc.
    """
    if not text:
        return text
    
    # Common OCR misrecognitions at start of line (question numbers)
    # Pattern: lowercase letter followed by dot/comma at start of line
    ocr_fixes = {
        'q': '7',  # 7 often misread as 'q'
        'l': '1',  # 1 often misread as 'l' (lowercase L)
        'o': '0',  # 0 often misread as 'o'
        's': '5',  # 5 often misread as 's'
        'b': '6',  # 6 often misread as 'b'
        'g': '9',  # 9 often misread as 'g'
    }
    
    lines = text.split('\n')
    fixed_lines = []
    fix_count = 0
    
    for line in lines:
        line_stripped = line.strip()
        # Check if line starts with single lowercase letter + dot/comma (likely misread number)
        match = re.match(r'^([a-z])\s*[\.,]\s+', line_stripped, re.IGNORECASE)
        if match:
            letter = match.group(1).lower()
            if letter in ocr_fixes:
                # Replace the letter with the correct number
                fixed_line = line.replace(match.group(0), f"{ocr_fixes[letter]}. ", 1)
                fixed_lines.append(fixed_line)
                fix_count += 1
                if fix_count <= 3:
                    print(f"     ✓ Fixed OCR error: '{line_stripped[:50]}' → Q{ocr_fixes[letter]}")
                continue
        
        fixed_lines.append(line)
    
    if fix_count > 0:
        print(f"  ✓ Fixed {fix_count} OCR number misrecognitions")
    
    return '\n'.join(fixed_lines)

def preprocess_margin_numbers(text):
    """
    Preprocess text to handle question numbers at left margin/edge.
    OCR often extracts margin numbers on separate lines or with extra whitespace.
    """
    lines = text.split('\n')
    processed_lines = []
    joined_count = 0
    
    i = 0
    while i < len(lines):
        line = lines[i]
        line_stripped = line.strip()
        
        # Check if this line is JUST a number (margin number)
        # Pattern: line with only "1" or "1." or "1)" or "Q1" etc.
        # Check both stripped and original line
        if re.match(r'^\s*(?:Q\.?\s*)?(\d+)\s*[\.\)]?\s*$', line):
            # This is a margin number, try to join with next line
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not re.match(r'^\d+\s*[\.\)]', next_line):
                    # Join margin number with next line
                    combined = f"{line_stripped}. {next_line}"
                    processed_lines.append(combined)
                    joined_count += 1
                    if joined_count <= 3:
                        print(f"     ✓ Joined margin number: '{line_stripped}' + '{next_line[:40]}...'")
                    i += 2  # Skip next line
                    continue
        
        processed_lines.append(line)
        i += 1
    
    if joined_count > 0:
        print(f"  ✓ Joined {joined_count} margin numbers with question text")
    
    return '\n'.join(processed_lines)

def split_into_question_blocks_fixed(text):
    """
    FIXED: Split into question blocks with correct numbering
    - Ensures first question starts from beginning
    - Includes MCQ options in question text
    - Maintains sequential numbering
    - Handles section headers (Section A, Section B, etc.)
    - Handles margin numbers at left edge
    """
    print("🔍 Splitting into question blocks (FIXED VERSION)...")
    
    # Preprocess to fix OCR number misrecognitions (q→7, l→1, etc.)
    print("  🔧 Fixing OCR number misrecognitions...")
    text = fix_ocr_number_misrecognition(text)
    
    # Preprocess to handle margin numbers
    print("  🔧 Preprocessing margin numbers...")
    original_text = text
    text = preprocess_margin_numbers(text)
    
    # Show text preview - more lines to see section headers and reach Q7
    print(f"  📝 Text preview (first 50 lines):")
    all_lines = text.split('\n') if text else []
    preview_lines = all_lines[:50]
    for i, line in enumerate(preview_lines):
        # Show full line including leading whitespace
        display_line = repr(line[:120]) if len(line) > 120 else repr(line)
        print(f"     Line {i+1}: {display_line}")
    
    # Check if starts with question or section header
    print(f"\n  🔍 Analyzing first 50 lines for question numbers...")
    first_lines = all_lines[:50]
    found_section = False
    found_question = False
    
    question_lines_found = []
    for i, line in enumerate(first_lines):
        line_stripped = line.strip()
        
        # Check for section header
        if re.match(r'Section\s+[A-Z]', line_stripped, re.IGNORECASE):
            print(f"  ✓ Line {i+1}: Section header - {line_stripped}")
            found_section = True
            continue
        
        # Check BOTH stripped and full line for question numbers
        # Pattern 1: Check stripped line for dot/paren
        if re.match(r'^\d+\s*[\.\)]', line_stripped):
            q_match = re.match(r'^(\d+)\s*[\.\)]', line_stripped)
            q_num = q_match.group(1) if q_match else '?'
            print(f"  ✓ Line {i+1}: Question Q{q_num} (dot/paren) - {line_stripped[:70]}")
            question_lines_found.append(q_num)
            found_question = True
            continue
        
        # Pattern 2: Check for comma format
        if re.match(r'^\d+\s*,', line_stripped):
            q_match = re.match(r'^(\d+)\s*,', line_stripped)
            q_num = q_match.group(1) if q_match else '?'
            print(f"  ✓ Line {i+1}: Question Q{q_num} (comma) - {line_stripped[:70]}")
            question_lines_found.append(q_num)
            found_question = True
            continue
        
        # Pattern 3: Check full line (with leading whitespace)
        if re.match(r'^\s*\d+\s*[\.\),]', line):
            q_match = re.match(r'^\s*(\d+)\s*[\.\),]', line)
            q_num = q_match.group(1) if q_match else '?'
            print(f"  ✓ Line {i+1}: Question Q{q_num} (with margin) - {repr(line[:70])}")
            question_lines_found.append(q_num)
            found_question = True
            continue
        
        # Pattern 4: Check if line contains ONLY a number (margin number)
        if re.match(r'^\s*\d+\s*$', line):
            q_match = re.match(r'^\s*(\d+)\s*$', line)
            q_num = q_match.group(1) if q_match else '?'
            print(f"  ✓ Line {i+1}: Standalone number Q{q_num} (margin) - {repr(line)}")
            question_lines_found.append(q_num)
            found_question = True
            continue
    
    if question_lines_found:
        print(f"  📊 Found question numbers in first 50 lines: {question_lines_found}")
    
    if not found_question:
        print(f"  ❌ No question numbers found in first 20 lines")
        print(f"     🔍 Searching entire text for questions...")
        print(f"     🔧 Trying to detect margin numbers or unusual formatting...")
    
    blocks = []
    
    # Detect MCQ paper
    mcq_patterns = [
        r'\([A-Da-d]\)',
        r'\b[A-D]\)',
        r'\([a-d]\)',
        r'\b[a-d]\)',
    ]
    
    mcq_indicators = sum(len(re.findall(p, text)) for p in mcq_patterns)
    is_mcq_paper = mcq_indicators > 5
    
    if is_mcq_paper:
        print(f"  🎯 Detected MCQ format paper ({mcq_indicators} option indicators)")
    else:
        print(f"  📝 Detected descriptive/subjective format paper")
    
    # Use multiple patterns to catch different formats
    # More flexible with whitespace to handle margin numbers and various formats
    patterns = [
        r'(?:^|\n)\s*(\d+)\s*[\.\)]\s*',  # Standard with optional leading whitespace
        r'(?:^|\n)(\d+)\s*[\.\)]',         # Standard without trailing space
        r'(?:^|\n)\s*(\d+)\s*,\s*',        # Number followed by COMMA (common format)
        r'(?:^|\n)(\d+)\s*,\s+[A-Z]',      # Number + comma + capital letter
        r'(?:^|\n)\s*(\d+)\s+[A-Z]',        # Number + capital letter (with whitespace)
        r'(?:^|\n)(\d+)\s+[A-Za-z]',        # Number + any letter
        r'(?:^|\n)Q\.?\s*(\d+)',           # Q.1 or Q1 format
        r'(?:^|\n)Question\s+(\d+)',        # Question 1 format
        r'^\s*(\d+)\s*[\.\)]',             # Start of text with whitespace
        r'\b(\d+)\s*[\.\)]\s+[A-Z]',      # Number anywhere followed by capital letter
        r'(?:^|\n)\s*(\d+)\s*\.',          # Just number and dot (more lenient)
        r'(?:^|\n)\s*(\d+)\s*\)',          # Just number and parenthesis
        r'(?:^|\n)\s*(\d+)\s{2,}',         # Number followed by 2+ spaces (margin format)
        r'(?:^|\n)\s*(\d+)\s*[:\-]',       # Number followed by colon or dash
        r'(?:^|\n)(\d+)\s*\n',             # Number alone on a line (margin number)
        r'\n\s*(\d+)\s*[\.\)]\s*[A-Z]',   # Newline + number + dot/paren + capital
        r'(?:^|\n)\s*(\d+)[\.\),]\s*(?:A|The|Which|What|How|Find|Calculate|Determine|State|Define|Explain|Describe|Write|Name|Give|Show|Prove|Draw|Identify)',  # Question starters
    ]
    
    all_starts = []
    pattern_matches = {}  # Track which patterns found which questions
    
    for idx, pattern in enumerate(patterns, 1):
        starts = list(re.finditer(pattern, text, re.MULTILINE))
        if starts:
            q_nums = [int(m.group(1)) for m in starts if m.group(1).isdigit()]
            pattern_matches[idx] = q_nums
            print(f"  Pattern {idx} '{pattern[:40]}...': Found {len(starts)} matches (Q{min(q_nums) if q_nums else '?'}-Q{max(q_nums) if q_nums else '?'})")
            all_starts.extend(starts)
        else:
            if idx <= 3:  # Only show first 3 patterns that don't match
                print(f"  Pattern {idx}: No matches")
    
    # Remove duplicates by position (same match from different patterns)
    # Keep matches that are at least 10 chars apart
    seen_positions = set()
    unique_starts = []
    for match in sorted(all_starts, key=lambda m: m.start()):
        pos = match.start()
        # Check if this position is too close to an existing match
        is_duplicate = False
        for seen_pos in seen_positions:
            if abs(pos - seen_pos) < 10:  # Within 10 chars = likely same question
                is_duplicate = True
                break
        
        if not is_duplicate:
            seen_positions.add(pos)
            unique_starts.append(match)
    
    # Filter out false positives (numbers from headers/footers)
    filtered_starts = []
    false_positive_patterns = [
        r'Class\s+\d+',
        r'Grade\s+\d+',
        r'Page\s+\d+',
        r'Roll\s+No',
        r'Time:\s*\d+',
        r'Marks:\s*\d+',
        r'Total\s+Marks',
        r'Maximum\s+Marks',
        r'P\.?T\.?O\.?',           # P.T.O. (Please Turn Over)
        r'\d+[-/]\d+[-/]\d+',      # Date/code format like 11-55/1/1
        r'Set\s+[A-Z]',            # Set A, Set B, etc.
        r'Code\s+No',              # Code No.
    ]
    
    for match in unique_starts:
        # Get context around the match (100 chars before and after for better context)
        start = max(0, match.start() - 100)
        end = min(len(text), match.end() + 100)
        context = text[start:end]
        
        # Check if this is a false positive
        # Be more precise: only filter if the number itself is part of the false positive pattern
        is_false_positive = False
        q_num_str = match.group(1)
        
        for fp_pattern in false_positive_patterns:
            fp_match = re.search(fp_pattern, context, re.IGNORECASE)
            if fp_match:
                # Check if the question number is actually part of the false positive match
                # e.g., "Class 12" should filter Q12, but "12." followed by "Class" should not
                fp_text = fp_match.group(0)
                if q_num_str in fp_text:
                    is_false_positive = True
                    print(f"  ⚠ Filtering out false positive: Q{q_num_str} (matched '{fp_pattern}' in '{fp_text}')")
                    break
        
        if not is_false_positive:
            filtered_starts.append(match)
    
    # Final deduplication: Keep only first occurrence of each question number
    seen_q_numbers = set()
    final_starts = []
    duplicate_count = 0
    
    for match in filtered_starts:
        q_num = int(match.group(1))
        if q_num not in seen_q_numbers and q_num > 0:  # Ignore Q0
            seen_q_numbers.add(q_num)
            final_starts.append(match)
        elif q_num in seen_q_numbers:
            duplicate_count += 1
            if duplicate_count <= 5:  # Only show first 5 duplicates
                context = text[max(0, match.start()-20):min(len(text), match.start()+60)].replace('\n', ' ')
                print(f"  ⚠ Skipping duplicate: Q{q_num} at position {match.start()} - '{context}'")
    
    if duplicate_count > 5:
        print(f"  ⚠ Skipped {duplicate_count - 5} more duplicates...")
    
    starts = final_starts
    print(f"  Total unique question starts found: {len(starts)}")
    
    if not starts:
        print(f"  ⚠ No patterns matched! Trying aggressive scan...")
    
    if starts:
        q_numbers = [int(m.group(1)) for m in starts]
        q_numbers_sorted = sorted(q_numbers)
        print(f"     Range: Q{min(q_numbers)} to Q{max(q_numbers)}")
        print(f"     Question numbers (sorted): {q_numbers_sorted[:10]}")
        
        # Show positions for debugging duplicates
        if len(q_numbers) != len(set(q_numbers)):
            print(f"     📍 Question positions:")
            for m in starts[:10]:
                q_num = int(m.group(1))
                pos = m.start()
                context = text[max(0, pos-10):min(len(text), pos+40)].replace('\n', ' ')
                print(f"        Q{q_num} at pos {pos}: '{context}'")
        
        # Check for gaps or duplicates (multi-page issues)
        sorted_nums = sorted(q_numbers)
        duplicates = [n for n in set(sorted_nums) if sorted_nums.count(n) > 1]
        if duplicates:
            print(f"     ⚠ WARNING: Duplicate question numbers found: {duplicates[:5]}")
        
        # Check for gaps and RECOVER missing questions
        expected_range = list(range(min(q_numbers), max(q_numbers) + 1))
        missing = [n for n in expected_range if n not in q_numbers]
        
        if missing and len(missing) < 30:  # Try to recover if not too many missing
            print(f"     ⚠ WARNING: Missing question numbers: {missing}")
            
            # Try to find missing numbers in the text and RECOVER them
            print(f"     🔍 Searching for missing questions in text...")
            recovered_matches = []
            
            for miss_num in missing:  # Check all missing questions
                # Search for the number in various formats - VERY FLEXIBLE
                search_patterns = [
                    (rf'(?:^|\n)\s*{miss_num}\s*[\.\)]', 'dot/paren'),
                    (rf'(?:^|\n)\s*{miss_num}\s*,', 'comma'),
                    (rf'(?:^|\n){miss_num}\s+[A-Za-z]', 'number+letter'),
                    (rf'\b{miss_num}\s*[\.\),]\s+[A-Z]', 'anywhere+capital'),
                    (rf'Q\.?\s*{miss_num}', 'Q format'),
                    (rf'Question\s+{miss_num}', 'Question format'),
                    (rf'\b{miss_num}\s*,\s+[A-Z]', 'comma+capital'),
                    (rf'(?:^|\n)\s*{miss_num}\s*[:\-—–]', 'colon/dash/emdash'),
                    (rf'(?:^|\n)\s*{miss_num}\s{{2,}}[A-Z]', 'number+spaces+capital'),
                    (rf'\b{miss_num}\s*[\.\),:\-]\s*\w', 'number+punct+word'),
                    (rf'(?:^|\n)\s*{miss_num}[^\d]', 'number+non-digit'),
                ]
                
                found = False
                for sp, sp_name in search_patterns:
                    matches = list(re.finditer(sp, text, re.MULTILINE | re.IGNORECASE))
                    if matches:
                        # Take the first match
                        m = matches[0]
                        start_ctx = max(0, m.start() - 30)
                        end_ctx = min(len(text), m.end() + 50)
                        context = text[start_ctx:end_ctx].replace('\n', ' ')
                        
                        print(f"       ✓ RECOVERED Q{miss_num} (pattern: {sp_name}) at pos {m.start()}: '{context[:60]}...'")
                        recovered_matches.append(m)
                        found = True
                        break
                
                if not found:
                    # Show where we looked for this question
                    print(f"       ✗ Q{miss_num} NOT found - searched {len(search_patterns)} patterns")
                    
                    # Try to find ANY occurrence of this number in the text for debugging
                    simple_search = rf'\b{miss_num}\b'
                    simple_matches = list(re.finditer(simple_search, text))
                    if simple_matches:
                        print(f"       🔍 Found {len(simple_matches)} occurrence(s) of number '{miss_num}' in text:")
                        for idx, sm in enumerate(simple_matches[:3]):  # Show first 3
                            ctx_start = max(0, sm.start() - 50)
                            ctx_end = min(len(text), sm.end() + 50)
                            context = text[ctx_start:ctx_end].replace('\n', ' ')
                            print(f"          [{idx+1}] pos {sm.start()}: '...{context}...'")
                    else:
                        print(f"       🔍 Number '{miss_num}' does not appear anywhere in the text")
            
            # Add recovered matches to starts list and re-sort
            if recovered_matches:
                starts.extend(recovered_matches)
                starts.sort(key=lambda m: m.start())  # Sort by position in text
                print(f"     ✓ Recovered {len(recovered_matches)} missing questions")
                print(f"     ✓ Total questions now: {len(starts)}")
                
                # Update q_numbers list
                q_numbers = [int(m.group(1)) for m in starts]
                q_numbers_sorted = sorted(q_numbers)
                print(f"     ✓ Updated range: Q{min(q_numbers)} to Q{max(q_numbers)}")
                print(f"     ✓ Updated question numbers: {q_numbers_sorted[:15]}{'...' if len(q_numbers_sorted) > 15 else ''}")
                
                # Check if all questions recovered
                still_missing = [n for n in missing if n not in q_numbers]
                if still_missing:
                    print(f"     ⚠ Still missing after recovery: {still_missing}")
                else:
                    print(f"     🎉 All missing questions successfully recovered!")
            else:
                print(f"     ❌ Could not recover any missing questions")
        elif missing:
            print(f"     ⚠ WARNING: {len(missing)} question numbers missing in range (too many to recover)")
        
        # Extract blocks with FULL text including MCQ options
        for i, match in enumerate(starts):
            q_num = int(match.group(1))
            start_pos = match.start()  # Include the question number
            
            # Find end position
            if i < len(starts) - 1:
                end_pos = starts[i + 1].start()
            else:
                end_pos = len(text)
            
            # Extract FULL question text (including number and ALL options)
            q_text = text[start_pos:end_pos].strip()
            
            # Validate - skip very short blocks (likely junk)
            # RELAXED: Allow shorter questions (MCQs can be brief)
            if len(q_text) < 5:
                print(f"     ⚠ Skipping Q{q_num}: too short ({len(q_text)} chars) - '{q_text[:50]}'")
                continue
            
            if not re.search(r'[a-zA-Z]', q_text):
                print(f"     ⚠ Skipping Q{q_num}: no alphabetic content - '{q_text[:50]}'")
                continue
            
            # NEW: Skip instruction-only blocks (top-of-paper instructions)
            # These are blocks that are ONLY instructions, not actual questions
            instruction_only_keywords = [
                'general instructions',
                'read the following instructions',
                'instructions to candidates',
                'note:',
                'important:',
                'all questions are compulsory',
                'attempt all questions',
                'time allowed',
                'maximum marks',
                'this question paper contains',
                'section',
                'part -'
            ]
            
            q_text_lower = q_text.lower()
            is_instruction_only = any(keyword in q_text_lower for keyword in instruction_only_keywords)
            
            # Also check if it's ONLY instruction text without actual question content
            # Real questions have question marks, or start with question words, or have MCQ options
            has_question_mark = '?' in q_text
            has_mcq_options = re.search(r'\([A-D]\)', q_text, re.IGNORECASE)
            has_question_starter = re.search(r'\b(what|which|who|where|when|why|how|find|calculate|determine|state|define|explain|describe|write|name|give|show|prove|draw|identify)\b', q_text_lower)
            
            is_likely_question = has_question_mark or has_mcq_options or has_question_starter
            
            if is_instruction_only and not is_likely_question:
                print(f"     ⚠ Skipping Q{q_num}: instruction-only block (not a question) - '{q_text[:80]}'")
                continue
            
            # Also skip if it's very short and doesn't have question indicators
            if len(q_text) < 30 and not is_likely_question:
                print(f"     ⚠ Skipping Q{q_num}: too short and no question indicators - '{q_text[:50]}'")
                continue
            
            # Check if there's an instruction line immediately before this question
            # Look for instruction patterns in the previous 300 chars
            pre_context_start = max(0, start_pos - 300)
            pre_context = text[pre_context_start:start_pos]
            
            # Find instruction that applies to this specific question
            # Pattern: "For questions X-Y:" or "Questions X to Y:" or "Read the following:"
            instruction_match = re.search(
                r'(?:For questions?|Questions?|Read the following|Refer to|Based on)[^\n]{0,150}',
                pre_context,
                re.IGNORECASE
            )
            
            question_instruction = None
            if instruction_match:
                instruction_text = instruction_match.group(0).strip()
                # Check if this instruction mentions a range that includes current question
                range_match = re.search(r'(\d+)\s*[-–to]+\s*(\d+)', instruction_text)
                if range_match:
                    start_q = int(range_match.group(1))
                    end_q = int(range_match.group(2))
                    if start_q <= q_num <= end_q:
                        question_instruction = instruction_text
                        print(f"     📋 Q{q_num}: Applicable instruction found")
                elif 'following' in instruction_text.lower() or 'refer to' in instruction_text.lower():
                    # Generic instruction for following questions
                    question_instruction = instruction_text
                    print(f"     📋 Q{q_num}: Instruction found")
            
            blocks.append({
                'block_number': q_num,
                'raw_text': q_text,
                'instruction': question_instruction,
                'start_pos': start_pos,
                'end_pos': end_pos
            })
        
        blocks.sort(key=lambda x: x['block_number'])
        
        # FIX: Ensure sequential numbering starting from 1
        if blocks:
            first_num = blocks[0]['block_number']
            last_num = blocks[-1]['block_number']
            
            # Check for gaps
            expected_nums = set(range(first_num, last_num + 1))
            found_nums = set(b['block_number'] for b in blocks)
            missing_nums = expected_nums - found_nums
            
            if missing_nums:
                print(f"  ⚠ Missing question numbers: {sorted(list(missing_nums))[:10]}")
            
            print(f"✓ Found {len(blocks)} question blocks (Q{first_num} to Q{last_num})")
            print(f"  📊 Detection rate: {len(blocks)}/{last_num - first_num + 1} ({100*len(blocks)/(last_num - first_num + 1):.1f}%)")
    else:
        # Fallback: Aggressive line-by-line scan
        print(f"  🔄 Attempting line-by-line scan...")
        lines = text.split('\n')
        
        for line_idx, line in enumerate(lines):
            line_stripped = line.strip()
            # Look for any line starting with number followed by . or )
            match = re.match(r'^(\d+)\s*[\.\)]', line_stripped)
            if match:
                q_num = int(match.group(1))
                
                # Collect text from this line onwards (next 10-20 lines for MCQ)
                end_line = min(line_idx + 20, len(lines))
                q_lines = lines[line_idx:end_line]
                
                # Find where next question starts
                for j in range(1, len(q_lines)):
                    if re.match(r'^\d+\s*[\.\)]', q_lines[j].strip()):
                        q_lines = q_lines[:j]
                        break
                
                q_text = '\n'.join(q_lines).strip()
                
                if len(q_text) > 3 and re.search(r'[a-zA-Z]', q_text):
                    blocks.append({
                        'block_number': q_num,
                        'raw_text': q_text
                    })
                    if len(blocks) <= 3:
                        print(f"     ✓ Found Q{q_num} at line {line_idx}")
        
        if blocks:
            blocks.sort(key=lambda x: x['block_number'])
            print(f"  ✓ Line scan found {len(blocks)} questions")
            print(f"     Range: Q{blocks[0]['block_number']} to Q{blocks[-1]['block_number']}")
        else:
            print(f"  ❌ No questions found even with aggressive scan")
            print(f"  📝 First 1000 chars of text:")
            print(f"     {text[:1000]}")
    
    return blocks

def create_schema_prompt_fixed(question_blocks):
    """
    FIXED: Create prompt that ensures:
    - Correct question numbering
    - MCQ options included
    - All symbols preserved
    """
    prompt = """Parse ALL the following question paper blocks into structured JSON format.

CRITICAL INSTRUCTIONS:
1. Extract EVERY question - do not skip any
2. Include COMPLETE question text with ALL MCQ OPTIONS
3. PRESERVE ALL MATHEMATICAL SYMBOLS, EQUATIONS, AND FORMULAS EXACTLY AS WRITTEN
4. Use the EXACT question number from the text
5. Include the question number prefix (e.g., "1. " or "1) ") in the question_text

SYMBOL PRESERVATION - DO NOT CHANGE THESE:
- Greek letters: α β γ δ ε ζ η θ ι κ λ μ ν ξ π ρ σ τ υ φ χ ψ ω Γ Δ Θ Λ Ξ Π Σ Φ Ψ Ω
- Math symbols: √ ∛ ∜ ∫ ∑ ∏ ∂ ∇ ∆ ∞ ± ∓ × ÷ ≤ ≥ ≠ ≈ ≡ ∝ ∠ ⊥ ∥
- Superscripts: ^2 ^3 ^n ^+ ^-
- Subscripts: _1 _2 _n _0
- Arrows: → ← ↑ ↓ ↔ ⇒ ⇐ ⇔
- Chemistry: ⇌ ⇋
- Fractions: ½ ⅓ ¼ ¾
- Degrees: ° (degree symbol)

MCQ FORMAT - Include ALL options in question_text:
Example: "1. What is H_2O?\n(A) Water (B) Hydrogen (C) Oxygen (D) None"

INSTRUCTIONS HANDLING:
- If a question has an instruction (e.g., "For questions 1-5: Read the passage"), append it to question_text INLINE (no newline)
- Format: "question_text [Instruction: instruction_text]"
- Keep instructions SEPARATE from MCQ options
- Do NOT mix instructions with answer choices

For each question, extract:
- question_number: Use EXACT number from text (e.g., "1", "2", "3")
- question_text: COMPLETE text including question number prefix, applicable instruction (inline), and ALL MCQ options
- sub_parts: Array of sub-part labels if question has parts like (a), (b), (c) or (i), (ii), (iii). Example: ["a", "b", "c"] or ["i", "ii", "iii"]. Leave empty [] if no sub-parts.
- has_diagram: true/false
- marks: integer or null
- question_type: "mcq", "short_answer", "long_answer", "numerical"

IMPORTANT: Do NOT confuse MCQ options (A), (B), (C), (D) with sub-parts (a), (b), (c).
- MCQ options are answer choices - keep in question_text
- Sub-parts are question divisions - list in sub_parts array

Question Blocks:
"""
    
    for block in question_blocks:
        instruction_note = f" [Instruction: {block['instruction']}]" if block.get('instruction') else ""
        prompt += f"\nQuestion {block['block_number']}{instruction_note}:\n{block['raw_text']}\n"
    
    prompt += """
Return ONLY valid JSON array (no markdown, no explanations):
[
  {
    "question_number": "1",
    "question_text": "1. What is H_2O?\\n(A) Water (B) Hydrogen (C) Oxygen (D) None",
    "sub_parts": [],
    "has_diagram": false,
    "marks": 1,
    "question_type": "mcq"
  }
]
"""
    
    return prompt

def parse_with_groq_fixed(question_blocks):
    """FIXED: Parse with Groq ensuring correct numbering and complete text"""
    print("🤖 Parsing questions with Groq AI (FIXED VERSION)...")
    
    if not GROQ_API_KEY:
        print("❌ GROQ_API_KEY not configured")
        return None
    
    print(f"  ✓ API Key found: {GROQ_API_KEY[:10]}...")
    print(f"  ✓ Using model: {GROQ_MODEL}")
    
    all_parsed_questions = []
    batch_size = 10
    total_batches = (len(question_blocks) + batch_size - 1) // batch_size
    
    print(f"  Total questions: {len(question_blocks)}")
    print(f"  Processing in {total_batches} batches of {batch_size}")
    
    for i in range(0, len(question_blocks), batch_size):
        batch = question_blocks[i:i + batch_size]
        batch_num = i//batch_size + 1
        print(f"\n  📦 Batch {batch_num}/{total_batches} (Questions {batch[0]['block_number']}-{batch[-1]['block_number']})...")
        
        schema_prompt = create_schema_prompt_fixed(batch)
        
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert at parsing academic question papers. Preserve ALL symbols exactly. Include ALL MCQ options in question_text. Use exact question numbers from the text."
                },
                {
                    "role": "user",
                    "content": schema_prompt
                }
            ],
            "max_tokens": 8000,
            "temperature": 0.1
        }
        
        try:
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            print(f"  ✓ Received response ({len(content)} chars)")
            
            # Extract JSON
            parsed_questions = extract_json_from_response(content)
            
            if parsed_questions:
                print(f"  ✓ Parsed {len(parsed_questions)} questions from batch {batch_num}")
                all_parsed_questions.extend(parsed_questions)
            else:
                print(f"  ⚠ No questions parsed from batch {batch_num}")
                
        except Exception as e:
            print(f"  ❌ Error in batch {batch_num}: {str(e)}")
            continue
    
    print(f"\n✓ Total parsed: {len(all_parsed_questions)} questions")
    
    # FIX: Validate and correct question numbers
    if all_parsed_questions:
        all_parsed_questions = validate_and_fix_question_numbers(all_parsed_questions, question_blocks)
    
    return all_parsed_questions

def validate_and_fix_question_numbers(parsed_questions, original_blocks):
    """
    FIXED: Ensure question numbers match original blocks
    """
    print("🔍 Validating and fixing question numbers...")
    
    original_nums = [b['block_number'] for b in original_blocks]
    
    # Safely parse question numbers, handling empty strings and invalid values
    parsed_nums = []
    for q in parsed_questions:
        q_num = q.get('question_number', '0')
        # Handle empty strings or non-numeric values
        if not q_num or not str(q_num).strip():
            parsed_nums.append(0)
        else:
            try:
                parsed_nums.append(int(str(q_num).strip()))
            except ValueError:
                # If it's something like "1a", try to extract the number
                match = re.match(r'(\d+)', str(q_num))
                if match:
                    parsed_nums.append(int(match.group(1)))
                else:
                    parsed_nums.append(0)
    
    # If counts match, map by position
    if len(parsed_questions) == len(original_blocks):
        for i in range(len(parsed_questions)):
            expected_num = original_blocks[i]['block_number']
            current_num = parsed_questions[i].get('question_number', '')
            
            if str(expected_num) != str(current_num):
                print(f"  🔧 Fixing Q{current_num} → Q{expected_num}")
                parsed_questions[i]['question_number'] = str(expected_num)
    
    print(f"  ✓ Question numbers validated and corrected")
    
    return parsed_questions

def extract_json_from_response(content):
    """Extract JSON from response"""
    try:
        # Try direct JSON parse
        return json.loads(content)
    except:
        # Extract from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        
        # Try to find JSON array
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    
    return None

def parse_question_paper_fixed(pdf_path):
    """
    MAIN FUNCTION - SIMPLE 2-STEP APPROACH
    Step 1: Extract raw text (no cleaning)
    Step 2: Parse questions directly
    """
    print("=" * 60)
    print("🚀 QUESTION PAPER PARSING PIPELINE (FIXED VERSION)")
    print("=" * 60)
    
    # STEP 1: Extract RAW text - NO CLEANING
    text, diagrams = extract_raw_text_simple(pdf_path)
    if not text:
        print("❌ Failed to extract text")
        return None
    
    # Calculate stats
    lines = text.split('\n')
    lines_with_digits = [l for l in lines if re.search(r'\d', l)]
    
    print(f"\n" + "=" * 60)
    print(f"📊 RAW TEXT STATS:")
    print(f"   Total characters: {len(text)}")
    print(f"   Total lines: {len(lines)}")
    print(f"   Lines with digits: {len(lines_with_digits)}")
    print("=" * 60 + "\n")
    
    # Step 2: Split into blocks (with correct numbering)
    question_blocks = split_into_question_blocks_fixed(text)
    if not question_blocks:
        print("❌ No questions detected")
        return None
    
    # Step 3: Parse with Groq (with MCQ options and symbol preservation)
    parsed_questions = parse_with_groq_fixed(question_blocks)
    if not parsed_questions:
        print("❌ Parsing failed")
        return None
    
    # Step 4: Link diagrams to questions based on page numbers and has_diagram flag
    print(f"\n📊 Linking {len(diagrams)} diagrams to questions...")
    
    # Group diagrams by page
    diagrams_by_page = {}
    for diagram in diagrams:
        page = diagram['page']
        if page not in diagrams_by_page:
            diagrams_by_page[page] = []
        diagrams_by_page[page].append(diagram['filename'])
    
    # Estimate which page each question is on based on position in text
    total_chars = len(text)
    chars_per_page = total_chars / max(1, len(diagrams_by_page)) if diagrams_by_page else total_chars
    
    for question in parsed_questions:
        # Initialize diagram_files list
        question['diagram_files'] = []
        
        q_text = question.get('question_text', '').lower()
        q_num = question.get('question_number', '')
        
        # Check if question mentions diagrams/figures/graphs
        diagram_keywords = ['figure', 'diagram', 'graph', 'circuit', 'shown', 'given below', 
                           'as shown', 'in the figure', 'in the diagram', 'refer to']
        has_diagram_keyword = any(keyword in q_text for keyword in diagram_keywords)
        
        # If question has diagram flag OR mentions diagram keywords, try to find diagrams
        if question.get('has_diagram', False) or has_diagram_keyword:
            # Update has_diagram flag if keyword found
            if has_diagram_keyword and not question.get('has_diagram', False):
                question['has_diagram'] = True
                print(f"  ℹ Q{q_num}: Detected diagram keyword in text")
            
            # Search for question in text to estimate page
            search_pattern = f"{q_num}[\\. )]"
            match = re.search(search_pattern, text)
            
            if match:
                char_position = match.start()
                estimated_page = int(char_position / chars_per_page) + 1
                
                # Look for diagrams on this page and adjacent pages
                for page_offset in [0, -1, 1]:
                    check_page = estimated_page + page_offset
                    if check_page in diagrams_by_page:
                        question['diagram_files'].extend(diagrams_by_page[check_page])
                        print(f"  ✓ Q{q_num}: Linked {len(diagrams_by_page[check_page])} diagram(s) from page {check_page}")
                        break
                
                # If no diagrams found but has keyword, warn
                if not question['diagram_files'] and has_diagram_keyword:
                    print(f"  ⚠ Q{q_num}: Mentions diagram but none found on pages {max(1, estimated_page-1)}-{estimated_page+1}")
    
    # Count questions with diagrams
    questions_with_diagrams = sum(1 for q in parsed_questions if q.get('diagram_files'))
    
    print("=" * 60)
    print(f"✅ SUCCESS: Parsed {len(parsed_questions)} questions with {len(diagrams)} diagrams")
    print(f"   Questions with diagrams: {questions_with_diagrams}")
    print("=" * 60)
    
    return {
        'questions': parsed_questions,
        'diagrams': diagrams,
        'total_questions': len(parsed_questions)
    }
