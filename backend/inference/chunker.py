# backend/inference/chunker.py

import re
import spacy


class ArticleChunker:
    """
    Splits article text into chunks suitable for model inference.
    Must produce the same chunks as training did, to ensure consistency.
    """
    
    def __init__(
        self,
        min_chunk_len: int = 20,
        max_chunk_len: int = 512,
    ):
        self.nlp = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer"])
        self.min_chunk_len = min_chunk_len
        self.max_chunk_len = max_chunk_len
        
    
    def is_boilerplate(self, sent):
        """Filter out common news article junk."""
        patterns = [
            r"^(Getty Images|AP Photo|Reuters|Copyright|All rights reserved)",
            r"^(Share this|Follow us|Subscribe|Sign up)",
            r"^(Loading|Advertisement|ADVERTISEMENT)",
            r"^\s*\(Reuters\)\s*[-\u2013\u2014]?\s*$",
            r"^(Read more|Related:|See also|WATCH:)",
            r"^[A-Z]{2,}\s*[-\u2013\u2014]",  # datelines like "WASHINGTON —"
        ]
        for p in patterns:
            if re.match(p, sent, re.IGNORECASE):
                return True
        if len(sent.split()) < 4 and sent.rstrip(".").endswith(("said", "reports")):
            return True
        return False


    def split_long_sentence(self, sent, max_len):
        """Split on clause boundaries: em-dashes, semicolons, or coordinating conjunctions."""
        parts = re.split(
            r'\s*[;\u2013\u2014]\s*|\s*,\s+(?:but|and|or|yet|so|because|while)\s+', sent
        )
        if all(len(p) <= max_len for p in parts) and len(parts) > 1:
            return [p.strip() for p in parts if p.strip()]

        # Fallback: split on commas
        parts = sent.split(",")
        chunks = []
        current = ""
        for part in parts:
            candidate = f"{current}, {part}".strip(", ") if current else part.strip()
            if len(candidate) > max_len and current:
                chunks.append(current.strip())
                current = part.strip()
            else:
                current = candidate
        if current:
            chunks.append(current.strip())
        return chunks


    def chunk_article(self, article_text):
        """Break an article into sentence-level chunks with merging and splitting logic."""
        doc = self.nlp(article_text)
        raw_sents = [sent.text.strip() for sent in doc.sents if sent.text.strip()]

        chunks = []
        buffer = ""

        for sent in raw_sents:
            if self.is_boilerplate(sent):
                continue

            if len(sent) < self.min_chunk_len:
                buffer = f"{buffer} {sent}".strip() if buffer else sent
                continue

            if buffer:
                sent = f"{buffer} {sent}"
                buffer = ""

            if len(sent) > self.max_chunk_len:
                sub_chunks = self.split_long_sentence(sent, self.max_chunk_len)
                chunks.extend(sub_chunks)
            else:
                chunks.append(sent)

        if buffer:
            if chunks:
                chunks[-1] = f"{chunks[-1]} {buffer}"
            else:
                chunks.append(buffer)

        return chunks