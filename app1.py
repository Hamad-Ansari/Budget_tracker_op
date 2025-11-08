"""
Enhanced Budget Tracker with Reports - Streamlit Single File App
- Stores transactions in SQLite
- Add Income / Expense
- Dashboard with animations
- Export to Excel and PDF
- File upload functionality
- Modern UI with color scheme
"""

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
from fpdf import FPDF
import tempfile
import os
import time

# Configure page
st.set_page_config(
    page_title="Budget Tracker Pro",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = "budget_tracker.db"

# Custom CSS for modern styling and animations
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: bold;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: transform 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-5px);
    }
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.5rem 1rem;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: scale(1.05);
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
    }
    .success-animation {
        animation: fadeIn 0.5s ease-in;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .upload-section {
        border: 2px dashed #667eea;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        margin: 1rem 0;
        background: rgba(102, 126, 234, 0.05);
    }
</style>
""", unsafe_allow_html=True)

# ---------- Database helpers ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,        -- 'income' or 'expense'
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            date TEXT NOT NULL,        -- YYYY-MM-DD
            notes TEXT
        )
        """
    )
    conn.commit()
    conn.close()

def add_transaction(tx_type, category, amount, currency, tx_date, notes=""):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO transactions (type, category, amount, currency, date, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (tx_type, category, float(amount), currency, tx_date, notes),
    )
    conn.commit()
    conn.close()

def load_transactions():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM transactions ORDER BY date DESC, id DESC", conn, parse_dates=["date"])
    conn.close()
    if not df.empty:
        df['date'] = pd.to_datetime(df['date']).dt.date
    return df

def bulk_insert_transactions(transactions_df):
    """Insert multiple transactions at once"""
    conn = sqlite3.connect(DB_PATH)
    transactions_df.to_sql('transactions', conn, if_exists='append', index=False)
    conn.commit()
    conn.close()

# ---------- Report / visualization helpers ----------
def monthly_summary(df, year=None, month=None):
    if df.empty:
        return pd.DataFrame(columns=["metric","value"])
    tmp = df.copy()
    tmp['date'] = pd.to_datetime(tmp['date'])
    if year:
        tmp = tmp[tmp['date'].dt.year == year]
    if month:
        tmp = tmp[tmp['date'].dt.month == month]
    income = tmp[tmp['type'] == 'income']['amount'].sum()
    expense = tmp[tmp['type'] == 'expense']['amount'].sum()
    balance = income - expense
    return pd.DataFrame({
        "metric": ["Total Income", "Total Expense", "Balance"],
        "value": [income, expense, balance]
    })

def category_breakdown(df, year=None, month=None, tx_type='expense'):
    if df.empty:
        return pd.DataFrame(columns=["category","amount"])
    tmp = df.copy()
    tmp['date'] = pd.to_datetime(tmp['date'])
    if year:
        tmp = tmp[tmp['date'].dt.year == year]
    if month:
        tmp = tmp[tmp['date'].dt.month == month]
    tmp = tmp[tmp['type'] == tx_type]
    return tmp.groupby('category')['amount'].sum().reset_index().sort_values('amount', ascending=False)

def create_animated_chart(df_cat, title):
    if df_cat.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available", x=0.5, y=0.5, showarrow=False, font=dict(size=16))
        fig.update_layout(title=title)
    else:
        fig = px.pie(df_cat, values='amount', names='category', title=title,
                    color_discrete_sequence=px.colors.sequential.Plasma)
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(transition={'duration': 500})
    return fig

def create_trend_chart(df):
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available", x=0.5, y=0.5, showarrow=False, font=dict(size=16))
        return fig
    
    df_trend = df.copy()
    df_trend['date'] = pd.to_datetime(df_trend['date'])
    df_trend['month_year'] = df_trend['date'].dt.to_period('M').astype(str)
    
    monthly = df_trend.groupby(['month_year', 'type'])['amount'].sum().reset_index()
    monthly_pivot = monthly.pivot(index='month_year', columns='type', values='amount').fillna(0)
    
    fig = go.Figure()
    if 'income' in monthly_pivot.columns:
        fig.add_trace(go.Scatter(x=monthly_pivot.index, y=monthly_pivot['income'], 
                               name='Income', line=dict(color='#2ecc71', width=3)))
    if 'expense' in monthly_pivot.columns:
        fig.add_trace(go.Scatter(x=monthly_pivot.index, y=monthly_pivot['expense'], 
                               name='Expense', line=dict(color='#e74c3c', width=3)))
    
    fig.update_layout(
        title="Monthly Income vs Expense Trend",
        xaxis_title="Month",
        yaxis_title="Amount",
        hovermode='x unified',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )
    return fig

# ---------- Export helpers ----------
def to_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='transactions')
        # Add summary sheet
        summary = monthly_summary(df)
        summary.to_excel(writer, index=False, sheet_name='summary')
        writer.save()
    return output.getvalue()

def create_pdf_report(df, summary_df, category_df, period_name="All time", currency="PKR"):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Header
    pdf.set_font("Arial", "B", 20)
    pdf.set_text_color(102, 126, 234)  # Purple color
    pdf.cell(0, 15, f"Budget Report - {period_name}", ln=True, align='C')
    pdf.ln(10)

    # Summary
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, "Financial Summary", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", "", 12)
    for _, row in summary_df.iterrows():
        if row['metric'] == 'Balance':
            color = (0, 128, 0) if row['value'] >= 0 else (255, 0, 0)
        else:
            color = (0, 0, 0)
        pdf.set_text_color(*color)
        pdf.cell(0, 8, f"{row['metric']}: {row['value']:.2f} {currency}", ln=True)
    
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)
    
    # Category breakdown
    def add_category_breakdown(pdf, category_df, currency):
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Category Breakdown", ln=True)
        pdf.ln(5)

        pdf.set_font("Arial", "", 11)
        if category_df.empty:
            pdf.cell(0, 8, "No category data available.", ln=True)
        else:
            for _, r in category_df.iterrows():
                pdf.cell(0, 7, f"{r['category']}: {r['amount']:.2f} {currency}", ln=True)

    add_category_breakdown(pdf, category_df, currency)

    # Recent transactions
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Recent Transactions", ln=True)
    pdf.ln(5)

    if df.empty:
        pdf.cell(0, 8, "No transactions to show.", ln=True)
    else:
        # Header
        pdf.set_fill_color(102, 126, 234)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(30, 8, "Date", border=1, fill=True)
        pdf.cell(25, 8, "Type", border=1, fill=True)
        pdf.cell(50, 8, "Category", border=1, fill=True)
        pdf.cell(30, 8, f"Amount ({currency})", border=1, fill=True, ln=True)
        
        # Rows
        pdf.set_text_color(0, 0, 0)
        for _, r in df.head(20).iterrows():
            pdf.cell(30, 7, str(r['date']), border=1)
            pdf.cell(25, 7, r['type'], border=1)
            pdf.cell(50, 7, str(r['category'])[:30], border=1)
            pdf.cell(30, 7, f"{r['amount']:.2f}", border=1, ln=True)

    return pdf.output(dest='S').encode('latin-1')

# ---------- File upload processing ----------
def process_uploaded_file(uploaded_file):
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file)
        else:
            return None, "Unsupported file format. Please upload CSV or Excel file."
        
        # Validate required columns
        required_cols = ['type', 'category', 'amount', 'currency', 'date']
        if (missing_cols := [col for col in required_cols if col not in df.columns]):
            return None, f"Missing required columns: {', '.join(missing_cols)}"
        
        # Validate data types
        try:
            df['amount'] = pd.to_numeric(df['amount'])
            df['date'] = pd.to_datetime(df['date']).dt.date
        except:
            return None, "Invalid data types in amount or date columns"
            
        return df, "File processed successfully!"
        
    except Exception as e:
        return None, f"Error processing file: {str(e)}"

# ---------- Streamlit UI ----------
st.markdown('<h1 class="main-header">💸 Budget Tracker Pro</h1>', unsafe_allow_html=True)

init_db()
df = load_transactions()

# Sidebar with enhanced UI
with st.sidebar:
    st.markdown("### 💰 Add Transaction")
    
    with st.form("transaction_form", clear_on_submit=True):
        tx_type = st.selectbox("Type", ["expense", "income"])
        category = st.text_input("Category", value="General")
        amount = st.number_input("Amount", min_value=0.0, format="%.2f", step=10.0)
        currency = st.selectbox("Currency", ["PKR", "USD", "EUR", "GBP"], index=0)
        tx_date = st.date_input("Date", value=date.today())
        notes = st.text_area("Notes", placeholder="Optional notes...", height=60)
        
        if (submitted := st.form_submit_button("➕ Add Transaction", use_container_width=True)):
            if amount > 0:
                with st.spinner("Adding transaction..."):
                    add_transaction(tx_type, category.strip() or "General", amount, currency, tx_date.isoformat(), notes)
                    st.success("Transaction added successfully! ✅")
                    time.sleep(1)
                    st.rerun()
            else:
                st.error("Please enter a valid amount greater than 0.")

    st.markdown("---")
    st.markdown("### 📤 Import Data")
    
    st.markdown('<div class="upload-section">', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload CSV/Excel", type=['csv', 'xlsx'], 
                                   help="Upload file with columns: type, category, amount, currency, date")
    st.markdown('</div>', unsafe_allow_html=True)
    
    if uploaded_file is not None:
        processed_df, message = process_uploaded_file(uploaded_file)
        if processed_df is not None:
            st.success(message)
            if st.button("Import Transactions", use_container_width=True):
                with st.spinner("Importing transactions..."):
                    bulk_insert_transactions(processed_df)
                    st.success(f"Successfully imported {len(processed_df)} transactions!")
                    time.sleep(2)
                    st.rerun()
        else:
            st.error(message)

# Main content area
# Filters
st.markdown("### 📊 Dashboard")
col1, col2, col3, col4 = st.columns([2,2,2,1])
with col1:
    years = sorted({datetime.now().year} if df.empty else {d.year for d in pd.to_datetime(df['date']).dt.date}, reverse=True)
    year = st.selectbox("Year", options=["All"] + [str(y) for y in years], index=0)
with col2:
    months = list(range(1,13))
    month_names = ["All", "January","February","March","April","May","June","July","August","September","October","November","December"]
    month_idx = st.selectbox("Month", options=month_names, index=0)
with col3:
    currency_choice = st.selectbox("Currency", ["PKR", "USD", "EUR", "GBP"], index=0)
with col4:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Refresh"):
        st.rerun()

# Convert selected filters
sel_year = None if year == "All" else int(year)
sel_month = None if month_idx == "All" else (month_names.index(month_idx))

# Summary metrics with animations
st.markdown("---")
summary_df = monthly_summary(df, sel_year, sel_month)
if not summary_df.empty:
    cols = st.columns(3)
    metrics = [
        ("Total Income", "💰", "#2ecc71"),
        ("Total Expense", "💸", "#e74c3c"), 
        ("Balance", "⚖️", "#3498db")
    ]
    
    for idx, (metric, icon, color) in enumerate(metrics):
        with cols[idx]:
            value = summary_df[summary_df['metric'] == metric]['value'].values[0]
            st.markdown(f"""
            <div class="metric-card" style="background: linear-gradient(135deg, {color}20, {color}40); border-left: 4px solid {color};">
                <h3 style="margin:0; font-size:1.2rem; color:#2c3e50;">{icon} {metric}</h3>
                <h2 style="margin:0; font-size:2rem; color:{color};">{value:,.2f} {currency_choice}</h2>
            </div>
            """, unsafe_allow_html=True)

# Charts and visualizations
st.markdown("---")
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("#### 📈 Monthly Trend")
    trend_fig = create_trend_chart(df)
    st.plotly_chart(trend_fig, use_container_width=True)

with chart_col2:
    st.markdown("#### 🥧 Expense Categories")
    cat_df = category_breakdown(df, sel_year, sel_month, tx_type='expense')
    pie_fig = create_animated_chart(cat_df, "Expense Distribution")
    st.plotly_chart(pie_fig, use_container_width=True)

# Transactions table
st.markdown("---")
st.markdown("### 📋 All Transactions")
if not df.empty:
    # Apply filters to displayed table
    filtered_df = df.copy()
    if sel_year:
        filtered_df = filtered_df[pd.to_datetime(filtered_df['date']).dt.year == sel_year]
    if sel_month:
        filtered_df = filtered_df[pd.to_datetime(filtered_df['date']).dt.month == sel_month]
    
    st.dataframe(filtered_df.style.format({
        'amount': '{:,.2f}',
        'date': lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else ''
    }), use_container_width=True)
else:
    st.info("No transactions found. Start by adding transactions in the sidebar!")

# Export section
st.markdown("---")
st.markdown("### 📤 Export Data")

export_col1, export_col2, export_col3 = st.columns(3)

with export_col1:
    st.markdown("#### Excel Export")
    if st.button("📊 Export All to Excel", use_container_width=True):
        if df.empty:
            st.warning("No transactions to export.")
        else:
            excel_bytes = to_excel_bytes(df)
            st.download_button(
                "💾 Download Excel File",
                data=excel_bytes,
                file_name="budget_tracker_all.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

with export_col2:
    st.markdown("#### PDF Report")
    period_name = "All time"
    if sel_year and sel_month:
        period_name = f"{month_names[sel_month]} {sel_year}"
    elif sel_year:
        period_name = f"{sel_year}"
    
    if st.button("📄 Generate PDF Report", use_container_width=True):
        filtered = df.copy()
        if sel_year:
            filtered = filtered[pd.to_datetime(filtered['date']).dt.year == sel_year]
        if sel_month:
            filtered = filtered[pd.to_datetime(filtered['date']).dt.month == sel_month]

        if filtered.empty:
            st.warning("No data for selected filters.")
        else:
            summary = monthly_summary(filtered, None, None)
            categories = category_breakdown(filtered, None, None, tx_type='expense')
            pdf_bytes = create_pdf_report(filtered, summary, categories, period_name=period_name, currency=currency_choice)
            st.download_button(
                "📥 Download PDF Report",
                data=pdf_bytes,
                file_name=f"budget_report_{period_name.replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

with export_col3:
    st.markdown("#### Template")
    if st.button("📋 Get Sample Template", use_container_width=True):
        sample = pd.DataFrame([
            {"type":"income","category":"Salary","amount":50000,"currency":"PKR","date":date.today().isoformat(),"notes":"Monthly salary"},
            {"type":"expense","category":"Groceries","amount":8000,"currency":"PKR","date":date.today().isoformat(),"notes":"Weekly groceries"},
            {"type":"expense","category":"Rent","amount":15000,"currency":"PKR","date":date.today().isoformat(),"notes":"Monthly rent"},
            {"type":"income","category":"Freelance","amount":20000,"currency":"PKR","date":date.today().isoformat(),"notes":"Project payment"},
        ])
        st.download_button(
            "📥 Download Template",
            data=to_excel_bytes(sample),
            file_name="budget_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem;">
    <p>💡 <strong>Tips:</strong> Use consistent category names for better insights • Regularly export your data • Set monthly budgets based on your trends(Hammad_zahid)</p>
</div>
""", unsafe_allow_html=True)