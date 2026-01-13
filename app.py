import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import plotly.express as px
import plotly.graph_objects as go
import io
import requests

# --- 1. CONFIGURACIÓN Y ESTILO CORPORATIVO ---
st.set_page_config(
    page_title="Forestal Costing Pro", 
    layout="wide", 
    page_icon="🌲",
    initial_sidebar_state="expanded"
)

# CSS Profesional
st.markdown("""
<style>
    .main {background-color: #f8fafc;}
    h1, h2, h3 {color: #0f172a; font-family: 'Segoe UI', sans-serif;}
    .stMetric {
        background-color: white;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    div[data-testid="stExpander"] {
        background-color: white;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
    }
    .highlight-box {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        border-left: 6px solid #16a34a;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        text-align: center;
    }
    .kpi-card {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .kpi-title { font-size: 0.85em; color: #64748b; font-weight: 600; text-transform: uppercase; margin-bottom: 5px; }
    .kpi-value { font-size: 1.5em; font-weight: 700; color: #0f172a; }
    .kpi-sub { font-size: 0.8em; color: #94a3b8; }
    .profit-pos { color: #16a34a !important; }
    .profit-neg { color: #dc2626 !important; }
    
    /* Ocultar índice de tablas */
    thead tr th:first-child {display:none}
    tbody th {display:none}
</style>
""", unsafe_allow_html=True)

CONFIG_FILE = 'forest_config_v13_dash_time.json'

# --- 2. FUNCIONES GLOBALES ---

def fmt_money(x): 
    """Formatea números como moneda CLP"""
    if x is None: return "$ 0"
    return f"$ {x:,.0f}".replace(",", ".")

def calc_price(cost, margin_pct):
    if margin_pct >= 100: return 0 
    factor = 1 - (margin_pct / 100.0)
    return cost / factor if factor > 0 else 0

def calculate_system_costs(h_df, f_df, rrhh_df, flota_df, days_h, hrs_h, days_f, hrs_f, uf, diesel):
    # Pre-procesamiento
    h_df = h_df.fillna(0)
    f_df = f_df.fillna(0)
    rrhh_df = rrhh_df.fillna(0)
    flota_df = flota_df.fillna(0)

    # 1. Harvester
    total_h = 0
    total_h_hrs = days_h * hrs_h
    for _, row in h_df.iterrows():
        val = float(row.get('Valor', 0))
        tipo = row.get('Tipo', '$/Mes')
        frec = float(row.get('Frec', 1))
        
        cost = 0
        if tipo == '$/Mes': cost = val
        elif tipo == 'UF/Mes': cost = val * uf
        elif tipo == 'Litros/Día': cost = val * days_h * diesel
        elif tipo == '$/Ev': 
            if frec > 0 and total_h_hrs > 0: 
                cost = (val / frec) * total_h_hrs
        total_h += cost

    # 2. Forwarder
    total_f = 0
    total_f_hrs = days_f * hrs_f
    for _, row in f_df.iterrows():
        val = float(row.get('Valor', 0))
        tipo = row.get('Unidad', '$/Mes')
        
        cost = 0
        if tipo == '$/Mes': cost = val
        elif tipo == 'Litros/Día': cost = val * days_f * diesel
        total_f += cost

    # 3. Indirectos
    total_indirect = rrhh_df['Costo Empresa'].sum() + flota_df['Monto'].sum()

    return total_h, total_f, total_indirect, total_h_hrs, total_f_hrs

@st.cache_data(ttl=3600) 
def get_uf_api():
    try:
        url = "https://mindicador.cl/api/uf"
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            data = response.json()
            return data['serie'][0]['valor'], data['serie'][0]['fecha'][:10]
    except:
        return None, None
    return None, None

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.int_, np.intc, np.int64)): return int(obj)
        elif isinstance(obj, (np.float_, np.float64)): return float(obj)
        return json.JSONEncoder.default(self, obj)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_config():
    keys = ["uf_manual", "fuel_price", "h_days", "h_hours", "f_days", "f_hours", 
            "df_harvester", "df_forwarder", "df_rrhh", "df_flota", 
            "alloc_pct", "sales_price", "target_margin_h", "target_margin_f", "conv_factor"]
    
    state_to_save = {}
    for k in keys:
        if k in st.session_state:
            val = st.session_state[k]
            if isinstance(val, pd.DataFrame): state_to_save[k] = val.to_dict('records')
            else: state_to_save[k] = val
                
    with open(CONFIG_FILE, 'w') as f:
        json.dump(state_to_save, f, cls=NumpyEncoder)

# --- 3. INICIALIZACIÓN ---
saved = load_config()

def init_key(key, default_value):
    if key not in st.session_state:
        loaded_val = saved.get(key)
        if loaded_val is not None:
            if isinstance(default_value, pd.DataFrame):
                st.session_state[key] = pd.DataFrame(loaded_val)
            else:
                st.session_state[key] = loaded_val
        else:
            st.session_state[key] = default_value

init_key('uf_manual', 39755.0)
init_key('fuel_price', 774.0)
init_key('sales_price', 11500.0)
init_key('alloc_pct', 0.5)
init_key('target_margin_h', 35.0)
init_key('target_margin_f', 35.0)
init_key('conv_factor', 2.44)
init_key('h_days', 28)
init_key('h_hours', 10.0)
init_key('f_days', 28)
init_key('f_hours', 10.0)

# DataFrames
init_key('df_harvester', pd.DataFrame([
    {"Cat": "Fijos", "Ítem": "Arriendo Base", "Tipo": "$/Mes", "Frec": 1, "Valor": 10900000},
    {"Cat": "Fijos", "Ítem": "Operador T1", "Tipo": "$/Mes", "Frec": 1, "Valor": 1923721},
    {"Cat": "Variable", "Ítem": "Petróleo T1", "Tipo": "Litros/Día", "Frec": 1, "Valor": 200.0},
    {"Cat": "Mantención", "Ítem": "Mant. 600h", "Tipo": "$/Ev", "Frec": 600, "Valor": 350000},
]))

init_key('df_forwarder', pd.DataFrame([
    {"Cat": "Operación", "Ítem": "Arriendo", "Unidad": "$/Mes", "Valor": 8000000},
    {"Cat": "Operación", "Ítem": "Operador", "Unidad": "$/Mes", "Valor": 1900000},
    {"Cat": "Variable", "Ítem": "Petróleo", "Unidad": "Litros/Día", "Valor": 135.0},
]))

init_key('df_rrhh', pd.DataFrame([
    {"Cargo": "Jefe de Faena", "Sueldo Líquido": 1800000, "Costo Empresa": 2300000},
    {"Cargo": "Mecánico", "Sueldo Líquido": 1200000, "Costo Empresa": 1600000},
]))

init_key('df_flota', pd.DataFrame([
    {"Ítem": "Camionetas (Arriendo)", "Monto": 1600000},
    {"Ítem": "Combustible Apoyo", "Monto": 600000},
]))

# --- 4. SIDEBAR ---
with st.sidebar:
    st.markdown("## ⚙️ Panel de Control")
    if st.button("♻️ Resetear App", type="secondary"):
        if os.path.exists(CONFIG_FILE): os.remove(CONFIG_FILE)
        st.session_state.clear()
        st.rerun()

    with st.expander("💰 Mercado y Tarifas", expanded=True):
        use_api = st.checkbox("UF Automática", value=True)
        uf_api_val, _ = get_uf_api()
        val_uf_display = uf_api_val if (use_api and uf_api_val) else st.session_state['uf_manual']
        
        curr_uf = st.number_input("Valor UF ($)", value=float(val_uf_display), disabled=(use_api and uf_api_val is not None))
        if curr_uf != st.session_state['uf_manual']:
            st.session_state['uf_manual'] = curr_uf
            save_config()

        curr_fuel = st.number_input("Diesel ($/Lt)", value=float(st.session_state['fuel_price']), on_change=save_config, key="fuel_price")
        curr_sales = st.number_input("Tarifa Venta ($/MR)", value=float(st.session_state['sales_price']), on_change=save_config, key="sales_price")

    with st.expander("📏 Conversión Volumen"):
        curr_factor = st.number_input("Factor (m³/MR)", value=float(st.session_state.get('conv_factor', 2.44)), step=0.01, key="conv_factor_input")
        if curr_factor != st.session_state['conv_factor']:
            st.session_state['conv_factor'] = curr_factor
            save_config()

    with st.expander("⚖️ Distribución Indirectos"):
        alloc = st.slider("% Carga a Harvester", 0, 100, int(st.session_state['alloc_pct']*100)) / 100.0
        if alloc != st.session_state['alloc_pct']:
            st.session_state['alloc_pct'] = alloc
            save_config()

# --- 5. CÁLCULOS DEL SISTEMA ---
tot_h_dir, tot_f_dir, tot_ind, hrs_h, hrs_f = calculate_system_costs(
    st.session_state['df_harvester'], st.session_state['df_forwarder'], 
    st.session_state['df_rrhh'], st.session_state['df_flota'],
    int(st.session_state['h_days']), float(st.session_state['h_hours']), 
    int(st.session_state['f_days']), float(st.session_state['f_hours']), 
    curr_uf, curr_fuel
)

ind_h = tot_ind * st.session_state['alloc_pct']
ind_f = tot_ind * (1 - st.session_state['alloc_pct'])
final_h_mes = tot_h_dir + ind_h
final_f_mes = tot_f_dir + ind_f
cost_mensual_sistema = final_h_mes + final_f_mes

# Horas Operativas del Sistema (Usamos el mayor para dimensionar capacidad)
hrs_sistema_mes = max(hrs_h, hrs_f) if max(hrs_h, hrs_f) > 0 else 1

# --- 6. INTERFAZ PRINCIPAL ---
st.title("🌲 Sistema de Costos Forestales Profesional")

tab_dash, tab_h, tab_f, tab_ind, tab_sim = st.tabs([
    "📊 Dashboard Gerencial", "🚜 Harvester", "🚜 Forwarder", "👷 Indirectos", "📈 Simulador de Tarifas"
])

# --- TAB 1: DASHBOARD GERENCIAL ---
with tab_dash:
    st.markdown("### 📊 Tablero de Rentabilidad Operacional")
    
    # 1. Inputs Producción
    c_in1, c_in2, c_in3 = st.columns(3)
    with c_in1:
        st.markdown("**Producción Mensual (m³ Sólidos)**")
        prod_h_m3 = st.number_input("Harvester (m³)", value=5000.0, step=100.0)
        prod_f_m3 = st.number_input("Forwarder (m³)", value=5000.0, step=100.0)
    
    with c_in2:
        st.markdown("**Conversión a MR**")
        prod_f_mr = prod_f_m3 / st.session_state['conv_factor']
        st.metric("Total Producción MR", f"{prod_f_mr:,.1f}", f"Factor: {st.session_state['conv_factor']}")
        
    with c_in3:
        st.markdown("**Facturación**")
        ingresos_mes = prod_f_mr * st.session_state['sales_price']
        st.metric("Venta Neta Mes", fmt_money(ingresos_mes), "Base Producción Forwarder")

    st.divider()

    # 2. CÁLCULOS TEMPORALES (HORA / SEMANA / MES)
    utilidad_mes = ingresos_mes - cost_mensual_sistema
    margen_mes = (utilidad_mes / ingresos_mes * 100) if ingresos_mes > 0 else 0
    
    # Supuestos Semanales (Mes / 4) y Horarios (Mes / Horas Sistema)
    ingreso_sem = ingresos_mes / 4
    costo_sem = cost_mensual_sistema / 4
    utilidad_sem = utilidad_mes / 4
    
    ingreso_hr = ingresos_mes / hrs_sistema_mes
    costo_hr = cost_mensual_sistema / hrs_sistema_mes
    utilidad_hr = utilidad_mes / hrs_sistema_mes

    # 3. MATRIZ DE RENTABILIDAD
    st.subheader("⏱️ Rentabilidad por Escala de Tiempo")
    
    # Estilo de tarjeta personalizada
    def kpi_card(title, val1, label1, val2, label2, val3, label3, is_profit=False):
        color_class = "profit-pos" if is_profit and val3 > 0 else "profit-neg" if is_profit else ""
        return f"""
        <div class="kpi-card">
            <div class="kpi-title">{title}</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; align-items: end;">
                <div><div class="kpi-sub">{label1}</div><div class="kpi-value" style="font-size:1.1em">{fmt_money(val1)}</div></div>
                <div><div class="kpi-sub">{label2}</div><div class="kpi-value" style="font-size:1.1em; color:#ef4444">{fmt_money(val2)}</div></div>
                <div><div class="kpi-sub">{label3}</div><div class="kpi-value {color_class}" style="font-size:1.3em">{fmt_money(val3)}</div></div>
            </div>
        </div>
        """

    c_hr, c_sem, c_mes = st.columns(3)
    
    with c_hr:
        st.markdown(kpi_card("Rentabilidad por HORA", ingreso_hr, "Ingreso", costo_hr, "Costo", utilidad_hr, "Utilidad", True), unsafe_allow_html=True)
    with c_sem:
        st.markdown(kpi_card("Rentabilidad SEMANAL (Prom)", ingreso_sem, "Ingreso", costo_sem, "Costo", utilidad_sem, "Utilidad", True), unsafe_allow_html=True)
    with c_mes:
        st.markdown(kpi_card("Rentabilidad MENSUAL", ingresos_mes, "Ingreso", cost_mensual_sistema, "Costo", utilidad_mes, "Utilidad", True), unsafe_allow_html=True)

    st.write("")
    
    # 4. GRÁFICOS
    c_graph_l, c_graph_r = st.columns([1, 2])
    with c_graph_l:
        # Velocímetro Margen
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number", value = margen_mes, title = {'text': "Margen % Mes"},
            gauge = {'axis': {'range': [None, 60]}, 'bar': {'color': "#16a34a"},
                     'steps': [{'range': [0, 10], 'color': '#fee2e2'}, {'range': [10, 30], 'color': '#fef9c3'}],
                     'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 35}}
        ))
        fig_gauge.update_layout(height=300, margin=dict(l=20,r=20,t=30,b=20))
        st.plotly_chart(fig_gauge, use_container_width=True)
        
    with c_graph_r:
        # Cascada
        fig_water = go.Figure(go.Waterfall(
            name = "Finanzas", orientation = "v",
            measure = ["relative", "relative", "relative", "relative", "total"],
            x = ["Ventas", "Costo Harvester", "Costo Forwarder", "Indirectos", "UTILIDAD"],
            text = [fmt_money(ingresos_mes), fmt_money(-final_h_mes), fmt_money(-final_f_mes), fmt_money(-tot_ind), fmt_money(utilidad_mes)],
            y = [ingresos_mes, -tot_h_dir, -tot_f_dir, -tot_ind, utilidad_mes],
            connector = {"line":{"color":"rgb(63, 63, 63)"}},
            decreasing = {"marker":{"color":"#ef4444"}}, increasing = {"marker":{"color":"#16a34a"}}, totals = {"marker":{"color":"#15803d"}}
        ))
        fig_water.update_layout(title="Estructura de Resultados Mensual", height=300, margin=dict(l=20,r=20,t=40,b=20))
        st.plotly_chart(fig_water, use_container_width=True)

# --- TAB 2: HARVESTER ---
with tab_h:
    c1, c2 = st.columns([1, 3])
    with c1:
        h_days = st.number_input("Días/Mes H", value=int(st.session_state.get('h_days', 28)), key="h_days", on_change=save_config)
        h_hours = st.number_input("Horas/Día H", value=float(st.session_state.get('h_hours', 10.0)), key="h_hours", on_change=save_config)
        st.info(f"Total: {h_days*h_hours} Horas")
    with c2:
        st.subheader("Estructura de Costos")
        st.session_state['df_harvester'] = st.data_editor(
            st.session_state['df_harvester'], use_container_width=True, num_rows="dynamic", 
            column_config={"Valor": st.column_config.NumberColumn(format="$ %d", required=True), "Tipo": st.column_config.SelectboxColumn(options=["$/Mes", "UF/Mes", "Litros/Día", "$/Ev"], required=True)}
        )
        save_config()

# --- TAB 3: FORWARDER ---
with tab_f:
    c1, c2 = st.columns([1, 3])
    with c1:
        f_days = st.number_input("Días/Mes F", value=int(st.session_state.get('f_days', 28)), key="f_days", on_change=save_config)
        f_hours = st.number_input("Horas/Día F", value=float(st.session_state.get('f_hours', 10.0)), key="f_hours", on_change=save_config)
        st.info(f"Total: {f_days*f_hours} Horas")
    with c2:
        st.subheader("Estructura de Costos")
        st.session_state['df_forwarder'] = st.data_editor(
            st.session_state['df_forwarder'], use_container_width=True, num_rows="dynamic", 
            column_config={"Valor": st.column_config.NumberColumn(format="$ %d", required=True), "Unidad": st.column_config.SelectboxColumn(options=["$/Mes", "Litros/Día"], required=True)}
        )
        save_config()

# --- TAB 4: INDIRECTOS ---
with tab_ind:
    c_rrhh, c_flota = st.columns(2)
    with c_rrhh:
        st.markdown("### 👷 RRHH Indirecto")
        st.session_state['df_rrhh'] = st.data_editor(st.session_state['df_rrhh'], use_container_width=True, num_rows="dynamic", column_config={"Costo Empresa": st.column_config.NumberColumn(format="$ %d")})
    with c_flota:
        st.markdown("### 🛻 Flota y Gastos Generales")
        st.session_state['df_flota'] = st.data_editor(st.session_state['df_flota'], use_container_width=True, num_rows="dynamic", column_config={"Monto": st.column_config.NumberColumn(format="$ %d")})
    save_config()

# --- TAB 5: SIMULADOR TARIFAS ---
with tab_sim:
    st.header("🎯 Calculadora de Tarifas y Márgenes")
    
    col_input1, col_input2, col_input3 = st.columns(3)
    with col_input1:
        margin_h = st.slider("Margen Harvester (%)", 0, 60, int(st.session_state.get('target_margin_h', 35)))
        st.session_state['target_margin_h'] = margin_h
    with col_input2:
        margin_f = st.slider("Margen Forwarder (%)", 0, 60, int(st.session_state.get('target_margin_f', 35)))
        st.session_state['target_margin_f'] = margin_f
    with col_input3:
        prod_sim = st.number_input("Prod. Estimada (MR/Hr)", value=22.0, step=0.5)
        save_config()

    # Cálculos de Costo Unitario
    cost_h_hr_real = (tot_h_dir + ind_h) / hrs_h if hrs_h > 0 else 0
    cost_f_hr_real = (tot_f_dir + ind_f) / hrs_f if hrs_f > 0 else 0
    safe_prod = prod_sim if prod_sim > 0 else 1
    
    cost_unit_h = cost_h_hr_real / safe_prod
    cost_unit_f = cost_f_hr_real / safe_prod
    cost_unit_sys = cost_unit_h + cost_unit_f

    # Cálculo Tarifas
    p_h_sim = calc_price(cost_unit_h, margin_h)
    p_f_sim = calc_price(cost_unit_f, margin_f)
    profit_h = p_h_sim - cost_unit_h
    profit_f = p_f_sim - cost_unit_f

    st.divider()
    st.subheader(f"🎛️ Resultado Simulación Manual")
    
    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        st.markdown(f'<div class="highlight-box"><span class="label-text">Harvester</span><br><span class="big-number">{fmt_money(p_h_sim)}</span><br><span class="sub-text">Tarifa Sugerida / MR</span></div>', unsafe_allow_html=True)
    with col_d2:
        st.markdown(f'<div class="highlight-box"><span class="label-text">Forwarder</span><br><span class="big-number">{fmt_money(p_f_sim)}</span><br><span class="sub-text">Tarifa Sugerida / MR</span></div>', unsafe_allow_html=True)
    with col_d3:
        st.markdown(f'<div class="highlight-box" style="border-left-color: #1d4ed8;"><span class="label-text">TOTAL SISTEMA</span><br><span class="big-number" style="color:#1d4ed8;">{fmt_money(p_h_sim+p_f_sim)}</span><br><span class="sub-text">Tarifa / MR</span></div>', unsafe_allow_html=True)

    # Tabla Detalle
    st.write("")
    df_detail = pd.DataFrame({
        "Concepto": ["Harvester", "Forwarder", "SISTEMA TOTAL"],
        "Costo Unitario": [fmt_money(cost_unit_h), fmt_money(cost_unit_f), fmt_money(cost_unit_sys)],
        "Utilidad Unit.": [fmt_money(profit_h), fmt_money(profit_f), fmt_money(profit_h + profit_f)],
        "Tarifa Final": [fmt_money(p_h_sim), fmt_money(p_f_sim), fmt_money(p_h_sim + p_f_sim)],
        "Margen %": [f"{margin_h}%", f"{margin_f}%", f"{((profit_h+profit_f)/(p_h_sim+p_f_sim)*100):.1f}%"]
    })
    st.dataframe(df_detail, use_container_width=True, hide_index=True)
