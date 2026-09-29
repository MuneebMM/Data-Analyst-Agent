"""Focused checks for data profiling and obvious sandbox escapes."""
from __future__ import annotations

import tempfile
from pathlib import Path

from analyst.skills import load_csv, profile_dataset, run_code_safely


def main() -> None:
    source = Path(__file__).resolve().parents[1] / "data" / "sample_sales.csv"
    df = load_csv(source)
    profile = profile_dataset(df)
    assert len(df) == 100
    assert profile.missing["revenue"] > 0 and profile.missing["quantity"] > 0
    assert len(profile.sample_rows) == 5
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        windows_csv = folder / "windows.csv"
        windows_csv.write_bytes(b"brand,model\nFord,Focus \x96 edition\n")
        assert load_csv(windows_csv).loc[0, "model"] == "Focus – edition"
        decoded = run_code_safely("result = df['model'].iloc[0]", windows_csv, folder / "windows_run")
        assert decoded.ok and decoded.result == "Focus – edition", decoded
        safe = run_code_safely("result = len(df)", source, folder / "safe")
        assert safe.ok and safe.result == "100", safe
        for snippet in ["import os\nresult = 1", "result = open('bad.txt', 'w')", "result = eval('1+1')", "df['revenue'] = 0", "result = pd.read_csv('secret.csv')"]:
            blocked = run_code_safely(snippet, source, folder / "blocked")
            assert not blocked.ok and "Blocked" in blocked.error or "Changing df" in blocked.error, blocked
            print(f"BLOCKED: {snippet.splitlines()[0]} -> {blocked.error}")
    print(f"PROFILE: rows={profile.rows}, missing={profile.missing}")
    print("SAFE EXECUTION: result=100")
    print("WINDOWS CSV: cp1252 preview and worker passed")


if __name__ == "__main__":
    main()
