"""FastAPI application for Politerate."""

import json
import logging
from contextlib import asynccontextmanager
from hashlib import sha256

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

from ..config import (
    MODEL_WEIGHTS_PATH, DEVICE, MODEL_VERSION,
    CORS_ORIGINS, LOG_LEVEL,
)
from ..db.connection import init_db, get_connection
from ..inference.predictor import PoliterateAnalyzer
from .schemas import AnalyzeRequest, AnalyzeResponse, HealthResponse
from .middleware import log_requests, setup_logging


logger = logging.getLogger("politerate")
predictor = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialize DB and load model. Shutdown: cleanup."""
    global predictor
    
    setup_logging(LOG_LEVEL)
    logger.info("Starting Politerate API...")
    
    # Initialize database
    init_db()
    logger.info("Database ready.")
    
    # Load model
    logger.info(f"Loading model from {MODEL_WEIGHTS_PATH}...")
    predictor = PoliterateAnalyzer(
        weights_path=MODEL_WEIGHTS_PATH,
        device=DEVICE,
    )
    logger.info("Model loaded.")
    
    yield
    
    logger.info("Shutting down.")


app = FastAPI(
    title="Politerate API",
    version="0.1.0",
    lifespan=lifespan,
)

app.middleware("http")(log_requests)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Dependency: database connection ===

def get_db_dep():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


# === Endpoints ===

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        model_loaded=predictor is not None,
        model_version=MODEL_VERSION,
    )


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest, db=Depends(get_db_dep)):
    """Analyze an article, using cache if available."""
    
    # Step 1: Check cache if URL provided
    url_hash = None
    if req.url:
        url_hash = sha256(req.url.encode()).hexdigest()
        
        cached = db.execute("""
            SELECT analysis_json, article_json, analysis_model_version
            FROM articles
            WHERE url_hash = ? AND analysis_status = 'done'
        """, (url_hash,)).fetchone()
        
        if cached and cached["analysis_model_version"] == MODEL_VERSION:
            logger.info(f"Cache hit for url_hash={url_hash[:8]}...")
            return AnalyzeResponse(
                chunks=json.loads(cached["analysis_json"]),
                article=json.loads(cached["article_json"]),
                cached=True,
                model_version=cached["analysis_model_version"],
            )
    
    # Step 2: Run inference
    logger.info("Running inference...")
    try:
        result = predictor.predict_article(req.text)
    except Exception as e:
        logger.exception("Inference failed")
        raise HTTPException(500, "Analysis failed. Try again.")
    
    # Step 3: Save to cache if URL provided
    if req.url and url_hash:
        try:
            db.execute("""
                INSERT OR REPLACE INTO articles (
                    url, url_hash, title, source, content,
                    analysis_json, article_json,
                    bias_label, dominant_emotion, subjectivity_ratio,
                    analysis_model_version, analysis_status, analyzed_at,
                    source_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'done', CURRENT_TIMESTAMP, 'user_submitted')
            """, (
                req.url,
                url_hash,
                req.title,
                req.source,
                req.text,
                json.dumps(result["chunks"]),
                json.dumps(result["article"]),
                result["article"]["dominant_bias"],
                result["article"]["dominant_emotion"],
                result["article"]["subjectivity_ratio"],
                MODEL_VERSION,
            ))
            db.commit()
            logger.info(f"Cached analysis for url_hash={url_hash[:8]}...")
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")
            # Don't fail the request if caching fails
    
    return AnalyzeResponse(
        chunks=result["chunks"],
        article=result["article"],
        cached=False,
        model_version=MODEL_VERSION,
    )