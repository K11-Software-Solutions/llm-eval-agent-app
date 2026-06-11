"""
LLM Eval Agent — GitHub App
Entry point: FastAPI server with API routes + GitHub webhook receiver.
Run: uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from app.api_server import router as api_router
from app.webhook import router as webhook_router

app = FastAPI(
    title="LLM Eval Agent",
    description="GitHub App for automated LLM safety & quality evaluation on every PR",
    version="1.0.0",
)

# Existing API routes (/run-tests, /status, /results, /runs, /upload-data, /logs)
app.include_router(api_router)

# GitHub webhook endpoint (/github/webhook)
app.include_router(webhook_router, prefix="/github")


@app.get("/health")
def health():
    return {"status": "ok"}
