#!/usr/bin/env python
"""Debug OCR extraction to see what text is being read."""

import warnings
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

os.environ["PYTHONWARNINGS"] = "ignore"
warnings.filterwarnings("ignore")

import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings

# Get OCR reader
import easyocr
print("Initializing EasyOCR...")
reader = easyocr.Reader(['en'], gpu=False, verbose=False)

settings = get_settings()

# Test with first bill
image_path = settings.dataset_dir / "bill_innovh_01.png"
print(f"\nProcessing: {image_path}")

results = reader.readtext(str(image_path))

print("\n" + "="*60)
print("RAW OCR OUTPUT (all detected text)")
print("="*60)
for i, (bbox, text, conf) in enumerate(results):
    print(f"[{i:2d}] ({conf:.2f}) {text}")

# Join all text
full_text = " ".join([r[1] for r in results])
print("\n" + "="*60)
print("JOINED TEXT")
print("="*60)
print(full_text)

# Test amount extraction
print("\n" + "="*60)
print("AMOUNT EXTRACTION TEST")
print("="*60)

AMOUNT_PATTERNS = [
    r"(?:grand\s*total|total\s*amount|net\s*amount|amount\s*payable)[:\s]*(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{2})?)",
    r"(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{2})?)\s*(?:only|/-)?",
    r"([\d,]+(?:\.\d{2})?)\s*(?:Rs\.?|INR|₹)",
]

for i, pattern in enumerate(AMOUNT_PATTERNS):
    print(f"\nPattern {i+1}: {pattern}")
    matches = re.findall(pattern, full_text, re.IGNORECASE)
    print(f"  Matches: {matches}")

# Look for "grand total" specifically
print("\n" + "="*60)
print("SEARCHING FOR 'GRAND TOTAL' IN TEXT")
print("="*60)
lower_text = full_text.lower()
if "grand total" in lower_text:
    idx = lower_text.index("grand total")
    context = full_text[max(0, idx-20):idx+50]
    print(f"Found! Context: ...{context}...")
else:
    print("'grand total' NOT found in OCR text")

# Look for what patterns ARE in the text
print("\n" + "="*60)
print("LOOKING FOR AMOUNT-RELATED KEYWORDS")
print("="*60)
keywords = ["total", "amount", "grand", "net", "payable", "rs", "inr", "₹"]
for kw in keywords:
    if kw in lower_text:
        print(f"  Found: '{kw}'")
