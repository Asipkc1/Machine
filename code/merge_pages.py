from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_DIRS = [
    ROOT_DIR / "output" / "hsctvn_feb2026_by_page",
]
DEFAULT_OUTPUT_FILE = ROOT_DIR / "output" / "hsctvn_feb2026_all_pages_merged.xlsx"


def merge_pages(source_dirs: list[Path], output_file: Path) -> None:
    """Merge per-page Excel files into a single file, keeping newest per page."""
    by_page: dict[int, Path] = {}
    for src in source_dirs:
        if not src.exists():
            print(f"Bo qua thu muc khong ton tai: {src}")
            continue
        for filepath in src.glob("page_*.xlsx"):
            match = re.search(r"page_(\d+)\.xlsx", filepath.name)
            if not match:
                continue
            page = int(match.group(1))
            prev = by_page.get(page)
            if prev is None or filepath.stat().st_mtime > prev.stat().st_mtime:
                by_page[page] = filepath

    frames: list[pd.DataFrame] = []
    for page in sorted(by_page):
        try:
            df = pd.read_excel(by_page[page])
            if not df.empty:
                df["page_source"] = page
                frames.append(df)
        except Exception as e:
            print(f"Loi doc trang {page}: {e}")

    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    merged.to_excel(output_file, index=False)

    print(f"So trang tim thay: {len(by_page)}")
    print(f"So trang co du lieu: {len(frames)}")
    print(f"Tong so dong: {len(merged)}")
    print(f"File ket qua: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge per-page Excel files into one")
    parser.add_argument(
        "--source-dirs",
        nargs="+",
        type=str,
        default=None,
        help="Directories containing page_NNN.xlsx files",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Output merged Excel path",
    )
    args = parser.parse_args()

    sources = [Path(d) for d in args.source_dirs] if args.source_dirs else DEFAULT_SOURCE_DIRS
    output = Path(args.output_file) if args.output_file else DEFAULT_OUTPUT_FILE

    merge_pages(source_dirs=sources, output_file=output)
