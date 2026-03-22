# Politerate

**Making political news accessible through multi-source summarization and transparent term explanations.**

## Overview

Politerate addresses the challenge of staying informed about political news in an era of declining media trust, misinformation, and information fatigue. Our platform combines multiple sources across the political spectrum, summarizes key stories into digestible briefings, and explains political jargon with full source transparency.

## The Problem

- **Declining trust in media** - People are increasingly skeptical of news stations and unsure which sources to trust
- **Misinformation** - Facts and truth are often misrepresented to persuade readers toward particular viewpoints
- **Information fatigue** - News is boring and hard to keep up with. People don't like long reads or deciding which source to read

## Our Approach

Politerate combines sources from many different viewpoints of the political spectrum and summarizes them into a few short paragraphs based on the most relevant information present across all articles. We make information digestible and easy to interpret, simplifying the political landscape so relevant information doesn't get lost within all the nuances of the spectrum.

## Features

### Daily Brief View
Get a unified summary of all major political news in one comprehensive briefing. Topics are automatically connected with smooth transitions, giving you a complete picture of what's happening today.

### Topic Clusters View
Dive deeper into specific topics with individual summaries. Each cluster groups related articles together, showing multiple perspectives on the same story.

### Political Glossary
Learn political jargon with clear, accessible definitions. Each term includes links to the articles where it was used, providing full transparency about where our definitions are applied.

### Source Credibility
Understand source reliability at a glance. Each source is evaluated and displays a credibility indicator.

## How It Works

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Scrape    │ ──▶ │  Preprocess  │ ──▶ │   Cluster   │
│   Articles  │     │     Text     │     │    Topics   │
└─────────────┘     └──────────────┘     └─────────────┘
                                                │
                                                ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Highlight │ ◀── │   Summarize  │ ◀── │   Filter    │
│    Terms    │     │    (BART)    │     │ Credibility │
└─────────────┘     └──────────────┘     └─────────────┘
```

1. **Scrape** - Articles are collected from trusted RSS feeds
2. **Preprocess** - Text is cleaned and normalized
3. **Filter** - Credibility analysis flags low-quality sources
4. **Cluster** - Articles are grouped by topic using semantic embeddings
5. **Summarize** - Fine-tuned BART transformer generates natural summaries
6. **Highlight** - Political terms are detected and explained with tooltip definitions

## Technical Stack

- **Summarization**: Fine-tuned BART-large transformer model
- **Clustering**: Sentence Transformers (all-MiniLM-L6-v2) + Agglomerative Clustering
- **Credibility Analysis**: DeBERTa-v3 (in development by Sarah)
- **Backend**: Flask + SQLite
- **Frontend**: Vanilla JavaScript + HTML/CSS

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/Politerate.git
cd Politerate

# Install dependencies
pip install -r requirements.txt

# Run the web application
python webapp.py
```

## Project Structure

```
Politerate/
├── clustering.py         # Article topic clustering using embeddings
├── credibility.py         # Credibility checking interface
├── credibility_impl.py   # Sarah's DeBERTa-v3 implementation (in progress)
├── glossary.json         # Political terms and definitions
├── PAR Stuff.txt         # Project planning notes
├── pipeline.py           # Main processing pipeline
├── politerate.py         # Political term highlighter
├── preprocessor.py       # Text preprocessing
├── requirements.txt      # Python dependencies
├── rss_link_scraper.py  # RSS feed parsing
├── webapp.py            # Flask web application
├── webscraper.py        # Article content extraction
├── cache.py             # SQLite caching
├── templates/
│   ├── index.html       # Daily news view
│   └── glossary.html    # Political glossary view
└── fine_tuned_bart_news/  # Fine-tuned summarization model
```

## Team

| Member | Responsibilities |
|--------|-----------------|
| **Sameer** | Transformer summarizer model, web application, pipeline architecture |
| **Sarah** | Sentiment analysis for bias detection, DeBERTa-v3 model for credibility scoring |

## Next Steps

- **Sarah**: Integrate DeBERTa-v3 for political bias detection using multi-head analysis for political lean and emotional/subjective content
- **Sameer**: Improve summarization quality, add more RSS sources, enhance the frontend

## License

MIT License - See LICENSE file for details

---

*Making political news accessible, one summary at a time.*
