#!/usr/bin/env python
"""
Evaluation script for MediShield document classification pipeline.

Runs the pipeline on test images and calculates accuracy metrics.

Usage:
    uv run python scripts/evaluate.py              # Run on all labeled images
    uv run python scripts/evaluate.py --limit 5   # Run on first 5 images
    uv run python scripts/evaluate.py --dry-run   # Show what would be processed
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.pipeline.graph import process_document
from app.models.document import DocType


def load_ground_truth(dataset_dir: Path) -> dict:
    """Load ground truth labels from JSON file."""
    gt_path = dataset_dir / "ground_truth.json"
    if not gt_path.exists():
        print(f"Warning: ground_truth.json not found at {gt_path}")
        return {"labels": []}

    with open(gt_path) as f:
        return json.load(f)


def evaluate_classification(
    dataset_dir: Path,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict:
    """Evaluate classification accuracy on labeled dataset.

    Args:
        dataset_dir: Path to dataset directory
        limit: Maximum number of images to process
        dry_run: If True, only show what would be processed

    Returns:
        Dictionary with evaluation metrics
    """
    ground_truth = load_ground_truth(dataset_dir)
    labels = ground_truth.get("labels", [])

    if not labels:
        print("No ground truth labels found. Please update ground_truth.json")
        return {}

    # Filter to images that exist
    valid_labels = []
    for label in labels:
        img_path = dataset_dir / label["filename"]
        if img_path.exists():
            label["path"] = img_path
            valid_labels.append(label)

    if limit:
        valid_labels = valid_labels[:limit]

    print(f"\n{'='*60}")
    print(f"  MediShield Evaluation - {len(valid_labels)} documents")
    print(f"{'='*60}\n")

    if dry_run:
        print("DRY RUN - Would process:")
        for label in valid_labels:
            print(f"  - {label['filename']}: expected {label['expected_doc_type']}")
        return {}

    # Run evaluation
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
            result = process_document(image_path=str(label["path"]))
            elapsed = time.perf_counter() - start
            total_time += elapsed

            # Get actual results
            classifier_output = result.get("classifier_output")
            final_decision = result.get("final_decision")

            actual_type = classifier_output.doc_type.value if classifier_output else "Unknown"
            actual_decision = final_decision.decision.value if final_decision else None

            # Check classification
            type_match = actual_type.lower() == expected_type.lower()
            if type_match:
                correct_classifications += 1

            # Check decision
            decision_match = False
            if expected_decision and actual_decision:
                decision_match = actual_decision.lower() == expected_decision.lower()
                if decision_match:
                    correct_decisions += 1

            confidence = classifier_output.confidence if classifier_output else 0

            print(f"  Expected: {expected_type} | Actual: {actual_type} | {'✓' if type_match else '✗'}")
            print(f"  Decision: {actual_decision} (expected: {expected_decision}) | {'✓' if decision_match else '✗'}")
            print(f"  Time: {elapsed:.2f}s | Confidence: {confidence:.2f}\n")

            results.append({
                "filename": filename,
                "expected_type": expected_type,
                "actual_type": actual_type,
                "type_correct": type_match,
                "expected_decision": expected_decision,
                "actual_decision": actual_decision,
                "decision_correct": decision_match,
                "confidence": confidence,
                "time": elapsed,
            })

        except Exception as e:
            elapsed = time.perf_counter() - start
            print(f"  ERROR: {e}\n")
            results.append({
                "filename": filename,
                "error": str(e),
                "time": elapsed,
            })

    # Calculate metrics
    total = len(valid_labels)
    classification_accuracy = correct_classifications / total if total > 0 else 0
    decision_accuracy = correct_decisions / total if total > 0 else 0
    avg_time = total_time / total if total > 0 else 0

    # Summary
    print(f"\n{'='*60}")
    print("  EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Documents processed    : {total}")
    print(f"  Classification accuracy: {classification_accuracy*100:.1f}% ({correct_classifications}/{total})")
    print(f"  Decision accuracy      : {decision_accuracy*100:.1f}% ({correct_decisions}/{total})")
    print(f"  Average processing time: {avg_time:.2f}s")
    print(f"  Total time             : {total_time:.2f}s")
    print(f"{'='*60}\n")

    # Check against targets
    print("  Target Metrics:")
    print(f"  - Classification ≥95%: {'✓ PASS' if classification_accuracy >= 0.95 else '✗ FAIL'}")
    print(f"  - Decision ≥60%      : {'✓ PASS' if decision_accuracy >= 0.60 else '✗ FAIL'}")
    print(f"  - Avg time <5s       : {'✓ PASS' if avg_time < 5 else '✗ FAIL'}")
    print()

    return {
        "total": total,
        "classification_accuracy": classification_accuracy,
        "decision_accuracy": decision_accuracy,
        "avg_time": avg_time,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate MediShield pipeline")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of images to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without running",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file for results",
    )

    args = parser.parse_args()
    settings = get_settings()

    results = evaluate_classification(
        dataset_dir=settings.dataset_dir,
        limit=args.limit,
        dry_run=args.dry_run,
    )

    if args.output and results:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Results saved to {output_path}")


if __name__ == "__main__":
    main()
