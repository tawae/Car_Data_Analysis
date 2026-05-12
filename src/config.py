"""
config.py
---------
File cấu hình trung tâm cho toàn bộ dự án.
Thay đổi các giá trị tại đây để điều chỉnh hành vi của scraper và ETL pipeline.

Lưu ý: Credentials DB (host, user, password) vẫn nằm trong .env để bảo mật.
       File này chỉ chứa các tham số kỹ thuật không nhạy cảm.
"""

from pathlib import Path

# ==================================================================
# ĐƯỜNG DẪN GỐC DỰ ÁN
# ==================================================================
ROOT = Path(__file__).resolve().parent.parent

# ==================================================================
# CẤU HÌNH SCRAPER
# ==================================================================

# Số trang tối đa cào mỗi loại (xe cũ / xe mới)
# Mỗi trang có ~15-16 xe → 99 trang ≈ ~1500 xe mỗi loại
SCRAPER_OLD_CAR_PAGES: int = 99
SCRAPER_NEW_CAR_PAGES: int = 99

# Khoảng thời gian nghỉ ngẫu nhiên giữa các request (giây)
# Tăng nếu bị block, giảm nếu muốn cào nhanh hơn
SCRAPER_SLEEP_MIN: float = 0.2
SCRAPER_SLEEP_MAX: float = 0.6

# Timeout mỗi request HTTP (giây)
SCRAPER_TIMEOUT: int = 15

# Ghi log tiến trình mỗi N xe
SCRAPER_LOG_EVERY: int = 50

# URL gốc
SCRAPER_BASE_URL: str = "https://oto.com.vn"
SCRAPER_OLD_CAR_PATTERN: str = SCRAPER_BASE_URL + "/mua-ban-xe/p{page}"
SCRAPER_NEW_CAR_PATTERN: str = SCRAPER_BASE_URL + "/mua-ban-xe-moi/p{page}"

# ==================================================================
# CẤU HÌNH ETL PIPELINE
# ==================================================================

# Hành vi khi load vào DB:
#   "append"  → Thêm bản ghi mới, bỏ qua duplicate (INSERT IGNORE)
#   "replace" → Xóa toàn bộ bảng rồi load lại từ đầu (TRUNCATE + INSERT)
ETL_IF_EXISTS: str = "append"

# ==================================================================
# ĐƯỜNG DẪN FILE & THƯ MỤC
# ==================================================================
RAW_CSV        = ROOT / "data" / "raw" / "car_data.csv"
PROCESSED_CSV  = ROOT / "data" / "processed" / "car_data_cleaned.csv"
SQL_SCHEMA     = ROOT / "sql" / "init_schema.sql"
OUTPUT_DIR     = ROOT / "output"
