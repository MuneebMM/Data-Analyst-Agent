"""Subprocess entry point. This is intentionally separate from the Streamlit process."""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict, "enumerate": enumerate,
    "float": float, "int": int, "len": len, "list": list, "max": max, "min": min,
    "range": range, "round": round, "set": set, "sorted": sorted, "str": str,
    "sum": sum, "tuple": tuple, "zip": zip,
}


def main() -> None:
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        # The worker reads a temporary copy; generated code cannot write the upload.
        df = pd.read_csv(job["csv_path"], encoding=job["encoding"])
        scope = {"__builtins__": SAFE_BUILTINS, "df": df, "pd": pd, "plt": plt}
        # Only validated code reaches this built-in exec call.
        exec(compile(job["code"], "<generated>", "exec"), scope, scope)
        if "result" not in scope:
            raise ValueError("Code must set a result variable")
        # Save every figure so multi-chart questions keep all requested visuals.
        for index, number in enumerate(plt.get_fignums(), 1):
            plt.figure(number).savefig(Path(job["work_dir"]) / f"chart_{index}.png", bbox_inches="tight")
        print(json.dumps({"ok": True, "result": str(scope["result"])}))
    except Exception:
        print(json.dumps({"ok": False, "error": traceback.format_exc(limit=2)[-1200:]}))


if __name__ == "__main__":
    main()
