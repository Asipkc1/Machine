"""Utility functions for web scraping project"""
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"


def ensure_output_dir() -> None:
    """Ensure output directory exists."""
    OUTPUT_DIR.mkdir(exist_ok=True)


def load_input_json(filename: str) -> dict[str, Any] | list[Any] | None:
    """Load JSON from input folder."""
    filepath = INPUT_DIR / filename
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as file:
            return json.load(file)
    return None


def save_json(data: dict[str, Any] | list[Any], filename: str) -> None:
    """Save data to JSON in output folder."""
    ensure_output_dir()
    filepath = OUTPUT_DIR / filename
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
    print(f"✓ Saved: {filepath}")
