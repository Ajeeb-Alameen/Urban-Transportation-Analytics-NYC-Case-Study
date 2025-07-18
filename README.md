# Metropolitan City Traffic Analysis - Capstone Project

This project is the final capstone for the German University in Cairo's Data Engineering & AI Diploma. It provides a comprehensive end-to-end data pipeline for analyzing urban traffic patterns using real New York City traffic datasets.

## 🚦 Project Overview

We analyze traffic trends in a large metropolitan city using public NYC Taxi datasets (Bus, Subway, Taxi). The pipeline performs:

- Ingestion of large-scale raw data
- Preprocessing & cleaning
- Data warehousing
- Exploratory data analysis (EDA)
- Machine Learning for ride duration prediction
- Dashboarding using Apache Superset

## 🏗️ Architecture

This project leverages a modern data engineering stack:

- **Apache Airflow** – DAG orchestration
- **PostgreSQL** – Data warehouse
- **Docker** – Containerized deployment
- **Pandas, Scikit-learn** – Data processing & ML
- **Apache Superset** – Visualization & BI
- **Jupyter Notebooks** – EDA & experimentation

## 📂 Project Structure

```
├── Infra/                  # Docker setup and infra structure
├── Bus_BusLanes/              # Code for Bus and bus lanes datasets
├── Subway/                  # Code for Subway dataset
├── Taxi/                  # Code for Taxi dataset
├── ML_Model/              # Machine learning Model code for fare predication
├── Airflow_pipelines/          # Dags and python scripts for datasets pipelines
├── Sample_data/              # Data samples to be used with Airflow pipeline dags
├── Capstone Project-NYC Transportation Analysis.pptx              # Small presentation for the project and some analytics
└── README.md
```

## 🛠️ How to Run

1. Clone the repository
2. Ensure Docker is installed
3. From Docker folder Run (add build as bash parameter to rebuild containers):

<pre> ```bash # Initialize Postgress and Airflow services bash init.sh build # Initialize Superset bash init_superset.sh ``` </pre>

4. Access Airflow at: `http://localhost:8080`
5. Access pgadmin at: `http://localhost:5050`
6. Access Superset at: `http://localhost:8088`
5. To shut down all the env. Run:

<pre> ```bash shutdown.sh``` </pre>

## 🧠 Machine Learning

We trained models on Taxi data to predict trip fare using:
- Deep Learning FFNN Model

## 📊 Dashboards

Notebooks code provide key insights to be used on superset dashboard:
- Trip durations over time
- Day vs. night ride trends

## 👥 Authors

- **Abdullah Kamal** - Senior Data Steward - Schneider Electric
- **Ahmed Abdullah** - Senior Data Analyst - Seoudi Corporate
- **Adham Abdelhameed ElSharkawy** – Cloud Solution Architect - Microsoft
- **Ajeeb ElAmeen** - Senior data Analyst
- **Osama ElNaggar** - Data Management Lead - Dana Petroleum

## 📜 License

MIT License

## 🌐 Public Datasets Used

- [NYC Traffic Commission Data](https://www.nyc.gov/html/dot/html/about/datafeeds)
                               (https://catalog.data.gov/dataset/mta-subway-stations)
                               (https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)

---

> This project aims to serve as a reusable and extendable framework for urban mobility and traffic analysis. Contributions welcome!
