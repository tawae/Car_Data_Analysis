# Car Market Analysis & Segmentation using K-Means Clustering

> **Course:** Introduction to Data Science  
> **Institution:** Posts and Telecommunications Institute of Technology (PTIT)  
> **Instructor:** ThS. Vu Hoai Thu  

## Overview

In the rapidly growing automotive market, pricing strategies and market segmentation are crucial for both buyers and sellers. This project aims to automate the process of collecting car data from **oto.com.vn** (one of Vietnam's largest car listing platforms) and applying **Unsupervised Machine Learning (K-Means Clustering)** to identify distinct market segments.

The system scrapes raw data, processes and cleans it, performs exploratory data analysis (EDA), and groups cars into clusters based on key features like price, manufacturing year, and mileage.


## Tech Stack & Tools

* **Language:** Python 3.x
* **Data Acquisition:** `Requests`, `BeautifulSoup4`, `html5lib`
* **Data Manipulation:** `Pandas`, `NumPy`
* **Visualization:** `Matplotlib`, `Seaborn`
* **Machine Learning:** `Scikit-learn` (K-Means, Silhouette Score, RobustScaler)

## Dataset

The data was scraped dynamically from `oto.com.vn`.
* **Total Records:** ~3,000 car listings (Raw data).
* **Key Features Collected:**
    * `Name`: Car model and make.
    * `Price`: Listing price (in VND).
    * `Year`: Year of manufacture.
    * `Mileage`: Km driven.
    * `Origin`: Domestic or Imported.
    * `Gearbox`: Automatic or Manual.
    * `Fuel`: Petrol, Diesel, Hybrid, or Electric.
    * `Style`: Sedan, SUV, Hatchback, etc.

## Project Pipeline

### 1. Data Acquisition (Web Scraping)
We built a scraper using `requests` and `BeautifulSoup` to iterate through pages of used and new cars. The script handles:
* Extraction of detailed attributes from HTML.
* Random sleep intervals to mimic human behavior.
* Exporting raw data to CSV (`car_data.csv`).

### 2. Data Preprocessing
Raw data is rarely ready for modeling. We performed:
* **Cleaning:** Removing non-numeric characters from mileage and price.
* **Handling Missing Values:** Imputing missing `Mileage`, `Origin`, and `Style` using median and mode strategies based on car condition (New/Old).
* **Feature Engineering:** Log-transformation of `Price` and `Mileage` to handle skewness.
* **Scaling:** Applied `RobustScaler` to mitigate the impact of outliers (e.g., luxury supercars).

### 3. Exploratory Data Analysis (EDA)
We used visualization to understand market trends:
* **Price Distribution:** Visualized using Histograms and Boxplots.
* **Correlation Heatmap:** To identify relationships between variables (e.g., Year vs. Price).
* **Categorical Analysis:** Bar charts for car origin, style, and gearbox types.

### 4. Machine Learning (Clustering)
* **Algorithm:** K-Means Clustering.
* **Optimal K:** Determined using the **Elbow Method** and **Silhouette Analysis**.
* **Result:** The optimal number of clusters was determined to be **K=4**.

## Key Findings & Results

The K-Means algorithm successfully segmented the car market into 4 distinct groups (Clusters):

1.  **Label 0 (Budget/Old Cars):** Low price (< 4 billion VND), high mileage, older manufacturing years. Typically manual transmission.
2.  **Label 2 (Mass-Market/New & Like-New):** Mid-range price, very low mileage, recent production years (2020-2025). This is the largest segment.
3.  **Label 1 (Luxury Cars):** High price range, low mileage, imported origin.
4.  **Label 3 (Super Luxury):** Extremely high price, distinct outliers in terms of value.

## Future Improvements

* **Advanced NLP:** Use Natural Language Processing to extract more features from car descriptions.
* **Hybrid Models:** Combine K-Means with Hierarchical Clustering or DBSCAN for better outlier handling.
* **Web App:** Deploy the model as a web application to recommend cars to users based on their budget and preferences.

## Acknowledgments

Special thanks to our instructor, **ThS. Vu Hoai Thu**, for her guidance and feedback throughout this course.

---
*This project is for educational purposes as part of the Data Science curriculum.*
