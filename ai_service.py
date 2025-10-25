"""
AI Service for Question Analysis and Solution Generation
Uses ChromaDB for vector storage and OpenAI for LLM capabilities
"""

import os
import sys

# Python 3.8 compatibility - Fix for type subscripting
from typing import List, Dict, Any
import collections.abc
if sys.version_info < (3, 9):
    # Make built-in types subscriptable for Python 3.8
    import typing
    collections.abc.Mapping.register(dict)
    collections.abc.Sequence.register(list)

# Fix for huggingface_hub compatibility issues
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)

try:
    # Import and patch huggingface_hub for compatibility
    import huggingface_hub
    from huggingface_hub import hf_hub_download
    
    # Monkey patch for old sentence-transformers versions
    if not hasattr(huggingface_hub, 'cached_download'):
        # Create a wrapper that ignores the 'url' parameter
        def cached_download_wrapper(url=None, **kwargs):
            # Remove 'url' from kwargs if present
            kwargs.pop('url', None)
            # Use the repo_id if available, otherwise use first positional arg
            if 'repo_id' in kwargs:
                return hf_hub_download(**kwargs)
            else:
                # Try to extract repo_id from url if provided
                return hf_hub_download(**kwargs)
        
        huggingface_hub.cached_download = cached_download_wrapper
        
except ImportError:
    pass

import fitz  # PyMuPDF
import faiss
import numpy as np
import pickle
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import re
import json
import requests

# Load environment variables
load_dotenv()

# Initialize these lazily to avoid startup errors
embedding_model = None
vector_store = {}  # Store FAISS indices and metadata by textbook_id

# Directory for storing vector indices
VECTOR_DB_DIR = "./vector_db"
os.makedirs(VECTOR_DB_DIR, exist_ok=True)

# Groq API configuration (free tier available)
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"  # Latest Llama 3.3 model (Dec 2024)

def get_embedding_model():
    """Lazy load embedding model"""
    global embedding_model
    if embedding_model is None:
        print("Loading embedding model...")
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        print("✓ Embedding model loaded")
    return embedding_model

def save_vector_index(textbook_id, index, metadata):
    """Save FAISS index and metadata to disk"""
    try:
        index_path = os.path.join(VECTOR_DB_DIR, f"textbook_{textbook_id}.index")
        metadata_path = os.path.join(VECTOR_DB_DIR, f"textbook_{textbook_id}.pkl")
        
        # Save FAISS index
        faiss.write_index(index, index_path)
        
        # Save metadata
        with open(metadata_path, 'wb') as f:
            pickle.dump(metadata, f)
        
        print(f"✓ Saved vector index for textbook {textbook_id}")
        return True
    except Exception as e:
        print(f"Error saving vector index: {e}")
        return False

def load_vector_index(textbook_id):
    """Load FAISS index and metadata from disk"""
    try:
        index_path = os.path.join(VECTOR_DB_DIR, f"textbook_{textbook_id}.index")
        metadata_path = os.path.join(VECTOR_DB_DIR, f"textbook_{textbook_id}.pkl")
        
        if not os.path.exists(index_path) or not os.path.exists(metadata_path):
            return None, None
        
        # Load FAISS index
        index = faiss.read_index(index_path)
        
        # Load metadata
        with open(metadata_path, 'rb') as f:
            metadata = pickle.load(f)
        
        print(f"✓ Loaded vector index for textbook {textbook_id}")
        return index, metadata
    except Exception as e:
        print(f"Error loading vector index: {e}")
        return None, None

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF with page information, diagrams, and clean headers/footers"""
    try:
        print(f"Opening PDF: {pdf_path}")
        doc = fitz.open(pdf_path)
        pages_text = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()
            
            # Check for images/diagrams on the page
            image_list = page.get_images()
            has_diagrams = len(image_list) > 0
            
            # If no text found, try OCR (scanned/image PDF)
            if len(text) < 50:  # Very little text, likely scanned
                print(f"  Page {page_num + 1}: No text found, trying OCR...")
                try:
                    # Try OCR
                    import pytesseract
                    from PIL import Image
                    import io
                    
                    # Convert page to image
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    
                    # Perform OCR
                    text = pytesseract.image_to_string(img)
                    print(f"  ✓ OCR extracted {len(text)} characters")
                    
                except ImportError:
                    print(f"  ⚠ OCR not available (pytesseract not installed)")
                    print(f"  Install: pip install pytesseract Pillow pdf2image")
                    print(f"  And install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki")
                except Exception as ocr_error:
                    print(f"  ⚠ OCR failed: {ocr_error}")
            
            # Clean headers and footers
            text = clean_headers_footers(text)
            
            pages_text.append({
                'page_number': page_num + 1,
                'text': text.strip(),
                'has_diagrams': has_diagrams,
                'diagram_count': len(image_list)
            })
        
        doc.close()
        
        total_chars = sum(len(p['text']) for p in pages_text)
        total_diagrams = sum(p['diagram_count'] for p in pages_text)
        print(f"✓ Extracted text from {len(pages_text)} pages ({total_chars} characters, {total_diagrams} diagrams)")
        
        if total_chars < 100:
            print(f"⚠ Very little text extracted - PDF might be image-based")
            print(f"  Install OCR: pip install pytesseract Pillow")
            print(f"  Install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki")
        
        return pages_text
        
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        import traceback
        traceback.print_exc()
        return []

def clean_headers_footers(text):
    """Remove common headers and footers from text"""
    if not text:
        return text
    
    lines = text.split('\n')
    cleaned_lines = []
    
    # Common header/footer patterns to ignore
    ignore_patterns = [
        r'^Page\s+\d+',  # Page 1, Page 2
        r'^\d+\s*$',  # Just page numbers
        r'^-\s*\d+\s*-$',  # - 1 -, - 2 -
        r'^\[\s*\d+\s*\]$',  # [1], [2]
        r'^www\.',  # Website URLs
        r'^https?://',  # URLs
        r'©.*\d{4}',  # Copyright notices
        r'^CBSE\s+\d{4}',  # CBSE 2024
        r'^Class\s+\d+',  # Class 10, Class 12
        r'^Subject:',  # Subject headers
        r'^Time:.*Marks:',  # Time and marks
        r'^General Instructions',  # At start only
    ]
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        
        # Skip empty lines
        if not line_stripped:
            continue
        
        # Check if line matches ignore patterns
        should_ignore = False
        
        # Only check first 3 and last 3 lines for headers/footers
        if i < 3 or i >= len(lines) - 3:
            for pattern in ignore_patterns:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    should_ignore = True
                    break
        
        if not should_ignore:
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)

def extract_chapters_from_textbook(textbook_path, textbook_id):
    """Extract chapters from textbook and store in FAISS vector DB"""
    try:
        pages_text = extract_text_from_pdf(textbook_path)
        
        if not pages_text:
            return {"error": "Could not extract text from textbook"}
        
        # Detect chapters using heuristics (headings, page breaks, etc.)
        print(f"Detecting chapters in textbook...")
        chapters = detect_chapters(pages_text)
        
        if not chapters:
            print("⚠ No chapters detected, creating single chapter from all content")
            # If no chapters detected, treat entire textbook as one chapter
            all_text = " ".join([p['text'] for p in pages_text])
            chapters = [{
                'chapter_number': 1,
                'title': 'Complete Textbook',
                'page_start': 1,
                'page_end': len(pages_text),
                'content': all_text
            }]
        
        # Get embedding model
        model = get_embedding_model()
        
        # Create embeddings for all chapters
        print(f"Creating embeddings for {len(chapters)} chapters...")
        chapter_texts = [chapter['content'] for chapter in chapters]
        embeddings = model.encode(chapter_texts, show_progress_bar=False)
        
        # Convert to numpy array
        embeddings_np = np.array(embeddings).astype('float32')
        
        # Create FAISS index
        dimension = embeddings_np.shape[1]  # Embedding dimension (384 for MiniLM)
        index = faiss.IndexFlatL2(dimension)  # L2 distance (Euclidean)
        
        # Add vectors to index
        index.add(embeddings_np)
        
        # Prepare metadata
        metadata = {
            'textbook_id': textbook_id,
            'chapters': [
                {
                    'chapter_number': ch['chapter_number'],
                    'chapter_title': ch['title'],
                    'page_start': ch['page_start'],
                    'page_end': ch['page_end'],
                    'content': ch['content'][:500]  # Store first 500 chars for reference
                }
                for ch in chapters
            ]
        }
        
        # Save to disk
        save_vector_index(textbook_id, index, metadata)
        
        # Store in memory for quick access
        vector_store[textbook_id] = {
            'index': index,
            'metadata': metadata
        }
        
        print(f"✓ Indexed {len(chapters)} chapters for textbook {textbook_id}")
        
        return {
            "success": True,
            "chapters_indexed": len(chapters),
            "textbook_id": textbook_id
        }
    
    except Exception as e:
        import traceback
        print(f"Error in extract_chapters_from_textbook: {traceback.format_exc()}")
        return {"error": str(e)}

def detect_chapters(pages_text):
    """Detect chapters from pages using table of contents first, then heuristics"""
    chapters = []
    
    # First, try to find and parse table of contents
    toc_chapters = extract_from_table_of_contents(pages_text)
    if toc_chapters:
        print(f"✓ Found {len(toc_chapters)} chapters from table of contents")
        # Map TOC chapters to actual content
        chapters = map_toc_to_content(toc_chapters, pages_text)
        if chapters:
            return chapters
    
    print("⚠ Table of contents not found or incomplete, using pattern matching...")
    
    # Try manual chapter list for NCERT Physics Class 12
    manual_chapters = try_manual_chapter_mapping(pages_text)
    if manual_chapters and len(manual_chapters) > 5:
        print(f"✓ Using manual chapter mapping: {len(manual_chapters)} chapters")
        return manual_chapters
    
    # Fallback to pattern matching
    current_chapter = None
    chapter_number = 0
    
    # Stricter chapter patterns - must be at start of line
    chapter_patterns = [
        r'^Chapter\s+(\d+)[:\s]+([A-Z][A-Za-z\s\-]+)$',      # Chapter 1: Title
        r'^CHAPTER\s+(\d+)[:\s]+([A-Z][A-Za-z\s\-]+)$',      # CHAPTER 1: TITLE
        r'^Unit\s+(\d+)[:\s]+([A-Z][A-Za-z\s\-]+)$',         # Unit 1: Title
        r'^UNIT\s+(\d+)[:\s]+([A-Z][A-Za-z\s\-]+)$',         # UNIT 1: TITLE
        r'^(\d+)\.\s+([A-Z][A-Za-z\s\-]{5,})$',              # 1. Title (at least 5 chars)
    ]
    
    for page in pages_text:
        text = page['text']
        lines = text.split('\n')
        
        for line in lines[:10]:  # Check first 10 lines of each page
            line = line.strip()
            
            # Skip if line is too short or too long (likely not a chapter heading)
            if len(line) < 5 or len(line) > 100:
                continue
            
            for pattern in chapter_patterns:
                match = re.match(pattern, line)  # Use match instead of search
                if match:
                    title = match.group(2).strip() if len(match.groups()) > 1 else match.group(1).strip()
                    
                    # Validate title - skip sentence fragments
                    invalid_starts = ['what', 'to calculate', 'determine', 'find', 'however', 'therefore']
                    if any(title.lower().startswith(start) for start in invalid_starts):
                        continue
                    
                    # Skip if title has punctuation that suggests it's not a chapter title
                    if '?' in title or title.endswith(','):
                        continue
                    
                    # Save previous chapter
                    if current_chapter:
                        current_chapter['page_end'] = page['page_number'] - 1
                        current_chapter['content'] = current_chapter['content'].strip()
                        chapters.append(current_chapter)
                    
                    # Start new chapter
                    chapter_number += 1
                    current_chapter = {
                        'chapter_number': chapter_number,
                        'title': title,
                        'page_start': page['page_number'],
                        'page_end': page['page_number'],
                        'content': ''
                    }
                    print(f"    Found chapter {chapter_number}: '{title}' on page {page['page_number']}")
                    break
        
        # Add page content to current chapter
        if current_chapter:
            current_chapter['content'] += '\n' + text
            current_chapter['page_end'] = page['page_number']
    
    # Add last chapter
    if current_chapter:
        current_chapter['content'] = current_chapter['content'].strip()
        chapters.append(current_chapter)
    
    # If no chapters detected, create one chapter per 10 pages
    if not chapters:
        for i in range(0, len(pages_text), 10):
            chunk = pages_text[i:i+10]
            content = '\n'.join([p['text'] for p in chunk])
            chapters.append({
                'chapter_number': i // 10 + 1,
                'title': f'Section {i // 10 + 1}',
                'page_start': chunk[0]['page_number'],
                'page_end': chunk[-1]['page_number'],
                'content': content
            })
    
    return chapters

def try_manual_chapter_mapping(pages_text):
    """Try to map chapters using known NCERT textbook structure"""
    
    # NCERT Physics Class 12 standard chapters
    ncert_physics_12 = [
        {'number': 1, 'title': 'Electric Charges and Fields', 'approx_start': 1},
        {'number': 2, 'title': 'Electrostatic Potential and Capacitance', 'approx_start': 45},
        {'number': 3, 'title': 'Current Electricity', 'approx_start': 89},
        {'number': 4, 'title': 'Moving Charges and Magnetism', 'approx_start': 133},
        {'number': 5, 'title': 'Magnetism and Matter', 'approx_start': 177},
        {'number': 6, 'title': 'Electromagnetic Induction', 'approx_start': 221},
        {'number': 7, 'title': 'Alternating Current', 'approx_start': 265},
        {'number': 8, 'title': 'Electromagnetic Waves', 'approx_start': 309},
        {'number': 9, 'title': 'Ray Optics and Optical Instruments', 'approx_start': 353},
        {'number': 10, 'title': 'Wave Optics', 'approx_start': 397},
        {'number': 11, 'title': 'Dual Nature of Radiation and Matter', 'approx_start': 441},
        {'number': 12, 'title': 'Atoms', 'approx_start': 485},
        {'number': 13, 'title': 'Nuclei', 'approx_start': 529},
        {'number': 14, 'title': 'Semiconductor Electronics', 'approx_start': 573},
    ]
    
    # Check if this looks like NCERT Physics 12 by searching for key chapter titles
    full_text = ' '.join([p['text'] for p in pages_text[:50]]).lower()
    
    # Look for distinctive chapter combinations
    if ('electric charges' in full_text and 'electrostatic potential' in full_text and 
        'current electricity' in full_text):
        
        print("  Detected NCERT Physics Class 12 textbook")
        
        # Map chapters to actual pages
        chapters = []
        for i, ch_info in enumerate(ncert_physics_12):
            # Determine page range
            page_start = ch_info['approx_start']
            page_end = ncert_physics_12[i + 1]['approx_start'] - 1 if i + 1 < len(ncert_physics_12) else len(pages_text)
            
            # Extract content from those pages
            content = []
            for page in pages_text:
                if page_start <= page['page_number'] <= page_end:
                    content.append(page['text'])
            
            if content:
                chapters.append({
                    'chapter_number': ch_info['number'],
                    'title': ch_info['title'],
                    'page_start': page_start,
                    'page_end': page_end,
                    'content': '\n'.join(content)
                })
                print(f"    {ch_info['number']}. {ch_info['title']} (pages {page_start}-{page_end})")
        
        return chapters
    
    return None

def extract_from_table_of_contents(pages_text):
    """Extract chapter information from table of contents"""
    toc_chapters = []
    
    print(f"  Searching for TOC in first 20 pages...")
    
    # Look for table of contents in first 20 pages (some books have longer TOCs)
    for page in pages_text[:20]:
        text = page['text']
        lines = text.split('\n')
        
        # More flexible TOC detection - look for chapter-like patterns
        toc_indicators = ['contents', 'table of contents', 'index', 'syllabus', 'chapter']
        
        # Also check if page has multiple lines with numbers (likely TOC)
        numbered_lines = sum(1 for line in lines if re.match(r'^\d{1,2}\.', line.strip()))
        
        is_toc_page = (
            any(indicator in text.lower()[:500] for indicator in toc_indicators) or
            numbered_lines >= 5  # If 5+ lines start with numbers, likely TOC
        )
        
        print(f"  Page {page['page_number']}: {len(text)} chars, {numbered_lines} numbered lines")
        
        if not is_toc_page:
            continue
        
        print(f"  Found potential TOC on page {page['page_number']}")
        print(f"  Analyzing {len(lines)} lines for chapter entries...")
        
        # Debug: Print first 20 lines of TOC to see what we're working with
        print(f"  First 20 lines of TOC page:")
        for i, line in enumerate(lines[:20], 1):
            if line.strip():
                print(f"    {i}: {line.strip()[:80]}")
        
        # Parse TOC entries - ONLY match lines that look like TOC entries
        # Must have: chapter number + title + page number
        toc_patterns = [
            # NCERT format: "1. Electric Charges and Fields 1"
            r'^(\d{1,2})\.\s+([A-Z][A-Za-z\s\-\&]+?)\s+(\d{1,3})\s*$',
            
            # With dots: "1. Electric Charges and Fields ........ 1"
            r'^(\d{1,2})\.\s+(.+?)\s+\.{3,}\s*(\d{1,3})\s*$',
            
            # Chapter prefix: "Chapter 1 Electric Charges 1"
            r'^(?:Chapter|CHAPTER)\s+(\d{1,2})\s+([A-Z][A-Za-z\s\-\&]+?)\s+(\d{1,3})\s*$',
            
            # With colon: "Chapter 1: Electric Charges 1"
            r'^(?:Chapter|CHAPTER)\s+(\d{1,2}):\s+(.+?)\s+(\d{1,3})\s*$',
        ]
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 5:
                continue
            
            for pattern in toc_patterns:
                match = re.search(pattern, line)
                if match:
                    groups = match.groups()
                    if len(groups) == 3:
                        # Chapter number, title, page
                        ch_num = int(groups[0]) if groups[0].isdigit() else len(toc_chapters) + 1
                        title = groups[1].strip()
                        page_num = int(groups[2]) if groups[2].isdigit() else 1
                    elif len(groups) == 2:
                        # Title, page
                        title = groups[0].strip()
                        page_num = int(groups[1]) if groups[1].isdigit() else 1
                        ch_num = len(toc_chapters) + 1
                    else:
                        continue
                    
                    # Clean title aggressively
                    title = re.sub(r'\s+\d+\s*$', '', title)      # Remove trailing numbers
                    title = re.sub(r'\.{3,}.*$', '', title)       # Remove dots and everything after
                    title = re.sub(r'\s+\.\s*$', '', title)       # Remove trailing dot
                    title = re.sub(r'^\d+\.\s*', '', title)       # Remove leading number+dot
                    title = re.sub(r'\s*-\s*$', '', title)        # Remove trailing dash
                    title = title.strip()
                    
                    # Skip if title is too short or too long
                    if len(title) < 5 or len(title) > 80:
                        continue
                    
                    # Skip if all digits
                    if title.isdigit():
                        continue
                    
                    # Skip section headings (they have dashes or are too specific)
                    if '-' in title and len(title) > 50:
                        print(f"    Skipping section heading: '{title}'")
                        continue
                    
                    # Skip common sentence starters that aren't chapter titles
                    invalid_starts = ['what', 'to calculate', 'determine', 'find', 'calculate', 'however', 'therefore', 'thus', 'hence', 'electric field at', 'magnetic field at']
                    if any(title.lower().startswith(start) for start in invalid_starts):
                        print(f"    Skipping invalid title: '{title}'")
                        continue
                    
                    # Title should start with capital letter (proper chapter name)
                    if not title[0].isupper():
                        continue
                    
                    # Skip if it looks like a question or instruction
                    if '?' in title or title.lower().startswith(('how', 'why', 'when', 'where')):
                        continue
                    
                    toc_chapters.append({
                        'chapter_number': ch_num,
                        'title': title,
                        'page_start': page_num
                    })
                    break
    
    # Remove duplicates and sort by chapter number
    if toc_chapters:
        seen = set()
        unique_chapters = []
        for ch in toc_chapters:
            key = (ch['chapter_number'], ch['title'])
            if key not in seen:
                seen.add(key)
                unique_chapters.append(ch)
        
        toc_chapters = sorted(unique_chapters, key=lambda x: x['chapter_number'])
        print(f"  Extracted {len(toc_chapters)} chapters from TOC:")
        for ch in toc_chapters:
            print(f"    {ch['chapter_number']}. {ch['title']} (page {ch['page_start']})")
    
    return toc_chapters

def map_toc_to_content(toc_chapters, pages_text):
    """Map TOC chapter info to actual page content"""
    chapters = []
    
    for i, toc_ch in enumerate(toc_chapters):
        # Determine page range
        page_start = toc_ch['page_start']
        page_end = toc_chapters[i + 1]['page_start'] - 1 if i + 1 < len(toc_chapters) else len(pages_text)
        
        # Extract content from pages
        content = []
        for page in pages_text:
            if page_start <= page['page_number'] <= page_end:
                content.append(page['text'])
        
        if content:
            chapters.append({
                'chapter_number': toc_ch['chapter_number'],
                'title': toc_ch['title'],
                'page_start': page_start,
                'page_end': page_end,
                'content': '\n'.join(content)
            })
    
    return chapters

def extract_questions_from_paper(paper_path):
    """Extract individual questions from question paper"""
    try:
        pages_text = extract_text_from_pdf(paper_path)
        
        if not pages_text:
            return {"error": "Could not extract text from paper"}
        
        full_text = '\n'.join([p['text'] for p in pages_text])
        
        # Detect questions using patterns
        questions = detect_questions(full_text, pages_text)
        
        return {
            "success": True,
            "questions": questions,
            "total_questions": len(questions)
        }
    
    except Exception as e:
        return {"error": str(e)}

def clean_question_text(text):
    """Clean and normalize question text - KEEP ALL MCQ OPTIONS"""
    # Replace newlines with spaces
    text = text.replace('\n', ' ')
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    # DO NOT remove MCQ options - keep them with the question
    # Limit length
    text = text[:2000] if len(text) > 2000 else text
    return text.strip()

def extract_sub_parts(main_q_num, q_text):
    """Extract sub-parts from a multi-part question, distinguishing from MCQ options"""
    sub_questions = []
    
    # Try different sub-part patterns
    patterns = [
        (r'\(([a-z])\)\s*(.+?)(?=\([a-z]\)|\Z)', 'letter'),  # (a), (b), (c)
        (r'\(([ivxlcdm]+)\)\s*(.+?)(?=\([ivxlcdm]+\)|\Z)', 'roman'),  # (i), (ii), (iii)
        (r'(?:^|\n)([a-z])\)\s*(.+?)(?=\n[a-z]\)|\Z)', 'letter_paren'),  # a), b), c)
        (r'(?:^|\n)([ivxlcdm]+)\)\s*(.+?)(?=\n[ivxlcdm]+\)|\Z)', 'roman_paren'),  # i), ii), iii)
    ]
    
    for pattern, pattern_type in patterns:
        matches = list(re.finditer(pattern, q_text, re.MULTILINE | re.DOTALL | re.IGNORECASE))
        if len(matches) >= 2:  # At least 2 sub-parts to be valid
            
            # Check if these are MCQ options (short, similar length)
            if is_mcq_options(matches):
                print(f"    Detected MCQ options, not sub-questions")
                continue
            
            print(f"    Using {pattern_type} pattern for sub-parts")
            
            # Extract intro text (before first sub-part)
            first_match_pos = matches[0].start()
            intro_text = q_text[:first_match_pos].strip()
            
            # Check for diagram indicators in intro
            has_diagram = detect_diagram_reference(intro_text)
            
            for match in matches:
                sub_label = match.group(1).lower()
                sub_text = match.group(2).strip()
                
                # Clean sub-text
                sub_text = sub_text.replace('\n', ' ')
                sub_text = re.sub(r'\s+', ' ', sub_text)
                
                # KEEP ALL MCQ OPTIONS - do not remove them
                
                # Combine intro + sub-part
                if intro_text and len(intro_text) > 10:
                    full_text = f"{intro_text} ({sub_label}) {sub_text}"
                else:
                    full_text = f"({sub_label}) {sub_text}"
                
                # Add diagram note if present
                if has_diagram:
                    full_text = f"[Contains diagram/figure] {full_text}"
                
                full_text = full_text[:2500] if len(full_text) > 2500 else full_text
                
                if len(full_text) > 15:
                    sub_questions.append({
                        'question_number': f"{main_q_num}{sub_label}",
                        'question_text': full_text,
                        'position': 0,
                        'has_diagram': has_diagram
                    })
            
            return sub_questions
    
    return []

def is_mcq_options(matches):
    """Check if matches are MCQ options rather than sub-questions"""
    if len(matches) < 2:
        return False
    
    # Get text lengths
    lengths = [len(match.group(2).strip()) for match in matches]
    avg_length = sum(lengths) / len(lengths)
    
    # MCQ options are typically:
    # 1. Short (< 100 chars)
    # 2. Similar length to each other
    # 3. 4 options (a, b, c, d)
    
    if avg_length < 100 and len(matches) == 4:
        # Check if lengths are similar (within 50% of average)
        similar_lengths = all(abs(l - avg_length) < avg_length * 0.5 for l in lengths)
        if similar_lengths:
            return True
    
    # Check for common MCQ option patterns
    first_text = matches[0].group(2).strip().lower()
    mcq_indicators = ['both', 'none', 'all of the above', 'none of the above', 
                      'only', 'and', 'or', 'neither']
    
    if any(indicator in first_text for indicator in mcq_indicators) and avg_length < 80:
        return True
    
    return False

def looks_like_question(text):
    """Check if text looks like a question rather than an answer"""
    text_lower = text.lower()
    
    # Question indicators
    question_words = ['what', 'why', 'how', 'when', 'where', 'who', 'which', 
                      'explain', 'describe', 'define', 'calculate', 'find', 
                      'prove', 'show', 'derive', 'state', 'write', 'draw',
                      'compare', 'differentiate', 'discuss', 'analyze']
    
    # Check for question words
    has_question_word = any(word in text_lower for word in question_words)
    
    # Check for question mark
    has_question_mark = '?' in text
    
    # Check length (questions are usually longer)
    is_long_enough = len(text) > 50
    
    return has_question_word or has_question_mark or is_long_enough

def detect_diagram_reference(text):
    """Detect if text references a diagram or figure"""
    text_lower = text.lower()
    
    diagram_keywords = [
        'diagram', 'figure', 'graph', 'chart', 'image', 'picture',
        'illustration', 'shown', 'given below', 'above', 'following figure',
        'circuit', 'table', 'map', 'drawing'
    ]
    
    return any(keyword in text_lower for keyword in diagram_keywords)

# REMOVED: remove_mcq_options() function
# We want to KEEP ALL MCQ OPTIONS with the question text
# MCQ options are essential part of the question and should not be removed

def detect_questions(full_text, pages_text):
    """Detect individual questions from text, including multi-part questions"""
    questions = []
    
    print(f"Detecting questions in {len(full_text)} characters of text...")
    
    # Strategy 1: Detect main questions with sub-parts
    # Pattern to detect main questions (1., 2., 3., etc.)
    main_pattern = r'(?:^|\n)(\d+)\.\s+(.+?)(?=\n\d+\.\s+|\Z)'
    
    main_matches = list(re.finditer(main_pattern, full_text, re.MULTILINE | re.DOTALL))
    
    if main_matches:
        print(f"  Found {len(main_matches)} main questions")
        
        for match in main_matches:
            q_num = match.group(1)
            q_text = match.group(2).strip()
            
            # Check for sub-parts within this question
            # Patterns: (a), (b), (i), (ii), a), b), i), ii)
            sub_part_patterns = [
                r'\(([a-z])\)',  # (a), (b), (c)
                r'\(([ivxlcdm]+)\)',  # (i), (ii), (iii), (iv), (v)
                r'^([a-z])\)',  # a), b), c)
                r'^([ivxlcdm]+)\)',  # i), ii), iii)
            ]
            
            has_sub_parts = False
            for sub_pattern in sub_part_patterns:
                if re.search(sub_pattern, q_text, re.MULTILINE | re.IGNORECASE):
                    has_sub_parts = True
                    break
            
            if has_sub_parts:
                # Split into sub-parts
                sub_parts = extract_sub_parts(q_num, q_text)
                if sub_parts:
                    questions.extend(sub_parts)
                    print(f"  Q{q_num}: Split into {len(sub_parts)} sub-parts")
                else:
                    # Fallback: treat as single question
                    q_text_clean = clean_question_text(q_text)
                    if len(q_text_clean) > 15:
                        questions.append({
                            'question_number': q_num,
                            'question_text': q_text_clean,
                            'position': match.start()
                        })
            else:
                # Single question without sub-parts
                q_text_clean = clean_question_text(q_text)
                if len(q_text_clean) > 15:
                    questions.append({
                        'question_number': q_num,
                        'question_text': q_text_clean,
                        'position': match.start()
                    })
    else:
        # Fallback: Try other patterns
        print("  No main questions found, trying alternative patterns...")
        patterns = [
            (r'(?:^|\n)(\d+)\)\s+(.+?)(?=\n\d+\)\s+|\Z)', '1) format'),
            (r'(?:^|\n)Q\.?\s*(\d+)[:\.\s]+(.+?)(?=\nQ\.?\s*\d+|\Z)', 'Q1 format'),
            (r'(?:^|\n)Question\s+(\d+)[:\s]+(.+?)(?=\nQuestion\s+\d+|\Z)', 'Question 1 format'),
        ]
        
        for pattern, name in patterns:
            matches = list(re.finditer(pattern, full_text, re.MULTILINE | re.DOTALL))
            if matches:
                print(f"  {name}: Found {len(matches)} matches")
                for match in matches:
                    q_num = match.group(1)
                    q_text = clean_question_text(match.group(2).strip())
                    if len(q_text) > 15:
                        questions.append({
                            'question_number': q_num,
                            'question_text': q_text,
                            'position': match.start()
                        })
                break
    
    # Remove duplicates
    seen = set()
    unique_questions = []
    for q in questions:
        if q['question_number'] not in seen:
            seen.add(q['question_number'])
            unique_questions.append(q)
    
    if len(questions) > len(unique_questions):
        print(f"  Removed {len(questions) - len(unique_questions)} duplicates")
    
    questions = unique_questions
    
    # If no questions detected, try line-by-line approach
    if not questions:
        print("No patterns matched, trying line-by-line detection...")
        lines = full_text.split('\n')
        current_q = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Try multiple line patterns
            match = (re.match(r'^(\d+)[\.\)]\s+(.+)', line) or
                    re.match(r'^Q\.?\s*(\d+)[:\.\s]+(.+)', line) or
                    re.match(r'^\[(\d+)\]\s+(.+)', line))
            
            if match:
                if current_q and len(current_q['question_text']) > 15:
                    # Keep ALL MCQ options with the question
                    questions.append(current_q)
                current_q = {
                    'question_number': match.group(1),
                    'question_text': match.group(2).strip(),
                    'position': 0
                }
            elif current_q and line:
                # Continue previous question
                current_q['question_text'] += ' ' + line
        
        if current_q and len(current_q['question_text']) > 15:
            # Keep ALL MCQ options with the question
            questions.append(current_q)
    
    # If still no questions, create sample questions from paragraphs
    if not questions:
        print("⚠ No questions detected, creating from paragraphs...")
        paragraphs = [p.strip() for p in full_text.split('\n\n') if len(p.strip()) > 30]
        for i, para in enumerate(paragraphs, 1):  # No limit - extract all
            questions.append({
                'question_number': str(i),
                'question_text': para[:800],  # Increased from 500 to 800 chars
                'position': 0
            })
    
    print(f"✓ Detected {len(questions)} questions")
    return questions

def map_questions_to_chapters(questions, textbook_id):
    """Map questions to textbook chapters using FAISS + Groq LLM for enhanced accuracy"""
    try:
        # Load or get vector index
        if textbook_id in vector_store:
            index = vector_store[textbook_id]['index']
            metadata = vector_store[textbook_id]['metadata']
        else:
            index, metadata = load_vector_index(textbook_id)
            if index is None:
                return {"error": f"No vector index found for textbook {textbook_id}. Please index the textbook first."}
            vector_store[textbook_id] = {'index': index, 'metadata': metadata}
        
        model = get_embedding_model()
        mapped_questions = []
        
        # Get all chapter titles for LLM context
        chapter_list = [f"{ch['chapter_number']}. {ch['chapter_title']}" for ch in metadata['chapters']]
        
        print(f"🤖 Starting AI Search with LLM for {len(questions)} questions...")
        print(f"📚 Available chapters: {len(metadata['chapters'])}")
        
        for idx, question in enumerate(questions, 1):
            # Create embedding for question
            q_text = question['question_text']
            q_embedding = model.encode([q_text], show_progress_bar=False)
            q_embedding_np = np.array(q_embedding).astype('float32')
            
            # Search for top 5 similar chapters using FAISS (get more candidates)
            k = min(5, index.ntotal)
            distances, indices = index.search(q_embedding_np, k)
            
            # Get candidate chapters
            candidates = []
            for i, idx in enumerate(indices[0]):
                if idx < len(metadata['chapters']):
                    chapter = metadata['chapters'][idx]
                    distance = distances[0][i]
                    similarity_score = max(0, 100 - (distance * 10))
                    
                    candidates.append({
                        'chapter_number': chapter['chapter_number'],
                        'chapter_title': chapter['chapter_title'],
                        'page_start': chapter['page_start'],
                        'page_end': chapter['page_end'],
                        'similarity_score': round(similarity_score, 2),
                        'content_preview': chapter.get('content', '')[:1000]  # Increased from 500 to 1000
                    })
            
            # Use Groq LLM to refine the match
            if GROQ_API_KEY and len(candidates) > 0:
                try:
                    print(f"  [{idx}/{len(questions)}] 🧠 Invoking LLM for question: {q_text[:60]}...")
                    print(f"     Candidates: {', '.join([c['chapter_title'] for c in candidates[:3]])}")
                    
                    # Add delay between API calls to avoid rate limiting
                    # Groq free tier: 12,000 TPM (tokens per minute)
                    # With ~800 tokens per call, we can do ~15 calls/minute
                    # Add 4-second delay = 15 calls/minute max
                    if idx > 0:  # Skip delay for first question
                        import time
                        time.sleep(4)  # 4 seconds between calls
                    
                    refined_match = refine_chapter_match_with_llm(q_text, candidates, chapter_list)
                    
                    if refined_match:
                        print(f"     LLM Response: {refined_match}")
                        # Find the matched chapter in candidates
                        best_match = next((c for c in candidates if c['chapter_title'] == refined_match['chapter_title']), candidates[0])
                        best_match['similarity_score'] = refined_match.get('confidence', best_match['similarity_score'])
                        best_match['llm_reasoning'] = refined_match.get('reasoning', '')
                        chapters_matched = [best_match]
                        print(f"  ✓ LLM matched to: {best_match['chapter_title']} (confidence: {best_match['similarity_score']}%)")
                        print(f"     Reasoning: {best_match['llm_reasoning'][:100]}...")
                    else:
                        # Fallback to top FAISS result
                        chapters_matched = [candidates[0]]
                        print(f"  ⚠ LLM returned None, using FAISS: {candidates[0]['chapter_title']}")
                except Exception as llm_error:
                    print(f"  ❌ LLM refinement failed: {str(llm_error)[:100]}")
                    print(f"     Using FAISS result: {candidates[0]['chapter_title']}")
                    chapters_matched = candidates[:1]  # Use top FAISS result
            else:
                # No LLM available, use FAISS results
                if not GROQ_API_KEY:
                    print(f"  [{idx}/{len(questions)}] ⚠ No Groq API key configured!")
                print(f"     Using FAISS only: {candidates[0]['chapter_title']}")
                chapters_matched = candidates[:1]
            
            # Format final results
            final_chapters = []
            for ch in chapters_matched:
                preview_text = ch.get('content_preview', '')[:300]
                if len(ch.get('content_preview', '')) > 300:
                    preview_text += '...'
                
                final_chapters.append({
                    'chapter_number': ch['chapter_number'],
                    'chapter_title': ch['chapter_title'],
                    'page_start': ch['page_start'],
                    'page_end': ch['page_end'],
                    'similarity_score': ch['similarity_score'],
                    'preview': preview_text,
                    'page_range': f"Pages {ch['page_start']}-{ch['page_end']}",
                    'llm_reasoning': ch.get('llm_reasoning', '')
                })
            
            mapped_questions.append({
                **question,
                'chapters': final_chapters
            })
        
        return {
            "success": True,
            "mapped_questions": mapped_questions
        }
    
    except Exception as e:
        import traceback
        print(f"Error in map_questions_to_chapters: {traceback.format_exc()}")
        return {"error": str(e)}

def refine_chapter_match_with_llm(question_text, candidates, all_chapters):
    """Use Groq LLM to analyze and select the best matching chapter"""
    import requests
    import time
    
    print(f"     🔍 LLM Analysis starting...")
    print(f"     Question length: {len(question_text)} chars")
    print(f"     Number of candidates: {len(candidates)}")
    
    try:
        # Prepare candidate info with more content
        print(f"     📋 Preparing candidates for LLM:")
        for i, c in enumerate(candidates[:3]):
            print(f"        {i+1}. '{c['chapter_title']}' (Pages {c['page_start']}-{c['page_end']}, Score: {c['similarity_score']}%)")
        
        candidates_text = "\n".join([
            f"{i+1}. Chapter Title: \"{c['chapter_title']}\"\n   Pages: {c['page_start']}-{c['page_end']}\n   Similarity Score: {c['similarity_score']}%\n   Content from this chapter:\n   \"{c['content_preview'][:400]}...\"\n"
            for i, c in enumerate(candidates[:3])  # Top 3 candidates
        ])
        
        # Create prompt for LLM
        prompt = f"""You are an expert physics/science educator analyzing a question to find which textbook chapter it belongs to.

QUESTION TO ANALYZE:
{question_text}

STEP 1 - UNDERSTAND THE QUESTION:
First, identify what scientific concept, principle, or topic this question is testing. Think about:
- What is the fundamental concept being tested? (e.g., "capacitors in series/parallel", "Ohm's law", "photosynthesis")
- What physics/chemistry/biology principle does this involve?
- What formulas or laws might be needed to solve this?
- What topic would a student need to study to answer this?

STEP 2 - AVAILABLE CHAPTERS IN TEXTBOOK:
{chr(10).join(all_chapters)}

STEP 3 - EXAMINE CHAPTER CONTENT:
Here are the top candidate chapters with actual content from their pages:
{candidates_text}

STEP 4 - MATCH CONCEPT TO CHAPTER:
Now match the concept you identified in Step 1 to the chapter whose content discusses that concept:
- Look for the underlying principle/concept in the chapter content, not just keywords
- Consider if the chapter teaches the knowledge needed to solve this question
- Check if formulas, definitions, or explanations in the chapter relate to the question
- Think about which chapter a teacher would assign this question from

CRITICAL RULES - YOU MUST FOLLOW THESE:
1. You MUST select ONLY from these EXACT chapter titles (copy one of these EXACTLY):
   {chr(10).join([f'   - "{c["chapter_title"]}"' for c in candidates[:3]])}

2. COPY THE ENTIRE CHAPTER TITLE EXACTLY as shown above
   - Include all words, punctuation, and capitalization
   - Do NOT shorten, paraphrase, or modify it in any way
   - Do NOT use partial titles or create new titles

3. If unsure which to pick, choose the one with highest similarity score

4. Base your decision on which chapter's CONTENT best matches the question's concept

RESPONSE FORMAT - Use this exact JSON structure:
{{
    "chapter_title": "EXACT chapter title from candidates above",
    "confidence": 85,
    "reasoning": "The question tests [concept]. The [chapter name] chapter discusses [specific content from preview]"
}}

EXAMPLE - If candidates are "Electricity", "Magnetic Effects", "Light":
{{
    "chapter_title": "Electricity",
    "confidence": 92,
    "reasoning": "The question tests capacitor combinations in series. The Electricity chapter discusses capacitors and their series/parallel connections."
}}

DO NOT create new chapter names. ONLY use the exact titles from the candidates list above.
"""

        # Call Groq API
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "llama-3.3-70b-versatile",  # Updated to current model
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,  # Lower for more focused reasoning
            "max_tokens": 800    # Increased for detailed reasoning
        }
        
        print(f"     📡 Calling Groq API...")
        
        # Retry logic with exponential backoff for rate limiting
        max_retries = 3
        base_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=30
                )
                
                print(f"     📥 API Response Status: {response.status_code}")
                
                if response.status_code == 429:
                    # Rate limit hit
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # 5s, 10s, 20s
                        print(f"     ⏳ Rate limit hit, waiting {delay}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                        continue
                    else:
                        print(f"     ❌ Rate limit exceeded after {max_retries} attempts")
                        return None
                
                response.raise_for_status()
                break  # Success, exit retry loop
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"     ⚠️ Request failed: {e}, retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"     ❌ Request failed after {max_retries} attempts: {e}")
                    return None
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"     📄 LLM Raw Response: {content[:200]}...")
            
            # Parse JSON response
            import json
            import re
            
            # Try multiple methods to extract JSON
            llm_result = None
            
            # Method 1: Look for JSON code block
            code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if code_block_match:
                json_str = code_block_match.group(1)
                print(f"     ✅ JSON extracted from code block: {json_str[:150]}...")
                try:
                    llm_result = json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"     ⚠️ JSON decode error (code block): {e}")
            
            # Method 2: Look for JSON object with proper structure
            if not llm_result:
                # More robust regex that looks for complete JSON objects
                json_match = re.search(r'\{\s*"chapter_title"\s*:\s*"[^"]+"\s*,\s*"confidence"\s*:\s*\d+\s*,\s*"reasoning"\s*:\s*"[^"]*"\s*\}', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    print(f"     ✅ JSON extracted (structured): {json_str[:150]}...")
                    try:
                        llm_result = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        print(f"     ⚠️ JSON decode error (structured): {e}")
            
            # Method 3: Fallback - any JSON-like structure
            if not llm_result:
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    # Skip if it's too short (like {max})
                    if len(json_str) > 20:
                        print(f"     ✅ JSON extracted (fallback): {json_str[:150]}...")
                        try:
                            llm_result = json.loads(json_str)
                        except json.JSONDecodeError as e:
                            print(f"     ⚠️ JSON decode error (fallback): {e}")
                            print(f"     Invalid JSON: {json_str[:100]}")
            
            if llm_result:
                # Validate that chapter_title is from candidates
                returned_title = llm_result.get('chapter_title', '')
                valid_titles = [c['chapter_title'] for c in candidates]
                
                if returned_title not in valid_titles:
                    print(f"     ⚠️ LLM returned invalid chapter: '{returned_title}'")
                    print(f"     Valid options were: {valid_titles}")
                    print(f"     Using best FAISS match instead")
                    return None
                
                return llm_result
            else:
                print(f"     ⚠️ No valid JSON found in response")
                print(f"     Full response: {content[:500]}")
                return None
        else:
            print(f"     ❌ API Error: {response.status_code} - {response.text[:200]}")
            return None
        
    except Exception as e:
        print(f"LLM refinement error: {e}")
        return None

def generate_solution(question_text, context=""):
    """Generate solution for a question using Groq (Llama 3) with rate limiting"""
    import time
    
    try:
        # Check if Groq API key is available
        if not GROQ_API_KEY:
            return {
                "success": False,
                "solution": "Groq API key not configured. Please set GROQ_API_KEY in .env file.\n\nGet your free API key at: https://console.groq.com",
                "method": "none"
            }
        
        # Create prompt
        prompt = f"""You are an expert academic tutor. Provide a clear, step-by-step solution to the following question.

Question: {question_text}

{f'Context from textbook: {context[:500]}' if context else ''}

Provide:
1. A brief explanation of the concept
2. Step-by-step solution with clear reasoning
3. Final answer

Keep the solution concise, educational, and easy to understand."""

        # Call Groq API (OpenAI-compatible)
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": "You are a helpful academic tutor specializing in CBSE curriculum."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        # Retry logic with exponential backoff for rate limiting
        max_retries = 3
        base_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                solution = result['choices'][0]['message']['content']
                
                return {
                    "success": True,
                    "solution": solution,
                    "method": "groq-llama3"
                }
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Too Many Requests
                    if attempt < max_retries - 1:
                        # Exponential backoff: 2s, 4s, 8s
                        delay = base_delay * (2 ** attempt)
                        print(f"⚠ Rate limit hit, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                        continue
                    else:
                        return {
                            "success": False,
                            "solution": "Rate limit exceeded. Please wait a moment and try again.\n\nGroq free tier limits: 30 requests/minute, 14,400 requests/day",
                            "method": "rate_limited"
                        }
                else:
                    raise  # Re-raise other HTTP errors
    
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "solution": "Solution generation timed out. Please try again.",
            "method": "error"
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "solution": f"API Error: {str(e)}\n\nPlease check your GROQ_API_KEY in .env file.\nGet your free API key at: https://console.groq.com",
            "method": "error"
        }
    except Exception as e:
        return {
            "success": False,
            "solution": f"Solution generation failed: {str(e)}\n\nTo enable AI-powered solutions, please configure your GROQ_API_KEY in the .env file.\nGet your free API key at: https://console.groq.com",
            "method": "fallback"
        }

def analyze_question_paper(paper_id, paper_path, textbook_id, textbook_path):
    """Complete analysis: extract questions, map to chapters, prepare for solutions"""
    try:
        # Step 1: Index textbook chapters if not already done
        print(f"[1/3] Indexing textbook {textbook_id}...")
        chapters_result = extract_chapters_from_textbook(textbook_path, textbook_id)
        
        if "error" in chapters_result:
            print(f"ERROR in indexing: {chapters_result['error']}")
            return chapters_result
        
        print(f"✓ Indexed {chapters_result.get('chapters_indexed', 0)} chapters")
        
        # Step 2: Extract questions from paper
        print(f"[2/3] Extracting questions from paper {paper_id}...")
        questions_result = extract_questions_from_paper(paper_path)
        
        if "error" in questions_result:
            print(f"ERROR in extraction: {questions_result['error']}")
            return questions_result
        
        print(f"✓ Extracted {len(questions_result.get('questions', []))} questions")
        
        # Step 3: Map questions to chapters
        print(f"[3/3] Mapping questions to chapters...")
        mapping_result = map_questions_to_chapters(
            questions_result['questions'],
            textbook_id
        )
        
        if "error" in mapping_result:
            print(f"ERROR in mapping: {mapping_result['error']}")
            return mapping_result
        
        print(f"✓ Analysis complete!")
        
        return {
            "success": True,
            "paper_id": paper_id,
            "textbook_id": textbook_id,
            "total_questions": len(mapping_result['mapped_questions']),
            "chapters_indexed": chapters_result['chapters_indexed'],
            "questions": mapping_result['mapped_questions']
        }
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"FATAL ERROR in analyze_question_paper:")
        print(error_details)
        return {
            "error": f"Analysis failed: {str(e)}",
            "details": error_details
        }

def solve_question_with_llm(question_text, question_type, subject=None, chapter_context=None):
    """
    Solve a question using Groq LLM with detailed step-by-step explanation
    Returns solution with steps, diagrams (if needed), and highlighted answer
    """
    import requests
    import re
    
    if not GROQ_API_KEY:
        return {"error": "GROQ_API_KEY not configured"}
    
    # Remove MCQ options from question text
    # Pattern: (a), (b), (c), (d) or A), B), C), D) or a., b., c., d.
    cleaned_question = re.sub(r'\n\s*[\(]?[a-dA-D][\)\.].*?(?=\n|$)', '', question_text, flags=re.MULTILINE)
    # Also remove option patterns like "Options:" or "Choices:"
    cleaned_question = re.sub(r'(?i)(options?|choices?):\s*\n.*', '', cleaned_question, flags=re.DOTALL)
    cleaned_question = cleaned_question.strip()
    
    # Build context-aware prompt
    context_info = ""
    if subject:
        context_info += f"Subject: {subject}\n"
    if chapter_context:
        context_info += f"Chapter: {chapter_context}\n"
    
    # Create concise, focused prompt
    prompt = f"""You are an expert teacher. Solve this question concisely and clearly.

{context_info}
Question: {cleaned_question}

Provide a CRISP solution with:

**Given:**
List given values/information (one line each)

**Find:**
What to calculate/answer (one line)

**Formula/Concept:**
Key formula or concept (use proper notation: x², √x, ∫, ∑, α, β, π, etc.)

**Solution:**
Step 1: [Brief step with calculation]
Step 2: [Brief step with calculation]
Step 3: [Brief step with calculation]

**Diagram:** (if needed - use simple ASCII art with proper spacing)

**FINAL ANSWER:** [Clear, concise answer]

IMPORTANT:
- Be concise, not verbose
- Use proper mathematical notation: x², x³, √x, ∛x, π, ∞, ≈, ≤, ≥, ±, ×, ÷, °, α, β, γ, Δ, Σ
- Use proper scientific notation: H₂O, CO₂, Fe²⁺, subscripts/superscripts
- For diagrams, use clean ASCII with proper alignment
- Keep explanations brief and to the point
- Focus on the solution approach, not lengthy theory"""

    try:
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert teacher who provides concise, clear solutions with proper mathematical and scientific notation. Focus on crisp explanations without verbose text."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 4000,
            "temperature": 0.3
        }
        
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        print(f"🤖 Solving question with LLM...")
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        solution_text = result['choices'][0]['message']['content']
        
        # Extract token usage
        usage = result.get('usage', {})
        tokens_used = usage.get('total_tokens', 0)
        prompt_tokens = usage.get('prompt_tokens', 0)
        completion_tokens = usage.get('completion_tokens', 0)
        
        print(f"✓ Solution generated ({len(solution_text)} chars, {tokens_used} tokens)")
        
        # Parse the solution to extract components
        solution_parts = parse_solution_text(solution_text)
        
        return {
            "success": True,
            "solution": solution_text,
            "parsed_solution": solution_parts,
            "tokens_used": tokens_used,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "model": GROQ_MODEL
        }
        
    except Exception as e:
        import traceback
        print(f"Error solving question: {traceback.format_exc()}")
        return {"error": str(e)}

def parse_solution_text(solution_text):
    """Parse the solution text to extract different sections"""
    import re
    
    sections = {
        "understanding": "",
        "given": "",
        "required": "",
        "concept": "",
        "steps": "",
        "diagram": "",
        "final_answer": ""
    }
    
    # Extract final answer (highlighted)
    final_answer_match = re.search(r'FINAL ANSWER:\s*(.+?)(?:\n\n|\n\*\*|$)', solution_text, re.IGNORECASE | re.DOTALL)
    if final_answer_match:
        sections["final_answer"] = final_answer_match.group(1).strip()
    
    # Try to extract sections by headers
    section_patterns = {
        "understanding": r'\*\*Understanding.*?\*\*:?\s*(.+?)(?=\n\*\*|\n\d+\.|\Z)',
        "given": r'\*\*Given.*?\*\*:?\s*(.+?)(?=\n\*\*|\n\d+\.|\Z)',
        "required": r'\*\*Required.*?\*\*:?\s*(.+?)(?=\n\*\*|\n\d+\.|\Z)',
        "concept": r'\*\*Concept.*?\*\*:?\s*(.+?)(?=\n\*\*|\n\d+\.|\Z)',
        "steps": r'\*\*Step.*?Solution.*?\*\*:?\s*(.+?)(?=\n\*\*Diagram|\n\*\*Final|\Z)',
        "diagram": r'\*\*Diagram.*?\*\*:?\s*(.+?)(?=\n\*\*Final|\Z)'
    }
    
    for key, pattern in section_patterns.items():
        match = re.search(pattern, solution_text, re.IGNORECASE | re.DOTALL)
        if match:
            sections[key] = match.group(1).strip()
    
    return sections
