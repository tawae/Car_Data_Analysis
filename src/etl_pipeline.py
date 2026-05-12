"""
etl_pipeline.py
---------------
Orchestrator cho quy trình ETL (Extract → Transform → Load).

Luồng:
    1. EXTRACT: Gọi scraper để cào dữ liệu từ oto.com.vn
    2. TRANSFORM: Làm sạch, chuẩn hóa dữ liệu (logic từ notebook gốc)
    3. LOAD: Insert vào MySQL (bảng raw_cars và cleaned_cars)

Cách chạy:
    python -m src.etl_pipeline
    hoặc:
    python -m src.etl_pipeline --skip-scrape   # Dùng CSV có sẵn thay vì cào mới
"""

import argparse
import hashlib
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Đảm bảo có thể import từ root project
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import (        # noqa: E402
    RAW_CSV, PROCESSED_CSV, SQL_SCHEMA,
    ETL_IF_EXISTS,
    SCRAPER_OLD_CAR_PAGES, SCRAPER_NEW_CAR_PAGES,
)
from src.db_connector import DBConnector  # noqa: E402
from src.scraper import scrape_all         # noqa: E402

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ETL] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ==================================================================
# BƯỚC 1: EXTRACT
# ==================================================================
def extract(skip_scrape: bool = False,
            old_pages: int = SCRAPER_OLD_CAR_PAGES,
            new_pages: int = SCRAPER_NEW_CAR_PAGES) -> pd.DataFrame:
    """
    Trích xuất dữ liệu thô.

    Args:
        skip_scrape: Nếu True, đọc CSV có sẵn thay vì cào mới.
        old_pages: Số trang cào xe cũ (mặc định từ config.py).
        new_pages: Số trang cào xe mới (mặc định từ config.py).

    Returns:
        DataFrame dữ liệu thô.
    """
    if skip_scrape and RAW_CSV.exists():
        logger.info(f"[EXTRACT] Đọc dữ liệu từ CSV: {RAW_CSV}")
        df = pd.read_csv(RAW_CSV, encoding="utf-8-sig")
        logger.info(f"[EXTRACT] Đọc xong: {len(df)} records")
        return df

    logger.info(f"[EXTRACT] Bắt đầu cào dữ liệu từ oto.com.vn "
                f"(xe cũ: {old_pages} trang, xe mới: {new_pages} trang)...")
    df = scrape_all(old_pages=old_pages, new_pages=new_pages, save_raw_path=str(RAW_CSV))
    logger.info(f"[EXTRACT] Hoàn tất: {len(df)} records → {RAW_CSV}")
    return df


# ==================================================================
# BƯỚC 2: TRANSFORM
# ==================================================================
def transform(df: pd.DataFrame) -> pd.DataFrame:
    """
    Làm sạch và chuẩn hóa dữ liệu thô.
    Logic được tách từ notebook gốc.

    Các bước:
        1. Chuẩn hóa tên cột
        2. Chuyển kiểu dữ liệu (Giá, Số ghế, Năm SX → int/float)
        3. Làm sạch cột 'Km đã đi' (bỏ ký tự, chuyển float)
        4. Xử lý NaN theo từng loại xe (cũ/mới)
        5. Điền giá trị thiếu cho Kiểu dáng và Xuất xứ
        6. Tính log_gia và log_km để phục vụ ML

    Args:
        df: DataFrame dữ liệu thô.

    Returns:
        DataFrame đã clean.
    """
    logger.info(f"[TRANSFORM] Bắt đầu làm sạch {len(df)} records...")
    df_clean = df.copy()

    # ---------------------------------------------------------
    # 1. Chuẩn hóa tên cột (map sang tên đơn giản hơn nếu cần)
    # ---------------------------------------------------------
    # Đảm bảo các cột cần thiết tồn tại
    expected_cols = [
        "URL", "Tên xe", "Giá", "Số ghế", "Năm SX",
        "Nhiên liệu", "Kiểu dáng", "Tình trạng",
        "Km đã đi", "Hộp số", "Xuất xứ", "Tỉnh thành", "Ngày đăng",
    ]
    for col in expected_cols:
        if col not in df_clean.columns:
            df_clean[col] = None
            logger.warning(f"[TRANSFORM] Cột '{col}' không tồn tại, tạo cột rỗng.")

    # ---------------------------------------------------------
    # 2. Chuyển kiểu dữ liệu cơ bản
    # ---------------------------------------------------------
    df_clean["Giá"] = pd.to_numeric(df_clean["Giá"], errors="coerce")
    df_clean["Số ghế"] = pd.to_numeric(df_clean["Số ghế"], errors="coerce")
    df_clean["Năm SX"] = pd.to_numeric(df_clean["Năm SX"], errors="coerce")

    # ---------------------------------------------------------
    # 3. Làm sạch cột 'Km đã đi'
    #    Xóa các ký tự: dấu '.', ' ', 'k', 'm' → chuyển sang float
    # ---------------------------------------------------------
    df_clean["Km đã đi"] = (
        df_clean["Km đã đi"]
        .astype(str)
        .str.replace(r"[.\s]", "", regex=True)    # Bỏ dấu chấm và khoảng trắng
        .str.replace(r"km", "", regex=True, case=False)  # Bỏ chữ 'km'
        .str.strip()
        .replace("nan", np.nan)
        .replace("", np.nan)
    )
    df_clean["Km đã đi"] = pd.to_numeric(df_clean["Km đã đi"], errors="coerce")

    null_before = df_clean.isnull().sum()
    logger.info(f"[TRANSFORM] Giá trị NaN trước khi xử lý:\n{null_before[null_before > 0]}")

    # ---------------------------------------------------------
    # 4. Xử lý NaN cột 'Km đã đi' theo loại xe
    #    - Xe mới: km = 0 (chưa đi)
    #    - Xe cũ: điền median của xe cũ có dữ liệu
    # ---------------------------------------------------------
    median_km_old = df_clean.loc[
        df_clean["Tình trạng"] == "Xe cũ", "Km đã đi"
    ].median()
    logger.info(f"[TRANSFORM] Median 'Km đã đi' xe cũ: {median_km_old:,.0f} km")

    # Xe mới thiếu km → 0
    mask_new_null = (df_clean["Tình trạng"] == "Xe mới") & df_clean["Km đã đi"].isnull()
    df_clean.loc[mask_new_null, "Km đã đi"] = 0

    # Xe cũ thiếu km → median
    mask_old_null = (df_clean["Tình trạng"] == "Xe cũ") & df_clean["Km đã đi"].isnull()
    df_clean.loc[mask_old_null, "Km đã đi"] = median_km_old

    # ---------------------------------------------------------
    # 5. Điền NaN cho các cột phân loại bằng mode
    # ---------------------------------------------------------
    for col in ["Xuất xứ", "Kiểu dáng"]:
        if df_clean[col].isnull().any():
            mode_val = df_clean[col].mode()[0]
            df_clean[col] = df_clean[col].fillna(mode_val)
            logger.info(f"[TRANSFORM] Điền NaN '{col}' bằng mode: '{mode_val}'")

    # Loại bỏ các dòng còn thiếu Giá hoặc Năm SX (không thể phục hồi)
    before_drop = len(df_clean)
    df_clean = df_clean.dropna(subset=["Giá", "Năm SX"])
    dropped = before_drop - len(df_clean)
    if dropped > 0:
        logger.warning(f"[TRANSFORM] Đã loại {dropped} dòng thiếu Giá/Năm SX.")

    # ---------------------------------------------------------
    # 6. Feature Engineering: log_gia, log_km
    # ---------------------------------------------------------
    df_clean["log_gia"] = np.log1p(df_clean["Giá"])
    df_clean["log_km"] = np.log1p(df_clean["Km đã đi"])

    logger.info(f"[TRANSFORM] Hoàn tất. Kết quả: {len(df_clean)} records sạch.")
    null_after = df_clean.isnull().sum()
    remaining_nulls = null_after[null_after > 0]
    if not remaining_nulls.empty:
        logger.warning(f"[TRANSFORM] NaN còn lại:\n{remaining_nulls}")

    return df_clean


# ==================================================================
# BƯỚC 3: LOAD
# ==================================================================
def load(raw_df: pd.DataFrame, cleaned_df: pd.DataFrame,
         if_exists: str = ETL_IF_EXISTS) -> None:
    """
    Load dữ liệu vào MySQL.

    Args:
        raw_df: DataFrame dữ liệu thô → bảng raw_cars.
        cleaned_df: DataFrame đã clean → bảng cleaned_cars.
        if_exists: 'append' (thêm, bỏ qua duplicate) hoặc 'replace' (xóa, thêm lại).
    """
    def _add_url_hash(df: pd.DataFrame) -> pd.DataFrame:
        """Tính MD5 của cột URL để dùng làm UNIQUE KEY."""
        df = df.copy()
        df["url_hash"] = df["URL"].apply(
            lambda u: hashlib.md5(str(u).encode()).hexdigest()
        )
        return df

    # Map tên cột DataFrame → tên cột bảng MySQL
    raw_col_map = {
        "URL": "url", "url_hash": "url_hash",
        "Tên xe": "ten_xe", "Giá": "gia",
        "Số ghế": "so_ghe", "Năm SX": "nam_sx", "Nhiên liệu": "nhien_lieu",
        "Kiểu dáng": "kieu_dang", "Tình trạng": "tinh_trang",
        "Km đã đi": "km_da_di", "Hộp số": "hop_so", "Xuất xứ": "xuat_xu",
        "Tỉnh thành": "tinh_thanh", "Ngày đăng": "ngay_dang",
    }
    cleaned_col_map = {
        **raw_col_map,
        "log_gia": "log_gia",
        "log_km": "log_km",
    }

    with DBConnector() as db:
        # Khởi tạo schema (nếu chưa có bảng)
        logger.info(f"[LOAD] Chạy init schema từ {SQL_SCHEMA}...")
        db.execute_sql_file(str(SQL_SCHEMA))

        # Load raw data
        logger.info("[LOAD] Loading raw_cars...")
        raw_with_hash = _add_url_hash(raw_df)
        raw_to_load = raw_with_hash[[c for c in raw_col_map if c in raw_with_hash.columns]].copy()
        raw_to_load.columns = [raw_col_map[c] for c in raw_to_load.columns]
        # Chuyển km_da_di thành string để match kiểu VARCHAR trong raw_cars
        if "km_da_di" in raw_to_load.columns:
            raw_to_load["km_da_di"] = raw_to_load["km_da_di"].astype(str)
        db.load_dataframe(raw_to_load, "raw_cars", if_exists=if_exists)

        # Load cleaned data
        logger.info("[LOAD] Loading cleaned_cars...")
        cleaned_with_hash = _add_url_hash(cleaned_df)
        clean_cols_available = [c for c in cleaned_col_map if c in cleaned_with_hash.columns]
        clean_to_load = cleaned_with_hash[clean_cols_available].copy()
        clean_to_load.columns = [cleaned_col_map[c] for c in clean_to_load.columns]
        db.load_dataframe(clean_to_load, "cleaned_cars", if_exists=if_exists)

    logger.info("[LOAD] Hoàn tất load vào MySQL.")


# ==================================================================
# ORCHESTRATOR: Chạy toàn bộ pipeline
# ==================================================================
def run_pipeline(
    skip_scrape: bool = False,
    old_pages: int = SCRAPER_OLD_CAR_PAGES,
    new_pages: int = SCRAPER_NEW_CAR_PAGES,
    if_exists: str = ETL_IF_EXISTS,
) -> None:
    """
    Chạy toàn bộ ETL pipeline: Extract → Transform → Load.

    Args:
        skip_scrape: True = đọc CSV có sẵn, False = cào mới từ web.
        old_pages: Số trang cào xe cũ (mặc định từ config.py).
        new_pages: Số trang cào xe mới (mặc định từ config.py).
        if_exists: 'append' hoặc 'replace' khi load vào DB.
    """
    logger.info("=" * 60)
    logger.info("BẮT ĐẦU ETL PIPELINE — Car Analytics")
    logger.info("=" * 60)

    # --- EXTRACT ---
    raw_df = extract(skip_scrape=skip_scrape, old_pages=old_pages, new_pages=new_pages)

    # --- TRANSFORM ---
    cleaned_df = transform(raw_df)

    # Lưu CSV processed backup
    cleaned_df.to_csv(PROCESSED_CSV, index=False, encoding="utf-8-sig")
    logger.info(f"[ETL] Đã lưu processed data → {PROCESSED_CSV}")

    # --- LOAD ---
    load(raw_df, cleaned_df, if_exists=if_exists)

    logger.info("=" * 60)
    logger.info("ETL PIPELINE HOÀN TẤT ✓")
    logger.info("=" * 60)


# ==================================================================
# Chạy từ command line
# ==================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ETL Pipeline — Used Car Analytics"
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Bỏ qua bước cào web, đọc CSV có sẵn trong data/raw/car_data.csv",
    )
    parser.add_argument(
        "--old-pages",
        type=int,
        default=SCRAPER_OLD_CAR_PAGES,
        help=f"Số trang cào xe cũ (mặc định từ config.py: {SCRAPER_OLD_CAR_PAGES})",
    )
    parser.add_argument(
        "--new-pages",
        type=int,
        default=SCRAPER_NEW_CAR_PAGES,
        help=f"Số trang cào xe mới (mặc định từ config.py: {SCRAPER_NEW_CAR_PAGES})",
    )
    parser.add_argument(
        "--if-exists",
        choices=["append", "replace"],
        default=ETL_IF_EXISTS,
        help="Hành động khi bảng đã có dữ liệu: append (thêm) hoặc replace (xóa, tạo lại)",
    )

    args = parser.parse_args()
    run_pipeline(
        skip_scrape=args.skip_scrape,
        old_pages=args.old_pages,
        new_pages=args.new_pages,
        if_exists=args.if_exists,
    )
