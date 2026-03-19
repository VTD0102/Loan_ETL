"""
Data Handler Module
Manages database connections and data retrieval caching for the application.
"""
import os
import yaml
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

@st.cache_data(show_spinner="Connecting to Data Warehouse...")
def load_data():
    """
    Retrieves the gold layer dataset from PostgreSQL database.
    Results are cached to optimize application performance.
    """
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'settings.yaml')
    with open(config_path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    
    db = config["database"]
    conn_uri = f"postgresql://{db['user']}:{db['password']}@{db['host']}:{db['port']}/{db['name']}"
    engine = create_engine(conn_uri)
    
    query = "SELECT * FROM gold.loan_features_v1;"
    return pd.read_sql(query, engine)