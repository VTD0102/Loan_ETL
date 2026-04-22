"""
Dashboard View Module
Renders the interactive risk management dashboard, KPIs, and data tables.
"""
import plotly.express as px
import streamlit as st


def render_dashboard(df_gold):
    """Renders the Portfolio Risk Dashboard tab."""
    st.title("Portfolio Risk Dashboard")
    st.write("Overview of loan performance and risk metrics.")
    st.markdown("---")

    st.markdown("### Filters")
    col_f1, col_f2, col_f3 = st.columns(3)

    with col_f1:
        list_jobs = ["All"] + df_gold["employment_status"].dropna().unique().tolist()
        filter_job = st.selectbox("Employment Status", list_jobs)
    with col_f2:
        list_ratings = ["All"] + sorted(df_gold["prosper_rating_alpha"].dropna().unique().tolist())
        filter_rating = st.selectbox("Prosper Rating", list_ratings)
    with col_f3:
        list_cats = ["All"] + df_gold["listing_category_numeric"].dropna().astype(str).unique().tolist()
        filter_cat = st.selectbox("Loan Category", list_cats)

    df_filtered = df_gold.copy()
    if filter_job != "All":
        df_filtered = df_filtered[df_filtered["employment_status"] == filter_job]
    if filter_rating != "All":
        df_filtered = df_filtered[df_filtered["prosper_rating_alpha"] == filter_rating]
    if filter_cat != "All":
        df_filtered = df_filtered[df_filtered["listing_category_numeric"].astype(str) == filter_cat]

    st.markdown("---")

    total_loans = len(df_filtered)
    defaulted_loans = df_filtered["is_default"].sum()
    default_rate = (defaulted_loans / total_loans * 100) if total_loans > 0 else 0
    avg_loan_amt = df_filtered["loan_original_amount"].mean() if total_loans > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(f'<div class="kpi-card" style="background: linear-gradient(135deg, #1e3c72, #2a5298);"><div class="kpi-title">Total Loans</div><div class="kpi-value">{total_loans:,}</div></div>', unsafe_allow_html=True)
    col2.markdown(f'<div class="kpi-card" style="background: linear-gradient(135deg, #cb2d3e, #ef473a);"><div class="kpi-title">Defaulted</div><div class="kpi-value">{defaulted_loans:,}</div></div>', unsafe_allow_html=True)
    col3.markdown(f'<div class="kpi-card" style="background: linear-gradient(135deg, #f12711, #f5af19);"><div class="kpi-title">Default Rate</div><div class="kpi-value">{default_rate:.2f}%</div></div>', unsafe_allow_html=True)
    col4.markdown(f'<div class="kpi-card" style="background: linear-gradient(135deg, #11998e, #38ef7d);"><div class="kpi-title">Avg Loan Amount</div><div class="kpi-value">${avg_loan_amt:,.0f}</div></div>', unsafe_allow_html=True)

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.subheader("1. Portfolio Status")
        if total_loans > 0:
            df_pie = df_filtered["is_default"].replace({1: "Defaulted", 0: "Healthy"}).value_counts().reset_index()
            df_pie.columns = ["Status", "Count"]
            fig1 = px.pie(df_pie, values="Count", names="Status", hole=0.5, color="Status", color_discrete_map={"Healthy": "#2ecc71", "Defaulted": "#e74c3c"})
            fig1.update_layout(margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig1, use_container_width=True)

    with col_chart2:
        st.subheader("2. Risk by Income Range")
        if total_loans > 0:
            df_income_risk = df_filtered.groupby("income_range")["is_default"].mean().reset_index()
            df_income_risk["Default Rate (%)"] = df_income_risk["is_default"] * 100
            income_order = ["Not displayed", "Not employed", "$0", "$1-24,999", "$25,000-49,999", "$50,000-74,999", "$75,000-99,999", "$100,000+"]
            fig2 = px.bar(df_income_risk, x="income_range", y="Default Rate (%)", color="Default Rate (%)", color_continuous_scale="Reds", category_orders={"income_range": income_order})
            fig2.update_layout(xaxis_title="", margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    st.subheader("Loan Records")
    search_query = st.text_input("Search (ID or Occupation...)")
    if search_query:
        df_table = df_filtered[df_filtered["occupation"].str.contains(search_query, case=False, na=False) | df_filtered["listing_key"].str.contains(search_query, case=False, na=False)]
    else:
        df_table = df_filtered

    cols_to_show = ["listing_key", "employment_status", "occupation", "credit_score_midpoint", "stated_monthly_income", "loan_original_amount", "is_default"]
    df_table_display = df_table[cols_to_show].rename(columns={
        "listing_key": "ID",
        "employment_status": "Employment",
        "occupation": "Occupation",
        "credit_score_midpoint": "FICO Mid",
        "stated_monthly_income": "Monthly Inc ($)",
        "loan_original_amount": "Loan Amt ($)",
        "is_default": "Default (1=Yes)",
    })
    st.dataframe(df_table_display, use_container_width=True, height=300)
