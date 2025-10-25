# 📚 Vector Storage Guide - Local FAISS

## Overview

This guide explains how the vector storage system works using **local FAISS** for semantic search and question-to-chapter mapping.

---

## 🎯 What is Vector Storage?

Vector storage enables **semantic search** - finding similar content based on meaning, not just keywords.

**Use Cases:**
- Map questions to relevant textbook chapters
- Find similar questions
- Search textbook content by meaning
- Intelligent chapter recommendations

---

## 🔧 How It Works

### 1. Upload Textbook

```
User uploads PDF textbook
    ↓
System extracts text from PDF
    ↓
Identifies chapters and page ranges
```

### 2. Create Embeddings

```
Each chapter text
    ↓
Sentence Transformer Model (all-MiniLM-L6-v2)
    ↓
384-dimensional vector embedding
```

### 3. Store in FAISS Index

```
Chapter embeddings
    ↓
FAISS Index (L2 distance)
    ↓
Saved to: vector_indices/{textbook_id}/
```

### 4. Semantic Search

```
Question text
    ↓
Convert to embedding
    ↓
Search FAISS index
    ↓
Find top 3 similar chapters
```

---

## 📁 File Structure

### Vector Storage Directory

```
vector_indices/
├── 1/                          # Textbook ID 1
│   ├── index.faiss            # FAISS index file
│   ├── metadata.pkl           # Chapter metadata
│   └── embeddings.npy         # Raw embeddings
├── 2/                          # Textbook ID 2
│   ├── index.faiss
│   ├── metadata.pkl
│   └── embeddings.npy
└── 3/                          # Textbook ID 3
    ├── index.faiss
    ├── metadata.pkl
    └── embeddings.npy
```

### File Contents

**`index.faiss`**
- Binary FAISS index
- Optimized for fast similarity search
- Uses L2 (Euclidean) distance

**`metadata.pkl`**
- Chapter information (title, pages, content)
- Textbook metadata
- Mapping between vectors and chapters

**`embeddings.npy`**
- Raw numpy array of embeddings
- Shape: (num_chapters, 384)
- Used for backup and analysis

---

## 🚀 Usage

### Extract Chapters from Textbook

```python
from ai_service import extract_chapters_from_textbook

# Extract chapters and create FAISS index
chapters = extract_chapters_from_textbook(
    textbook_id=1,
    pdf_path='uploads/physics_textbook.pdf'
)

print(f"Extracted {len(chapters)} chapters")
# Output: Extracted 15 chapters

# FAISS index automatically created at:
# vector_indices/1/index.faiss
```

### Map Questions to Chapters

```python
from ai_service import map_questions_to_chapters

questions = [
    {
        'id': 1,
        'question_text': 'What is Ohm\'s law?'
    },
    {
        'id': 2,
        'question_text': 'Explain the working of a transformer'
    }
]

result = map_questions_to_chapters(questions, textbook_id=1)

for q in result['mapped_questions']:
    print(f"Q{q['id']}: {q['question_text']}")
    for ch in q['chapters']:
        print(f"  → {ch['chapter_title']} (Score: {ch['similarity_score']:.1f}%)")
        print(f"     Pages: {ch['page_range']}")
```

**Output:**
```
Q1: What is Ohm's law?
  → Electricity (Score: 92.5%)
     Pages: 1-20
  → Current Electricity (Score: 85.3%)
     Pages: 21-35

Q2: Explain the working of a transformer
  → Electromagnetic Induction (Score: 89.7%)
     Pages: 156-175
```

### Search Textbook Chapters

```python
from ai_service import search_textbook_chapters

results = search_textbook_chapters(
    textbook_id=1,
    query="How does a motor work?",
    top_k=3
)

for result in results:
    print(f"{result['chapter_title']}")
    print(f"  Similarity: {result['similarity_score']:.1f}%")
    print(f"  Pages: {result['page_range']}")
    print(f"  Preview: {result['preview'][:100]}...")
    print()
```

---

## 🔍 Technical Details

### Embedding Model

**Model:** `all-MiniLM-L6-v2`
- **Dimensions:** 384
- **Speed:** Very fast (~1000 sentences/sec)
- **Quality:** Good for semantic similarity
- **Size:** ~80 MB

**Why this model?**
- ✅ Fast inference
- ✅ Good accuracy
- ✅ Small size
- ✅ Works offline
- ✅ No API costs

### FAISS Index Type

**Index:** `IndexFlatL2`
- **Distance:** L2 (Euclidean)
- **Accuracy:** 100% (exact search)
- **Speed:** Fast for small datasets (<10K vectors)
- **Memory:** Stores all vectors in RAM

**Alternative for large datasets:**
```python
# For >10K vectors, use IVF index
import faiss
index = faiss.IndexIVFFlat(quantizer, d, nlist)
```

### Similarity Scoring

```python
# Convert L2 distance to similarity score (0-100)
similarity_score = max(0, 100 - (distance * 10))
```

**Interpretation:**
- **90-100%** - Highly relevant
- **70-90%** - Relevant
- **50-70%** - Somewhat relevant
- **<50%** - Not very relevant

---

## 📊 Performance

### Speed Benchmarks

**Chapter Extraction:**
- 15 chapters: ~5-10 seconds
- 30 chapters: ~10-20 seconds
- Includes: PDF parsing, text extraction, embedding creation

**Question Mapping:**
- 1 question: ~0.1 seconds
- 10 questions: ~0.5 seconds
- 100 questions: ~3 seconds

**Search:**
- Single query: <0.01 seconds
- Batch (10 queries): ~0.05 seconds

### Memory Usage

**Per Textbook:**
- 15 chapters: ~2 MB
- 30 chapters: ~4 MB
- 100 chapters: ~12 MB

**Total System:**
- Model: ~80 MB (loaded once)
- Indices: ~2-4 MB per textbook
- Total: ~100-200 MB for typical usage

---

## 🧪 Testing

### Test 1: Create FAISS Index

```python
import os
from ai_service import extract_chapters_from_textbook

# Extract chapters
chapters = extract_chapters_from_textbook(
    textbook_id=1,
    pdf_path='uploads/test_textbook.pdf'
)

# Verify index created
index_path = 'vector_indices/1/index.faiss'
assert os.path.exists(index_path), "Index not created!"

print(f"✅ Index created with {len(chapters)} chapters")
```

### Test 2: Search Accuracy

```python
from ai_service import map_questions_to_chapters

# Test question about electricity
questions = [{
    'id': 1,
    'question_text': 'What is the relationship between voltage and current?'
}]

result = map_questions_to_chapters(questions, textbook_id=1)
top_chapter = result['mapped_questions'][0]['chapters'][0]

print(f"Top match: {top_chapter['chapter_title']}")
print(f"Score: {top_chapter['similarity_score']:.1f}%")

# Should match "Electricity" or "Current Electricity" chapter
assert top_chapter['similarity_score'] > 70, "Low similarity score!"
```

### Test 3: Performance

```python
import time
from ai_service import search_textbook_chapters

# Measure search time
start = time.time()
results = search_textbook_chapters(
    textbook_id=1,
    query="Explain photosynthesis",
    top_k=5
)
elapsed = time.time() - start

print(f"Search time: {elapsed*1000:.2f} ms")
assert elapsed < 0.1, "Search too slow!"  # Should be <100ms
```

---

## 🔧 Maintenance

### Rebuild Index

If index gets corrupted or you update the textbook:

```python
from ai_service import extract_chapters_from_textbook

# This will overwrite existing index
chapters = extract_chapters_from_textbook(
    textbook_id=1,
    pdf_path='uploads/updated_textbook.pdf'
)

print("✅ Index rebuilt successfully")
```

### Backup Indices

```bash
# Backup all vector indices
xcopy vector_indices vector_indices_backup /E /I

# Or use zip
tar -czf vector_indices_backup.tar.gz vector_indices/
```

### Delete Index

```python
import shutil

# Delete index for textbook
textbook_id = 1
shutil.rmtree(f'vector_indices/{textbook_id}')

print(f"✅ Deleted index for textbook {textbook_id}")
```

### Check Index Health

```python
import os
import pickle
import faiss

def check_index_health(textbook_id):
    """Check if FAISS index is valid"""
    index_dir = f'vector_indices/{textbook_id}'
    
    # Check files exist
    files = ['index.faiss', 'metadata.pkl', 'embeddings.npy']
    for file in files:
        path = os.path.join(index_dir, file)
        if not os.path.exists(path):
            print(f"❌ Missing: {file}")
            return False
    
    # Load and verify index
    try:
        index = faiss.read_index(os.path.join(index_dir, 'index.faiss'))
        print(f"✅ Index has {index.ntotal} vectors")
        
        with open(os.path.join(index_dir, 'metadata.pkl'), 'rb') as f:
            metadata = pickle.load(f)
        print(f"✅ Metadata has {len(metadata['chapters'])} chapters")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# Test
check_index_health(textbook_id=1)
```

---

## 🐛 Troubleshooting

### Issue: "No vector index found"

**Cause:** Index not created for textbook

**Solution:**
```python
# Extract chapters to create index
from ai_service import extract_chapters_from_textbook
extract_chapters_from_textbook(textbook_id=1, pdf_path='path/to/pdf')
```

### Issue: "Dimension mismatch"

**Cause:** Different embedding model used

**Solution:**
```python
# Always use the same model
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')  # 384 dimensions
```

### Issue: "Low similarity scores"

**Cause:** Question and chapter content too different

**Solutions:**
1. Check if textbook covers the topic
2. Try different question phrasing
3. Lower similarity threshold
4. Extract more detailed chapters

### Issue: "Slow search"

**Cause:** Large index or slow disk

**Solutions:**
1. Use SSD for vector_indices directory
2. Increase RAM
3. Use IVF index for large datasets
4. Cache frequently searched queries

---

## 💡 Best Practices

### 1. Chapter Extraction

**DO:**
- ✅ Extract chapters with clear boundaries
- ✅ Include page ranges
- ✅ Keep chapter text concise (1-2 pages)
- ✅ Remove headers/footers

**DON'T:**
- ❌ Make chapters too long (>5 pages)
- ❌ Include irrelevant content
- ❌ Mix multiple topics in one chapter

### 2. Question Mapping

**DO:**
- ✅ Use clear, specific questions
- ✅ Include key terms from textbook
- ✅ Check top 3 results
- ✅ Verify similarity scores

**DON'T:**
- ❌ Use very short questions (<5 words)
- ❌ Rely only on top result
- ❌ Ignore low similarity scores

### 3. Index Management

**DO:**
- ✅ Backup indices regularly
- ✅ Rebuild if textbook updated
- ✅ Monitor disk space
- ✅ Check index health periodically

**DON'T:**
- ❌ Delete indices without backup
- ❌ Manually edit index files
- ❌ Share indices between environments

---

## 📚 API Reference

### `extract_chapters_from_textbook(textbook_id, pdf_path)`

Extract chapters and create FAISS index.

**Parameters:**
- `textbook_id` (int): Unique textbook identifier
- `pdf_path` (str): Path to PDF file

**Returns:**
- `list`: List of chapter dictionaries

**Example:**
```python
chapters = extract_chapters_from_textbook(1, 'physics.pdf')
```

### `map_questions_to_chapters(questions, textbook_id)`

Map questions to textbook chapters using semantic search.

**Parameters:**
- `questions` (list): List of question dictionaries
- `textbook_id` (int): Textbook identifier

**Returns:**
- `dict`: Mapping results with similarity scores

**Example:**
```python
result = map_questions_to_chapters(questions, 1)
```

### `search_textbook_chapters(textbook_id, query, top_k=3)`

Search textbook chapters by query.

**Parameters:**
- `textbook_id` (int): Textbook identifier
- `query` (str): Search query
- `top_k` (int): Number of results (default: 3)

**Returns:**
- `list`: Top matching chapters with scores

**Example:**
```python
results = search_textbook_chapters(1, "photosynthesis", top_k=5)
```

---

## ✅ Summary

**Vector Storage System:**
- ✅ Uses local FAISS (no cloud needed)
- ✅ Fast semantic search
- ✅ Automatic index creation
- ✅ Works offline
- ✅ No API costs
- ✅ Simple maintenance

**Storage Location:**
- `vector_indices/{textbook_id}/`

**Key Files:**
- `index.faiss` - FAISS index
- `metadata.pkl` - Chapter metadata
- `embeddings.npy` - Raw embeddings

**Performance:**
- Search: <10ms per query
- Extraction: ~10 seconds per textbook
- Memory: ~100-200 MB total

---

**Your vector storage system is ready to use!** 🎉
