# Web Scraping Project

Dự án crawl dữ liệu từ website using Selenium, xử lý với Pandas và xuất ra JSON/CSV/Excel.

## Cấu trúc Folder

```
Machine/
├── code/              # Chứa code Python
│   ├── main.py        # File chính
│   └── utils.py       # Hàm tiện ích
├── input/             # Chứa file input (nếu cần)
├── output/            # Lưu kết quả JSON, CSV, Excel
├── .venv/             # Virtual environment (không commit)
├── pyproject.toml     # Cấu hình project
├── uv.lock            # Lock file dependencies
└── run.bat            # Script chạy nhanh
```

## Cài đặt & Chạy

### 1. Kích hoạt Virtual Environment
```powershell
.venv\Scripts\activate.bat
```

### 2. Chạy Project
```powershell
# Cách 1: Dùng run.bat
.\run.bat

# Cách 2: Chạy trực tiếp
python -m uv run python code/main.py

# Cách 3: Từ folder code
cd code
python main.py
cd ..
```

## Thêm Package Mới

```powershell
python -m uv add package_name
```

Ví dụ:
- `python -m uv add requests` (HTTP requests)
- `python -m uv add python-dotenv` (Environment variables)

## Workflow

1. **Crawl dữ liệu** → Lưu vào `input/` nếu cần
2. **Xử lý dữ liệu** → Code trong `code/main.py`
3. **Xuất kết quả** → JSON/CSV/Excel tự động vào `output/`

---

Chúc bạn code vui! 🚀
