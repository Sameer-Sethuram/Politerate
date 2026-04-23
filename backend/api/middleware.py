"""Logging and error handling middleware for FastAPI."""

import time
import logging
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("politerate")


async def log_requests(request: Request, call_next):
    """Log every request with timing."""
    start = time.time()
    
    try:
        response = await call_next(request)
        elapsed = time.time() - start
        
        logger.info(
            f"{request.method} {request.url.path} "
            f"→ {response.status_code} ({elapsed:.2f}s)"
        )
        
        return response
    
    except Exception as e:
        elapsed = time.time() - start
        logger.exception(
            f"{request.method} {request.url.path} "
            f"→ ERROR ({elapsed:.2f}s): {e}"
        )
        
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )


def setup_logging(log_level: str = "INFO"):
    """Configure root logger."""
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )