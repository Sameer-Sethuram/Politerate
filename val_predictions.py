"""
generate_val_predictions.py

Runs the trained Politerate model over the validation set and saves
the raw sigmoid scores + true labels as .npy files for threshold tuning.

Usage:
    python generate_val_predictions.py

Outputs:
    - val_probs.npy : shape (n_chunks, 18), sigmoid scores per technique
    - val_true.npy  : shape (n_chunks, 18), binary ground-truth labels

Then run tune_thresholds.py to produce technique_thresholds.json.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

# Adjust these imports to match your project structure
from backend.inference.model import MultiHeadDeBERTa
from backend.inference.labels import TECHNIQUE_LABELS, NUM_TECHNIQUE
from transformers import AutoTokenizer


# =============================================================================
# Configuration
# =============================================================================

MODEL_WEIGHTS_PATH = "backend/models/analyzer.pt"
BACKBONE_NAME = "microsoft/deberta-v3-base"

# Path to your validation set with gold labels
# Should have columns: text, technique_labels (or similar)
VAL_CSV_PATH = "audit_set_with_gold_labels.csv"

# Filter to validation split if your CSV has both val and test
VAL_SPLIT_FILTER = "val"  # or None to use all rows

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
BATCH_SIZE = 32
MAX_LENGTH = 128

OUTPUT_PROBS = "val_probs.npy"
OUTPUT_TRUE = "val_true.npy"


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
# Load model
# =============================================================================


def load_model() -> tuple[MultiHeadDeBERTa, AutoTokenizer]:
    """Load model and tokenizer."""
    logger.info(f"Loading tokenizer: {BACKBONE_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(BACKBONE_NAME)

    logger.info(f"Loading model from {MODEL_WEIGHTS_PATH}")
    model = MultiHeadDeBERTa(
        backbone_name=BACKBONE_NAME,
        num_technique=NUM_TECHNIQUE,
        num_emotion=28,    # adjust if different
        num_subj=2,
        num_bias=3,
    )

    checkpoint = torch.load(MODEL_WEIGHTS_PATH, map_location=DEVICE)
    state_dict = checkpoint.get("model_state_dict", checkpoint)
    model.load_state_dict(state_dict, strict=False)

    model = model.to(DEVICE).float().eval()
    logger.info(f"Model loaded on {DEVICE}")

    return model, tokenizer


# =============================================================================
# Encode validation labels
# =============================================================================


def encode_techniques(label_string: str, label_list: list[str]) -> np.ndarray:
    """Convert a comma-separated label string into a multi-hot vector."""
    vec = np.zeros(len(label_list), dtype=np.int8)

    if not isinstance(label_string, str) or not label_string.strip():
        return vec

    labels_in_chunk = [l.strip() for l in label_string.split(",")]
    label_to_idx = {l: i for i, l in enumerate(label_list)}

    for label in labels_in_chunk:
        if label in label_to_idx:
            vec[label_to_idx[label]] = 1

    return vec


# =============================================================================
# Main inference loop
# =============================================================================


def main():
    # Load validation data
    logger.info(f"Loading validation set: {VAL_CSV_PATH}")
    val_path = Path(VAL_CSV_PATH)
    if not val_path.exists():
        logger.error(f"Validation CSV not found: {val_path}")
        logger.error("Adjust VAL_CSV_PATH to point at your gold-labeled val set")
        return

    df = pd.read_csv(val_path)
    logger.info(f"Loaded {len(df)} rows total")

    # Filter to validation split if applicable
    if VAL_SPLIT_FILTER and "split" in df.columns:
        df = df[df["split"] == VAL_SPLIT_FILTER].reset_index(drop=True)
        logger.info(f"Filtered to '{VAL_SPLIT_FILTER}' split: {len(df)} rows")

    # Detect text and label columns
    text_col = None
    for candidate in ["text", "chunk_text", "sentence", "content"]:
        if candidate in df.columns:
            text_col = candidate
            break

    if text_col is None:
        logger.error("Could not find a text column. Looked for: text, chunk_text, sentence, content")
        logger.error(f"Available columns: {list(df.columns)}")
        return

    label_col = None
    for candidate in ["technique_labels", "techniques", "labels", "gold_techniques"]:
        if candidate in df.columns:
            label_col = candidate
            break

    if label_col is None:
        logger.error("Could not find a labels column. Looked for: technique_labels, techniques, labels")
        logger.error(f"Available columns: {list(df.columns)}")
        return

    logger.info(f"Using text column: {text_col}, label column: {label_col}")

    # Drop rows with empty text
    df = df[df[text_col].notna() & (df[text_col].str.strip().str.len() > 0)].reset_index(drop=True)
    logger.info(f"Rows after filtering empty text: {len(df)}")

    # Encode labels
    logger.info("Encoding labels...")
    val_true = np.array([
        encode_techniques(label_str, TECHNIQUE_LABELS)
        for label_str in df[label_col].fillna("")
    ])
    logger.info(f"True labels shape: {val_true.shape}")
    logger.info(f"Total positive labels: {val_true.sum()}")
    logger.info(f"Per-class positive counts: {val_true.sum(axis=0).tolist()}")

    # Load model
    model, tokenizer = load_model()

    # Run inference in batches
    logger.info(f"Running inference (batch size {BATCH_SIZE})...")
    val_probs = np.zeros((len(df), NUM_TECHNIQUE), dtype=np.float32)

    texts = df[text_col].tolist()

    for batch_start in range(0, len(texts), BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, len(texts))
        batch_texts = texts[batch_start:batch_end]

        # Tokenize
        inputs = tokenizer(
            batch_texts,
            truncation=True,
            padding="max_length",
            max_length=MAX_LENGTH,
            return_tensors="pt",
        ).to(DEVICE)

        # Forward
        with torch.no_grad():
            outputs = model(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
                token_type_ids=inputs.get("token_type_ids"),
            )

        # Sigmoid for technique head (multi-label)
        tech_probs = torch.sigmoid(outputs["technique_logits"]).cpu().numpy()
        val_probs[batch_start:batch_end] = tech_probs

        if batch_start % (BATCH_SIZE * 20) == 0:
            logger.info(f"  Processed {batch_end}/{len(texts)}")

    logger.info("Inference complete")

    # Save outputs
    np.save(OUTPUT_PROBS, val_probs)
    np.save(OUTPUT_TRUE, val_true)
    logger.info(f"Saved probabilities to {OUTPUT_PROBS}")
    logger.info(f"Saved true labels to {OUTPUT_TRUE}")

    # Quick sanity check
    print()
    print(f"Saved files:")
    print(f"  {OUTPUT_PROBS}: shape {val_probs.shape}, range [{val_probs.min():.3f}, {val_probs.max():.3f}]")
    print(f"  {OUTPUT_TRUE}:  shape {val_true.shape}, total positives {val_true.sum()}")
    print()
    print(f"Now run: python tune_thresholds.py")


if __name__ == "__main__":
    main()