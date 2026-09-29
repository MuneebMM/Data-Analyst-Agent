"""Run the six promised questions in mock mode and print actual answers."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from analyst.graph import graph
from analyst.skills import load_csv, profile_dataset

QUESTIONS = [
    "How many rows are in the dataset?",
    "What is total revenue?",
    "Which product has the highest total revenue?",
    "Which month had the highest sales? Show a chart.",
    "Which region had the highest average revenue per order?",
    "Force an error first, then recover: Which product sold the most units?",
]


def main() -> None:
    os.environ["LLM_PROVIDER"] = "mock"
    source = Path(__file__).resolve().parents[1] / "data" / "sample_sales.csv"
    profile = profile_dataset(load_csv(source))
    with tempfile.TemporaryDirectory() as temp:
        for number, question in enumerate(QUESTIONS, 1):
            state = graph.invoke({"question": question, "csv_path": str(source), "work_dir": str(Path(temp) / str(number)), "profile": profile.model_dump(), "attempts": 0, "retries": 0})
            assert not state["error"], state["error"]
            assert state["attempts"] == (2 if number == 6 else 1)
            if number == 4:
                assert state["chart_path"] and Path(state["chart_path"]).is_file()
            print(f"{number}. {state['answer']} | attempts={state['attempts']} retries={state['retries']} chart={bool(state['chart_path'])}")


if __name__ == "__main__":
    main()
