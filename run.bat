@echo off
cd code
python -m uv run python hsctvn_batch_by_page.py %*
cd ..
