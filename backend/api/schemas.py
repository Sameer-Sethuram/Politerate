"""Pydantic schemas for API request/response validation."""

from pydantic import BaseModel, Field
from typing import Optional


# === Request schemas ===

class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=50, max_length=50000)
    url: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None


# === Response schemas ===

class TechniqueDetection(BaseModel):
    label: str
    confidence: float


class ChunkAnalysis(BaseModel):
    text: str
    techniques: list[TechniqueDetection]
    emotion: str
    subjective: bool
    bias: str


class ArticleLevelAnalysis(BaseModel):
    dominant_bias: Optional[str] = None
    dominant_emotion: Optional[str] = None
    subjectivity_ratio: float
    technique_counts: dict[str, int]


class AnalyzeResponse(BaseModel):
    chunks: list[ChunkAnalysis]
    article: ArticleLevelAnalysis
    cached: bool = False
    model_version: Optional[str] = None


# === Health ===

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_version: Optional[str] = None