"""
Main Application Router
Entry point for the CreditIntel Web Application.
"""
import streamlit as st

# Import our custom modules
from data_handler import load_data
from dashboard import render_dashboard
from prediction_ui import render_predictor

# =======================================================
# 1. PAGE CONFIGURATION & VISUAL IDENTITY
# =======================================================
LOG_URL = "https://cdn-icons-png.flaticon.com/512/3135/3135706.png"

st.set_page_config(
    page_title="CreditIntel | Risk Management", 
    page_icon=LOG_URL, 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .kpi-card {
        border-radius: 10px; padding: 20px; text-align: center;
        color: white; font-family: sans-serif; margin-bottom: 20px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
    }
    .kpi-title { font-size: 16px; font-weight: 600; opacity: 0.9; }
    .kpi-value { font-size: 32px; font-weight: bold; margin: 10px 0 0 0; }
</style>
""", unsafe_allow_html=True)

# =======================================================
# 2. INITIALIZATION & ROUTING
# =======================================================
# Fetch data from the Data Warehouse
df_gold = load_data()

# Sidebar Setup
with st.sidebar:
    st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
    st.image(LOG_URL, width=120) 
    st.markdown("<h2 style='margin-top: 10px; margin-bottom: 0;'>CreditIntel</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: gray; font-size: 14px;'>Risk Management System</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    menu_choice = st.radio(
        label="NAVIGATION",
        options=("📊 Risk Dashboard", "🤖 Underwriting System")
    )

# Render the selected module
if menu_choice == "📊 Risk Dashboard":
    render_dashboard(df_gold)
elif menu_choice == "🤖 Underwriting System":
    render_predictor(df_gold)