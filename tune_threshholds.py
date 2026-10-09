"""
tune_thresholds.py

Per-class threshold tuning for Politerate's multi-label technique head.

Optimizes thresholds with a PRECISION FLOOR — finds the most lenient threshold
that achieves a minimum precision target, then maximizes recall. This produces
stricter, more trustworthy predictions than F1-maximizing.

Outputs:
    - technique_thresholds.json : final thresholds dict (drop into labels.py)
    - threshold_diagnostics.json : detailed per-class metrics
    - threshold_report.txt : human-readable summary table

Usage:
    # 1. Generate val_probs and val_true with predict_validation_set.py
    # 2. Run this script:
    python tune_thresholds.py

Requirements:
    pip install numpy scikit-learn
"""

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.metrics import (
    precision_recall_curve,
    fbeta_score,
    classification_report,
)


# =============================================================================
# Configuration
# =============================================================================

# Paths to your saved predictions and ground truth
VAL_PROBS_PATH = "val_probs.npy"   # shape: (n_chunks, n_classes), sigmoid outputs
VAL_TRUE_PATH = "val_true.npy"     # shape: (n_chunks, n_classes), binary labels

# Output paths
OUTPUT_THRESHOLDS = "technique_thresholds.json"
OUTPUT_DIAGNOSTICS = "threshold_diagnostics.json"
OUTPUT_REPORT = "threshold_report.txt"

# Tuning strategy
MIN_PRECISION_TARGET = 0.70  # require at least 70% precision per class
MIN_PRECISION_FALLBACK = 0.50  # if 0.70 not achievable, try 0.50
MIN_POSITIVES_TO_TUNE = 20   # below this, use safe default
SAFE_DEFAULT_THRESHOLD = 0.85  # for classes with too few positives or unreachable
MIN_RECALL_FOR_VALID = 0.05   # threshold valid only if recall > 5%

# Match your training setup
TECHNIQUE_LABELS = [
    "Loaded_Language",
    "Appeal_to_fear_prejudice",
    "Exaggeration_Minimization",
    "Repetition",
    "Flag_Waving",
    "Name_Calling_Labeling",
    "Reductio_ad_hitlerum",
    "Black_and_White_Fallacy",
    "Causal_Oversimplification",
    "Whataboutism_Straw_Men_Red_Herring",
    "Straw_Man",
    "Red_Herring",
    "Doubt",
    "Appeal_to_Authority",
    "Thought_terminating_Cliches",
    "Bandwagon",
    "Slogans",
    "Obfuscation_Intentional_Vagueness_Confusion",
]


# =============================================================================
# Setup
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Threshold tuning functions
# =============================================================================


def find_threshold_with_precision_floor(
    y_true: np.ndarray,
    y_probs: np.ndarray,
    min_precision: float = 0.70,
) -> tuple[float, float, float, bool]:
    """Find threshold meeting precision floor, maximizing recall among valid options.

    Args:
        y_true: binary ground truth, shape (n,)
        y_probs: predicted probabilities, shape (n,)
        min_precision: minimum precision required

    Returns:
        (threshold, precision_at_threshold, recall_at_threshold, achieved_floor)
        achieved_floor is True if min_precision was met, False if fallback applied.
    """
    if y_true.sum() == 0:
        return 0.95, 0.0, 0.0, False

    precisions, recalls, thresholds = precision_recall_curve(y_true, y_probs)

    # precision_recall_curve returns one extra precision/recall value
    # for the trivial "no threshold" case. Drop it.
    precisions = precisions[:-1]
    recalls = recalls[:-1]

    if len(thresholds) == 0:
        return 0.95, 0.0, 0.0, False

    # Find indices where precision meets the floor
    valid_mask = precisions >= min_precision

    if not valid_mask.any():
        # No threshold reaches the precision floor at all
        return 0.95, 0.0, 0.0, False

    # Among valid thresholds, pick the one with highest recall
    valid_recalls = recalls[valid_mask]
    valid_precisions = precisions[valid_mask]
    valid_thresholds = thresholds[valid_mask]

    best_idx = int(np.argmax(valid_recalls))

    return (
        float(valid_thresholds[best_idx]),
        float(valid_precisions[best_idx]),
        float(valid_recalls[best_idx]),
        True,
    )


def find_threshold_fbeta(
    y_true: np.ndarray,
    y_probs: np.ndarray,
    beta: float = 0.5,
) -> tuple[float, float]:
    """Find threshold maximizing F-beta score. beta < 1 favors precision."""
    if y_true.sum() == 0:
        return 0.95, 0.0

    best_score = 0.0
    best_threshold = 0.5

    for t in np.arange(0.10, 0.95, 0.01):
        preds = (y_probs >= t).astype(int)
        if preds.sum() == 0:
            continue
        score = fbeta_score(y_true, preds, beta=beta, zero_division=0)
        if score > best_score:
            best_score = score
            best_threshold = float(t)

    return best_threshold, float(best_score)


def tune_class(
    y_true: np.ndarray,
    y_probs: np.ndarray,
    label: str,
) -> dict:
    """Tune threshold for a single class with smart fallback strategies."""
    n_positive = int(y_true.sum())

    # Strategy 0: skip rare classes
    if n_positive < MIN_POSITIVES_TO_TUNE:
        return {
            "label": label,
            "threshold": SAFE_DEFAULT_THRESHOLD,
            "approach": "default_too_few_positives",
            "n_positive": n_positive,
            "precision": None,
            "recall": None,
            "warning": f"Only {n_positive} positives in val set",
        }

    # Strategy 1: precision floor at target
    t, p, r, achieved = find_threshold_with_precision_floor(
        y_true, y_probs, min_precision=MIN_PRECISION_TARGET
    )

    if achieved and r >= MIN_RECALL_FOR_VALID:
        return {
            "label": label,
            "threshold": t,
            "approach": f"precision_floor_{MIN_PRECISION_TARGET}",
            "n_positive": n_positive,
            "precision": p,
            "recall": r,
        }

    # Strategy 2: precision floor at fallback
    t, p, r, achieved = find_threshold_with_precision_floor(
        y_true, y_probs, min_precision=MIN_PRECISION_FALLBACK
    )

    if achieved and r >= MIN_RECALL_FOR_VALID:
        return {
            "label": label,
            "threshold": t,
            "approach": f"precision_floor_{MIN_PRECISION_FALLBACK}_fallback",
            "n_positive": n_positive,
            "precision": p,
            "recall": r,
            "warning": f"Could not reach {MIN_PRECISION_TARGET} precision",
        }

    # Strategy 3: F0.5 (last resort)
    t, score = find_threshold_fbeta(y_true, y_probs, beta=0.5)

    # Verify it actually predicts something
    preds = (y_probs >= t).astype(int)
    if preds.sum() == 0:
        return {
            "label": label,
            "threshold": SAFE_DEFAULT_THRESHOLD,
            "approach": "default_no_valid_threshold",
            "n_positive": n_positive,
            "precision": None,
            "recall": None,
            "warning": "Even F0.5 produces no predictions; class likely unlearnable",
        }

    # Compute actual precision/recall at this threshold
    tp = ((preds == 1) & (y_true == 1)).sum()
    fp = ((preds == 1) & (y_true == 0)).sum()
    fn = ((preds == 0) & (y_true == 1)).sum()
    precision_at_t = tp / max(tp + fp, 1)
    recall_at_t = tp / max(tp + fn, 1)

    return {
        "label": label,
        "threshold": t,
        "approach": "fbeta_0.5_last_resort",
        "n_positive": n_positive,
        "precision": float(precision_at_t),
        "recall": float(recall_at_t),
        "warning": "Class is hard to detect reliably; consider excluding from UI",
    }


# =============================================================================
# Reporting
# =============================================================================


def build_report(diagnostics: list[dict]) -> str:
    """Pretty-print diagnostics as a text report."""
    lines = []
    lines.append("=" * 100)
    lines.append("Politerate Threshold Tuning Report")
    lines.append("=" * 100)
    lines.append("")
    lines.append(f"Strategy: precision floor at {MIN_PRECISION_TARGET}, "
                 f"fallback at {MIN_PRECISION_FALLBACK}")
    lines.append(f"Minimum positives to tune: {MIN_POSITIVES_TO_TUNE}")
    lines.append(f"Safe default for unlearnable classes: {SAFE_DEFAULT_THRESHOLD}")
    lines.append("")
    lines.append("-" * 100)

    header = f"{'Technique':<40} {'N_pos':>8} {'Threshold':>10} {'Precision':>10} {'Recall':>10}  Approach"
    lines.append(header)
    lines.append("-" * 100)

    # Sort by quality (best precision/recall first)
    def sort_key(d):
        if d.get("precision") is None:
            return (0, 0)
        return (d["precision"] or 0, d["recall"] or 0)

    sorted_diags = sorted(diagnostics, key=sort_key, reverse=True)

    for d in sorted_diags:
        label = d["label"][:39]
        n_pos = d["n_positive"]
        threshold = d["threshold"]

        if d["precision"] is not None:
            p_str = f"{d['precision']:>10.1%}"
            r_str = f"{d['recall']:>10.1%}"
        else:
            p_str = f"{'N/A':>10}"
            r_str = f"{'N/A':>10}"

        approach = d["approach"]

        lines.append(
            f"{label:<40} {n_pos:>8} {threshold:>10.3f} {p_str} {r_str}  {approach}"
        )

        if "warning" in d:
            lines.append(f"  ⚠  {d['warning']}")

    lines.append("-" * 100)
    lines.append("")

    # Summary
    n_tuned = sum(1 for d in diagnostics
                  if d["approach"].startswith("precision_floor"))
    n_fallback = sum(1 for d in diagnostics
                    if "fallback" in d["approach"]
                    or d["approach"] == "fbeta_0.5_last_resort")
    n_default = sum(1 for d in diagnostics
                   if d["approach"].startswith("default"))

    lines.append("Summary:")
    lines.append(f"  Cleanly tuned:   {n_tuned}/{len(diagnostics)} classes")
    lines.append(f"  Fallback used:   {n_fallback}/{len(diagnostics)} classes")
    lines.append(f"  Safe default:    {n_default}/{len(diagnostics)} classes")
    lines.append("")

    if n_default > 0:
        lines.append("Classes using safe defaults are unlikely to fire in production.")
        lines.append("Consider excluding them from the UI rather than showing 'no detection'.")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# Sanity checks on tuned thresholds
# =============================================================================


def evaluate_with_thresholds(
    val_probs: np.ndarray,
    val_true: np.ndarray,
    thresholds_dict: dict[str, float],
    technique_labels: list[str],
) -> dict:
    """Apply tuned thresholds and compute aggregate metrics."""
    threshold_array = np.array([thresholds_dict[label] for label in technique_labels])
    predictions = (val_probs >= threshold_array).astype(int)

    # Predictions per chunk distribution
    preds_per_chunk = predictions.sum(axis=1)

    # Per-class breakdown
    class_metrics = {}
    for i, label in enumerate(technique_labels):
        y_true_i = val_true[:, i]
        y_pred_i = predictions[:, i]

        tp = int(((y_pred_i == 1) & (y_true_i == 1)).sum())
        fp = int(((y_pred_i == 1) & (y_true_i == 0)).sum())
        fn = int(((y_pred_i == 0) & (y_true_i == 1)).sum())
        tn = int(((y_pred_i == 0) & (y_true_i == 0)).sum())

        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-10)

        class_metrics[label] = {
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
        }

    return {
        "preds_per_chunk_mean": float(preds_per_chunk.mean()),
        "preds_per_chunk_median": float(np.median(preds_per_chunk)),
        "preds_per_chunk_max": int(preds_per_chunk.max()),
        "chunks_with_no_preds": int((preds_per_chunk == 0).sum()),
        "chunks_with_preds": int((preds_per_chunk > 0).sum()),
        "total_chunks": len(preds_per_chunk),
        "class_metrics": class_metrics,
    }


# =============================================================================
# Main
# =============================================================================


def main():
    logger.info("Loading validation predictions and labels...")

    val_probs_path = Path(VAL_PROBS_PATH)
    val_true_path = Path(VAL_TRUE_PATH)

    if not val_probs_path.exists():
        logger.error(f"Predictions file not found: {val_probs_path}")
        logger.error("Generate it first by running model inference on validation set.")
        logger.error("Save the sigmoid outputs as .npy file with shape (n_chunks, 18)")
        return

    if not val_true_path.exists():
        logger.error(f"True labels file not found: {val_true_path}")
        return

    val_probs = np.load(val_probs_path)
    val_true = np.load(val_true_path)

    logger.info(f"Loaded {len(val_probs)} chunks with {val_probs.shape[1]} classes")
    logger.info(f"Class label count: {len(TECHNIQUE_LABELS)}")

    if val_probs.shape[1] != len(TECHNIQUE_LABELS):
        logger.error(
            f"Shape mismatch: predictions have {val_probs.shape[1]} columns "
            f"but TECHNIQUE_LABELS has {len(TECHNIQUE_LABELS)} entries"
        )
        return

    logger.info(f"Strategy: precision floor at {MIN_PRECISION_TARGET}")
    logger.info("Tuning per-class thresholds...")

    diagnostics = []
    thresholds = {}

    for i, label in enumerate(TECHNIQUE_LABELS):
        diag = tune_class(val_true[:, i], val_probs[:, i], label)
        diagnostics.append(diag)
        thresholds[label] = diag["threshold"]

    # Save thresholds dict
    with open(OUTPUT_THRESHOLDS, "w") as f:
        json.dump(thresholds, f, indent=2)
    logger.info(f"Saved thresholds to {OUTPUT_THRESHOLDS}")

    # Save diagnostics
    with open(OUTPUT_DIAGNOSTICS, "w") as f:
        json.dump(diagnostics, f, indent=2)
    logger.info(f"Saved diagnostics to {OUTPUT_DIAGNOSTICS}")

    # Generate human-readable report
    report = build_report(diagnostics)
    with open(OUTPUT_REPORT, "w") as f:
        f.write(report)
    logger.info(f"Saved report to {OUTPUT_REPORT}")

    # Print report to console
    print()
    print(report)

    # Sanity check
    logger.info("Running sanity check on tuned thresholds...")
    sanity = evaluate_with_thresholds(val_probs, val_true, thresholds, TECHNIQUE_LABELS)

    print("\n" + "=" * 60)
    print("Sanity Check on Validation Set")
    print("=" * 60)
    print(f"Mean predictions per chunk:     {sanity['preds_per_chunk_mean']:.2f}")
    print(f"Median predictions per chunk:   {sanity['preds_per_chunk_median']:.2f}")
    print(f"Max predictions on any chunk:   {sanity['preds_per_chunk_max']}")
    print(f"Chunks with no detections:      {sanity['chunks_with_no_preds']} ({sanity['chunks_with_no_preds']/sanity['total_chunks']:.1%})")
    print(f"Chunks with detections:         {sanity['chunks_with_preds']} ({sanity['chunks_with_preds']/sanity['total_chunks']:.1%})")
    print()

    if sanity['preds_per_chunk_mean'] > 3:
        print("⚠  Mean predictions per chunk is high (>3).")
        print("   Consider raising MIN_PRECISION_TARGET to 0.75 or 0.80.")
        print()

    if sanity['chunks_with_no_preds'] / sanity['total_chunks'] > 0.7:
        print("⚠  Most chunks have zero detections (>70%).")
        print("   Thresholds may be too strict, or model has weak signal on this validation set.")
        print()

    print("Done. To use these thresholds in your app:")
    print(f"  1. Copy contents of {OUTPUT_THRESHOLDS} into TECHNIQUE_THRESHOLDS in labels.py")
    print(f"  2. Restart your service: sudo systemctl restart politerate")
    print(f"  3. Test on a few real articles to verify behavior")


if __name__ == "__main__":
    main()