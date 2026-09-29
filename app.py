"""Run with: streamlit run app.py"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import streamlit as st

from analyst.graph import graph
from analyst.llm import has_api_key
from analyst.skills import load_csv, profile_dataset

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

st.set_page_config(page_title="Data Analyst Agent", page_icon="📊", layout="wide")
st.title("📊 Data Analyst Agent")
st.caption("Upload one CSV, ask a question, and inspect the plan, code, and result.")
provider = st.sidebar.selectbox("Analysis mode", ["OpenRouter", "Mock demo"], help="OpenRouter analyzes new questions and CSV schemas. Mock demo is a limited offline example.")
api_key = st.sidebar.text_input("OpenRouter API key for this session", type="password") if provider == "OpenRouter" else ""
if provider == "OpenRouter" and not has_api_key(api_key):
    st.sidebar.info("Add your OpenRouter API key here or in .env to analyze new questions. The key is not shown in results.")
elif provider == "Mock demo":
    st.sidebar.warning("Mock demo supports only a few example patterns. Choose OpenRouter for new datasets and questions.")
uploaded = st.file_uploader("Upload a CSV", type="csv")
sample = st.checkbox("Use the included sales sample", value=True) if uploaded is None else False
question = st.text_input("Question", "Which month had the highest sales? Show a chart.")

if uploaded is not None or sample:
    try:
        with tempfile.TemporaryDirectory(prefix="analyst_ui_") as temp:
            path = Path(temp) / "input.csv"
            # Copy input bytes into a temporary file; the original is never changed.
            path.write_bytes(uploaded.getvalue() if uploaded else (Path(__file__).parent / "data" / "sample_sales.csv").read_bytes())
            df = load_csv(path)
            st.subheader("Data preview")
            st.dataframe(df.head(10), width="stretch")
            st.caption(f"{len(df)} rows · {len(df.columns)} columns")
    except ValueError as exc:
        st.error(str(exc))

if st.button("Analyze", type="primary"):
    if uploaded is None and not sample:
        st.warning("Upload a CSV or select the included sample.")
    elif not question.strip():
        st.warning("Enter a question.")
    elif provider == "OpenRouter" and not has_api_key(api_key):
        st.error("OpenRouter needs an API key. Enter it in the sidebar or add OPENROUTER_API_KEY to .env, then try again.")
    else:
        try:
            with tempfile.TemporaryDirectory(prefix="analyst_run_") as temp:
                folder = Path(temp)
                csv_path = folder / "input.csv"
                csv_path.write_bytes(uploaded.getvalue() if uploaded else (Path(__file__).parent / "data" / "sample_sales.csv").read_bytes())
                profile = profile_dataset(load_csv(csv_path))
                with st.spinner("Planner → Coder → Executor → Responder"):
                    state = graph.invoke({"question": question.strip(), "csv_path": str(csv_path), "work_dir": str(folder), "profile": profile.model_dump(), "provider": "openrouter" if provider == "OpenRouter" else "mock", "api_key": api_key, "attempts": 0, "retries": 0})
                st.subheader("Answer")
                st.write(state["answer"])
                st.caption(f"Provider: {state['provider']} · Attempts: {state['attempts']} · Retries: {state['retries']}")
                st.subheader("Plan")
                for step in state["plan"]["steps"]:
                    st.write("•", step)
                st.subheader("Code used")
                st.code(state["code"], language="python")
                if state.get("chart_paths"):
                    st.subheader("Charts")
                    for index, chart in enumerate(state["chart_paths"], 1):
                        st.image(chart, caption=f"Chart {index}")
                if state.get("error"):
                    st.error(state["error"])
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")
