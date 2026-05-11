import streamlit as st
import pandas as pd

def render_kpi_dashboard():

    st.header("Dashboard KPI Operacional")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Producción Día", "124")
    col2.metric("Horas Efectivas", "10.5")
    col3.metric("Horas Detención", "1.2")
    col4.metric("Disponibilidad", "91%")

    st.subheader("Indicadores")

    data = pd.DataFrame({
        "Operador": ["Juan", "Pedro", "Luis"],
        "Producción": [120, 98, 135],
        "Disponibilidad": [91, 88, 95]
    })

    st.dataframe(data, use_container_width=True)