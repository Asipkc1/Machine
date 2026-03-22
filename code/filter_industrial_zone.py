from pathlib import Path
import pandas as pd


def keep_industrial_zone(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Filter to keep only companies with 'công nghiệp' or 'cn' in address."""
    if dataframe.empty or "Địa chỉ" not in dataframe.columns:
        return dataframe
    
    mask = dataframe["Địa chỉ"].fillna("").str.lower().str.contains(
        r"công nghiệp|cn", na=False, regex=True
    )
    return dataframe[mask]


def filter_pages(start_page: int, end_page: int, input_dir: Path) -> None:
    """Filter pages and rewrite them with industrial zone companies only."""
    input_dir = Path(input_dir)
    
    for page in range(start_page, end_page + 1):
        file_path = input_dir / f"page_{page:03d}.xlsx"
        if not file_path.exists():
            print(f"Trang {page}: file không tồn tại")
            continue
        
        try:
            df = pd.read_excel(file_path)
            original_count = len(df)
            
            df_filtered = keep_industrial_zone(df)
            filtered_count = len(df_filtered)
            
            df_filtered.to_excel(file_path, index=False)
            
            print(f"Trang {page}: {original_count} -> {filtered_count} ({filtered_count}/{original_count})")
        except Exception as e:
            print(f"Trang {page}: Lỗi - {e}")


if __name__ == "__main__":
    input_dir = Path(__file__).resolve().parent.parent / "output" / "hsctvn_feb2026_by_page"
    print("=== BẮT ĐẦU LỌC LẠI TRANG 1-86 ===")
    filter_pages(start_page=1, end_page=86, input_dir=input_dir)
    print("=== HOÀN TẤT LỌC ===")
