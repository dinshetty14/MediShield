#!/usr/bin/env python
"""
Confidence Calibration Plot for MediShield Pipeline.

Generates a calibration curve showing how well the model's confidence
scores correlate with actual accuracy.

A well-calibrated model should have points close to the diagonal:
- 80% confident predictions should be correct ~80% of the time
- 60% confident predictions should be correct ~60% of the time

Usage:
    uv run python scripts/calibration_plot.py              # Run full evaluation
    uv run python scripts/calibration_plot.py --limit 10   # Quick test with 10 docs
    uv run python scripts/calibration_plot.py --output results.png  # Custom output
"""

import argparse
import json
import os
import sys
import time
import warnings
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Suppress warnings
os.environ["PYTHONWARNINGS"] = "ignore"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
warnings.filterwarnings("ignore")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def collect_predictions(dataset_dir: Path, limit: int | None = None) -> list[dict]:
    """Run pipeline and collect predictions with confidence scores.

    Returns:
        List of dicts with 'confidence', 'correct', 'filename' keys
    """
    from app.config import get_settings
    from app.pipeline.graph import process_document

    # Load ground truth
    gt_path = dataset_dir / "ground_truth.json"
    if not gt_path.exists():
        print(f"Error: ground_truth.json not found at {gt_path}")
        return []

    with open(gt_path) as f:
        ground_truth = json.load(f)

    labels = ground_truth.get("labels", [])
    if not labels:
        print("No ground truth labels found")
        return []

    # Filter to existing images
    valid_labels = []
    for label in labels:
        img_path = dataset_dir / label["filename"]
        if img_path.exists():
            label["path"] = img_path
            valid_labels.append(label)

    if limit:
        valid_labels = valid_labels[:limit]

    print(f"\nCollecting predictions from {len(valid_labels)} documents...\n")

    predictions = []
    for i, label in enumerate(valid_labels, 1):
        filename = label["filename"]
        expected_type = label["expected_doc_type"].lower()

        print(f"[{i}/{len(valid_labels)}] {filename}...", end=" ", flush=True)

        try:
            result = process_document(image_path=str(label["path"]))
            classifier_output = result.get("classifier_output")

            if classifier_output:
                actual_type = classifier_output.doc_type.value.lower()
                confidence = classifier_output.confidence
                correct = (actual_type == expected_type)

                predictions.append({
                    "filename": filename,
                    "confidence": confidence,
                    "correct": correct,
                    "expected": expected_type,
                    "actual": actual_type,
                })
                print(f"conf={confidence:.2f} {'PASS' if correct else 'FAIL'}")
            else:
                print("No output")

        except Exception as e:
            print(f"ERROR: {e}")

    return predictions


def plot_calibration_curve(predictions: list[dict], output_path: str = "calibration_curve.png"):
    """Generate and save calibration curve plot.

    Args:
        predictions: List of dicts with 'confidence' and 'correct' keys
        output_path: Path to save the plot
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("Error: matplotlib and numpy required. Install with:")
        print("  uv add matplotlib numpy")
        return

    if not predictions:
        print("No predictions to plot")
        return

    # Extract data
    confidences = np.array([p["confidence"] for p in predictions])
    correct = np.array([p["correct"] for p in predictions])

    # Create bins for calibration
    n_bins = 10
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    bin_accuracies = []
    bin_counts = []
    bin_confidences = []

    for i in range(n_bins):
        mask = (confidences >= bin_edges[i]) & (confidences < bin_edges[i + 1])
        if i == n_bins - 1:  # Include right edge for last bin
            mask = (confidences >= bin_edges[i]) & (confidences <= bin_edges[i + 1])

        bin_count = np.sum(mask)
        bin_counts.append(bin_count)

        if bin_count > 0:
            bin_acc = np.mean(correct[mask])
            bin_conf = np.mean(confidences[mask])
        else:
            bin_acc = np.nan
            bin_conf = bin_centers[i]

        bin_accuracies.append(bin_acc)
        bin_confidences.append(bin_conf)

    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Plot 1: Calibration curve
    ax1.plot([0, 1], [0, 1], 'k--', label='Perfectly calibrated', linewidth=2)

    # Plot bins with samples
    valid_bins = [(bc, ba, bn) for bc, ba, bn in zip(bin_confidences, bin_accuracies, bin_counts)
                  if not np.isnan(ba) and bn > 0]

    if valid_bins:
        confs, accs, counts = zip(*valid_bins)
        sizes = [max(50, min(300, c * 30)) for c in counts]  # Scale point size by count
        scatter = ax1.scatter(confs, accs, s=sizes, alpha=0.7, c='blue', edgecolors='darkblue', linewidth=1.5)
        ax1.plot(confs, accs, 'b-', alpha=0.5, linewidth=1)

    ax1.set_xlabel('Mean Predicted Confidence', fontsize=12)
    ax1.set_ylabel('Actual Accuracy (Fraction Correct)', fontsize=12)
    ax1.set_title('Confidence Calibration Curve', fontsize=14, fontweight='bold')
    ax1.set_xlim(-0.05, 1.05)
    ax1.set_ylim(-0.05, 1.05)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='lower right')

    # Add calibration error
    valid_accs = [a for a in bin_accuracies if not np.isnan(a)]
    valid_confs = [c for c, a in zip(bin_confidences, bin_accuracies) if not np.isnan(a)]
    if valid_accs:
        ece = np.mean(np.abs(np.array(valid_accs) - np.array(valid_confs)))
        ax1.text(0.05, 0.95, f'ECE: {ece:.3f}', transform=ax1.transAxes,
                fontsize=11, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # Plot 2: Histogram of confidence scores
    colors = ['green' if c else 'red' for c in correct]
    ax2.hist([confidences[correct], confidences[~correct]],
             bins=20, range=(0, 1), stacked=True,
             color=['green', 'red'], alpha=0.7,
             label=['Correct', 'Incorrect'])

    ax2.set_xlabel('Confidence Score', fontsize=12)
    ax2.set_ylabel('Number of Predictions', fontsize=12)
    ax2.set_title('Distribution of Confidence Scores', fontsize=14, fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')

    # Overall stats
    overall_acc = np.mean(correct)
    mean_conf = np.mean(confidences)
    fig.suptitle(f'MediShield Classifier Calibration Analysis\n'
                 f'N={len(predictions)} | Accuracy={overall_acc:.1%} | Mean Confidence={mean_conf:.2f}',
                 fontsize=12, y=1.02)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\nCalibration plot saved to: {output_path}")

    # Print summary
    print(f"\n{'='*50}")
    print("  CALIBRATION SUMMARY")
    print(f"{'='*50}")
    print(f"  Total predictions: {len(predictions)}")
    print(f"  Overall accuracy : {overall_acc:.1%}")
    print(f"  Mean confidence  : {mean_conf:.2f}")
    if valid_accs:
        print(f"  ECE (lower=better): {ece:.3f}")
    print(f"{'='*50}")

    # Interpretation
    print("\n  Interpretation:")
    if valid_accs and ece < 0.1:
        print("  Model is well-calibrated (ECE < 0.1)")
    elif valid_accs and ece < 0.2:
        print("  Model is reasonably calibrated (ECE < 0.2)")
    else:
        print("  Model may be over/under-confident (ECE >= 0.2)")

    if mean_conf > overall_acc + 0.1:
        print("  Model tends to be OVERCONFIDENT")
    elif mean_conf < overall_acc - 0.1:
        print("  Model tends to be UNDERCONFIDENT")
    else:
        print("  Confidence roughly matches accuracy")


def main():
    parser = argparse.ArgumentParser(description="Generate calibration plot for MediShield")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of documents to process",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="calibration_curve.png",
        help="Output path for the plot (default: calibration_curve.png)",
    )
    parser.add_argument(
        "--data",
        type=str,
        default=None,
        help="Load predictions from JSON file instead of running pipeline",
    )
    parser.add_argument(
        "--save-data",
        type=str,
        default=None,
        help="Save predictions to JSON file for reuse",
    )

    args = parser.parse_args()

    if args.data:
        # Load from file
        print(f"Loading predictions from {args.data}")
        with open(args.data) as f:
            predictions = json.load(f)
    else:
        # Run pipeline
        from app.config import get_settings
        settings = get_settings()
        predictions = collect_predictions(settings.dataset_dir, limit=args.limit)

        if args.save_data and predictions:
            with open(args.save_data, "w") as f:
                json.dump(predictions, f, indent=2)
            print(f"Predictions saved to {args.save_data}")

    if predictions:
        plot_calibration_curve(predictions, args.output)


if __name__ == "__main__":
    main()
