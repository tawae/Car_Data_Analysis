-- ============================================================
-- SQL Schema: car_analytics
-- Mô tả: Tạo các bảng lưu trữ dữ liệu xe
-- Lưu ý: Database được tạo tự động bởi DBConnector.connect()
--        Chạy file này sau khi đã kết nối vào đúng database
-- Chống duplicate: UNIQUE KEY trên url_hash (MD5 của URL)
-- ============================================================

-- ------------------------------------------------------------
-- Bảng 1: raw_cars
-- Lưu dữ liệu thô cào trực tiếp từ oto.com.vn
-- Không có xử lý, đây là nguồn dữ liệu gốc
-- url_hash: MD5(url) — dùng để phát hiện và bỏ qua duplicate
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_cars (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    url           TEXT            NOT NULL,
    url_hash      CHAR(32)        NOT NULL,             -- MD5(url), dùng để chống duplicate
    ten_xe        VARCHAR(255)    NOT NULL,
    gia           BIGINT          NOT NULL,             -- Đơn vị: VND
    so_ghe        INT,
    nam_sx        INT,
    nhien_lieu    VARCHAR(50),
    kieu_dang     VARCHAR(50),
    tinh_trang    VARCHAR(20),                          -- 'Xe cũ' | 'Xe mới'
    km_da_di      VARCHAR(30),                          -- Dạng text thô, vd: '80.000 km'
    hop_so        VARCHAR(30),
    xuat_xu       VARCHAR(50),
    tinh_thanh    VARCHAR(100),
    ngay_dang     VARCHAR(20),                          -- Dạng text thô, vd: '12/07/2025'
    scraped_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_url_hash (url_hash),                 -- Chống insert duplicate
    INDEX idx_tinh_trang (tinh_trang),
    INDEX idx_nam_sx (nam_sx)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Bảng 2: cleaned_cars
-- Lưu dữ liệu đã được làm sạch và chuẩn hóa từ ETL pipeline
-- Đây là nguồn dữ liệu cho EDA và ML
-- url_hash: MD5(url) — sync với raw_cars để chống duplicate
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cleaned_cars (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    url             TEXT,
    url_hash        CHAR(32)        NOT NULL,           -- MD5(url), dùng để chống duplicate
    ten_xe          VARCHAR(255)    NOT NULL,
    gia             BIGINT          NOT NULL,           -- Đơn vị: VND
    so_ghe          INT,
    nam_sx          INT,
    nhien_lieu      VARCHAR(50),
    kieu_dang       VARCHAR(50),
    tinh_trang      VARCHAR(20),
    km_da_di        FLOAT,                              -- Đã chuyển thành số (km)
    hop_so          VARCHAR(30),
    xuat_xu         VARCHAR(50),
    tinh_thanh      VARCHAR(100),
    ngay_dang       VARCHAR(20),
    -- Cột bổ sung cho Machine Learning
    log_gia         FLOAT,                              -- log(gia) để xử lý skewness
    log_km          FLOAT,                              -- log(km_da_di + 1)
    cluster_label   INT DEFAULT NULL,                  -- Nhãn cụm K-Means (cập nhật sau)
    loaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_url_hash (url_hash),                 -- Chống insert duplicate
    INDEX idx_tinh_trang (tinh_trang),
    INDEX idx_nam_sx (nam_sx),
    INDEX idx_cluster (cluster_label)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
