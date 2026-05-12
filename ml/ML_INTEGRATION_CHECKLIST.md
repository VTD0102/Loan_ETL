# 🤝 ML Integration Checklist for Backend

Tài liệu này dành cho **Thành viên phụ trách Machine Learning** (Task 4.6). Vui lòng tham khảo cấu trúc dưới đây để đảm bảo mô hình `.pkl` khi xuất ra tương thích 100% với Backend.

## 1. Input Features (Dữ liệu Backend truyền vào Model)
Khi người dùng gọi `POST /applications/submit`, Backend sẽ build 1 `pandas.DataFrame` gồm đúng 8 cột (Feature names) truyền thẳng vào Pipeline học máy. Mô hình lúc Train bắt buộc phải sử dụng đúng tên cột nhãn dưới đây:

| Field Name | Type | Description / Valid Range | Example |
| :--- | :--- | :--- | :--- |
| `monthly_income` | `float` | Thu nhập hàng tháng (> 0) | `5000.0` |
| `loan_amount` | `float` | Tiền muốn vay (> 0) | `10000.0` |
| `term` | `int` | Thời hạn vay tính bằng tháng (12, 36, 60...) | `36` |
| `employment_status` | `string` | Tình trạng ("Employed", "Unemployed", "Self-employed")| `"Employed"`|
| `dti` | `float` | Debt-to-Income (Thường từ 0.0 -> 1.0) | `0.35` |
| `is_homeowner` | `int` | Biến boolean nhị phân (`1`: Có nhà, `0`: Không) | `1` |
| `listing_category` | `int` | Mã số lý do vay (0 -> 21) | `1` |
| `credit_score` | `int` | Điểm hồ sơ tín dụng thô | `700` |

> [!WARNING]
> Mức độ rủi ro: Nếu model ML thiết kế bằng các feature names như `borrower_apr`, `annual_income_est` thì `pd.DataFrame` của Backend đẩy xuống sẽ bị `ValueError: unseen validation feature`. Team ML cần cập nhật `ColumnTransformer` phù hợp.

## 2. Expected Object Structure (Thành phần Pickle)
File `loan_risk_model.pkl` khi sinh ra từ `joblib.dump()` bắt buộc là 1 Tự Điển (Dictionary) chứa:
```python
{
    "pipeline": scikit_learn_pipeline, # Pipeline bắt buộc có hàm .predict_proba(X)
    "thresholds": {
        "low": 0.2,   # Dưới mốc = Low Risk
        "high": 0.4   # Vượt mốc = High Risk (Trực tiếp bị Server quăng nhãn AUTO_REJECTED)
    }
}
```

## 3. Quá trình Bắt tay Backend (Mạn sườn API)
- Backend **ĐÃ CODE XONG** luồng gọi ML tại hàm `application_service.submit()`. 
- **Cơ chế phòng thân (Fault Tolerance):** Hiện tại vì file Pickle chưa match cột Schema, vòng gọi Model rẽ vào ngõ Exception. Để Server ko chết, Backend đang xuất ra `Mock Probability` giả lập.
- Khi ML Team tinh chỉnh lại Model chuẩn với bảng Features bên trên và ném lại vô thư mục `ml/models`, vòng Call-out của Backend tự động sáng lên màu xanh mà ko cần đổi thêm dòng Code API nào!

## 4. Yêu cầu Hiệu Năng Vận Hành
- Việc Convert sang Array và Pipeline suy luận (`predict_proba`) bị giới hạn SLA bắt buộc **< 500ms** để Router không phản hồi timeout tới Server React Của Người dùng. Thống kê Log File đang pass cực ngọt. Mọi người chỉ việc đắp thịt Machine Learning nốt là hoàn chỉnh.
