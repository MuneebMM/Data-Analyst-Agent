"""Exercise arbitrary-schema OpenRouter flow without making a paid API call."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from analyst.graph import graph
from analyst.skills import load_csv, profile_dataset


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        csv_path = folder / "insurance.csv"
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
        assert profile.rows == 6 and len(profile.sample_rows) == 5

        def fake_response(node: str, payload: dict, api_key: str = "") -> dict:
            assert api_key == "test-key"
            if "profile" in payload:
                assert len(payload["profile"]["sample_rows"]) == 5
                assert "csv_path" not in payload
            if node == "Planner":
                # The graph should still recognize an explicit chart request.
                return {"steps": ["Use the named columns", "Calculate", "Plot"], "chart_wanted": False}
            if node == "Coder" and "region" in payload["question"]:
                return {"code": "counts = df['region'].value_counts().sort_index(); result = counts.to_string(); plt.figure(); counts.plot(kind='bar'); plt.tight_layout()"}
            if node == "Coder":
                return {"code": "result = f'{len(df)} people'"}  # Deliberately forget the scatter plot.
            if node == "Debugger":
                assert "chart" in payload["error"].lower()
                return {"code": "result = f'{len(df)} people'; plt.figure(); plt.scatter(df['bmi'], df['charges']); plt.xlabel('bmi'); plt.ylabel('charges')"}
            return {"answer": payload["result"]}

        with patch("analyst.llm._openrouter_json", side_effect=fake_response):
            for index, question in enumerate([
                "How many people are in each region? Show a bar chart.",
                "Show a scatter plot of bmi and charges.",
            ], 1):
                state = graph.invoke({
                    "question": question, "csv_path": str(csv_path), "work_dir": str(folder / f"run_{index}"),
                    "profile": profile.model_dump(), "provider": "openrouter", "api_key": "test-key", "attempts": 0,
                })
                assert not state["error"], state["error"]
                assert state["chart_path"] and Path(state["chart_path"]).is_file()
                assert state["attempts"] == index
                print(f"{index}. {question} -> {state['answer']} | chart=True retries={state['retries']}")


if __name__ == "__main__":
    main()
