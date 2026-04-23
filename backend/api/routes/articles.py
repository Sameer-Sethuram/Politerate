# backend/api/routes/articles.py

from fastapi import APIRouter, Depends, Query
from ..db.connection import get_db
import json

router = APIRouter(prefix="/articles")


@router.get("/")
async def list_articles(
    source: str | None = Query(None),
    bias: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db=Depends(get_db),
):
    query = "SELECT id, url, title, source, published_at, bias_label, dominant_emotion FROM articles WHERE analysis_status = 'done'"
    params = []
    
    if source:
        query += " AND source = ?"
        params.append(source)
    if bias:
        query += " AND bias_label = ?"
        params.append(bias)
    
    query += " ORDER BY published_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    rows = db.execute(query, params).fetchall()
    return [dict(row) for row in rows]


@router.get("/{article_id}")
async def get_article(article_id: int, db=Depends(get_db)):
    row = db.execute(
        "SELECT * FROM articles WHERE id = ?", (article_id,)
    ).fetchone()
    
    if not row:
        return {"error": "Not found"}
    
    article = dict(row)
    article["chunks"] = json.loads(article["analysis_json"]) if article["analysis_json"] else []
    article["article"] = json.loads(article["article_json"]) if article["article_json"] else {}
    return article