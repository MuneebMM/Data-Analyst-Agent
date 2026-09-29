"""Small schemas shared by the graph and tools."""
from __future__ import annotations

from typing import Any, TypedDict
from pydantic import BaseModel, Field


class DatasetProfile(BaseModel):
    rows: int
    columns: list[str]
    dtypes: dict[str, str]
    missing: dict[str, int]
    sample_rows: list[dict[str, Any]]


class PlanOutput(BaseModel):
    steps: list[str] = Field(min_length=1)
    chart_wanted: bool = False


class CodeOutput(BaseModel):
    code: str


class AnswerOutput(BaseModel):
    answer: str


class ExecOutput(BaseModel):
    ok: bool
    result: str = ""
    error: str = ""
    chart_path: str | None = None
    chart_paths: list[str] = Field(default_factory=list)


class AgentState(TypedDict, total=False):
    question: str
    csv_path: str
    work_dir: str
    profile: dict[str, Any]
    plan: dict[str, Any]
    code: str
    attempts: int
    retries: int
    error: str
    result: str
    chart_path: str | None
    chart_paths: list[str]
    answer: str
    provider: str
    api_key: str
