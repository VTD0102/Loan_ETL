import sys
import os
import pandas as pd
import numpy as np
import joblib
import yaml
from sqlalchemy import create_engine
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer

# 1. Cấu hình hệ thống
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    with open(config_path, "r") as file:
        return yaml.safe_load(file)

def load_data():
    config = load_config()
    db = config["database"]
    conn_uri = f"postgresql://{db['user']}:{db['password']}@{db['host']}:{db['port']}/{db['name']}"
    engine = create_engine(conn_uri)
    
    query = "SELECT * FROM gold.loan_features_v1;"
    print("⏳ Đang tải dữ liệu từ gold.loan_features_v1...")
    df = pd.read_sql(query, engine)
    return df

def preprocess_and_clean(df):
    """Làm sạch dữ liệu và ép kiểu tường minh"""
    # Loại bỏ các cột không cần thiết cho ML
    leakage_columns = [
        'listing_key', 'loan_status', 'closed_date', 
        'listing_creation_date', 'loan_origination_date'
    ]
    cols_to_drop = [col for col in leakage_columns if col in df.columns]
    df = df.drop(columns=cols_to_drop)

    # TÁCH BIỆT: Ép kiểu dữ liệu để tránh lỗi 'float'
    for col in df.columns:
        if df[col].dtype == 'object' or df[col].dtype.name == 'category':
            df[col] = df[col].astype(str) # Ép hết về string thuần túy
            
    return df

def build_pipeline(X):
    # Xác định các nhóm cột
    numeric_features = X.select_dtypes(include=['int64', 'float64']).columns.tolist()
    categorical_features = X.select_dtypes(include=['object', 'string']).columns.tolist()

    print(f"📊 Đặc trưng: {len(numeric_features)} số, {len(categorical_features)} phân loại.")

    # Pipeline cho biến số
    numeric_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])

    # Pipeline cho biến phân loại (Sửa lỗi quan trọng ở đây)
    categorical_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='constant', fill_value='missing')), # Dùng hằng số để an toàn hơn
        ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', numeric_transformer, numeric_features),
            ('cat', categorical_transformer, categorical_features)
        ])

    model = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('classifier', RandomForestClassifier(
            n_estimators=100, 
            random_state=42, 
            class_weight='balanced', 
            max_depth=8, # Giảm nhẹ độ sâu để tránh overfitting
            n_jobs=-1
        ))
    ])
    
    return model

def main():
    try:
        df = load_data()
        df = preprocess_and_clean(df)
        
        if 'is_default' not in df.columns:
            print("❌ Lỗi: Thiếu cột 'is_default'.")
            return

        X = df.drop(columns=['is_default'])
        y = df['is_default'].astype(int)
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        print(f"🚀 Đang huấn luyện trên {len(X_train)} hồ sơ...")
        pipeline = build_pipeline(X_train)
        pipeline.fit(X_train, y_train)
        
        print("\n✅ --- KẾT QUẢ ĐÁNH GIÁ ---")
        y_pred = pipeline.predict(X_test)
        y_proba = pipeline.predict_proba(X_test)[:, 1]
        
        print(classification_report(y_test, y_pred))
        print(f"🎯 ROC AUC Score: {roc_auc_score(y_test, y_proba):.4f}")
        
        # Lưu mô hình
        os.makedirs('ml/models', exist_ok=True)
        joblib.dump(pipeline, 'ml/models/loan_risk_model.pkl')
        print(f"💾 Đã lưu mô hình thành công!")

    except Exception as e:
        print(f"❌ Lỗi thực thi: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()