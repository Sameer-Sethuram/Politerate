# backend/test_load.py
# Verify the model loads correctly before wiring into FastAPI

import sys
sys.path.insert(0, '.')

from inference.predictor import PoliterateAnalyzer

print("Loading predictor...")
predictor = PoliterateAnalyzer(
    weights_path="models/analyzer.pt",
    device="cpu",
)
print("Loaded successfully.")

# Test with a sample article
test_text = """
The president's disastrous new policy is a complete catastrophe for working families. 
This reckless decision will destroy the economy and hurt millions of hardworking Americans.
Meanwhile, the opposition stands strong in their principled resistance.
"""

print("\nRunning test prediction...")
result = predictor.predict_article(test_text)

print(f"\nArticle-level analysis:")
print(f"  Dominant bias: {result['article']['dominant_bias']}")
print(f"  Dominant emotion: {result['article']['dominant_emotion']}")
print(f"  Subjectivity ratio: {result['article']['subjectivity_ratio']:.2f}")
print(f"  Technique counts: {result['article']['technique_counts']}")

print(f"\nPer-chunk analysis:")
for i, chunk in enumerate(result['chunks']):
    print(f"\nChunk {i}: {chunk['text'][:80]}...")
    print(f"  Emotion: {chunk['emotion']}")
    print(f"  Subjective: {chunk['subjective']}")
    print(f"  Techniques: {[t['label'] for t in chunk['techniques']]}")