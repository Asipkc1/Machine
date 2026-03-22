from pathlib import Path

import pandas as pd


def save_report_excel(rows: list[dict[str, str]], output_dir: Path, filename: str) -> Path:
    """Save audit rows to an Excel report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{filename}.xlsx"

    dataframe = pd.DataFrame(rows)
    if dataframe.empty:
        dataframe = pd.DataFrame(columns=["scope", "page_url", "text", "source", "reason"])

    dataframe.to_excel(output_path, index=False)
    return output_path
