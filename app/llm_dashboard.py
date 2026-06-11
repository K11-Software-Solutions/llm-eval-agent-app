import streamlit as st
import requests
import os

API_URL = os.environ.get("LLM_API_URL", "http://localhost:8000")

st.set_page_config(page_title="LLM Eval Agent", page_icon="🧪", layout="wide")
st.title("🧪 LLM Eval Agent — Dashboard")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Upload Test Data")
    data_file = st.file_uploader("Upload test data (CSV or JSONL)", type=["csv", "jsonl"])
    if st.button("Upload Data") and data_file:
        files = {"file": (data_file.name, data_file, "text/csv")}
        resp = requests.post(f"{API_URL}/upload-data", files=files)
        st.success(f"Uploaded: {data_file.name}") if resp.ok else st.error(resp.text)

with col2:
    st.subheader("Start Eval Run")
    if st.button("▶ Start Test Run"):
        resp = requests.post(f"{API_URL}/run-tests")
        if resp.ok:
            st.success(f"Run started: `{resp.json().get('run_id')}`")
        else:
            st.error(resp.text)

st.divider()
st.subheader("Test Runs")

runs_resp = requests.get(f"{API_URL}/runs")
runs = runs_resp.json().get("runs", []) if runs_resp.ok else []

if runs:
    table_rows = []
    for run in runs:
        rid = run["run_id"]
        status_resp = requests.get(f"{API_URL}/status/{rid}")
        status = status_resp.json().get("status", "unknown") if status_resp.ok else "unknown"
        files_resp = requests.get(f"{API_URL}/results/{rid}")
        files = files_resp.json().get("files", []) if files_resp.ok else []
        json_files = [f for f in files if f.endswith(".json")]
        download = f'<a href="{API_URL}/results/{rid}/{json_files[0]}" download>⬇ JSON</a>' if json_files else "—"
        status_badge = {"completed": "🟢", "running": "🟡", "failed": "🔴"}.get(status, "⚪") + f" {status}"
        table_rows.append(f"<tr><td><code>{rid}</code></td><td>{status_badge}</td><td>{download}</td></tr>")
    st.markdown(
        "<table><thead><tr><th>Run ID</th><th>Status</th><th>Results</th></tr></thead><tbody>"
        + "".join(table_rows)
        + "</tbody></table>",
        unsafe_allow_html=True,
    )
else:
    st.info("No test runs yet. Upload data and start a run above.")
