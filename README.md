# Crawl Thông Tin Công Ty (hsctvn.com)

Crawl danh sách công ty thành lập mới từ [hsctvn.com](https://hsctvn.com), lọc theo khu công nghiệp, enrich thêm thông tin từ masothue.com và thuvienphapluat.vn, xuất ra Excel.

## Cấu trúc

```
Machine/
├── code/
│   ├── shared.py                  # Shared: build_driver(), industrial zone regex
│   ├── hsctvn_feb2026_export.py   # Core: crawl listing + detail từ hsctvn.com
│   ├── hsctvn_batch_by_page.py    # Wrapper: chạy từng trang với retry
│   ├── merge_pages.py             # Gộp các file page_NNN.xlsx thành 1 file
│   ├── filter_industrial_zone.py  # Lọc lại file Excel theo khu CN
│   └── mst_enrich_sample.py       # Enrich email/ngành nghề qua MST
├── input/
├── output/                        # Kết quả Excel
├── pyproject.toml
└── run.bat
```

## Cài đặt

```powershell
# Kích hoạt virtual environment
.venv\Scripts\activate.bat
```

## Chạy

### Crawl theo từng trang (khuyến nghị)
```powershell
# Chạy tất cả (mặc định trang 1-867)
python code/hsctvn_batch_by_page.py

# Chạy phạm vi cụ thể
python code/hsctvn_batch_by_page.py --start-page 1 --end-page 50

# Tùy chỉnh rate limit và retry
python code/hsctvn_batch_by_page.py --start-page 1 --end-page 50 --rps 0.2 --max-retries 10
```

### Crawl một lần toàn bộ
```powershell
python code/hsctvn_feb2026_export.py --start-page 1 --end-page 50
```

### Gộp kết quả các trang
```powershell
python code/merge_pages.py
```

### Lọc lại theo khu CN
```powershell
python code/filter_industrial_zone.py
```

### Enrich MST (sample)
```powershell
python code/mst_enrich_sample.py --input-file output/hsctvn_feb2026_all_pages_merged.xlsx --sample-size 5
```

## Thêm Package

```powershell
python -m uv add package_name
```

## Workflow

1. **Crawl dữ liệu** → Lưu vào `input/` nếu cần
2. **Xử lý dữ liệu** → Code trong `code/main.py`
3. **Xuất kết quả** → JSON/CSV/Excel tự động vào `output/`

---

Chúc bạn code vui! 🚀
