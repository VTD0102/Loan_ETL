import joblib
import pandas as pd
import yaml
from sqlalchemy import create_engine
import os

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    with open(config_path, "r") as file:
        return yaml.safe_load(file)

def run_prediction_on_samples():
    try:
        # 1. Kết nối Database
        config = load_config()
        db = config["database"]
        conn_uri = f"postgresql://{db['user']}:{db['password']}@{db['host']}:{db['port']}/{db['name']}"
        engine = create_engine(conn_uri)

        # 2. Load mô hình
        model_path = 'ml/models/loan_risk_model.pkl'
        if not os.path.exists(model_path):
            print(f"❌ Không tìm thấy file mô hình tại {model_path}")
            return
        model = joblib.load(model_path)

        # 3. Lấy 5 hồ sơ ngẫu nhiên từ Gold layer để test
        # Chúng ta lấy luôn cột is_default để đối soát xem mô hình đoán đúng không
        query = "SELECT * FROM gold.loan_features_v1 ORDER BY RANDOM() LIMIT 5;"
        df_samples = pd.read_sql(query, engine)

        if df_samples.empty:
            print("❌ Không có dữ liệu trong bảng gold.loan_features_v1")
            return

        # Tách thực tế và dữ liệu truyền vào mô hình
        y_actual = df_samples['is_default']
        X_samples = df_samples.drop(columns=['is_default'])

        # 4. Dự đoán
        print(f"🔮 Đang dự đoán rủi ro cho {len(X_samples)} hồ sơ mẫu...")
        print("-" * 60)
        
        predictions = model.predict(X_samples)
        probabilities = model.predict_proba(X_samples)[:, 1]

        # 5. Hiển thị kết quả đối soát
        for i in range(len(df_samples)):
            actual_status = "Nợ xấu" if y_actual[i] == 1 else "Tốt"
            pred_status = "⚠️ RỦI RO" if predictions[i] == 1 else "✅ AN TOÀN"
            color_match = "🎯 ĐÚNG" if y_actual[i] == predictions[i] else "❌ SAI"
            
            print(f"Hồ sơ thứ {i+1}:")
            print(f"   - Thực tế: {actual_status}")
            print(f"   - Dự đoán: {pred_status} (Xác suất nợ xấu: {probabilities[i]*100:.2f}%)")
            print(f"   - Đánh giá: {color_match}")
            print("-" * 30)

    except Exception as e:
        print(f"❌ Lỗi: {e}")

if __name__ == "__main__":
    run_prediction_on_samples()