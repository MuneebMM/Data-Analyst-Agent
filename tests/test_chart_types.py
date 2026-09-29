"""Representative matplotlib chart families work through the guarded worker."""
from __future__ import annotations

import tempfile
from pathlib import Path

from analyst.skills import run_code_safely


def main() -> None:
    examples = {
        "bar": "counts = df['region'].value_counts(); result = counts.to_string(); plt.figure(); counts.plot(kind='bar')",
        "line": "result = 'line'; plt.figure(); plt.plot(df['bmi'], df['charges'])",
        "scatter": "result = 'scatter'; plt.figure(); plt.scatter(df['bmi'], df['charges'])",
        "histogram": "result = 'histogram'; plt.figure(); plt.hist(df['bmi'])",
        "box": "result = 'box'; plt.figure(); plt.boxplot(df['charges'])",
        "pie": "counts = df['region'].value_counts(); result = 'pie'; plt.figure(); plt.pie(counts, labels=counts.index)",
        "heatmap": "result = 'heatmap'; plt.figure(); plt.imshow(df[['bmi', 'charges']].corr()); plt.colorbar()",
        "multiple": "counts = df['region'].value_counts(); result = counts.to_string(); plt.figure(); plt.pie(counts, labels=counts.index); plt.figure(); counts.plot(kind='bar')",
    }
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        csv_path = folder / "insurance.csv"
        csv_path.write_text("region,bmi,charges\nsouthwest,27.9,16884\nsoutheast,33.77,1725\nnorthwest,22.7,21984\n", encoding="utf-8")
        for name, code in examples.items():
            outcome = run_code_safely(code, csv_path, folder / name)
            assert outcome.ok and outcome.chart_path and Path(outcome.chart_path).is_file(), (name, outcome)
            assert len(outcome.chart_paths) == (2 if name == "multiple" else 1), (name, outcome.chart_paths)
            print(f"{name}: {len(outcome.chart_paths)} chart(s) created")


if __name__ == "__main__":
    main()
