"""
FastAPI API server — existing endpoints from llm_eval_agent,
adapted for the new package structure.
"""

import json
import shutil
import uuid
from pathlib import Path
import os

from fastapi import APIRouter, BackgroundTasks, Body, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.agent import LLMEvalAgent

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RESULTS_ROOT = Path(os.environ.get("RESULTS_DIR", str(BASE_DIR / "results")))
LOGS_DIR = BASE_DIR / "logs"
CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", str(BASE_DIR / "config" / "config.yaml")))
LATEST_DATA_PTR = DATA_DIR / "_latest.txt"

DATA_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

RUN_STATUS: dict = {}


def _safe_resolve(base: Path, relative: str) -> Path:
    p = (base / relative).resolve()
    if not str(p).startswith(str(base.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    return p


def _run_agent(run_id: str, data_file: str | None = None):
    run_dir = RESULTS_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    RUN_STATUS[run_id] = {"status": "running"}
    try:
        agent = LLMEvalAgent(config_path=str(CONFIG_PATH), results_dir=str(run_dir), data_file_override=data_file)
        agent.run_tests()
        RUN_STATUS[run_id]["status"] = "completed"
    except Exception as e:
        RUN_STATUS[run_id] = {"status": "failed", "error": str(e)}


@router.post("/run-tests")
def run_tests(background_tasks: BackgroundTasks):
    run_id = uuid.uuid4().hex[:12]
    data_file = LATEST_DATA_PTR.read_text(encoding="utf-8").strip() if LATEST_DATA_PTR.exists() else None
    background_tasks.add_task(_run_agent, run_id, data_file)
    return {"status": "started", "run_id": run_id, "data_file": data_file}


@router.get("/runs")
def list_runs():
    runs = []
    for run_dir in RESULTS_ROOT.iterdir():
        if run_dir.is_dir():
            status = RUN_STATUS.get(run_dir.name, {}).get("status", "unknown")
            runs.append({"run_id": run_dir.name, "status": status})
    return {"runs": runs}


@router.get("/status/{run_id}")
def get_status(run_id: str):
    return RUN_STATUS.get(run_id, {"status": "unknown"})


@router.get("/results/{run_id}")
def list_results_for_run(run_id: str):
    run_dir = _safe_resolve(RESULTS_ROOT, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    files = [str(p.relative_to(run_dir)) for p in run_dir.rglob("*") if p.is_file()]
    return {"run_id": run_id, "files": files}


@router.get("/results/{run_id}/{filepath:path}")
def get_result_file(run_id: str, filepath: str):
    run_dir = _safe_resolve(RESULTS_ROOT, run_id)
    requested = _safe_resolve(run_dir, filepath)
    if not requested.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=str(requested), filename=requested.name)


@router.post("/upload-data")
def upload_data(file: UploadFile = File(...)):
    dest = _safe_resolve(DATA_DIR, file.filename)
    with dest.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)
    LATEST_DATA_PTR.write_text(str(dest), encoding="utf-8")
    return {"status": "uploaded", "filename": file.filename, "saved_to": str(dest)}


@router.get("/logs/{run_id}")
def get_logs(run_id: str):
    log_file = LOGS_DIR / f"{run_id}.log"
    if not log_file.exists():
        return {"run_id": run_id, "log": "No log file found."}
    return {"run_id": run_id, "log": log_file.read_text(encoding="utf-8")}


@router.get("/trend")
def get_trend(last: int = 0):
    """Return audit log entries as JSON trend data."""
    log_path = BASE_DIR / "data" / "audit_log.jsonl"
    if not log_path.exists():
        return {"entries": [], "message": "No eval runs recorded yet."}
    entries = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    entries.sort(key=lambda e: e.get("timestamp", ""))
    if last:
        entries = entries[-last:]
    return {"entries": entries, "count": len(entries)}


@router.delete("/runs/{run_id}")
def delete_run(run_id: str):
    run_dir = _safe_resolve(RESULTS_ROOT, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    shutil.rmtree(run_dir)
    RUN_STATUS.pop(run_id, None)
    return {"status": "deleted", "run_id": run_id}
