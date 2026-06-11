import os
import re
import logging
from langtest import Harness
from app.utils import load_config, setup_logging

def _safe_name(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", s or "model")

REPORT_FORMAT_MAP = {
    "txt": "text", "text": "text",
    "xlsx": "excel", "excel": "excel",
    "html": "html",
    "md": "markdown", "markdown": "markdown",
    "json": "dict", "dict": "dict",
}

class LLMEvalAgent:
    def __init__(self, config_path="config/config.yaml", results_dir=None, data_file_override=None):
        self.config = load_config(config_path)
        self.models = self.config.get("models", [])
        self.data_file = data_file_override or self.config.get("data", {}).get("file")
        self.categories = self.config.get("categories", ["bias", "fairness", "robustness"])
        self.thresholds = self.config.get("thresholds", {})
        self.report_formats = self.config.get("report", {}).get("format", ["text"])
        self.results_dir = results_dir or self.config.get("report", {}).get("dir", "results")
        os.makedirs(self.results_dir, exist_ok=True)
        setup_logging()
        if not self.data_file or not os.path.exists(self.data_file):
            raise FileNotFoundError(f"Data file not found: {self.data_file}")

    def _build_tests_config(self) -> dict:
        defaults = {"min_pass_rate": float(self.thresholds.get("min_pass_rate", 0.0))}
        tests = {"defaults": defaults}
        if "bias" in self.categories:
            tests["bias"] = {"replace_to_female_pronouns": {"min_pass_rate": float(self.thresholds.get("bias_min_pass_rate", defaults["min_pass_rate"]))}}
        if "fairness" in self.categories:
            tests["fairness"] = {"min_gender_f1_score": {"min_score": float(self.thresholds.get("min_gender_f1_score", 0.0))}}
        if "robustness" in self.categories:
            tests["robustness"] = {"add_typo": {"min_pass_rate": float(self.thresholds.get("robustness_min_pass_rate", defaults["min_pass_rate"]))}}
        return {"tests": tests}

    def run_tests(self):
        for model_cfg in self.models:
            model_name = model_cfg.get("name")
            hub = model_cfg.get("hub")
            task = model_cfg.get("type", "text-classification")
            model_out_dir = os.path.join(self.results_dir, _safe_name(model_name))
            os.makedirs(model_out_dir, exist_ok=True)
            h = Harness(task=task, model={"model": model_name, "hub": hub}, data={"data_source": self.data_file})
            h.configure(self._build_tests_config())
            h.generate().run()
            for raw_fmt in self.report_formats:
                fmt = REPORT_FORMAT_MAP.get(str(raw_fmt).lower())
                if not fmt:
                    logging.warning(f"Skipping unsupported format: {raw_fmt}")
                    continue
                ext = {"text": "txt", "excel": "xlsx", "html": "html", "markdown": "md", "dict": "json"}[fmt]
                report_path = os.path.join(model_out_dir, f"langtest_report.{ext}")
                h.report(format=fmt, save_dir=report_path)
                logging.info(f"Saved report: {report_path}")

if __name__ == "__main__":
    agent = LLMEvalAgent()
    agent.run_tests()
