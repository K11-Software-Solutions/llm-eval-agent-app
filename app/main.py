"""
LLM Eval Agent — GitHub App
Entry point: FastAPI server with API routes + GitHub webhook receiver.
Run: uvicorn app.main:app --reload
"""

import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.api_server import router as api_router
from app.webhook import router as webhook_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="LLM Eval Agent",
    description="GitHub App for automated LLM safety & quality evaluation on every PR",
    version="1.0.0",
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})

# Existing API routes (/run-tests, /status, /results, /runs, /upload-data, /logs)
app.include_router(api_router)

# GitHub webhook endpoint (/github/webhook)
app.include_router(webhook_router, prefix="/github")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/debug/env")
def debug_env():
    """Show which critical env vars are configured (values masked)."""
    raw_key = os.environ.get("GITHUB_PRIVATE_KEY", "")
    return {
        "GITHUB_APP_ID":         os.environ.get("GITHUB_APP_ID", "MISSING"),
        "GITHUB_PRIVATE_KEY":    "set" if raw_key else "MISSING",
        "GITHUB_WEBHOOK_SECRET": "set" if os.environ.get("GITHUB_WEBHOOK_SECRET") else "MISSING",
        "key_length":            len(raw_key),
        "key_has_real_newlines": "\n" in raw_key,
        "key_has_escaped_n":     "\\n" in raw_key,
        "key_first_40":          raw_key[:40].replace("\n", "<NL>"),
        "key_has_begin":         "BEGIN" in raw_key,
    }
