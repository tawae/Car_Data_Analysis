"""
scraper.py
----------
Cào dữ liệu xe từ oto.com.vn.
Tách từ notebook gốc, đóng gói thành các hàm có thể tái sử dụng.

Cách dùng từ ETL pipeline:
    from src.scraper import scrape_all
    raw_df = scrape_all(pages=99)

Hoặc chạy độc lập:
    python -m src.scraper
"""

import random
import time
import logging
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.config import (
    SCRAPER_BASE_URL,
    SCRAPER_OLD_CAR_PATTERN,
    SCRAPER_NEW_CAR_PATTERN,
    SCRAPER_SLEEP_MIN,
    SCRAPER_SLEEP_MAX,
    SCRAPER_TIMEOUT,
    SCRAPER_LOG_EVERY,
    SCRAPER_OLD_CAR_PAGES,
    SCRAPER_NEW_CAR_PAGES,
)

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SCRAPER] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Header mặc định
# ------------------------------------------------------------------
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}


# ------------------------------------------------------------------
# Hàm tạo session
# ------------------------------------------------------------------
def _create_session() -> requests.Session:
    """Tạo requests.Session với header mặc định."""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session


# ------------------------------------------------------------------
# Bước 1: Thu thập links
# ------------------------------------------------------------------
def scrape_links(
    session: requests.Session,
    url_pattern: str,
    pages: int = SCRAPER_OLD_CAR_PAGES,
    sleep_min: float = SCRAPER_SLEEP_MIN,
    sleep_max: float = SCRAPER_SLEEP_MAX,
) -> list[str]:
    """
    Thu thập tất cả href link xe từ trang danh sách.

    Args:
        session: requests.Session đã cấu hình.
        url_pattern: URL pattern với placeholder {page}, vd: '.../p{page}'.
        pages: Số trang tối đa cần cào.
        sleep_min/max: Khoảng thời gian nghỉ ngẫu nhiên giữa các request (giây).

    Returns:
        List các relative link xe, vd: ['/mua-ban-xe-toyota-vios/...', ...]
    """
    links = []
    for page in range(1, pages + 1):
        url = url_pattern.format(page=page)
        try:
            resp = session.get(url, timeout=SCRAPER_TIMEOUT)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html5lib")

            car_divs = soup.find_all("div", class_="dev-item-car")
            if not car_divs:
                logger.info(f"Trang {page}: Không tìm thấy xe — kết thúc thu thập links.")
                break

            page_links = []
            for div in car_divs:
                a_tag = div.find("a")
                if a_tag:
                    href = a_tag.get("href", "")
                    if href.startswith("/mua-ban-xe"):
                        page_links.append(href)

            links.extend(page_links)
            logger.info(f"Trang {page}: +{len(page_links)} links (tổng: {len(links)})")

        except requests.exceptions.Timeout:
            logger.warning(f"Trang {page}: Timeout, bỏ qua.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Trang {page}: Lỗi request — {e}")

        time.sleep(random.uniform(sleep_min, sleep_max))

    return links


# ------------------------------------------------------------------
# Bước 2: Cào chi tiết từng xe
# ------------------------------------------------------------------
def scrape_car_details(
    session: requests.Session,
    links: list[str],
    sleep_min: float = SCRAPER_SLEEP_MIN,
    sleep_max: float = SCRAPER_SLEEP_MAX,
    log_every: int = SCRAPER_LOG_EVERY,
) -> list[dict]:
    """
    Cào thông tin chi tiết từng xe từ list links.

    Args:
        session: requests.Session đã cấu hình.
        links: List relative URLs cần cào.
        sleep_min/max: Khoảng nghỉ ngẫu nhiên giữa các request (giây).
        log_every: Ghi log tiến trình mỗi N xe.

    Returns:
        List các dict thông tin xe.
    """
    data = []
    total = len(links)

    for idx, link in enumerate(links, start=1):
        url = SCRAPER_BASE_URL + link
        car_info = {"URL": url}

        try:
            resp = session.get(url, timeout=SCRAPER_TIMEOUT)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html5lib")

            # --- Tên xe ---
            h1 = soup.find("h1", class_="title-detail")
            car_info["Tên xe"] = h1.get_text(strip=True) if h1 else None

            # --- Giá ---
            price_input = soup.find("input", {"id": "hddPrice"})
            car_info["Giá"] = price_input.get("value") if price_input else None

            # --- Số ghế ---
            seat_input = soup.find("input", {"id": "numberOfSeat"})
            car_info["Số ghế"] = seat_input.get("value") if seat_input else None

            # --- Ngày đăng ---
            date_span = soup.find("span", class_="date")
            car_info["Ngày đăng"] = date_span.get_text(strip=True) if date_span else None

            # --- Thông số kỹ thuật từ ul.list-info ---
            for li in soup.select("ul.list-info li"):
                label_tag = li.find("label", class_="label")
                if not label_tag:
                    continue
                label_text = label_tag.get_text(strip=True)
                # Lấy phần giá trị (toàn bộ text của li trừ đi label)
                full_text = li.get_text(strip=True)
                value = full_text.replace(label_text, "").strip()
                # Chuẩn hóa tên cột (bỏ dấu ':')
                col_name = label_text.rstrip(":")
                car_info[col_name] = value

            data.append(car_info)

        except requests.exceptions.Timeout:
            logger.warning(f"[{idx}/{total}] Timeout: {url}")
        except requests.exceptions.RequestException as e:
            logger.error(f"[{idx}/{total}] Lỗi request: {url} — {e}")
        except Exception as e:
            logger.error(f"[{idx}/{total}] Lỗi parse: {url} — {e}")

        if idx % log_every == 0:
            logger.info(f"Tiến trình: {idx}/{total} xe ({idx/total*100:.1f}%)")

        time.sleep(random.uniform(sleep_min, sleep_max))

    logger.info(f"Cào xong: {len(data)}/{total} xe thành công.")
    return data


# ------------------------------------------------------------------
# Hàm tổng hợp: Extract toàn bộ
# ------------------------------------------------------------------
def scrape_all(
    old_pages: int = SCRAPER_OLD_CAR_PAGES,
    new_pages: int = SCRAPER_NEW_CAR_PAGES,
    save_raw_path: Optional[str] = None,
) -> pd.DataFrame:
    """
    Cào toàn bộ xe cũ và xe mới từ oto.com.vn, gộp thành một DataFrame.

    Args:
        old_pages: Số trang tối đa cho xe cũ (mặc định từ config.py: SCRAPER_OLD_CAR_PAGES).
        new_pages: Số trang tối đa cho xe mới (mặc định từ config.py: SCRAPER_NEW_CAR_PAGES).
        save_raw_path: Nếu cung cấp, lưu CSV raw vào đường dẫn này.

    Returns:
        DataFrame gộp cả xe cũ và xe mới (dữ liệu thô, chưa clean).
    """
    session = _create_session()

    # --- XE CŨ ---
    logger.info("=" * 50)
    logger.info("Bắt đầu cào XE CŨ từ oto.com.vn/mua-ban-xe/")
    old_links = scrape_links(session, SCRAPER_OLD_CAR_PATTERN, pages=old_pages)
    logger.info(f"Thu thập được {len(old_links)} link xe cũ. Bắt đầu cào chi tiết...")
    old_data = scrape_car_details(session, old_links)
    old_df = pd.DataFrame(old_data)
    logger.info(f"Xe cũ: {len(old_df)} records")

    # --- XE MỚI ---
    logger.info("=" * 50)
    logger.info("Bắt đầu cào XE MỚI từ oto.com.vn/mua-ban-xe-moi/")
    new_links = scrape_links(session, SCRAPER_NEW_CAR_PATTERN, pages=new_pages)
    logger.info(f"Thu thập được {len(new_links)} link xe mới. Bắt đầu cào chi tiết...")
    new_data = scrape_car_details(session, new_links)
    new_df = pd.DataFrame(new_data)
    logger.info(f"Xe mới: {len(new_df)} records")

    # --- GHÉP LẠI ---
    all_df = pd.concat([old_df, new_df], ignore_index=True)
    logger.info(f"Tổng cộng: {len(all_df)} records")

    # --- LƯU CSV BACKUP ---
    if save_raw_path:
        all_df.to_csv(save_raw_path, index=False, encoding="utf-8-sig")
        logger.info(f"Đã lưu raw data → {save_raw_path}")

    return all_df


# ------------------------------------------------------------------
# Chạy độc lập
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Thêm root vào path để import được src/
    _ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_ROOT))

    from src.config import RAW_CSV  # noqa: E402 (re-import after path fix)

    logger.info("Chạy scraper độc lập...")
    logger.info(f"Cấu hình: xe cũ={SCRAPER_OLD_CAR_PAGES} trang, xe mới={SCRAPER_NEW_CAR_PAGES} trang")
    df = scrape_all(save_raw_path=str(RAW_CSV))
    print(df.head())
    print(f"\nShape: {df.shape}")
