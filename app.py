import streamlit as st

from segav_core.ops_reportes import render_operational_form
from segav_core.ops_kpi import render_kpi_dashboard

st.set_page_config(
    page_title="GYDMANAGER",
    layout="wide"
)

st.title("GYDMANAGER")
st.markdown("### Plataforma Operacional y KPI")

st.sidebar.title("GYDMANAGER")

menu = st.sidebar.selectbox(
    "Seleccionar módulo",
    [
        "Reportes Operacionales",
        "KPI Operacional"
    ]
)

if menu == "Reportes Operacionales":
    render_operational_form()

elif menu == "KPI Operacional":
    render_kpi_dashboard()