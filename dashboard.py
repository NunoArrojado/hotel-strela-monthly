import io
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Hotel Strela — Expenses Dashboard", layout="wide", page_icon="📊")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@st.cache_resource
def _gspread_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    return gspread.authorize(creds)


def _sheet():
    return _gspread_client().open_by_key(st.secrets["sheet_id"]).sheet1


@st.cache_data(ttl=300)
def load_data():
    records = _sheet().get_all_records()
    df = pd.DataFrame(records)
    if df.empty:
        return df
    df = df[df["Date"].astype(str).str.strip() != ""]
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True)
    df["Amount"] = pd.to_numeric(df["Subtotal"], errors="coerce").fillna(0)
    df["Day"] = df["Date"].dt.date
    df["Month"] = df["Date"].dt.to_period("M").astype(str)
    df["_row"] = range(2, len(df) + 2)  # actual Google Sheets row number (header = row 1)
    return df


def _write(data):
    sh = _sheet()
    headers = sh.row_values(1)
    sh.append_row([data.get(h, "") for h in headers], value_input_option="USER_ENTERED")
    st.cache_data.clear()


def _update(sheet_row, data):
    sh = _sheet()
    headers = sh.row_values(1)
    for i, h in enumerate(headers, 1):
        if h in data:
            sh.update_cell(sheet_row, i, data[h])
    st.cache_data.clear()


def _delete(sheet_row):
    _sheet().delete_rows(sheet_row)
    st.cache_data.clear()


df = load_data()
tab_dash, tab_manage = st.tabs(["📊 Dashboard", "✏️ Manage Data"])

# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

with tab_dash:
    st.title("📊 Hotel Strela — Expenses Dashboard")
    if not df.empty:
        st.caption(
            f"Data from {df['Date'].min().date()} to {df['Date'].max().date()} — {len(df)} transactions"
        )

    with st.sidebar:
        st.header("Filters")
        month_options = ["All"] + sorted(df["Month"].unique().tolist())
        selected_month = st.selectbox("Month", month_options)
        dept_opts = ["All"] + sorted(df["Department"].dropna().unique().tolist())
        selected_dept = st.selectbox("Department", dept_opts)
        type_opts = ["All"] + sorted(df["Cost Type"].dropna().unique().tolist())
        selected_type = st.selectbox("Cost Type", type_opts)
        supplier_opts = ["All"] + sorted(df["Supplier"].dropna().unique().tolist())
        selected_supplier = st.selectbox("Supplier", supplier_opts)

    filtered = df.copy()
    if selected_month != "All":
        filtered = filtered[filtered["Month"] == selected_month]
    if selected_dept != "All":
        filtered = filtered[filtered["Department"] == selected_dept]
    if selected_type != "All":
        filtered = filtered[filtered["Cost Type"] == selected_type]
    if selected_supplier != "All":
        filtered = filtered[filtered["Supplier"] == selected_supplier]

    total = filtered["Amount"].sum()
    avg_per_day = filtered.groupby("Day")["Amount"].sum().mean() if not filtered.empty else 0
    top_dept = filtered.groupby("Department")["Amount"].sum().idxmax() if not filtered.empty else "-"
    top_supplier = filtered.groupby("Supplier")["Amount"].sum().idxmax() if not filtered.empty else "-"

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Spent", f"{total:,.0f}")
    k2.metric("Avg / Day", f"{avg_per_day:,.0f}")
    k3.metric("Top Department", top_dept)
    k4.metric("Top Supplier", top_supplier)

    st.divider()

    if filtered.empty:
        st.info("No data matches the current filters.")
    else:
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
                title="Spending by Cost Type", hole=0.4,
            )
            fig_pie.update_traces(
                textinfo="percent+label",
                hovertemplate="%{label}<br>%{value:,.0f}<br>%{percent}<extra></extra>",
            )
            st.plotly_chart(fig_pie, use_container_width=True)

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
            top_s = (
                filtered.groupby("Supplier")["Amount"].sum()
                .sort_values(ascending=False).head(10).reset_index()
            )
            fig_sup = px.bar(
                top_s, x="Amount", y="Supplier", orientation="h",
                title="Top 10 Suppliers by Spend",
                color="Amount", color_continuous_scale="Oranges",
            )
            fig_sup.update_layout(coloraxis_showscale=False, yaxis=dict(autorange="reversed"))
            fig_sup.update_xaxes(tickformat=",")
            fig_sup.update_traces(hovertemplate="%{y}<br>%{x:,.0f}<extra></extra>")
            st.plotly_chart(fig_sup, use_container_width=True)

        st.subheader("Spend Heatmap — Department × Cost Type")
        pivot = filtered.pivot_table(
            index="Department", columns="Cost Type",
            values="Amount", aggfunc="sum", fill_value=0,
        )
        pivot_display = pivot.map(lambda v: f"{v:,.0f}")
        fig_heat = px.imshow(
            pivot, text_auto=False, aspect="auto",
            color_continuous_scale="YlOrRd", labels=dict(color="Amount"),
        )
        fig_heat.update_traces(
            text=pivot_display.values, texttemplate="%{text}",
            hovertemplate="%{y} / %{x}<br>%{z:,.0f}<extra></extra>",
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    with st.expander("View raw data"):
        if not filtered.empty:
            raw = filtered.sort_values("Date", ascending=False)
            skip = {"Amount", "Day", "Month", "_row"}
            display_cols = [c for c in raw.columns if c not in skip]
            st.dataframe(raw[display_cols], use_container_width=True)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                raw[display_cols].to_excel(writer, index=False, sheet_name="Expenses")
            st.download_button(
                label="⬇️ Download as Excel",
                data=buffer.getvalue(),
                file_name="expenses_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

# ─────────────────────────────────────────────────────────────────────────────
# MANAGE DATA
# ─────────────────────────────────────────────────────────────────────────────

with tab_manage:
    st.header("Manage Expenses")
    sub_add, sub_edit, sub_del = st.tabs(["Add Entry", "Edit Entry", "Delete Entry"])

    # ── Add ──────────────────────────────────────────────────────────────────
    with sub_add:
        st.subheader("Add New Entry")
        c1, c2 = st.columns(2)
        with c1:
            add_date = st.date_input("Date", key="add_date")
            add_dept = st.text_input("Department", key="add_dept")
            add_type = st.text_input("Cost Type", key="add_ctype")
        with c2:
            add_amount = st.number_input("Amount", min_value=0.0, step=0.01, format="%.2f", key="add_amount")
            add_supplier = st.text_input("Supplier", key="add_supplier")

        if not df.empty:
            with st.expander("Existing values (reference)"):
                r1, r2, r3 = st.columns(3)
                r1.write("**Departments**\n" + "\n".join(f"- {v}" for v in sorted(df["Department"].dropna().unique())))
                r2.write("**Cost Types**\n" + "\n".join(f"- {v}" for v in sorted(df["Cost Type"].dropna().unique())))
                r3.write("**Suppliers**\n" + "\n".join(f"- {v}" for v in sorted(df["Supplier"].dropna().unique())))

        if st.button("Add Entry", type="primary", key="btn_add"):
            if not add_dept.strip() or not add_type.strip() or not add_supplier.strip():
                st.error("Department, Cost Type, and Supplier cannot be empty.")
            else:
                _write({
                    "Date": add_date.strftime("%Y-%m-%d"),
                    "Department": add_dept.strip(),
                    "Cost Type": add_type.strip(),
                    "Supplier": add_supplier.strip(),
                    "Subtotal": add_amount,
                })
                st.success("Entry added.")
                st.rerun()

    # ── Edit ─────────────────────────────────────────────────────────────────
    with sub_edit:
        st.subheader("Edit Entry")
        if df.empty:
            st.info("No entries to edit.")
        else:
            search_e = st.text_input(
                "Search entries",
                placeholder="Filter by date, supplier, department...",
                key="edit_search",
            )
            edf = (
                df[df.apply(
                    lambda r: search_e.lower() in
                    f"{r['Date'].date()} {r['Supplier']} {r['Department']} {r['Cost Type']}".lower(),
                    axis=1,
                )]
                if search_e else df
            )

            if edf.empty:
                st.info("No entries match your search.")
            else:
                labels_e = edf.apply(
                    lambda r: f"{r['Date'].date()} | {r['Supplier']} | {r['Amount']:,.0f}", axis=1
                ).tolist()
                sel_e = st.selectbox(
                    "Select entry", range(len(labels_e)),
                    format_func=lambda i: labels_e[i], key="edit_sel",
                )
                row_e = edf.iloc[sel_e]

                c1, c2 = st.columns(2)
                with c1:
                    edit_date = st.date_input("Date", value=row_e["Date"].date(), key="edit_date")
                    edit_dept = st.text_input("Department", value=str(row_e["Department"]), key="edit_dept")
                    edit_type = st.text_input("Cost Type", value=str(row_e["Cost Type"]), key="edit_ctype")
                with c2:
                    edit_amount = st.number_input(
                        "Amount", value=float(row_e["Amount"]),
                        min_value=0.0, step=0.01, format="%.2f", key="edit_amount",
                    )
                    edit_supplier = st.text_input("Supplier", value=str(row_e["Supplier"]), key="edit_supplier")

                if st.button("Save Changes", type="primary", key="btn_edit"):
                    _update(int(row_e["_row"]), {
                        "Date": edit_date.strftime("%Y-%m-%d"),
                        "Department": edit_dept.strip(),
                        "Cost Type": edit_type.strip(),
                        "Supplier": edit_supplier.strip(),
                        "Subtotal": edit_amount,
                    })
                    st.success("Entry updated.")
                    st.rerun()

    # ── Delete ───────────────────────────────────────────────────────────────
    with sub_del:
        st.subheader("Delete Entry")
        if df.empty:
            st.info("No entries to delete.")
        else:
            search_d = st.text_input(
                "Search entries",
                placeholder="Filter by date, supplier, department...",
                key="del_search",
            )
            ddf = (
                df[df.apply(
                    lambda r: search_d.lower() in
                    f"{r['Date'].date()} {r['Supplier']} {r['Department']} {r['Cost Type']}".lower(),
                    axis=1,
                )]
                if search_d else df
            )

            if ddf.empty:
                st.info("No entries match your search.")
            else:
                labels_d = ddf.apply(
                    lambda r: f"{r['Date'].date()} | {r['Supplier']} | {r['Amount']:,.0f}", axis=1
                ).tolist()
                sel_d = st.selectbox(
                    "Select entry", range(len(labels_d)),
                    format_func=lambda i: labels_d[i], key="del_sel",
                )
                row_d = ddf.iloc[sel_d]

                st.warning(f"About to delete: **{labels_d[sel_d]}**")
                if st.button("Delete Entry", type="primary", key="btn_del"):
                    _delete(int(row_d["_row"]))
                    st.success("Entry deleted.")
                    st.rerun()
