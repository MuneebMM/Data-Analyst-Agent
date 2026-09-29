"""CSV, profile, and guarded execution tools."""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from .models import DatasetProfile, ExecOutput


BLOCKED_NAMES = {
    "open", "eval", "exec", "compile", "__import__", "input", "globals", "locals",
    "getattr", "setattr", "delattr", "vars", "dir", "help", "breakpoint",
    "os", "sys", "subprocess", "socket", "requests", "urllib", "pathlib", "shutil",
}
BLOCKED_ATTRS = {
    "read_csv", "read_pickle", "read_json", "read_html", "read_parquet", "read_sql",
    "to_csv", "to_pickle", "to_json", "to_parquet", "to_sql", "savefig",
    "system", "popen", "remove", "unlink", "rmdir", "write_text", "write_bytes",
    "get", "post", "request", "urlopen", "connect", "to_file", "pipe", "query", "eval",
    "to_excel", "to_hdf", "to_feather", "to_stata", "to_orc", "to_xml", "to_markdown",
}
BLOCKED_METHODS = {"drop", "dropna", "fillna", "rename", "replace", "update", "insert", "pop", "set_index", "reset_index", "sort_values"}


def detect_csv_encoding(path: Path) -> str:
    """Try UTF-8 first, then common Windows CSV encodings."""
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with path.open("r", encoding=encoding) as handle:
                for chunk in iter(lambda: handle.read(8192), ""):
                    pass
            return encoding
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode CSV")


def load_csv(path: Path) -> pd.DataFrame:
    """Load one CSV; reject empty or malformed input."""
    try:
        df = pd.read_csv(path, encoding=detect_csv_encoding(path))
    except Exception as exc:
        raise ValueError(f"Could not read CSV: {exc}") from exc
    if df.empty or not len(df.columns):
        raise ValueError("CSV has no data rows")
    return df


def profile_dataset(df: pd.DataFrame) -> DatasetProfile:
    """Return only compact metadata and five records for an LLM prompt."""
    if df.empty:
        raise ValueError("Dataset is empty")
    # Limit the prompt to five rows so the full uploaded CSV stays local.
    sample = json.loads(df.head(5).to_json(orient="records", date_format="iso"))
    return DatasetProfile(
        rows=len(df), columns=[str(c) for c in df.columns],
        dtypes={str(c): str(t) for c, t in df.dtypes.items()},
        missing={str(c): int(n) for c, n in df.isna().sum().items()},
        sample_rows=sample,
    )


def validate_code(code: str) -> None:
    """Reject obvious file, process, network, introspection, and DataFrame mutation code."""
    if len(code) > 8000:
        raise ValueError("Code exceeds 8,000 characters")
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValueError(f"Invalid syntax: {exc}") from exc
    for node in ast.walk(tree):
        # Imports permit filesystem/network access, so generated code uses preloaded pd/plt only.
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.With, ast.AsyncWith,
                             ast.Try, ast.Raise, ast.Delete, ast.While, ast.Await, ast.Yield, ast.YieldFrom)):
            raise ValueError(f"Blocked syntax: {type(node).__name__}")
        # Dynamic builtins and private attributes can bypass the simple sandbox.
        if isinstance(node, ast.Name) and (node.id in BLOCKED_NAMES or node.id.startswith("__")):
            raise ValueError(f"Blocked name: {node.id}")
        if isinstance(node, ast.Attribute) and (node.attr.startswith("_") or node.attr.startswith(("read_", "write_", "save_", "load_")) or node.attr in BLOCKED_ATTRS):
            raise ValueError(f"Blocked attribute: {node.attr}")
        # Prevent direct changes to the loaded DataFrame.
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(_targets_df(t) for t in targets):
                raise ValueError("Changing df is blocked; use df.copy()")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in BLOCKED_METHODS and _root_name(node.func.value) == "df":
                raise ValueError("Changing df is blocked; use df.copy()")
            if any(k.arg == "inplace" for k in node.keywords):
                raise ValueError("inplace operations are blocked")


def _root_name(node: ast.AST) -> str | None:
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _targets_df(node: ast.AST) -> bool:
    if isinstance(node, (ast.Tuple, ast.List)):
        return any(_targets_df(part) for part in node.elts)
    return _root_name(node) == "df"


def capture_chart(work_dir: Path) -> Path | None:
    charts = capture_charts(work_dir)
    return charts[0] if charts else None


def capture_charts(work_dir: Path) -> list[Path]:
    """Find every figure written by the worker, in figure order."""
    return sorted(work_dir.glob("chart_*.png"))


def run_code_safely(code: str, csv_path: Path, work_dir: Path, timeout: int = 10) -> ExecOutput:
    """Run generated code in a separate process with a hard timeout."""
    try:
        validate_code(code)
    except ValueError as exc:
        return ExecOutput(ok=False, error=str(exc))
    work_dir.mkdir(parents=True, exist_ok=True)
    payload = work_dir / "job.json"
    payload.write_text(json.dumps({"code": code, "csv_path": str(csv_path), "work_dir": str(work_dir), "encoding": detect_csv_encoding(csv_path)}), encoding="utf-8")
    try:
        # A subprocess timeout prevents an infinite or slow analysis from freezing the app.
        process = subprocess.run(
            [sys.executable, "-I", str(Path(__file__).with_name("worker.py")), str(payload)],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return ExecOutput(ok=False, error=f"Execution timed out after {timeout} seconds")
    try:
        data = json.loads(process.stdout)
        outcome = ExecOutput.model_validate(data)
    except Exception:
        return ExecOutput(ok=False, error=f"Worker failed: {process.stderr[-800:]}")
    charts = capture_charts(work_dir) if outcome.ok else []
    outcome.chart_paths = [str(chart) for chart in charts]
    outcome.chart_path = outcome.chart_paths[0] if charts else None
    return outcome


def format_answer(question: str, result: str, error: str = "") -> str:
    if error:
        return f"I could not answer '{question}' after three attempts. Last error: {error}"
    return f"{question.rstrip('?. ')}? {result}"
