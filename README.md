# CreditIntel: Portfolio Risk Management System

An end-to-end Data Engineering and Machine Learning project that monitors loan portfolios and predicts credit default risks.

## 🚀 Features
- **ETL Pipeline:** Multi-layer architecture (Bronze, Silver, Gold) powered by PostgreSQL.
- **Risk Dashboard:** Interactive visualization of portfolio health, default rates, and income-based risk analysis.
- **AI Predictor:** Machine Learning model (Random Forest) to evaluate real-time credit applications with a built-in Business Rule Engine.
- **Architecture:** Refactored using a modular MVC-lite approach for high maintainability.

## 🛠️ Tech Stack
- **Language:** Python 3.x
- **Database:** PostgreSQL
- **Frontend:** Streamlit
- **Data Science:** Pandas, Scikit-learn, Plotly, SQLAlchemy
- **Environment:** Virtualenv

## ⚙️ Installation & Usage
1. Clone the repository.
2. Create and activate a virtual environment: `python -m venv venv` & `.\venv\Scripts\activate`.
3. Install dependencies: `pip install -r requirements.txt`.
4. Run the ETL pipeline: `python load_bronze.py`, `python etl_silver.py`, `python etl_gold.py`.
5. Train the AI model: `python ml/train_model.py`.
6. Launch the app: `streamlit run app.py`.