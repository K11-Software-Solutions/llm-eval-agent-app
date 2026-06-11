import json
import csv
import yaml
import logging
from typing import Any, Dict, List

def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_data(path: str, fmt: str = "jsonl") -> List[Dict[str, Any]]:
    if fmt == "jsonl":
        with open(path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f]
    elif fmt == "csv":
        with open(path, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    raise ValueError(f"Unsupported data format: {fmt}")

def save_report(report: Any, path: str, fmt: str = "txt"):
    if fmt == "txt":
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(report))
    elif fmt == "json":
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    else:
        raise ValueError(f"Unsupported report format: {fmt}")

def setup_logging(logfile: str = None):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        filename=logfile,
        filemode="a" if logfile else None,
    )
