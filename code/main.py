import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import json
import os

# Lấy đường dẫn output folder
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'output')

# Ví dụ: Crawl dữ liệu từ website
def crawl_data(url):
    """Crawl dữ liệu từ website"""
    driver = webdriver.Chrome()
    try:
        driver.get(url)
        # Lấy HTML sau khi load
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        # TODO: Parse dữ liệu theo cấu trúc website
        data = []
        
        return data
    finally:
        driver.quit()

def save_to_formats(data, filename="output"):
    """Lưu dữ liệu vào JSON, CSV và Excel"""
    df = pd.DataFrame(data)
    
    # Tạo đường dẫn đầy đủ
    json_path = os.path.join(OUTPUT_DIR, f"{filename}.json")
    csv_path = os.path.join(OUTPUT_DIR, f"{filename}.csv")
    excel_path = os.path.join(OUTPUT_DIR, f"{filename}.xlsx")
    
    # Lưu JSON
    df.to_json(json_path, orient="records", indent=2, force_ascii=False)
    print(f"✓ Lưu: {json_path}")
    
    # Lưu CSV
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"✓ Lưu: {csv_path}")
    
    # Lưu Excel
    df.to_excel(excel_path, index=False)
    print(f"✓ Lưu: {excel_path}")

if __name__ == "__main__":
    print("Selenium + Pandas Web Scraper")
    # data = crawl_data("https://example.com")
    # save_to_formats(data)
