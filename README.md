# Data Analyst Agent demo

A beginner-friendly single-CSV analyst built with Streamlit, LangGraph, pandas, matplotlib, and Pydantic. It plans a question, writes code, runs it in a guarded subprocess, repairs a failure up to two times (three total attempts), and explains the result. OpenRouter uses the uploaded CSV's compact profile to generate analysis for new questions and chart types. Model output can still be wrong, so review the displayed code and result. Mock demo mode works without a key but supports only a small set of patterns.

## Setup (Python 3.11+)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run app.py
```

On a machine where `python` is not on PATH, use the installed Python 3.11+ executable in the first command. The remaining commands use the activated virtual environment.

The app opens at `http://localhost:8501`. Choose the included sample or upload one CSV, enter a question, and click **Analyze**. The UI shows the plan, answer, final code, optional chart, and retries. CSV loading tries UTF-8, Windows-1252, and Latin-1 so common Windows exports can be previewed and analyzed. **OpenRouter** is selected by default; enter its key in the sidebar for the current session or configure `.env`. Select **Mock demo** only to run the limited offline examples.

## OpenRouter mode

Copy `.env.example` to `.env` and edit it, or enter the key in the sidebar:

```text
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=google/gemini-2.5-flash
```

Get a key from the [OpenRouter key settings](https://openrouter.ai/settings/keys). Keep `.env` private; it is ignored by Git. The default model is `openai/gpt-6-luna`; you may choose another model slug supported by OpenRouter. OpenRouter calls use the [chat completions endpoint](https://openrouter.ai/docs/quickstart). Live mode requires network access and available model credits. The real GPT-6 Luna flow has been verified on the included sample and an insurance CSV; model generated code and output can still vary.

For example, upload an insurance CSV with a `region` column and ask, "How many people are in each region? Show a bar chart." OpenRouter chooses the calculation and chart from the schema and question. You can ask for a scatter plot, histogram, line, box, pie, heatmap, or another chart supported by matplotlib. Multiple figures are saved and displayed. A requested chart that is missing from generated output triggers the Debugger before the app answers.

## Example questions

1. How many rows are in the dataset?
2. What is total revenue?
3. Which product has the highest total revenue?
4. Which month had the highest sales? Show a chart.
5. Which region had the highest average revenue per order?
6. Force an error first, then recover: Which product sold the most units?

Question six deliberately asks mock Coder for a nonexistent `units_sold` column. Executor reports the error, Debugger changes it to `quantity`, and Executor succeeds on attempt two. These six examples are for offline verification, not the limit of OpenRouter mode.

## Architecture

```text
CSV -> compact profile -> Planner -> Coder -> Executor -> Responder -> UI
                                          ^        |
                                          + Debugger+  (error, fewer than 3 attempts)
```

Only the schema, types, missing counts, and five sample rows go to OpenRouter. Code runs in a separate process with a 10 second timeout and AST checks against imports, file operations, network/process access, and direct changes to `df`. The uploaded CSV is copied to a temporary path. These guardrails are suitable for a local teaching demo, not a hardened service for untrusted users.

## Verify

```powershell
$env:PYTHONPATH = "."
python tests/test_skills.py
python tests/demo_questions.py
python tests/test_openrouter_flow.py
python tests/test_chart_types.py
python tests/live_openrouter_smoke.py "C:\path\to\insurance.csv"
streamlit run app.py --server.headless true
```

See `TEST_RESULTS.md` for actual results from this checkout.

## Limits

- One CSV at a time; no database, authentication, deployment, or large-file optimization.
- Mock mode supports the listed examples and a few simple schema-based counts. OpenRouter mode is needed for broader questions; no model can guarantee a correct answer to every possible question.
- Charts are limited to what matplotlib and the available columns can represent; the model chooses a suitable type from the question.
- Safety checks reduce obvious misuse but Python is not a security sandbox. Do not host this for hostile users or upload sensitive data.
- Numeric answers follow pandas defaults: missing values are skipped in sums and means.
