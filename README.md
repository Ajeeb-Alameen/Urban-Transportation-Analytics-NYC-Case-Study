# Urban Transportation Analytics – NYC Case Study

This project is the final capstone for the German University in Cairo's Postgraduate Diploma in Data Science. It presents a production-grade data pipeline covering ingestion, warehousing, analysis, modeling, and visualization of multimodal New York City transportation data (taxis, buses, subways).

## 🚦 Project Overview

This project focuses on identifying traffic trends, accessibility gaps, and fare patterns in New York City through multimodal transportation data. The pipeline supports:

- Ingestion of large-scale raw trip data (2024-focused, 100M+ records)
- Automated preprocessing and data cleaning
- Centralized data warehousing using PostgreSQL
- Machine learning model training, validation, and evaluation
- Data visualization via interactive dashboards using Apache Superset

## 🏗️ Architecture

The project leverages a modern data engineering and ML stack:

- **Jupyter Notebooks**: EDA and feature engineering
- **Apache Airflow**: ETL workflow orchestration
- **PostgreSQL**: Centralized data warehouse
- **Docker**: Containerized deployment
- **Pandas, TensorFlow/Keras**: Data processing and modeling
- **Apache Superset**: Dashboarding and BI

## 📂 Project Structure

```
├── Infra/                  # Docker setup and infrastructure
├── Bus_BusLanes/           # Code for Bus and bus lanes datasets
├── Subway/                 # Code for Subway dataset
├── Taxi/                   # Code for Taxi dataset
├── ML_Model/               # ML code for taxi fare prediction
├── Airflow_pipelines/      # DAGs and scripts for ETL
├── Sample_data/            # Sample datasets used in pipeline
├── Capstone Project-NYC Transportation Analysis.pptx  # Slides
└── README.md
```

## 🛠️ How to Run

```bash
# Clone the repository and navigate inside
git clone https://github.com/Ajeeb-Alameen/Urban-Transportation-Analytics-NYC-Case-Study.git
cd Urban-Transportation-Analytics-NYC-Case-Study

# Initialize Postgres and Airflow
bash init.sh build

# Initialize Superset
bash init_superset.sh

# Access local services
# Airflow:     http://localhost:8080
# pgAdmin:     http://localhost:5050
# Superset:    http://localhost:8088

# Shutdown environment
bash shutdown.sh
```

## 🧹 Data Analysis & Preprocessing

Preprocessing was handled via Jupyter notebooks with a focus on creating clean, ML-ready datasets:

- **Exploratory Data Analysis (EDA)**: Identify patterns, outliers, and trends in trip data
- **Data Cleaning**: Remove nulls, outliers, and invalid durations/geolocations
- **Feature Engineering**:
  - Trip duration, average/median speed
  - Time flags (hour, day, weekend)
  - Congestion indicators, vendor mapping
- **Transformation**: Scaling, log transforms, categorical encoding

## 🧠 Machine Learning

Developed and evaluated a Feedforward Neural Network (FFNN) for taxi fare prediction:

- **Feature Engineering**:
  - Dense Features: Numerical, Binary, One-Hot Encoded
  - Embedding Features: RatecodeID, pickup/dropoff zones, payment_type

- **Model Architecture**:
  - 3 hidden layers (ReLU), output layer (linear)
  - Loss: MSE, Optimizer: Adam
  - Trained for 30 epochs with early stopping

- **Performance**:
  - **Test MAE**: $1.72  
  - 80%+ of predictions within 10% error margin  
  - Validation–Test MAE gap: –0.1% (no overfitting)

## 📊 Dashboards

Created dashboards using Apache Superset based on EDA outputs and engineered features:

- Trip duration by time-of-day
- Night vs. day travel patterns
- Congestion flags and trip gaps
- Fare behavior by vendor and service type

## 👥 Authors

- **Abdullah Kamal** – Senior Data Steward, Schneider Electric  
- **Ahmed Abdullah** – Senior Data Analyst, Seoudi Corporate  
- **Adham Abdelhameed ElSharkawy** – Cloud Solution Architect, Microsoft  
- **Ajeeb Alameen** – Senior Data Analyst  
- **Osama ElNaggar** – Data Management Lead, Dana Petroleum  

## 📜 License

This project is licensed under the MIT License.

## 🌐 Public Datasets Used

- [NYC Taxi & Limousine Commission (TLC) Trip Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)  
- [MTA Subway Stations](https://catalog.data.gov/dataset/mta-subway-stations)  
- [NYC DOT Bus Performance Metrics](https://www.nyc.gov/html/dot/html/about/datafeeds)  

---

> This capstone project provides a reusable and modular framework for urban traffic analysis and smart city planning.