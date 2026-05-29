# Used Car Analytics — Phân tích thị trường xe Việt Nam với ETL Pipeline

> **Môn học:** Nhập môn Khoa học Dữ liệu  
> **Trường:** Học viện Công nghệ Bưu chính Viễn thông (PTIT)  
> **Giảng viên:** ThS. Vũ Hoài Thu

---

## Tổng quan

Dự án phân tích thị trường xe đã qua sử dụng tại Việt Nam từ dữ liệu cào trên **oto.com.vn**, áp dụng quy trình ETL chuẩn và thuật toán **K-Means Clustering** để phân khúc thị trường.

## Kiến trúc dự án

```
Car_Data_Analysis/
│
├── data/                   # Dữ liệu CSV (backup khi DB sập)
│   ├── raw/                # Dữ liệu thô từ scraper
│   └── processed/          # Dữ liệu đã làm sạch + plots
│
├── sql/
│   └── init_schema.sql     # CREATE TABLE raw_cars, cleaned_cars
│
├── src/                    # Mã nguồn Python
│   ├── __init__.py
│   ├── config.py           # File cấu hình trung tâm (số trang, sleep, timeout)
│   ├── db_connector.py     # Class quản lý kết nối MySQL
│   ├── scraper.py          # Cào dữ liệu từ oto.com.vn
│   └── etl_pipeline.py     # Orchestrate Extract → Transform → Load
│
├── notebooks/
│   ├── 01_eda.ipynb        # EDA: kết nối DB → SELECT → visualize
│   └── 02_kmeans_model.ipynb  # ML: SELECT → K-Means → lưu labels vào DB
│
├── .env                    # MySQL credentials (không commit)
├── .gitignore
├── requirements.txt
└── README.md
```

## Luồng ETL

```
[oto.com.vn]
     │ scraper.py (requests + BeautifulSoup)
     ▼
[data/raw/car_data.csv]  ←── backup CSV
     │ etl_pipeline.py (transform)
     ▼
[MySQL: raw_cars]        ←── dữ liệu thô
     │ etl_pipeline.py (clean + feature engineering)
     ▼
[MySQL: cleaned_cars]    ←── dữ liệu đã clean
     │
     ├── 01_eda.ipynb   → EDA & Visualization
     └── 02_kmeans.ipynb → Clustering + UPDATE cluster_label
```

## Cài đặt

### 1. Clone & cài dependencies

```bash
git clone <repo-url>
cd Car_Data_Analysis
pip install -r requirements.txt
```

### 2. Cấu hình MySQL

Tạo file `.env` (hoặc chỉnh sửa file có sẵn):

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=car_analytics
```

> ⚠️ File `.env` đã được thêm vào `.gitignore`, không bao giờ commit file này.

### 3. Khởi tạo Database Schema

```bash
mysql -u root -p < sql/init_schema.sql
```

Hoặc schema sẽ tự động được chạy khi bắt đầu ETL pipeline.

### 4. Chạy ETL Pipeline

Có thể cấu hình số trang cào thông qua file `src/config.py`.

```bash
# Cào dữ liệu mới từ oto.com.vn (bỏ qua xe trùng lặp) + load vào MySQL
python -m src.etl_pipeline

# Cào với số trang tùy chỉnh (override config)
python -m src.etl_pipeline --old-pages 10 --new-pages 5

# Dùng CSV có sẵn (bỏ qua bước cào web)
python -m src.etl_pipeline --skip-scrape

# Xóa toàn bộ data cũ trong DB và load lại hoàn toàn
python -m src.etl_pipeline --skip-scrape --if-exists replace
```

### 5. Mở Notebooks

```bash
jupyter notebook notebooks/
```

Chạy theo thứ tự:
1. `01_eda.ipynb` — Phân tích khám phá dữ liệu (EDA)
2. `02_kmeans_model.ipynb` — Phân cụm K-Means

> 💡 **Lưu ý:** Tất cả biểu đồ từ notebook sẽ được tự động xuất ra thư mục `output/`.

## Tech Stack

| Thành phần | Công nghệ |
|---|---|
| Web Scraping | `requests`, `BeautifulSoup4`, `html5lib` |
| Database | MySQL + `mysql-connector-python` |
| Data Processing | `pandas`, `numpy` |
| Machine Learning | `scikit-learn` (KMeans, RobustScaler, Silhouette) |
| Visualization | `matplotlib`, `seaborn` |
| Config | `python-dotenv` |

## Mô tả Database

### Bảng `raw_cars`
Lưu dữ liệu thô cào từ oto.com.vn, không qua xử lý.

| Cột | Kiểu | Mô tả |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primary key |
| `url` | TEXT | URL bài đăng |
| `url_hash` | CHAR(32) | MD5 Hash của URL (Dùng làm UNIQUE KEY chống trùng lặp) |
| `ten_xe` | VARCHAR(255) | Tên xe |
| `gia` | BIGINT | Giá (VND) |
| `so_ghe` | INT | Số ghế |
| `nam_sx` | INT | Năm sản xuất |
| `nhien_lieu` | VARCHAR(50) | Nhiên liệu |
| `kieu_dang` | VARCHAR(50) | Kiểu dáng |
| `tinh_trang` | VARCHAR(20) | Xe cũ / Xe mới |
| `km_da_di` | VARCHAR(30) | Km đã đi (dạng text thô) |
| `hop_so` | VARCHAR(30) | Hộp số |
| `xuat_xu` | VARCHAR(50) | Xuất xứ |
| `tinh_thanh` | VARCHAR(100) | Tỉnh thành |
| `scraped_at` | TIMESTAMP | Thời điểm cào |

### Bảng `cleaned_cars`
Dữ liệu đã làm sạch và chuẩn hóa, phục vụ phân tích.

Bổ sung thêm các cột:
- `km_da_di`: FLOAT (đã chuyển từ text sang số)
- `log_gia`: Log biến đổi của giá
- `log_km`: Log biến đổi của km
- `cluster_label`: Nhãn cụm K-Means (NULL trước khi chạy notebook 02)

## Kết quả Phân tích & K-Means Clustering

Sau khi chạy mô hình K-Means trên ~3000 mẫu xe, thuật toán tìm ra **K = 4** là số cụm tối ưu nhất (dựa trên Silhouette Score và Elbow Method). 

Thị trường xe được phân thành 4 phân khúc chính với đặc trưng rõ rệt như sau:

| Cluster | Đặc trưng | Phân tích chi tiết |
|---|---|---|
| **Cluster 0** | **Xe lướt / Xe mới phổ thông** | Giá trung bình khá cao (~3.7 tỷ), km cực thấp (~8.500 km), đời mới nhất (~2023.7). Chiếm số lượng lớn. |
| **Cluster 1** | **Xe cũ giá rẻ (Cỏ)** | Xe đời sâu (~2012), ODO rất cao (>116.000 km), giá cực rẻ (~300 triệu). Phù hợp cho người mới lái hoặc chạy dịch vụ giá rẻ. |
| **Cluster 2** | **Xe phổ thông chạy lướt (Quốc dân)**| Mẫu xe tầm trung phổ biến, giá vừa phải (~670 triệu), ODO gần như bằng 0 (xe mới tinh), đời 2024-2025. Đây là phân khúc đông nhất (~1145 xe). |
| **Cluster 3** | **Xe cũ tầm trung** | Xe đời 2020, đã qua sử dụng ổn định (~62.000 km), giá khoảng 710 triệu. Lý tưởng cho các gia đình mua xe cũ chất lượng tốt. |

*Lưu ý: Bạn có thể xem hình ảnh trực quan chi tiết về độ phân tán, Silhouette plot, cũng như biểu đồ EDA trong thư mục `output/`.*

## Business Insights bổ sung

Ngoài các biểu đồ EDA, notebook đã bổ sung nhóm biểu đồ phục vụ quyết định kinh doanh cho showroom xe cũ:

| Vấn đề kinh doanh | Insight từ dữ liệu hiện có | Hàm ý hành động |
|---|---|---|
| **Tốc độ khấu hao** | Theo dữ liệu listing, nhóm xe Mỹ và Âu đang có tốc độ khấu hao ước tính cao nhất (~12.6% và ~11.2%/năm), trong khi nhóm xe Nhật thấp hơn (~4.9%/năm). Khi tính theo từng hãng đủ mẫu, BMW/Kia/Ford/Mercedes-Benz là nhóm khấu hao cao; Honda/VinFast thấp hơn. | Ưu tiên nhập các dòng giữ giá tốt khi cần vòng quay vốn an toàn; ép biên an toàn cao hơn với các dòng/nhóm/hãng khấu hao nhanh. |
| **Mileage Penalty** | Sau khi kiểm soát dòng xe, tuổi xe, kiểu dáng, xuất xứ, hộp số và nhiên liệu, mỗi **10.000 km** làm giảm khoảng **8.2 triệu VND**. | Có thể đưa hệ số ODO vào barem thu mua: `Giá thu mua = Giá trần dòng xe/đời xe - 8.2 triệu * số block 10.000 km`. |
| **Market Gap & Supply Concentration** | Cụm **xe mới/phổ thông** chiếm ~38.7% nguồn cung; phân khúc dày nhất là **SUV 700tr-1 tỷ** (~13.5%) và **SUV 500-700tr** (~10.3%). | Tránh tăng tồn kho ở các vùng quá đông nếu không có lợi thế bán nhanh; theo dõi các phân khúc nguồn cung thấp hơn để tìm cơ hội giữ giá. |
| **Feature Premium** | Xe nhập khẩu có premium bình quân trọng số ~7.3% so với xe trong nước khi so cùng dòng/năm, nhưng không phải dòng nào cũng cao hơn. Xe số tự động có premium ~23.3% so với số sàn. | Không áp premium nhập khẩu cố định cho mọi dòng xe; giữ `xuat_xu` và `hop_so` làm biến định giá khi chốt giá bán ra. |

Các biểu đồ mới:
- `output/business_01_depreciation_curve.png`
- `output/business_02_mileage_penalty.png`
- `output/business_03_feature_premium.png`
- `output/business_04_market_gap_supply.png`

> Lưu ý: Đây là phân tích từ **giá đăng bán** trên oto.com.vn, không phải giá giao dịch cuối cùng. Các hệ số nên được xem là mốc tham chiếu ban đầu và cần hiệu chỉnh thêm bằng dữ liệu bán thực tế nếu showroom có.

---
*Dự án học thuật — PTIT, 2025*
