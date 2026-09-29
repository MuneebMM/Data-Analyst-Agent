"""Small paid OpenRouter smoke test; reads .env through the app without printing it."""
from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

from analyst.graph import graph
from analyst.llm import has_api_key
from analyst.skills import load_csv, profile_dataset


def main() -> None:
    if not has_api_key():
        raise RuntimeError("OpenRouter key is unavailable to the app")
    # Use the model requested for this test without reading or changing .env.
    os.environ["OPENROUTER_MODEL"] = "openai/gpt-6-luna"
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else folder / "insurance.csv"
        if len(sys.argv) == 1:
            csv_path.write_text(
                "region,bmi,charges\n"
                "southwest,27.9,16884\n"
                "southeast,33.77,1725\n"
                "southeast,33.0,4449\n"
                "northwest,22.7,21984\n"
                "northeast,29.8,6406\n"
                "southeast,25.7,3756\n", encoding="utf-8",
            )
        profile = profile_dataset(load_csv(csv_path))
        question = sys.argv[2] if len(sys.argv) > 2 else "How many people are in each region? Show a bar chart."
        work_dir = (Path.cwd() / "output" / f"live_insurance_{uuid.uuid4().hex[:8]}") if len(sys.argv) > 1 else folder / "run"
        state = graph.invoke({
            "question": question,
            "csv_path": str(csv_path), "work_dir": str(work_dir),
            "profile": profile.model_dump(), "provider": "openrouter", "attempts": 0,
        })
        assert not state["error"], state["error"]
        assert state["chart_path"] and Path(state["chart_path"]).is_file()
        print(f"answer: {state['answer']}")
        print(f"attempts: {state['attempts']}; retries: {state['retries']}; charts: {len(state['chart_paths'])}")
        if len(sys.argv) > 1:
            print(f"chart_paths: {state['chart_paths']}")
        print(f"code: {state['code']}")


if __name__ == "__main__":
    main()
