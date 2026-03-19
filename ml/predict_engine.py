import numpy as np

def evaluate_risk(credit_score, monthly_income, loan_amount, employment_status, df_gold, model):
    # --- 1. CỔNG BẢO VỆ (HARD RULES) ---
    annual_income = monthly_income * 12
    
    # Ước tính số tiền phải trả hàng tháng (Vay 36 tháng)
    estimated_monthly_payment = (loan_amount / 36) * 1.15
    existing_debt = monthly_income * 0.10 # Giả định nợ cũ 10%
    
    dti = (estimated_monthly_payment + existing_debt) / monthly_income if monthly_income > 0 else 10.0
    lti = loan_amount / annual_income if annual_income > 0 else 10.0

    # Chặn đứng nếu DTI vượt 50% hoặc Vay quá 50% lương năm
    if dti > 0.50:
        return True, dti, "DTI (Tỷ lệ Nợ/Lương tháng) vượt quá 50%. Khả năng trả nợ không đảm bảo.", []
    if lti > 0.50:
        return True, lti, "Số tiền vay quá lớn so với tổng thu nhập cả năm.", []

    # --- 2. TẠO KHUÔN MẪU AN TOÀN TUYỆT ĐỐI LÀM GỐC ---
    # CHỈ lấy những người chưa từng vỡ nợ để làm mồi (Fix lỗi bóng ma)
    safe_profiles = df_gold[df_gold['is_default'] == 0].drop(columns=['is_default'])
    input_data = safe_profiles.mode().iloc[[0]].copy()

    # --- 3. GÁN ĐIỂM FICO VÀ HẠNG TÍN DỤNG ---
    if credit_score >= 760: rating, apr, ordinal, p_score, band = 'AA', 0.05, 7, 10, '720+'
    elif credit_score >= 720: rating, apr, ordinal, p_score, band = 'A', 0.09, 6, 8, '720+'
    elif credit_score >= 680: rating, apr, ordinal, p_score, band = 'B', 0.13, 5, 6, '680-719'
    elif credit_score >= 640: rating, apr, ordinal, p_score, band = 'C', 0.18, 4, 4, '640-679'
    elif credit_score >= 600: rating, apr, ordinal, p_score, band = 'D', 0.25, 3, 2, '600-639'
    else: rating, apr, ordinal, p_score, band = 'HR', 0.35, 1, 1, '<600'

    # --- 4. CƠ CHẾ PHẠT RỦI RO ĐỘNG VÀ EXPERT OVERLAY ---
    credit_score_adjusted = credit_score # Tạo một điểm FICO ảo để gửi cho AI
    risk_factors = [] # DANH SÁCH LƯU TRỮ LÝ DO PHẠT
    
    if dti > 0.35:
        risk_factors.append(f"High Monthly Debt Burden: Estimated DTI is {dti*100:.1f}%.")
        p_score = max(1, p_score - 2)
        ordinal = max(1, ordinal - 2)
        apr = min(0.35, apr + 0.08) 
    
    # TRỊ TẬN GỐC CASE "BẪY THU NHẬP THẤP" (Lương <= 2000 mà LTI > 30%)
    if monthly_income <= 2000 and lti > 0.30:
        risk_factors.append(f"Low Income Trap: Requesting a large loan ({loan_amount:,.0f} USD) with low monthly income ({monthly_income:,.0f} USD).")
        p_score = max(1, p_score - 4)      # Trừ tụt đáy hạng nội bộ
        ordinal = max(1, ordinal - 3)
        apr = min(0.35, apr + 0.15)        # Đẩy lãi suất lên kịch trần
        credit_score_adjusted -= 100       # KỸ THUẬT CHE MẮT: Kéo FICO 750 xuống 650 để AI bớt thiên vị
        
    if employment_status in ['Self-employed', 'Not employed']:
        risk_factors.append(f"Employment Risk: Applicant is {employment_status}, indicating potential income instability.")
        p_score = max(1, p_score - 1)
        ordinal = max(1, ordinal - 1)
        apr = min(0.35, apr + 0.04)

    rating_map = {7:'AA', 6:'A', 5:'B', 4:'C', 3:'D', 2:'E', 1:'HR'}
    rating = rating_map.get(ordinal, 'HR')

    # --- 5. ĐỒNG BỘ VÀO BẢNG DỮ LIỆU ---
    # Nạp điểm FICO ĐÃ BỊ PHẠT cho AI thay vì điểm gốc
    input_data['credit_score_midpoint'] = credit_score_adjusted 
    
    input_data['stated_monthly_income'] = monthly_income
    input_data['loan_original_amount'] = loan_amount
    input_data['employment_status'] = employment_status
    input_data['employment_status_grouped'] = employment_status
    
    input_data['debt_to_income_ratio'] = dti
    input_data['loan_amount_to_income'] = lti
    input_data['log_monthly_income'] = np.log1p(monthly_income)
    
    input_data['prosper_score'] = p_score
    input_data['prosper_rating_alpha'] = rating
    input_data['rating_ordinal'] = ordinal
    input_data['borrower_apr'] = apr
    input_data['borrower_rate'] = max(0.01, apr - 0.03)
    input_data['credit_score_band'] = band # Bạn có thể đổi cả band nếu muốn kỹ hơn
    
    if annual_income == 0: inc_ord = 0
    elif annual_income < 25000: inc_ord = 1
    elif annual_income < 50000: inc_ord = 2
    elif annual_income < 75000: inc_ord = 3
    elif annual_income < 100000: inc_ord = 4
    else: inc_ord = 5
    input_data['income_range_ordinal'] = inc_ord

    # --- 6. GỌI AI ---
    probability = model.predict_proba(input_data)[0][1]
    
    # Trả về thêm mảng risk_factors
    return False, dti, probability, risk_factors