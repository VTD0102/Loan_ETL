import os
import joblib
import streamlit as st
import plotly.graph_objects as go
from ml.predict_engine import evaluate_risk

def render_predictor(df_gold):
    st.title("🤖 Credit Underwriting System")
    st.write("Enter applicant details to evaluate default risk.")
    st.markdown("---")
    
    project_root = os.path.dirname(os.path.dirname(__file__))
    model_path = os.path.join(project_root, 'ml', 'models', 'loan_risk_model.pkl')
    try:
        model = joblib.load(model_path)
    except FileNotFoundError:
        st.error("❌ Model artifact not found. Please retrain.")
        st.stop()
        
    with st.form("applicant_form"):
        st.subheader("Applicant Information")
        col1, col2 = st.columns(2)
        
        with col1:
            credit_score = st.slider("Credit Score (FICO)", min_value=300, max_value=850, value=650)
            monthly_income = st.number_input("Monthly Income ($)", min_value=0.0, value=5000.0, step=100.0)
            
        with col2:
            loan_amount = st.number_input("Requested Loan Amount ($)", min_value=1000.0, value=10000.0, step=500.0)
            employment_status = st.selectbox("Employment Status", ["Employed", "Self-employed", "Not employed", "Retired"])
            
        submit_button = st.form_submit_button("Evaluate Risk Profile")
        
    if submit_button:
        st.markdown("---")
        st.subheader("Assessment Result")
        
        with st.spinner('🤖 AI is running analysis...'):
            # Nhận 4 biến từ hàm đánh giá thay vì 3
            is_rule_reject, metric_value, result, risk_factors = evaluate_risk(
                credit_score, monthly_income, loan_amount, employment_status, df_gold, model
            )
        
        if is_rule_reject:
            st.error("⚠️ AUTOMATIC REJECTION")
            st.write(f"**Policy Violation:** {result}")
            st.write(f"*(Calculated Metric Ratio: {metric_value*100:.1f}%)*")
        else:
            probability = result
            is_rejected = probability > 0.15 
            
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number", value = probability * 100,
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "Predicted Default Risk", 'font': {'size': 18}},
                number = {'suffix': "%", 'font': {'size': 36}, 'valueformat': '.1f'},
                gauge = {
                    'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
                    'bar': {'color': "rgba(0,0,0,0)"}, 
                    'steps': [
                        {'range': [0, 15], 'color': "#2ecc71"},   
                        {'range': [15, 30], 'color': "#f1c40f"},  
                        {'range': [30, 100], 'color': "#e74c3c"}  
                    ],
                    'threshold': {'line': {'color': "black", 'width': 5}, 'thickness': 0.75, 'value': probability * 100}
                }
            ))
            fig_gauge.update_layout(height=300, margin=dict(t=50, b=20, l=20, r=20))
            
            col_res1, col_res2 = st.columns([1, 1])
            with col_res1:
                st.plotly_chart(fig_gauge, use_container_width=True)
                
            with col_res2:
                st.write("") 
                st.write("")
                if is_rejected:
                    # Hiển thị mức cảnh báo linh hoạt theo %
                    st.warning("⚠️ MANUAL REVIEW REQUIRED" if probability <= 0.30 else "❌ HIGH RISK DETECTED")
                    st.write("**Recommendation:** Do not auto-approve. Risk exceeds 15% threshold.")
                else:
                    st.success("✅ APPROVED - LOW RISK")
                    st.write("**Recommendation:** Safe to proceed. Applicant profile aligns with successful repayment models.")
                
                # --- EXPLAINABLE AI: IN RA LÝ DO (NẾU CÓ) ---
                if risk_factors:
                    st.markdown("---")
                    st.write("🔍 **AI Risk Insights:**")
                    for factor in risk_factors:
                        st.write(f"- {factor}")
