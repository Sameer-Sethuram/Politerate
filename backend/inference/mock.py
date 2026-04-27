"""
Mock analyzer that produces realistic-looking PoliterateAnalyzer output
without loading a real model.

Used while Sarah's `analyzer.pt` weights are pending. Matches the exact
output shape of `PoliterateAnalyzer.predict_article()` so the `/analyzer`
UI can be built and tested end-to-end. Swap the import in
`credibility/__init__.py:get_analyzer()` once the real weights arrive.

Behavior is deterministic: the same input text always produces the same
output, so demos are repeatable.
"""

import hashlib
import re
from collections import Counter
from typing import Optional

from .labels import (
    TECHNIQUE_LABELS,
    EMOTION_LABELS,
    BIAS_DISPLAY_NAMES,
)


# Very loose keyword heuristics — not real ML, just something that produces
# plausible-looking chunk labels from the content so the UI doesn't look
# random during demo mode.

_BIAS_HINTS = {
    "left": [
        "progressive", "social justice", "climate crisis", "inequality",
        "workers' rights", "universal", "systemic", "green",
    ],
    "right": [
        "conservative", "border", "family values", "free market",
        "second amendment", "patriot", "radical left", "tax cuts",
    ],
    "center": [
        "bipartisan", "moderate", "compromise", "study", "data",
        "research", "according to",
    ],
}

_EMOTION_HINTS = {
    "anger":       ["outrage", "furious", "angry", "condemn", "attack"],
    "fear":        ["danger", "crisis", "threat", "catastroph", "scary"],
    "sadness":     ["tragic", "grief", "mourn", "heartbreak"],
    "joy":         ["victory", "celebrat", "welcome", "triumph"],
    "approval":    ["praised", "applaud", "endorse", "support"],
    "disapproval": ["disapprove", "reject", "slam", "criticize"],
    "optimism":    ["hope", "promising", "confident", "progress"],
    "confusion":   ["unclear", "unsure", "unknown", "uncertain"],
    "neutral":     [],
}

_TECHNIQUE_HINTS = {
    "Loaded_Language": ["radical", "extremist", "regime", "scheme", "devastating"],
    "Appeal_to_fear_prejudice": ["danger", "threat", "could destroy"],
    "Exaggeration_Minimization": ["unprecedented", "historic", "never before"],
    "Name_Calling_Labeling": ["called him a", "so-called", "labeled a"],
    "Doubt": ["questionable", "supposedly", "alleged"],
    # "according to" is AP-style attribution, not a persuasion technique
    "Appeal_to_Authority": ["experts say", "studies show", "scientists confirm"],
    "Bandwagon": ["everyone knows", "nobody disputes", "most people agree"],
    "Black_and_White_Fallacy": ["the only option", "no other choice", "either you"],
    "Flag_Waving": ["american values", "our nation", "patriot"],
    "Thought_terminating_Cliches": ["at the end of the day", "it is what it is"],
}


def _content_rng(seed_text: str) -> int:
    """Deterministic int seed from text content."""
    return int(hashlib.sha1(seed_text.encode("utf-8")).hexdigest()[:8], 16)


def _sentence_split(text: str) -> list[str]:
    """Simple sentence splitter — good enough for mock mode. Replace with
    spaCy-backed ArticleChunker in real mode."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    chunks = []
    buffer = ""
    for part in parts:
        if len(part) < 30:
            buffer = (buffer + " " + part).strip() if buffer else part
            continue
        if buffer:
            part = (buffer + " " + part).strip()
            buffer = ""
        chunks.append(part)
    if buffer:
        if chunks:
            chunks[-1] = chunks[-1] + " " + buffer
        else:
            chunks.append(buffer)
    return chunks


def _detect_from_hints(text_lower: str, hints_map: dict, max_hits: int = 3) -> list[str]:
    """Return labels whose hint-words appear in the text."""
    matched = []
    for label, hints in hints_map.items():
        for hint in hints:
            if hint in text_lower:
                matched.append(label)
                break
        if len(matched) >= max_hits:
            break
    return matched


def _analyze_chunk(chunk: str, seed_offset: int) -> dict:
    text_lower = chunk.lower()
    rng_seed = _content_rng(chunk + str(seed_offset))

    # Techniques (multi-label): hint-based + small deterministic noise
    techniques = []
    for label in _detect_from_hints(text_lower, _TECHNIQUE_HINTS, max_hits=4):
        # Confidence varies a bit per-label based on seed
        confidence = 0.45 + ((rng_seed + hash(label)) % 45) / 100
        techniques.append({
            "label": label,
            "confidence": round(confidence, 3),
        })

    # Emotion (single-label): first hint match, else neutral
    emotion_matches = _detect_from_hints(text_lower, _EMOTION_HINTS, max_hits=1)
    emotion = emotion_matches[0] if emotion_matches else "neutral"

    # Bias (single-label): first hint match, else center
    bias_key = "center"
    for key in ("left", "right", "center"):
        if any(hint in text_lower for hint in _BIAS_HINTS[key]):
            bias_key = key
            break

    # Subjectivity: chunk is "subjective" if it has any technique match OR
    # non-neutral emotion (quick heuristic for demo)
    subjective = bool(techniques) or emotion != "neutral"

    return {
        "text": chunk,
        "techniques": techniques,
        "emotion": emotion,
        "subjective": subjective,
        "bias": bias_key,
    }


class MockAnalyzer:
    """
    Drop-in replacement for PoliterateAnalyzer that returns realistic-looking
    output without loading a real model. Swap out via
    credibility/__init__.py once Sarah's weights are in place.
    """

    model_version = "mock-v1"

    def predict_article(self, text: str) -> dict:
        chunks = _sentence_split(text)
        if not chunks:
            return {
                "chunks": [],
                "article": {
                    "dominant_bias": None,
                    "dominant_emotion": None,
                    "subjectivity_ratio": 0.0,
                    "technique_counts": {},
                },
            }

        chunk_predictions = [_analyze_chunk(c, i) for i, c in enumerate(chunks)]

        all_techniques = [t["label"] for c in chunk_predictions for t in c["techniques"]]
        all_emotions = [c["emotion"] for c in chunk_predictions]
        subj_count = sum(1 for c in chunk_predictions if c["subjective"])
        all_biases = [c["bias"] for c in chunk_predictions]

        return {
            "chunks": chunk_predictions,
            "article": {
                "dominant_bias": Counter(all_biases).most_common(1)[0][0] if all_biases else None,
                "dominant_emotion": Counter(all_emotions).most_common(1)[0][0] if all_emotions else None,
                "subjectivity_ratio": round(subj_count / len(chunk_predictions), 3),
                "technique_counts": dict(Counter(all_techniques)),
            },
        }
