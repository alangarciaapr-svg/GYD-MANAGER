import streamlit as st

def render_operational_form():
    st.header("Reportes Operacionales")

    with st.form("reporte_operacional"):

        col1, col2 = st.columns(2)

        with col1:
            fecha = st.date_input("Fecha")
            turno = st.selectbox("Turno", ["Día", "Noche"])
            operador = st.text_input("Operador")
            equipo = st.text_input("Equipo")

        with col2:
            supervisor = st.text_input("Supervisor")
            faena = st.text_input("Faena")
            horometro_inicio = st.number_input("Horómetro Inicio", min_value=0.0)
            horometro_fin = st.number_input("Horómetro Final", min_value=0.0)

        st.subheader("Producción")

        horas_trabajadas = st.number_input("Horas trabajadas", min_value=0.0)
        horas_detencion = st.number_input("Horas detención", min_value=0.0)
        combustible = st.number_input("Combustible", min_value=0.0)
        produccion = st.number_input("Producción", min_value=0.0)

        observaciones = st.text_area("Observaciones")

        enviado = st.form_submit_button("Guardar Reporte")

        if enviado:
            st.success("Reporte guardado correctamente.")