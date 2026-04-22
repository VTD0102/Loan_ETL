# CreditIntel

He thong ETL va Machine Learning de giam sat danh muc cho vay va du doan rui ro vo no tin dung tren Prosper Loan Dataset.

## Cau truc repo

- `ml_service/`: ma nguon cho Streamlit app va cac entrypoint ETL
- `ml_service/etl/`: cac script ETL Bronze, Silver, Core, Gold
- `ml/`: training, prediction engine, model artifacts
- `database/`: SQL schema va transformation scripts
- `config/`: cau hinh ket noi va tham so he thong
- `docs/`: tai lieu data dictionary, ML, va ke hoach phat trien
- `utils/`: helper dung chung, bao gom ket noi database

## Cong nghe

- Python 3.x
- PostgreSQL
- Streamlit
- Pandas
- scikit-learn
- Plotly
- SQLAlchemy

## Cai dat

1. Tao virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\activate
```

2. Cai dependencies:

```powershell
pip install -r requirements.txt
```

3. Cap nhat thong tin database trong `config/settings.yaml`.

## Khoi tao database

Chay cac script SQL trong thu tu sau:

1. `database/init_database.sql`
2. `database/init_core.sql`

## Chay ETL

Chay tu root cua repo:

```powershell
python -m ml_service.etl.load_bronze
python -m ml_service.etl.etl_silver
python -m ml_service.etl.etl_core
python -m ml_service.etl.etl_gold
```

## Train va predict model

```powershell
python ml/train_model.py
python ml/predict_engine.py 65928
```

## Chay ung dung

```powershell
streamlit run ml_service/app.py
```

## Tai lieu

- [Data Dictionary](docs/data_dictionary/)
- [ML Documentation](docs/ml_md/)
- [Project Planning](docs/overall/)
