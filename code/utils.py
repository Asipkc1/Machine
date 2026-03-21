"""Utility functions for web scraping project"""
import os
import json
from pathlib import Path

# Project directories
PROJECT_ROOT = Path(__file__).parent.parent
CODE_DIR = PROJECT_ROOT / "code"
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"

def ensure_output_dir():
    """Ensure output directory exists"""
    OUTPUT_DIR.mkdir(exist_ok=True)

def load_input_json(filename):
    """Load JSON from input folder"""
    filepath = INPUT_DIR / filename
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def save_json(data, filename):
    """Save data to JSON in output folder"""
    ensure_output_dir()
    filepath = OUTPUT_DIR / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved: {filepath}")
