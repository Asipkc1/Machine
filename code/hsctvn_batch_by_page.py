from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

import pandas as pd

from hsctvn_feb2026_export import run


def _keep_industrial_zone_companies(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Filter to keep only companies with 'công nghiệp' or 'cn' in address."""
    if dataframe.empty or "Địa chỉ" not in dataframe.columns:
        return dataframe

    mask = dataframe["Địa chỉ"].fillna("").str.lower().str.contains(
        (
            r"khu\s*c[oô]ng\s*nghi[ẹe]p|\bkcn\b|\bkhu\s*cn\b|"
            r"c[ụu]m\s*c[oô]ng\s*nghi[ẹe]p|\bccn\b|"
            r"khu\s*ch[ếe]\s*xu[ấa]t|\bkcx\b|"
            r"khu\s*kinh\s*t[ếe]|\bindustrial\s*park\b|"
            r"c[oô]ng\s*nghi[ẹe]p|cong\s*nghiep|\bcn\b"
        ),
        na=False,
        regex=True,
    )
    return dataframe[mask]


def run_by_page(
    start_page: int,
    end_page: int,
    workers: int,
    rps: float,
    min_interval: float,
    output_dir: Path,
    retry_wait_seconds: float,
    max_retries: int,
) -> int:
    """Run crawl/export page-by-page with bounded retry on anomalies."""
    root_dir = Path(__file__).resolve().parent.parent
    temp_output = root_dir / "output" / "cong_ty_thanh_lap_thang_02_2026_hsctvn.xlsx"
    output_dir.mkdir(parents=True, exist_ok=True)
    retry_wait_seconds = max(1.0, retry_wait_seconds)
    max_retries = max(1, max_retries)

    completed_pages = 0

    for page in range(start_page, end_page + 1):
        attempt = 1
        while attempt <= max_retries:
            print(f"\n=== Bat dau trang {page} (lan thu {attempt}) ===")
            try:
                run(
                    start_page=page,
                    end_page=page,
                    workers=workers,
                    requests_per_second=rps,
                    min_interval_seconds=min_interval,
                )

                if not temp_output.exists():
                    raise RuntimeError("Khong tim thay file output tam sau khi crawl")

                target_file = output_dir / f"page_{page:03d}.xlsx"

                dataframe = pd.read_excel(temp_output)
                original_count = len(dataframe)

                dataframe = _keep_industrial_zone_companies(dataframe)
                row_count = len(dataframe)
                dataframe.to_excel(target_file, index=False)

                required_cols = {"Tên Tiếng Việt", "Mã số thuế", "Link chi tiết"}
                missing_cols = [col for col in required_cols if col not in dataframe.columns]
                if missing_cols:
                    raise RuntimeError(f"Thieu cot bat buoc: {', '.join(missing_cols)}")

                completed_pages += 1
                print(
                    f"Trang {page} OK, so dong sau loc: {row_count}/{original_count}, "
                    f"file: {target_file}"
                )
                break
            except Exception as error:  # noqa: BLE001
                print("\n!!! PHAT HIEN BAT THUONG - SE THU LAI !!!")
                print(f"Trang dang xu ly: {page}")
                print(f"So trang da hoan tat: {completed_pages}")
                print(f"Loi: {error}")
                print(traceback.format_exc())
                if attempt >= max_retries:
                    raise RuntimeError(
                        f"Trang {page} that bai sau {max_retries} lan thu"
                    ) from error
                print(
                    f"Cho {retry_wait_seconds:g} giay roi thu lai trang {page} "
                    f"(lan tiep theo: {attempt + 1})..."
                )
                time.sleep(retry_wait_seconds)
                attempt += 1

    print("\n=== HOAN TAT PHAM VI YEU CAU ===")
    print(f"Tong trang da hoan tat: {completed_pages}")
    return completed_pages


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run HSCTVN crawler page-by-page with auto retry on anomalies")
    parser.add_argument("--start-page", type=int, default=1, help="Start page")
    parser.add_argument("--end-page", type=int, default=867, help="End page")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent workers for detail pages")
    parser.add_argument("--rps", type=float, default=0.2, help="Global requests per second")
    parser.add_argument("--min-interval", type=float, default=1.5, help="Minimum seconds between requests")
    parser.add_argument(
        "--retry-wait-seconds",
        type=float,
        default=10.0,
        help="Seconds to wait before retrying a failed page",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=10,
        help="Max retry attempts per page before stopping the program",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output/hsctvn_feb2026_by_page",
        help="Directory to save per-page Excel files",
    )
    args = parser.parse_args()

    try:
        done = run_by_page(
            start_page=args.start_page,
            end_page=args.end_page,
            workers=args.workers,
            rps=args.rps,
            min_interval=args.min_interval,
            output_dir=Path(args.output_dir),
            retry_wait_seconds=args.retry_wait_seconds,
            max_retries=args.max_retries,
        )
        print(f"KET QUA: da hoan tat {done} trang")
    except RuntimeError as error:
        print(f"DUNG CHUONG TRINH: {error}")
        sys.exit(1)
