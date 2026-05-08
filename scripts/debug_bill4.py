#!/usr/bin/env python
"""Debug why bill_innovh_04.png is being rejected."""

import warnings
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

os.environ["PYTHONWARNINGS"] = "ignore"
warnings.filterwarnings("ignore")

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pipeline.fast_graph import process_document_fast
from app.config import get_settings

settings = get_settings()
image_path = settings.dataset_dir / "bill_innovh_04.png"

print(f"Processing: {image_path}")
result = process_document_fast(image_path=str(image_path))

print("\n--- RESULT ---")
print(f"Classifier: {result.get('classifier_output')}")
print(f"Claims: {result.get('claims_output')}")
print(f"Policy: {result.get('policy_output')}")
print(f"Fraud: {result.get('fraud_output')}")
print(f"Decision: {result.get('final_decision')}")
