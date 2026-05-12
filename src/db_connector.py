"""
db_connector.py
---------------
Quản lý kết nối đến MySQL database.
Đọc credentials từ file .env trong thư mục gốc dự án.

Cách dùng:
    from src.db_connector import DBConnector

    db = DBConnector()
    conn = db.get_connection()
    df = pd.read_sql("SELECT * FROM cleaned_cars", conn)
    db.close()
"""

import os
import mysql.connector
from mysql.connector import Error
from pathlib import Path
from dotenv import load_dotenv

# Load .env từ thư mục gốc project (một cấp trên src/)
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


class DBConnector:
    """
    Class quản lý vòng đời kết nối MySQL.
    Hỗ trợ context manager (with statement).

    Ví dụ:
        with DBConnector() as db:
            conn = db.get_connection()
            ...
    """

    def __init__(self):
        self._config = {
            "host":     os.getenv("DB_HOST", "localhost"),
            "port":     int(os.getenv("DB_PORT", 3306)),
            "user":     os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
            "database": os.getenv("DB_NAME", "car_analytics"),
            "charset":  "utf8mb4",
            "use_unicode": True,
        }
        self._connection = None

    # ------------------------------------------------------------------
    # Kết nối
    # ------------------------------------------------------------------
    def connect(self) -> "DBConnector":
        """
        Tạo kết nối đến MySQL.
        Tự động tạo database nếu chưa tồn tại (CREATE DATABASE IF NOT EXISTS).
        """
        db_name = self._config["database"]

        # Bước 1: Kết nối KHÔNG chỉ định database để có thể tạo nếu chưa có
        config_no_db = {k: v for k, v in self._config.items() if k != "database"}
        try:
            tmp_conn = mysql.connector.connect(**config_no_db)
            cursor = tmp_conn.cursor()
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            tmp_conn.commit()
            cursor.close()
            tmp_conn.close()
        except Error as e:
            raise ConnectionError(
                f"[DB] Không thể kết nối MySQL (bước khởi tạo DB): {e}\n"
                f"Kiểm tra lại host/user/password trong file .env và đảm bảo MySQL đang chạy."
            ) from e

        # Bước 2: Kết nối lại với đúng database
        try:
            self._connection = mysql.connector.connect(**self._config)
            if self._connection.is_connected():
                db_info = self._connection.get_server_info()
                print(f"[DB] Kết nối thành công → MySQL Server {db_info} | DB: {db_name}")
        except Error as e:
            raise ConnectionError(
                f"[DB] Không thể kết nối MySQL: {e}\n"
                f"Kiểm tra lại file .env và đảm bảo MySQL đang chạy."
            ) from e
        return self


    def get_connection(self) -> mysql.connector.MySQLConnection:
        """Trả về đối tượng connection. Tự động kết nối nếu chưa có."""
        if self._connection is None or not self._connection.is_connected():
            self.connect()
        return self._connection

    def close(self):
        """Đóng kết nối."""
        if self._connection and self._connection.is_connected():
            self._connection.close()
            print("[DB] Đã đóng kết nối MySQL.")

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------
    def __enter__(self):
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False  # Không nuốt exception

    # ------------------------------------------------------------------
    # Thực thi SQL
    # ------------------------------------------------------------------
    def execute_sql(self, sql: str, params: tuple = None) -> None:
        """
        Thực thi một câu SQL (CREATE, INSERT, UPDATE, DELETE).

        Args:
            sql: Câu lệnh SQL.
            params: Tuple tham số để tránh SQL injection.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params)
            conn.commit()
        except Error as e:
            conn.rollback()
            raise RuntimeError(f"[DB] Lỗi thực thi SQL: {e}") from e
        finally:
            cursor.close()

    def execute_sql_file(self, sql_file_path: str) -> None:
        """
        Đọc và thực thi toàn bộ file .sql (ví dụ: init_schema.sql).

        Args:
            sql_file_path: Đường dẫn tuyệt đối hoặc tương đối đến file .sql.
        """
        with open(sql_file_path, "r", encoding="utf-8") as f:
            sql_content = f.read()

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Thực thi từng câu lệnh trong file (phân cách bởi ';')
            for statement in sql_content.split(";"):
                stmt = statement.strip()
                if stmt:
                    cursor.execute(stmt)
            conn.commit()
            print(f"[DB] Đã thực thi file SQL: {sql_file_path}")
        except Error as e:
            conn.rollback()
            raise RuntimeError(f"[DB] Lỗi thực thi file SQL: {e}") from e
        finally:
            cursor.close()

    # ------------------------------------------------------------------
    # Load DataFrame vào DB
    # ------------------------------------------------------------------
    def load_dataframe(self, df, table_name: str, if_exists: str = "append") -> int:
        """
        Insert toàn bộ DataFrame vào bảng MySQL.

        Args:
            df: pandas DataFrame cần insert.
            table_name: Tên bảng đích trong database.
            if_exists: 'append' (thêm vào) hoặc 'replace' (xóa bảng cũ, tạo lại).

        Returns:
            Số dòng đã insert thành công.
        """
        import pandas as pd  # noqa: F401

        if df.empty:
            print(f"[DB] DataFrame rỗng, không insert vào '{table_name}'.")
            return 0

        conn = self.get_connection()
        cursor = conn.cursor()

        # Lấy tên cột từ DataFrame
        columns = list(df.columns)
        placeholders = ", ".join(["%s"] * len(columns))
        col_names = ", ".join([f"`{c}`" for c in columns])
        sql = f"INSERT IGNORE INTO `{table_name}` ({col_names}) VALUES ({placeholders})"

        # Chuyển DataFrame sang list of tuples
        data = [
            tuple(None if (isinstance(v, float) and v != v) else v for v in row)
            for row in df.itertuples(index=False, name=None)
        ]

        try:
            if if_exists == "replace":
                cursor.execute(f"TRUNCATE TABLE `{table_name}`")

            cursor.executemany(sql, data)
            conn.commit()
            inserted = cursor.rowcount
            skipped = len(data) - inserted
            if skipped > 0:
                print(f"[DB] Bảng '{table_name}': insert {inserted} dòng mới, bỏ qua {skipped} dòng trùng lặp.")
            else:
                print(f"[DB] Bảng '{table_name}': đã insert {inserted} dòng.")
            return inserted
        except Error as e:
            conn.rollback()
            raise RuntimeError(f"[DB] Lỗi insert vào '{table_name}': {e}") from e
        finally:
            cursor.close()

    def update_cluster_labels(self, ids: list, labels: list) -> None:
        """
        Cập nhật cột cluster_label trong bảng cleaned_cars.

        Args:
            ids: List các ID cần update.
            labels: List nhãn cluster tương ứng.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            data = list(zip(labels, ids))
            cursor.executemany(
                "UPDATE `cleaned_cars` SET `cluster_label` = %s WHERE `id` = %s",
                data
            )
            conn.commit()
            print(f"[DB] Đã cập nhật cluster_label cho {cursor.rowcount} dòng.")
        except Error as e:
            conn.rollback()
            raise RuntimeError(f"[DB] Lỗi update cluster_label: {e}") from e
        finally:
            cursor.close()
