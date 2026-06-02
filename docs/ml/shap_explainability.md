# Hướng Dẫn Kỹ Thuật: Cơ Chế Giải Thích Mô Hình Bằng SHAP (Explainable AI - XAI)

Tài liệu này cung cấp chi tiết toàn diện về phương pháp toán học, kiến trúc tích hợp và quy trình vận hành của cơ chế giải thích mô hình **SHAP (SHapley Additive exPlanations)** trong hệ thống đánh giá rủi ro tín dụng **CreditIntel**.

---

## 1. Tại Sao Credit Scoring Cần Khả Năng Giải Thích (Explainability)?

Trong lĩnh vực tài chính và ngân hàng, việc phê duyệt hay từ chối một khoản vay không chỉ đòi hỏi độ chính xác cao về mặt thống kê, mà còn phải đáp ứng hai yêu cầu cốt lõi sau:

### 1.1. Tuân thủ quy định pháp lý (Regulatory Compliance)
Theo các quy định pháp luật về tín dụng tiêu dùng (như *Đạo luật Cơ hội Tín dụng Bình đẳng - ECOA* hoặc các quy chuẩn của ngân hàng trung ương), khi một hồ sơ vay vốn bị từ chối, tổ chức tín dụng bắt buộc phải gửi **Báo cáo lý do bất lợi (Adverse Action Notice)** để giải trình cụ thể các lý do dẫn đến việc từ chối đó. Hệ thống không thể trả lời chung chung rằng: *"Mô hình AI học máy tự động từ chối hồ sơ của bạn"*.

### 1.2. Minh bạch hóa và trải nghiệm khách hàng (Customer Transparency)
Khi khách hàng nhận được điểm số tín dụng (ví dụ FICO Score = 569 điểm), họ luôn có nhu cầu biết:
* Tại sao điểm của họ lại nằm ở mức đó?
* Những hành vi tài chính nào của họ đang kéo điểm số đi xuống?
* Làm cách nào để họ có thể cải thiện điểm số tín dụng trong tương lai?

SHAP là chiếc cầu nối kỹ thuật giúp chuyển đổi các mô hình toán học phức tạp thành các lý do cụ thể và hành động tư vấn cá nhân hóa thời gian thực.

---

## 2. Nền Tảng Lý Thuyết Của Giá Trị Shapley (Shapley Values)

**SHAP** là phương pháp giải thích mô hình dựa trên khái niệm **Giá trị Shapley (Shapley Values)** thuộc Lý thuyết trò chơi hợp tác (Cooperative Game Theory), được phát triển bởi nhà toán học *Lloyd Shapley*.

### 2.1. Khái niệm tổng quát
Giả sử có một nhóm người chơi $S$ cùng hợp tác tham gia một trò chơi để tạo ra một giá trị gia tăng chung $v(S)$ (ví dụ: một liên minh doanh nghiệp tạo ra lợi nhuận). Câu hỏi đặt ra là: **Làm thế nào để phân chia phần thưởng một cách công bằng nhất cho từng người chơi dựa trên đóng góp thực tế của họ?**

Lloyd Shapley đã chứng minh toán học rằng đóng góp biên trung bình của người chơi $i$ (ký hiệu là $\phi_i$) là cách phân chia duy nhất thỏa mãn đồng thời 4 tính chất (tiên đề) công bằng:
1. **Tiên đề Hiệu quả (Efficiency / Local Accuracy)**: Tổng đóng góp của tất cả các người chơi bằng chính xác tổng giá trị gia tăng được tạo ra:
   $$\sum_{i=1}^{M} \phi_i = v(S) - v(\emptyset)$$
2. **Tiên đề Đối xứng (Symmetry)**: Hai người chơi có đóng góp biên vào mọi liên minh như nhau thì nhận phần thưởng như nhau: Nếu $v(S \cup \{i\}) = v(S \cup \{j\})$ với mọi $S$, thì $\phi_i = \phi_j$.
3. **Tiên đề Người chơi rỗng (Dummy / Null Player)**: Người chơi không đóng góp thêm bất kỳ giá trị nào vào mọi liên minh thì nhận phần thưởng bằng 0: Nếu $v(S \cup \{i\}) = v(S)$ với mọi $S$, thì $\phi_i = 0$.
4. **Tiên đề Cộng tính (Additivity)**: Nếu trò chơi là tổng của hai trò chơi độc lập $v = v_1 + v_2$, đóng góp của người chơi sẽ bằng tổng đóng góp trong hai trò chơi: $\phi_i(v_1 + v_2) = \phi_i(v_1) + \phi_i(v_2)$.

### 2.2. Công thức toán học tính Giá trị Shapley
Giá trị đóng góp $\phi_i$ của người chơi thứ $i$ được tính bằng giá trị kỳ vọng của đóng góp biên của họ trên tất cả các tổ hợp liên minh có thể có của các người chơi khác:
$$\phi_i = \sum_{S \subseteq F \setminus \{i\}} \frac{|S|!(|F| - |S| - 1)!}{|F|!} \left[ v(S \cup \{i\}) - v(S) \right]$$

Trong đó:
* $F$: Tập hợp tất cả các đặc trưng đầu vào (người chơi).
* $S$: Một liên minh (tập con) của các đặc trưng không chứa đặc trưng $i$.
* $v(S)$: Dự đoán của mô hình khi chỉ sử dụng tập hợp đặc trưng $S$.
* $v(S \cup \{i\}) - v(S)$: Đóng góp biên khi đưa thêm đặc trưng $i$ vào liên minh $S$.

---

## 3. Chứng Minh Toán Học: Sự Đồng Bộ 1-1 Giữa Giá Trị SHAP Và Điểm Scorecard

Một trong những ưu điểm nổi bật của việc thiết lập hệ thống chấm điểm dựa trên mô hình Hồi quy Logistic tuyến tính là chúng ta có thể chứng minh sự tương đương hoàn hảo về mặt toán học giữa giá trị đóng góp SHAP và điểm số FICO thành phần.

### 3.1. Phương trình logit dự báo
Mô hình hồi quy Logistic dự báo ra giá trị Log-Odds mặc định nợ (logit) theo phương trình:
$$\text{logit}(p) = \beta_0 + \sum_{i=1}^{M} \beta_i z_i$$

Với các đặc trưng số $z_i$ đã được chuẩn hóa qua StandardScaler, phân phối của chúng có giá trị trung bình kỳ vọng bằng 0 ($E[z_i] = 0$). 
Do đó, giá trị logit trung bình kỳ vọng trên toàn tập dữ liệu huấn luyện là:
$$E[\text{logit}] = E\left[ \beta_0 + \sum_{i=1}^{M} \beta_i z_i \right] = \beta_0 + \sum_{i=1}^{M} \beta_i E[z_i] = \beta_0$$

### 3.2. Giá trị SHAP của mô hình tuyến tính
Đối với các mô hình tuyến tính, giá trị SHAP của đặc trưng $i$ được định nghĩa bằng tích của hệ số hồi quy và độ lệch so với trung bình:
$$\text{SHAP}_i = \beta_i \times (z_i - E[z_i])$$

Thay thế $E[z_i] = 0$, ta thu được giá trị SHAP của đặc trưng thứ $i$ cho một hồ sơ cụ thể:
$$\text{SHAP}_i = \beta_i \times z_i$$

### 3.3. Áp dụng vào công thức quy đổi điểm FICO
Công thức quy đổi điểm FICO từ giá trị logit của mô hình là:
$$\text{Score} = \text{Base\_Score} - \text{Factor} \times (\text{logit} - \text{Base\_Logit})$$
$$\text{Score} = \text{Base\_Score} - \text{Factor} \times \left( \beta_0 + \sum_{i=1}^{M} \beta_i z_i - \text{Base\_Logit} \right)$$
$$\text{Score} = \underbrace{\text{Base\_Score} - \text{Factor} \times (\beta_0 - \text{Base\_Logit})}_{\text{Base Points (Điểm Cơ Sở)}} + \sum_{i=1}^{M} \underbrace{(-\text{Factor} \times \beta_i z_i)}_{\text{Points of Feature } i}$$

Thay thế $\text{SHAP}_i = \beta_i z_i$ vào phần tổng điểm đặc trưng:
$$\text{Points}_i = -\text{Factor} \times \text{SHAP}_i$$

Với tham số cấu hình $\text{Factor} = 28.8539$:
$$\text{Points}_i \approx -28.8539 \times \text{SHAP}_i$$

### 3.4. Ý nghĩa của mối liên hệ toán học này
* **Tỷ lệ nghịch hoàn hảo**: Do hệ số $\text{Factor}$ luôn dương ($>0$), giá trị SHAP và điểm số thành phần tỉ lệ nghịch với nhau. 
* **Chiều hướng rủi ro**:
  * Nếu $\text{SHAP}_i > 0$ (Đặc trưng làm tăng rủi ro vỡ nợ, ví dụ: quá hạn DPD cao) $\rightarrow$ $\text{Points}_i < 0$ (Khách hàng bị trừ điểm FICO).
  * Nếu $\text{SHAP}_i < 0$ (Đặc trưng làm giảm rủi ro vỡ nợ, ví dụ: thâm niên công việc cao) $\rightarrow$ $\text{Points}_i > 0$ (Khách hàng được cộng điểm FICO).
* **Tính đồng nhất**: Thứ tự sắp xếp các đặc trưng ảnh hưởng mạnh nhất theo giá trị tuyệt đối của SHAP ($|\text{SHAP}_i|$) trùng khớp hoàn toàn với thứ tự sắp xếp theo trị tuyệt đối điểm đóng góp ($|\text{Points}_i|$). Điều này cho phép hệ thống sử dụng chung một logic xử lý Backend.

---

## 4. Kiến Trúc Tích Hợp SHAP Trong CreditIntel Backend

Trong backend FastAPI của CreditIntel, lớp dịch vụ [credit_score_service.py](file:///D:/GIT%20REPO/loan-etl/Loan_ETL/backend/services/credit_score_service.py) chịu trách nhiệm nạp mô hình Scorecard và chạy bộ giải thích SHAP để trả về các lý do tác động cho API.

### Mã Nguồn Thực Thi Tính SHAP (Trích đoạn từ `credit_score_service.py`)
```python
import shap
import numpy as np
import pandas as pd

def compute_member_score(session: Session, member_key: str):
    # 1. Nạp mô hình Scorecard pkl
    artifact = joblib.load(SCORECARD_PATH)
    pipeline = artifact["pipeline"]
    feature_cols = artifact["feature_cols"]
    fico_params = artifact["fico_params"]
    
    # 2. Xây dựng vector đặc trưng cho khách hàng từ Database
    features_df = _build_features_df(session, member_key, feature_cols)
    
    # 3. Tính toán xác suất vỡ nợ (PD)
    prob_default = float(pipeline.predict_proba(features_df)[0, 1])
    
    # 4. Tính toán điểm FICO Score
    fico_score = pd_to_credit_score(prob_default, fico_params)
    score_band = score_to_band(fico_score)
    
    # 5. Chạy bộ giải thích SHAP LinearExplainer
    # Trích xuất mô hình Logistic Regression và preprocessor từ Pipeline
    classifier = pipeline.named_steps["classifier"]
    preprocessor = pipeline.named_steps["preprocessor"]
    
    # Chuyển đổi dữ liệu thô sang không gian đặc trưng đã tiền xử lý (StandardScaler + OrdinalEncoder)
    X_transformed = preprocessor.transform(features_df)
    
    # Khởi tạo LinearExplainer với các hệ số của Logistic Regression
    # Cần cung cấp dữ liệu nền (background data) hoặc cấu hình độc lập tuyến tính
    explainer = shap.LinearExplainer(
        classifier,
        masker=shap.maskers.Independent(data=X_transformed)
    )
    
    # Tính toán SHAP values
    shap_values = explainer.shap_values(X_transformed)
    
    # Do đây là phân loại nhị phân, shap_values[0] đại diện cho sự thay đổi của log-odds vỡ nợ
    shap_contribs = shap_values[0] 
    
    # 6. Tạo danh sách các yếu tố đóng góp điểm FICO tương ứng
    factor = fico_params["factor"]
    contributions = []
    
    for i, col_name in enumerate(feature_cols):
        shap_val = float(shap_contribs[i])
        # Điểm đóng góp FICO = -Factor * SHAP
        points_impact = -factor * shap_val
        
        contributions.append({
            "feature": col_name,
            "shap_value": shap_val,
            "points_impact": round(points_impact, 2),
            "effect": "decrease_risk" if points_impact >= 0 else "increase_risk"
        })
        
    # Sắp xếp các đặc trưng theo thứ tự độ lớn ảnh hưởng giảm dần
    contributions_sorted = sorted(contributions, key=lambda x: abs(x["points_impact"]), reverse=True)
    
    # Lấy Top 3 đặc trưng ảnh hưởng mạnh nhất để làm Adverse Reasons
    top_3_drivers = contributions_sorted[:3]
    
    return {
        "score": fico_score,
        "band": score_band,
        "probability_default": prob_default,
        "explainability": top_3_drivers
    }
```

---

## 5. Ví Dụ Minh Họa Nghiệp Vụ (Tư Vấn Tài Chính Chatbot AI)

Khi API trả về kết quả cấu trúc giải thích SHAP, ứng dụng Chatbot AI tích hợp ở frontend sẽ sử dụng dữ liệu này để chuyển thể thành ngôn ngữ hội thoại tự nhiên, giúp hướng dẫn khách hàng cải thiện điểm số.

### Kịch bản minh họa: Khách hàng C có điểm FICO = 527 (Hạng Rủi Ro Rất Cao / Cảnh báo LOW)
Dữ liệu giải thích SHAP đầu ra từ Backend:
```json
{
  "score": 527,
  "band": "Poor",
  "explainability": [
    {
      "feature": "previous_default_rate",
      "shap_value": 0.3919,
      "points_impact": -11.31,
      "effect": "increase_risk"
    },
    {
      "feature": "income_verifiable_flag",
      "shap_value": 0.1960,
      "points_impact": -5.66,
      "effect": "increase_risk"
    },
    {
      "feature": "num_bureau_records",
      "shap_value": -0.1500,
      "points_impact": 4.33,
      "effect": "decrease_risk"
    }
  ]
}
```

### Cách Chatbot AI phân tích và đưa ra lời khuyên:
1. **Yếu tố tiêu cực 1 (`previous_default_rate`)**: Điểm tín dụng của khách hàng bị trừ mất **11.31 điểm** do trong lịch sử hệ thống đã từng ghi nhận tỷ lệ hồ sơ đăng ký của khách hàng bị từ chối hoặc vỡ nợ cao.
   * *Tư vấn*: *"Lịch sử đăng ký đơn vay trước đây của bạn có tỷ lệ từ chối cao. Bạn nên tránh việc nộp đơn vay dồn dập nhiều lần trong thời gian ngắn và đảm bảo các khoản vay cũ được tất toán đầy đủ."*
2. **Yếu tố tiêu cực 2 (`income_verifiable_flag`)**: Khách hàng bị phạt trừ **5.66 điểm** vì chưa xác minh được thu nhập hợp pháp.
   * *Tư vấn*: *"Điểm số của bạn đang bị ảnh hưởng do thiếu hồ sơ chứng minh thu nhập. Bạn có thể cải thiện bằng cách cập nhật thêm sao kê tài khoản nhận lương hoặc hợp đồng lao động hợp lệ trên hồ sơ ứng dụng."*
3. **Yếu tố tích cực 3 (`num_bureau_records`)**: Khách hàng được cộng **4.33 điểm** nhờ có lịch sử tín dụng phong phú tại liên ngân hàng.
   * *Tư vấn*: *"Điểm cộng của bạn là đã có lịch sử tín dụng hoạt động lâu năm tại hệ thống liên ngân hàng, hãy tiếp tục duy trì thói quen trả nợ đúng hạn để phát huy yếu tố tích cực này."*
