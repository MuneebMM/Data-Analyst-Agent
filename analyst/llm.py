"""One live LLM provider (OpenRouter) plus a deterministic offline demo mode."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import requests
from dotenv import dotenv_values

from .models import AnswerOutput, CodeOutput, DatasetProfile, PlanOutput
from .skills import format_answer

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
CHART_WORDS = ("chart", "plot", "graph", "visualiz", "histogram", "scatter", "boxplot", "box plot", "pie", "heatmap", "bar graph", "bar chart")


PROMPTS = {
    "Planner": "You are a data analyst. Given a question and a compact profile for an arbitrary CSV, return JSON with steps (list of strings) and chart_wanted (boolean). Use exact column names and identify the requested calculation and chart type. Never claim to have seen every row.",
    "Coder": "Return JSON with only code. Python has df (pandas DataFrame), pd, and plt preloaded. The CSV can have ANY schema: use only columns listed in the profile and answer the actual question. Set result to a concise printable value, including all requested groups when appropriate. If plan.chart_wanted is true, create matplotlib charts of every requested type (bar, line, scatter, histogram, box, pie, heatmap, or another matplotlib chart). If the user asks for two charts, make both, as separate figures or subplots. Leave figures open. Use pandas and matplotlib without imports. No files, network, eval, exec, or changes to df. Use df.copy() if needed.",
    "Debugger": "Return JSON with only repaired code. Fix the actual error using the code, traceback, question, plan, and compact profile. If the error says a requested chart is missing, add a suitable matplotlib figure. Keep the sandbox rules: no imports, file/network access, or changes to df.",
    "Responder": "Format the computed result plainly without inventing values.",
}


def setting(name: str, default: str = "") -> str:
    """Read current settings so adding .env does not require a server restart."""
    return os.getenv(name) or str(dotenv_values(ENV_FILE).get(name) or default)


def provider_name(requested: str | None = None) -> str:
    choice = (requested or setting("LLM_PROVIDER", "openrouter")).strip().lower()
    if choice not in {"openrouter", "mock"}:
        raise ValueError("LLM_PROVIDER must be 'openrouter' or 'mock'")
    return choice


def has_api_key(api_key: str = "") -> bool:
    return bool(api_key or setting("OPENROUTER_API_KEY"))


def _openrouter_json(node: str, payload: dict[str, Any], api_key: str = "") -> dict[str, Any]:
    key = api_key or setting("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is missing; choose LLM_PROVIDER=mock or add a key to .env")
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-OpenRouter-Title": "Data Analyst Agent Demo"},
        json={
            "model": setting("OPENROUTER_MODEL", "openai/gpt-6-luna"),
            "messages": [{"role": "system", "content": PROMPTS[node]}, {"role": "user", "content": json.dumps(payload, default=str)}],
            "response_format": {"type": "json_object"}, "temperature": 0,
        },
        timeout=30,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    return json.loads(content)


def plan(question: str, profile: DatasetProfile, provider: str | None = None, api_key: str = "") -> PlanOutput:
    chart = any(word in question.lower() for word in CHART_WORDS)
    if provider_name(provider) == "openrouter":
        output = PlanOutput.model_validate(_openrouter_json("Planner", {"question": question, "profile": profile.model_dump()}, api_key))
        output.chart_wanted = output.chart_wanted or chart
        return output
    return PlanOutput(steps=["Inspect the relevant columns", "Aggregate the requested values", "Report the result"], chart_wanted=chart)


def code(question: str, profile: DatasetProfile, plan_output: PlanOutput, provider: str | None = None, api_key: str = "") -> CodeOutput:
    if provider_name(provider) == "openrouter":
        return CodeOutput.model_validate(_openrouter_json("Coder", {"question": question, "profile": profile.model_dump(), "plan": plan_output.model_dump()}, api_key))
    q = question.lower()
    if "force an error" in q:
        return CodeOutput(code="result = df['units_sold'].sum()")
    if "how many rows" in q or "number of rows" in q:
        return CodeOutput(code="result = f'{len(df)} rows'")
    if "total revenue" in q and "product" not in q:
        return CodeOutput(code="result = f'Total revenue: {df[\"revenue\"].sum():,.2f}'")
    if "product" in q and ("highest" in q or "most" in q) and "revenue" in q:
        return CodeOutput(code="totals = df.groupby('product')['revenue'].sum(); result = f'{totals.idxmax()}: {totals.max():,.2f} revenue'")
    if "month" in q and ("sales" in q or "revenue" in q):
        return CodeOutput(code="monthly = df.assign(month=pd.to_datetime(df['date']).dt.to_period('M').astype(str)).groupby('month')['revenue'].sum(); result = f'{monthly.idxmax()}: {monthly.max():,.2f} revenue'; plt.figure(figsize=(7, 4)); monthly.plot(kind='bar', title='Revenue by month'); plt.ylabel('Revenue'); plt.tight_layout()")
    if "region" in q and "average" in q:
        return CodeOutput(code="averages = df.groupby('region')['revenue'].mean(); result = f'{averages.idxmax()}: {averages.max():,.2f} average revenue per order'")
    if "product" in q and ("units" in q or "quantity" in q):
        return CodeOutput(code="totals = df.groupby('product')['quantity'].sum(); result = f'{totals.idxmax()}: {totals.max():,.0f} units'")
    # In mock mode, use the uploaded schema for simple counts by a named category.
    if ("how many" in q or "count" in q or "number of" in q) and ("each" in q or " by " in q or " per " in q):
        for column in sorted(profile.columns, key=len, reverse=True):
            if re.search(rf"(?<!\w){re.escape(column.lower())}(?!\w)", q):
                name = repr(column)
                script = f"counts = df[{name}].value_counts(dropna=False).sort_index(); result = counts.to_string()"
                if plan_output.chart_wanted:
                    script += f"; plt.figure(figsize=(7, 4)); counts.plot(kind='bar', title='Count by {column}'); plt.xlabel({name}); plt.ylabel('Count'); plt.tight_layout()"
                return CodeOutput(code=script)
    return CodeOutput(code="result = f'This offline demo supports the six README example questions. Dataset has {len(df)} rows.'")


def debug(failed_code: str, error: str, profile: DatasetProfile, question: str, plan_output: PlanOutput, provider: str | None = None, api_key: str = "") -> CodeOutput:
    if provider_name(provider) == "openrouter":
        return CodeOutput.model_validate(_openrouter_json("Debugger", {"question": question, "code": failed_code, "error": error, "profile": profile.model_dump(), "plan": plan_output.model_dump()}, api_key))
    if "units_sold" in failed_code and "quantity" in profile.columns:
        return CodeOutput(code="totals = df.groupby('product')['quantity'].sum(); result = f'{totals.idxmax()}: {totals.max():,.0f} units'")
    return CodeOutput(code=failed_code)


def respond(question: str, result: str, error: str, provider: str | None = None, api_key: str = "") -> AnswerOutput:
    # Format locally: model response schemas vary, and computed results stay on this machine.
    return AnswerOutput(answer=format_answer(question, result, error))
