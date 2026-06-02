import io
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Hotel Strela — Expenses Dashboard", layout="wide", page_icon="📊")

@st.cache_data
def load_data():
    df = pd.read_excel("DataExpenses.xlsx")
    df["Date"] = pd.to_datetime(df["Date"])
    df["Amount"] = df["Subtotal"].fillna(0)
    df["Day"] = df["Date"].dt.date
    df["Month"] = df["Date"].dt.to_period("M").astype(str)
    return df

df = load_data()

st.title("📊 Hotel Strela — Expenses Dashboard")
st.caption(f"Data from {df['Date'].min().date()} to {df['Date'].max().date()} — {len(df)} transactions")

# --- Filters ---
with st.sidebar:
    st.header("Filters")
    month_options = ["All"] + sorted(df["Month"].unique().tolist())
    selected_month = st.selectbox("Month", month_options)

    dept_options = ["All"] + sorted(df["Department"].dropna().unique().tolist())
    selected_dept = st.selectbox("Department", dept_options)

    type_options = ["All"] + sorted(df["Cost Type"].dropna().unique().tolist())
    selected_type = st.selectbox("Cost Type", type_options)

    supplier_options = ["All"] + sorted(df["Supplier"].dropna().unique().tolist())
    selected_supplier = st.selectbox("Supplier", supplier_options)

filtered = df.copy()
if selected_month != "All":
    filtered = filtered[filtered["Month"] == selected_month]
if selected_dept != "All":
    filtered = filtered[filtered["Department"] == selected_dept]
if selected_type != "All":
    filtered = filtered[filtered["Cost Type"] == selected_type]
if selected_supplier != "All":
    filtered = filtered[filtered["Supplier"] == selected_supplier]

# --- KPIs ---
total = filtered["Amount"].sum()
avg_per_day = filtered.groupby("Day")["Amount"].sum().mean()
top_dept = filtered.groupby("Department")["Amount"].sum().idxmax() if not filtered.empty else "-"
top_supplier = filtered.groupby("Supplier")["Amount"].sum().idxmax() if not filtered.empty else "-"

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Spent", f"{total:,.0f}")
k2.metric("Avg / Day", f"{avg_per_day:,.0f}")
k3.metric("Top Department", top_dept)
k4.metric("Top Supplier", top_supplier)

st.divider()

# --- Row 1: Spending over time + by Cost Type ---
c1, c2 = st.columns([2, 1])

with c1:
    daily = filtered.groupby(["Day", "Cost Type"])["Amount"].sum().reset_index()
    fig_line = px.area(
        daily, x="Day", y="Amount", color="Cost Type",
        title="Daily Spending by Cost Type",
        labels={"Amount": "Amount", "Day": "Date"},
    )
    fig_line.update_layout(legend=dict(orientation="h", y=-0.2))
    fig_line.update_yaxes(tickformat=",")
    fig_line.update_traces(hovertemplate="%{x}<br>%{y:,.0f}<extra></extra>")
    st.plotly_chart(fig_line, use_container_width=True)

with c2:
    by_type = filtered.groupby("Cost Type")["Amount"].sum().reset_index()
    fig_pie = px.pie(
        by_type, names="Cost Type", values="Amount",
        title="Spending by Cost Type",
        hole=0.4,
    )
    fig_pie.update_traces(
        textinfo="percent+label",
        hovertemplate="%{label}<br>%{value:,.0f}<br>%{percent}<extra></extra>",
    )
    st.plotly_chart(fig_pie, use_container_width=True)

# --- Row 2: By Department + Top Suppliers ---
c3, c4 = st.columns(2)

with c3:
    by_dept = (
        filtered.groupby("Department")["Amount"].sum()
        .sort_values(ascending=True).reset_index()
    )
    fig_bar = px.bar(
        by_dept, x="Amount", y="Department", orientation="h",
        title="Total Spending by Department",
        color="Amount", color_continuous_scale="Blues",
    )
    fig_bar.update_layout(coloraxis_showscale=False)
    fig_bar.update_xaxes(tickformat=",")
    fig_bar.update_traces(hovertemplate="%{y}<br>%{x:,.0f}<extra></extra>")
    st.plotly_chart(fig_bar, use_container_width=True)

with c4:
    top_suppliers = (
        filtered.groupby("Supplier")["Amount"].sum()
        .sort_values(ascending=False).head(10).reset_index()
    )
    fig_sup = px.bar(
        top_suppliers, x="Amount", y="Supplier", orientation="h",
        title="Top 10 Suppliers by Spend",
        color="Amount", color_continuous_scale="Oranges",
    )
    fig_sup.update_layout(coloraxis_showscale=False, yaxis=dict(autorange="reversed"))
    fig_sup.update_xaxes(tickformat=",")
    fig_sup.update_traces(hovertemplate="%{y}<br>%{x:,.0f}<extra></extra>")
    st.plotly_chart(fig_sup, use_container_width=True)

# --- Row 3: Department x Cost Type heatmap ---
st.subheader("Spend Heatmap — Department × Cost Type")
pivot = filtered.pivot_table(index="Department", columns="Cost Type", values="Amount", aggfunc="sum", fill_value=0)
pivot_display = pivot.map(lambda v: f"{v:,.0f}")
fig_heat = px.imshow(
    pivot, text_auto=False, aspect="auto",
    color_continuous_scale="YlOrRd",
    labels=dict(color="Amount"),
)
fig_heat.update_traces(
    text=pivot_display.values,
    texttemplate="%{text}",
    hovertemplate="%{y} / %{x}<br>%{z:,.0f}<extra></extra>",
)
st.plotly_chart(fig_heat, use_container_width=True)

# --- Raw data toggle ---
with st.expander("View raw data"):
    raw = filtered.sort_values("Date", ascending=False)
    st.dataframe(raw, use_container_width=True)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        raw.to_excel(writer, index=False, sheet_name="Expenses")
    st.download_button(
        label="⬇️ Download as Excel",
        data=buffer.getvalue(),
        file_name="expenses_export.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
