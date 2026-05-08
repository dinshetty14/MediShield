#!/usr/bin/env python
import warnings
import os
import sys

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Suppress everything
os.environ["PYTHONWARNINGS"] = "ignore"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
warnings.filterwarnings("ignore")

# Monkey-patch warnings.warn to suppress LangChain warnings
_original_warn = warnings.warn
def _patched_warn(message, category=None, stacklevel=1, source=None):
    msg_str = str(message)
    if "allowed_objects" in msg_str or "LangChain" in str(category):
        return  # Suppress
    _original_warn(message, category, stacklevel, source)
warnings.warn = _patched_warn

"""
Fast evaluation script using OCR-first pipeline.

Usage:
    uv run python scripts/evaluate_fast.py --limit 5
"""

import argparse
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.pipeline.fast_graph import process_document_fast


def load_ground_truth(dataset_dir: Path) -> dict:
    gt_path = dataset_dir / "ground_truth.json"
    if not gt_path.exists():
        return {"labels": []}
    with open(gt_path) as f:
        return json.load(f)


def evaluate(dataset_dir: Path, limit: int | None = None) -> dict:
    ground_truth = load_ground_truth(dataset_dir)
    labels = ground_truth.get("labels", [])

    valid_labels = []
    for label in labels:
        img_path = dataset_dir / label["filename"]
        if img_path.exists():
            label["path"] = img_path
            valid_labels.append(label)

    if limit:
        valid_labels = valid_labels[:limit]

    print(f"\n{'='*60}")
    print(f"  FAST Pipeline Evaluation - {len(valid_labels)} documents")
    print(f"{'='*60}\n")

    results = []
    correct_classifications = 0
    correct_decisions = 0
    total_time = 0

    for i, label in enumerate(valid_labels, 1):
        filename = label["filename"]
        expected_type = label["expected_doc_type"]
        expected_decision = label.get("expected_decision")

        print(f"[{i}/{len(valid_labels)}] Processing: {filename}")

        start = time.perf_counter()
        try:
            result = process_document_fast(image_path=str(label["path"]))
            elapsed = time.perf_counter() - start
            total_time += elapsed

            classifier_output = result.get("classifier_output")
            final_decision = result.get("final_decision")

            actual_type = classifier_output.doc_type.value if classifier_output else "Unknown"
            actual_decision = final_decision.decision.value if final_decision else None

            type_match = actual_type.lower() == expected_type.lower()
            if type_match:
                correct_classifications += 1

            decision_match = False
            if expected_decision and actual_decision:
                decision_match = actual_decision.lower() == expected_decision.lower()
                if decision_match:
                    correct_decisions += 1

            confidence = classifier_output.confidence if classifier_output else 0

            print(f"  Expected: {expected_type} | Actual: {actual_type} | {'PASS' if type_match else 'FAIL'}")
            print(f"  Decision: {actual_decision} (expected: {expected_decision}) | {'PASS' if decision_match else 'FAIL'}")
            print(f"  Time: {elapsed:.2f}s | Confidence: {confidence:.2f}\n")

            results.append({
                "filename": filename,
                "expected_type": expected_type,
                "actual_type": actual_type,
                "type_correct": type_match,
                "decision_correct": decision_match,
                "time": elapsed,
            })

        except Exception as e:
            elapsed = time.perf_counter() - start
            print(f"  ERROR: {e}\n")
            results.append({"filename": filename, "error": str(e), "time": elapsed})

    total = len(valid_labels)
    classification_accuracy = correct_classifications / total if total > 0 else 0
    decision_accuracy = correct_decisions / total if total > 0 else 0
    avg_time = total_time / total if total > 0 else 0

    print(f"\n{'='*60}")
    print("  FAST EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Documents processed    : {total}")
    print(f"  Classification accuracy: {classification_accuracy*100:.1f}% ({correct_classifications}/{total})")
    print(f"  Decision accuracy      : {decision_accuracy*100:.1f}% ({correct_decisions}/{total})")
    print(f"  Average processing time: {avg_time:.2f}s")
    print(f"  Total time             : {total_time:.2f}s")
    print(f"{'='*60}\n")

    print("  Assignment Targets:")
    print(f"  - Classification (target: high): {'PASS' if classification_accuracy >= 0.95 else 'NEEDS REVIEW'}")
    print(f"  - Decision >=60% (required)    : {'PASS' if decision_accuracy >= 0.60 else 'FAIL'}")
    print()

    return {"classification_accuracy": classification_accuracy, "decision_accuracy": decision_accuracy, "avg_time": avg_time}


def main():
    parser = argparse.ArgumentParser(description="Fast pipeline evaluation")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    settings = get_settings()
    evaluate(settings.dataset_dir, args.limit)


if __name__ == "__main__":
    main()
