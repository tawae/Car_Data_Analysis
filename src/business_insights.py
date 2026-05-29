"""
business_insights.py
--------------------
Reusable analysis helpers for business-oriented used-car insights.

The notebooks keep their exploratory charts, while these functions turn the
same cleaned dataset into decision-focused metrics:
- depreciation curves by model/brand group
- adjusted mileage penalty
- market supply concentration and gaps
- feature premium for origin/transmission
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler


VI_TO_EN_COLUMNS = {
    "URL": "url",
    "Tên xe": "ten_xe",
    "Giá": "gia",
    "Số ghế": "so_ghe",
    "Năm SX": "nam_sx",
    "Nhiên liệu": "nhien_lieu",
    "Kiểu dáng": "kieu_dang",
    "Tình trạng": "tinh_trang",
    "Km đã đi": "km_da_di",
    "Hộp số": "hop_so",
    "Xuất xứ": "xuat_xu",
    "Tỉnh thành": "tinh_thanh",
    "Ngày đăng": "ngay_dang",
    "Nhãn": "cluster",
}

PRICE_BINS_MILLION = [0, 300, 500, 700, 1000, 1500, 3000, np.inf]
PRICE_BAND_LABELS = [
    "<300tr",
    "300-500tr",
    "500-700tr",
    "700tr-1ty",
    "1-1.5ty",
    "1.5-3ty",
    ">3ty",
]

MULTI_WORD_BRANDS = [
    "Mercedes-Benz",
    "Land Rover",
    "Rolls-Royce",
    "Aston Martin",
]

BRAND_GROUPS = {
    "Nhật": [
        "Toyota",
        "Honda",
        "Mazda",
        "Mitsubishi",
        "Lexus",
        "Suzuki",
        "Subaru",
        "Nissan",
        "Isuzu",
        "Infiniti",
    ],
    "Hàn": ["Hyundai", "Kia", "Genesis"],
    "Việt": ["VinFast", "Thaco"],
    "Âu": [
        "Mercedes-Benz",
        "BMW",
        "Audi",
        "Volkswagen",
        "Volvo",
        "Peugeot",
        "Porsche",
        "Land Rover",
        "MINI",
        "Mini",
        "Maserati",
        "Bentley",
        "Rolls-Royce",
        "Jaguar",
    ],
    "Mỹ": ["Ford", "Chevrolet", "Jeep"],
    "Trung Quốc": [
        "MG",
        "BYD",
        "Geely",
        "Lynk",
        "Omoda",
        "Jaecoo",
        "GAC",
        "Haval",
        "Chery",
        "Wuling",
        "Hongqi",
        "Baic",
    ],
}

MODEL_PATTERNS = [
    r"^(Toyota\s+Vios)",
    r"^(Toyota\s+Fortuner)",
    r"^(Toyota\s+Innova)",
    r"^(Toyota\s+Corolla Cross)",
    r"^(Toyota\s+Camry)",
    r"^(Honda\s+City)",
    r"^(Honda\s+CR-V)",
    r"^(Honda\s+HR-V)",
    r"^(Honda\s+Civic)",
    r"^(Hyundai\s+Accent)",
    r"^(Hyundai\s+Santa Fe)",
    r"^(Hyundai\s+Grand i10)",
    r"^(Hyundai\s+Kona)",
    r"^(Hyundai\s+Creta)",
    r"^(Kia\s+Morning)",
    r"^(Kia\s+Seltos)",
    r"^(Kia\s+Sonet)",
    r"^(Kia\s+K3)",
    r"^(Kia\s+Carnival)",
    r"^(Mazda\s+CX-5)",
    r"^(Mazda\s+CX-8)",
    r"^(Mazda\s+3)",
    r"^(Mazda\s+2)",
    r"^(Mazda\s+6)",
    r"^(Ford\s+Everest)",
    r"^(Ford\s+Ranger)",
    r"^(Ford\s+Territory)",
    r"^(Ford\s+Transit)",
    r"^(Mitsubishi\s+Xpander)",
    r"^(VinFast\s+VF\s*3)",
    r"^(VinFast\s+VF\s*5)",
    r"^(VinFast\s+VF\s*6)",
    r"^(VinFast\s+VF\s*7)",
    r"^(VinFast\s+VF\s*8)",
    r"^(VinFast\s+LUX\s+A2\.0)",
    r"^(Mercedes-Benz\s+GLC)",
    r"^(Mercedes-Benz\s+C\d{2,3})",
    r"^(Mercedes-Benz\s+C)",
    r"^(Mercedes-Benz\s+E)",
    r"^(BMW\s+X\d)",
    r"^(Lexus\s+RX)",
    r"^(MG\s+ZS)",
]


def standardize_car_columns(df: pd.DataFrame, ref_year: int | None = None) -> pd.DataFrame:
    """Normalize column names and add reusable business-analysis features."""
    data = df.rename(columns=VI_TO_EN_COLUMNS).copy()

    if "id" not in data.columns:
        data.insert(0, "id", np.arange(1, len(data) + 1))

    for col in ["gia", "so_ghe", "nam_sx", "km_da_di", "log_gia", "log_km"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")

    if "log_gia" not in data.columns and "gia" in data.columns:
        data["log_gia"] = np.log1p(data["gia"])
    if "log_km" not in data.columns and "km_da_di" in data.columns:
        data["log_km"] = np.log1p(data["km_da_di"])

    data["ten_xe"] = data["ten_xe"].fillna("").astype(str)
    data["brand"] = data["ten_xe"].apply(extract_brand)
    data["model_line"] = data["ten_xe"].apply(extract_model_line)
    data["brand_group"] = data["brand"].apply(assign_brand_group)

    if ref_year is None:
        ref_year = int(data["nam_sx"].max())
    data["age"] = ref_year - data["nam_sx"]
    data["gia_trieu"] = data["gia"] / 1_000_000
    data["price_band"] = pd.cut(
        data["gia_trieu"],
        bins=PRICE_BINS_MILLION,
        labels=PRICE_BAND_LABELS,
        include_lowest=True,
    )
    return data


def extract_brand(name: str) -> str:
    """Extract brand from the listing title."""
    for brand in MULTI_WORD_BRANDS:
        if str(name).startswith(brand):
            return brand
    parts = str(name).split()
    return parts[0] if parts else "Khác"


def assign_brand_group(brand: str) -> str:
    for group, brands in BRAND_GROUPS.items():
        if brand in brands:
            return group
    return "Khác"


def extract_model_line(name: str) -> str:
    """Extract a stable model line such as Toyota Vios or Ford Ranger."""
    normalized = re.sub(r"\s+", " ", str(name)).strip()
    for pattern in MODEL_PATTERNS:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()

    parts = normalized.split()
    return " ".join(parts[:2]) if len(parts) >= 2 else normalized


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    values = pd.to_numeric(values, errors="coerce")
    weights = pd.to_numeric(weights, errors="coerce")
    mask = values.notna() & weights.notna() & (weights > 0)
    if not mask.any():
        return np.nan
    return float(np.average(values[mask], weights=weights[mask]))


def _trim_numeric(
    data: pd.DataFrame,
    col: str,
    lower: float = 0.01,
    upper: float = 0.99,
) -> pd.DataFrame:
    lo, hi = data[col].quantile([lower, upper])
    return data[(data[col] >= lo) & (data[col] <= hi)].copy()


def _show_or_close(fig) -> None:
    """Show figures in notebooks, close them in headless test runs."""
    if "agg" in plt.get_backend().lower():
        plt.close(fig)
    else:
        plt.show()


def _fit_log_price_by_age(yearly: pd.DataFrame) -> float:
    slope, _ = np.polyfit(yearly["age"], np.log(yearly["median_price_million"]), 1)
    return float(1 - np.exp(slope))


def compute_depreciation(
    df: pd.DataFrame,
    min_records: int = 18,
    min_years: int = 4,
    max_age: int = 20,
    min_age_bin_records: int = 2,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Estimate annual depreciation from cross-sectional listing prices."""
    data = standardize_car_columns(df) if "model_line" not in df.columns else df.copy()
    used = data[
        (data["tinh_trang"] == "Xe cũ")
        & (data["gia"] > 0)
        & (data["age"].between(0, max_age))
    ].copy()
    used = _trim_numeric(used, "gia")

    curves = (
        used.groupby(["model_line", "age"], observed=True)
        .agg(
            median_price_million=("gia_trieu", "median"),
            n=("id", "count"),
            year=("nam_sx", "median"),
        )
        .reset_index()
    )
    curves["is_supported"] = curves["n"] >= min_age_bin_records

    model_rows = []
    for model, grp in used.groupby("model_line"):
        if len(grp) < min_records or grp["nam_sx"].nunique() < min_years:
            continue
        yearly = (
            grp.groupby("age", observed=True)["gia_trieu"]
            .agg(median_price_million="median", n="count")
            .reset_index()
        )
        yearly = yearly[yearly["n"] >= min_age_bin_records]
        if len(yearly) < min_years or (yearly["median_price_million"] <= 0).any():
            continue
        dep_rate = _fit_log_price_by_age(yearly)
        model_rows.append(
            {
                "model_line": model,
                "n": len(grp),
                "so_nam": grp["nam_sx"].nunique(),
                "annual_depreciation_pct": dep_rate * 100,
                "median_price_million": grp["gia_trieu"].median(),
                "min_age": grp["age"].min(),
                "max_age": grp["age"].max(),
            }
        )

    group_rows = []
    for group, grp in used.groupby("brand_group"):
        if group == "Khác" or len(grp) < 50 or grp["age"].nunique() < min_years:
            continue
        yearly = (
            grp[grp["age"].between(0, 10)]
            .groupby("age", observed=True)["gia_trieu"]
            .agg(median_price_million="median", n="count")
            .reset_index()
        )
        yearly = yearly[yearly["n"] >= min_age_bin_records]
        if len(yearly) < min_years or (yearly["median_price_million"] <= 0).any():
            continue
        dep_rate = _fit_log_price_by_age(yearly)
        group_rows.append(
            {
                "brand_group": group,
                "n": len(grp),
                "so_moc_tuoi": grp["age"].nunique(),
                "annual_depreciation_pct": dep_rate * 100,
                "median_price_million": grp["gia_trieu"].median(),
            }
        )

    brand_rows = []
    for brand, grp in used.groupby("brand"):
        if brand == "Khác" or len(grp) < 35 or grp["age"].nunique() < min_years:
            continue
        yearly = (
            grp[grp["age"].between(0, 12)]
            .groupby("age", observed=True)["gia_trieu"]
            .agg(median_price_million="median", n="count")
            .reset_index()
        )
        yearly = yearly[yearly["n"] >= min_age_bin_records]
        if len(yearly) < min_years or (yearly["median_price_million"] <= 0).any():
            continue
        dep_rate = _fit_log_price_by_age(yearly)
        brand_rows.append(
            {
                "brand": brand,
                "brand_group": grp["brand_group"].mode().iloc[0],
                "n": len(grp),
                "so_moc_tuoi": grp["age"].nunique(),
                "annual_depreciation_pct": dep_rate * 100,
                "median_price_million": grp["gia_trieu"].median(),
            }
        )

    model_summary = pd.DataFrame(model_rows).sort_values(
        "annual_depreciation_pct", ascending=False
    )
    group_summary = pd.DataFrame(group_rows).sort_values(
        "annual_depreciation_pct", ascending=False
    )
    brand_summary = pd.DataFrame(brand_rows).sort_values(
        "annual_depreciation_pct", ascending=False
    )
    return model_summary, group_summary, brand_summary, curves


def plot_depreciation(
    model_summary: pd.DataFrame,
    group_summary: pd.DataFrame,
    brand_summary: pd.DataFrame,
    curves: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    """Plot model depreciation curves and brand-group annual depreciation."""
    output_path = Path(output_path)
    fig_height = max(5.8, 1.8 + len(brand_summary) * 0.42)
    fig, axes = plt.subplots(1, 3, figsize=(21, fig_height))

    preferred = [
        "Toyota Vios",
        "Hyundai Accent",
        "Mazda CX-5",
        "Ford Everest",
        "Mercedes-Benz C200",
        "Mercedes-Benz C300",
    ]
    available = [m for m in preferred if m in set(curves["model_line"])]
    if len(available) < 4 and not model_summary.empty:
        extra = model_summary.sort_values("n", ascending=False)["model_line"].head(6).tolist()
        available = list(dict.fromkeys(available + extra))[:6]

    line_data = curves[
        curves["model_line"].isin(available)
        & curves["age"].between(0, 12)
        & curves["is_supported"]
    ]
    sns.lineplot(
        data=line_data,
        x="age",
        y="median_price_million",
        hue="model_line",
        marker="o",
        ax=axes[0],
    )
    axes[0].set_title("Đường cong giá theo tuổi xe", fontweight="bold")
    axes[0].set_xlabel("Tuổi xe (chỉ vẽ mốc có >=2 tin)")
    axes[0].set_ylabel("Giá trung vị (triệu VND)")
    axes[0].legend(title="Dòng xe", fontsize=8)

    group_plot = group_summary.sort_values("annual_depreciation_pct", ascending=True)
    axes[1].barh(
        group_plot["brand_group"],
        group_plot["annual_depreciation_pct"],
        color=sns.color_palette("viridis", len(group_plot)),
    )
    axes[1].set_title("Tốc độ khấu hao theo nhóm hãng", fontweight="bold")
    axes[1].set_xlabel("Khấu hao ước tính mỗi năm (%)")
    axes[1].set_ylabel("")
    for i, val in enumerate(group_plot["annual_depreciation_pct"]):
        axes[1].text(val + 0.3, i, f"{val:.1f}%", va="center", fontsize=9)

    brand_plot = brand_summary.sort_values("annual_depreciation_pct", ascending=True)
    axes[2].barh(
        brand_plot["brand"],
        brand_plot["annual_depreciation_pct"],
        color=sns.color_palette("crest", len(brand_plot)),
    )
    axes[2].set_title("Tốc độ khấu hao theo hãng", fontweight="bold")
    axes[2].set_xlabel("Khấu hao ước tính mỗi năm (%)")
    axes[2].set_ylabel("")
    for i, val in enumerate(brand_plot["annual_depreciation_pct"]):
        axes[2].text(val + 0.3, i, f"{val:.1f}%", va="center", fontsize=9)

    plt.tight_layout()
    fig.savefig(output_path, bbox_inches="tight", dpi=150)
    _show_or_close(fig)
    return output_path


def _dense_onehot_encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:  # scikit-learn < 1.2
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def compute_mileage_penalty(df: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """Estimate price penalty per 10,000 km after controlling for basic features."""
    data = standardize_car_columns(df) if "age" not in df.columns else df.copy()
    model_data = data[
        (data["tinh_trang"] == "Xe cũ")
        & (data["km_da_di"] > 0)
        & (data["age"].between(0, 20))
    ].copy()
    model_data = _trim_numeric(model_data, "gia")
    model_data = model_data[
        model_data["km_da_di"] <= model_data["km_da_di"].quantile(0.99)
    ].copy()
    model_data["km_10k"] = model_data["km_da_di"] / 10_000

    numeric_features = ["age", "km_10k", "so_ghe"]
    categorical_features = [
        "model_line",
        "kieu_dang",
        "xuat_xu",
        "hop_so",
        "nhien_lieu",
    ]
    model_data[categorical_features] = model_data[categorical_features].fillna("Không rõ")

    preprocessor = ColumnTransformer(
        [
            ("cat", _dense_onehot_encoder(), categorical_features),
            ("num", "passthrough", numeric_features),
        ]
    )
    reg = Pipeline(
        [
            ("preprocessor", preprocessor),
            ("regressor", LinearRegression()),
        ]
    )

    x = model_data[categorical_features + numeric_features]
    y = model_data["gia_trieu"]
    reg.fit(x, y)
    pred = reg.predict(x)

    feature_names = reg.named_steps["preprocessor"].get_feature_names_out()
    coefficients = dict(zip(feature_names, reg.named_steps["regressor"].coef_))
    km_coef = coefficients.get("num__km_10k", np.nan)
    age_coef = coefficients.get("num__age", np.nan)

    summary = {
        "n": len(model_data),
        "raw_corr_km_price": model_data[["km_da_di", "gia"]].corr().iloc[0, 1],
        "r2": r2_score(y, pred),
        "km_coef_million_per_10k": km_coef,
        "age_coef_million_per_year": age_coef,
        "penalty_million_per_10k": -km_coef,
        "penalty_million_per_year_age": -age_coef,
    }
    return summary, model_data


def plot_mileage_penalty(
    model_data: pd.DataFrame,
    summary: dict,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.6))

    sample = model_data.sample(min(len(model_data), 1400), random_state=42)
    scatter = axes[0].scatter(
        sample["km_da_di"] / 1000,
        sample["gia_trieu"],
        c=sample["age"],
        cmap="mako_r",
        alpha=0.45,
        s=20,
    )
    if sample["km_10k"].nunique() > 1:
        slope, intercept = np.polyfit(sample["km_da_di"] / 1000, sample["gia_trieu"], 1)
        xs = np.linspace(sample["km_da_di"].min() / 1000, sample["km_da_di"].max() / 1000, 100)
        axes[0].plot(xs, slope * xs + intercept, color="#d94801", linewidth=2)
    axes[0].set_title("Giá giảm khi ODO tăng (xe cũ)", fontweight="bold")
    axes[0].set_xlabel("Km đã đi (nghìn km)")
    axes[0].set_ylabel("Giá (triệu VND)")
    fig.colorbar(scatter, ax=axes[0], label="Tuổi xe")

    bars = pd.DataFrame(
        {
            "factor": ["ODO +10.000 km", "Tuổi xe +1 năm"],
            "penalty": [
                summary["penalty_million_per_10k"],
                summary["penalty_million_per_year_age"],
            ],
        }
    )
    sns.barplot(data=bars, x="penalty", y="factor", ax=axes[1], color="#2b8cbe")
    axes[1].axvline(0, color="black", linewidth=1)
    axes[1].set_title("Mức phạt giá đã điều chỉnh", fontweight="bold")
    axes[1].set_xlabel("Giảm giá ước tính (triệu VND)")
    axes[1].set_ylabel("")
    for i, val in enumerate(bars["penalty"]):
        axes[1].text(val + 1, i, f"{val:.1f}", va="center", fontsize=10)

    plt.tight_layout()
    fig.savefig(output_path, bbox_inches="tight", dpi=150)
    _show_or_close(fig)
    return output_path


def _cluster_persona(row: pd.Series) -> str:
    if row["median_price_million"] >= 1500:
        return "Xe mới/premium cao cấp"
    if row["median_year"] >= 2024 and row["median_km"] <= 1000:
        return "Xe mới/phổ thông"
    if row["median_year"] <= 2016 or row["median_km"] >= 90_000:
        return "Xe cũ giá rẻ"
    return "Xe cũ tầm trung"


def compute_market_gap(
    df: pd.DataFrame,
    cluster_col: str | None = None,
    n_clusters: int = 4,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Measure supply concentration by cluster, body style, and price band."""
    data = standardize_car_columns(df) if "price_band" not in df.columns else df.copy()

    if cluster_col and cluster_col in data.columns:
        data["business_cluster"] = data[cluster_col]
    elif "cluster" in data.columns:
        data["business_cluster"] = data["cluster"]
    elif "cluster_label" in data.columns:
        data["business_cluster"] = data["cluster_label"]
    else:
        features = data[["log_gia", "log_km", "nam_sx"]].dropna()
        labels = KMeans(
            n_clusters=n_clusters,
            random_state=random_state,
            n_init=10,
        ).fit_predict(RobustScaler().fit_transform(features))
        data = data.loc[features.index].copy()
        data["business_cluster"] = labels

    total = len(data)
    cluster_summary = (
        data.groupby("business_cluster", observed=True)
        .agg(
            n=("id", "count"),
            median_price_million=("gia_trieu", "median"),
            mean_price_million=("gia_trieu", "mean"),
            median_km=("km_da_di", "median"),
            median_year=("nam_sx", "median"),
            median_seats=("so_ghe", "median"),
            dominant_style=("kieu_dang", lambda s: s.value_counts().idxmax()),
            new_share_pct=("tinh_trang", lambda s: (s == "Xe mới").mean() * 100),
        )
        .reset_index()
    )
    cluster_summary["share_pct"] = cluster_summary["n"] / total * 100
    cluster_summary["persona"] = cluster_summary.apply(_cluster_persona, axis=1)
    cluster_summary = cluster_summary.sort_values("share_pct", ascending=False)

    segment_summary = (
        data.groupby(["kieu_dang", "price_band"], observed=True)
        .agg(
            n=("id", "count"),
            median_price_million=("gia_trieu", "median"),
            median_year=("nam_sx", "median"),
            median_km=("km_da_di", "median"),
        )
        .reset_index()
    )
    segment_summary["share_pct"] = segment_summary["n"] / total * 100
    segment_summary = segment_summary.sort_values("n", ascending=False)
    return data, cluster_summary, segment_summary


def plot_market_gap(
    clustered_df: pd.DataFrame,
    cluster_summary: pd.DataFrame,
    segment_summary: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    axes[0].scatter(
        cluster_summary["share_pct"],
        cluster_summary["median_price_million"],
        s=cluster_summary["n"] * 0.35,
        alpha=0.65,
        color="#2b8cbe",
        edgecolor="white",
        linewidth=1.5,
    )
    for _, row in cluster_summary.iterrows():
        axes[0].annotate(
            f"C{int(row['business_cluster'])}\n{row['persona']}",
            (row["share_pct"], row["median_price_million"]),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=8,
        )
    axes[0].set_title("Cụm cung thị trường: đông hay khan?", fontweight="bold")
    axes[0].set_xlabel("Tỷ trọng tin đăng (%)")
    axes[0].set_ylabel("Giá trung vị (triệu VND)")

    top_styles = clustered_df["kieu_dang"].value_counts().head(8).index
    heatmap_data = (
        segment_summary[segment_summary["kieu_dang"].isin(top_styles)]
        .pivot(index="kieu_dang", columns="price_band", values="share_pct")
        .reindex(columns=PRICE_BAND_LABELS)
        .fillna(0)
    )
    sns.heatmap(
        heatmap_data,
        annot=True,
        fmt=".1f",
        cmap="YlGnBu",
        linewidths=0.5,
        ax=axes[1],
        cbar_kws={"label": "Tỷ trọng tin đăng (%)"},
    )
    axes[1].set_title("Nguồn cung theo kiểu dáng x tầm giá", fontweight="bold")
    axes[1].set_xlabel("Tầm giá")
    axes[1].set_ylabel("Kiểu dáng")

    plt.tight_layout()
    fig.savefig(output_path, bbox_inches="tight", dpi=150)
    _show_or_close(fig)
    return output_path


def compute_feature_premium(
    df: pd.DataFrame,
    feature_col: str,
    premium_value: str,
    base_value: str,
    group_cols: Iterable[str] = ("model_line", "nam_sx"),
    min_each: int = 2,
) -> pd.DataFrame:
    """Compare median prices within same model-year while varying one feature."""
    data = standardize_car_columns(df) if "model_line" not in df.columns else df.copy()
    rows = []
    group_cols = list(group_cols)
    for keys, grp in data.groupby(group_cols, observed=True):
        counts = grp[feature_col].value_counts()
        if premium_value not in counts or base_value not in counts:
            continue
        if counts[premium_value] < min_each or counts[base_value] < min_each:
            continue
        med = grp.groupby(feature_col, observed=True)["gia_trieu"].median()
        premium_price = med[premium_value]
        base_price = med[base_value]
        if base_price <= 0:
            continue
        row = dict(zip(group_cols, keys if isinstance(keys, tuple) else (keys,)))
        row.update(
            {
                "n": len(grp),
                "premium_pct": (premium_price / base_price - 1) * 100,
                "premium_price_million": premium_price,
                "base_price_million": base_price,
                "premium_value": premium_value,
                "base_value": base_value,
            }
        )
        rows.append(row)

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result.attrs["weighted_premium_pct"] = weighted_mean(result["premium_pct"], result["n"])
    return result.sort_values("n", ascending=False)


def plot_feature_premium(
    origin_premium: pd.DataFrame,
    transmission_premium: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    for ax, data, title in [
        (axes[0], origin_premium, "Premium nhập khẩu so với trong nước"),
        (axes[1], transmission_premium, "Premium số tự động so với số sàn"),
    ]:
        if data.empty:
            ax.text(0.5, 0.5, "Không đủ cặp so sánh", ha="center", va="center")
            ax.set_axis_off()
            continue
        plot_data = data.head(10).copy()
        plot_data["label"] = (
            plot_data["model_line"]
            + " "
            + plot_data["nam_sx"].astype(str)
            + " (n="
            + plot_data["n"].astype(str)
            + ")"
        )
        sns.barplot(
            data=plot_data,
            x="premium_pct",
            y="label",
            hue="label",
            legend=False,
            ax=ax,
            palette="coolwarm",
        )
        ax.axvline(0, color="black", linewidth=1)
        min_val = min(0, plot_data["premium_pct"].min())
        max_val = max(0, plot_data["premium_pct"].max())
        pad = max((max_val - min_val) * 0.12, 3)
        ax.set_xlim(min_val - pad, max_val + pad)
        label_offset = pad * 0.08
        for patch, value in zip(ax.patches, plot_data["premium_pct"]):
            y = patch.get_y() + patch.get_height() / 2
            if value >= 0:
                x = value + label_offset
                ha = "left"
            else:
                x = value - label_offset
                ha = "right"
            ax.text(x, y, f"{value:.1f}%", va="center", ha=ha, fontsize=9)
        weighted = data.attrs.get("weighted_premium_pct", np.nan)
        ax.set_title(f"{title}\nBình quân trọng số: {weighted:.1f}%", fontweight="bold")
        ax.set_xlabel("Chênh lệch giá trung vị (%)")
        ax.set_ylabel("")

    plt.tight_layout()
    fig.savefig(output_path, bbox_inches="tight", dpi=150)
    _show_or_close(fig)
    return output_path
