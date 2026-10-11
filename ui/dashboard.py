import streamlit as st
import requests
import time
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="SAT-Hidro Dashboard", layout="wide")

st.title("🌊 Sistema de Alerta Temprana - Cuenca Piloto")
st.caption("Monitoreo de telemetría en tiempo real, modelo ML y alertas")

# Historial en memoria de sesión
if "historico" not in st.session_state:
    st.session_state.historico = []

API_URL = "http://localhost:8000/api/v1/estado"

def obtener_datos():
    try:
        r = requests.get(API_URL, timeout=1.5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None

datos = obtener_datos()

if datos:
    # Agregar a historial
    st.session_state.historico.append({
        "hora": datetime.now().strftime("%H:%M:%S"),
        "nivel": datos["nivel_actual_m"],
        "dh_dt": datos["dH_dt_m_min"],
        "prob_ml": datos["prob_desborde_ml"] * 100
    })
    # Mantener solo las últimas 30 muestras
    if len(st.session_state.historico) > 30:
        st.session_state.historico.pop(0)

    # --- BANNER DE ALERTA ---
    colores_alerta = {
        "NORMAL": ("#10B981", "NORMAL - Condiciones Seguras"),
        "PREVENTIVA": ("#F59E0B", "PREVENTIVA - Precaución"),
        "ALERTA": ("#F97316", "ALERTA - Incremento Súbito"),
        "EMERGENCIA": ("#EF4444", "EMERGENCIA - Riesgo Inminente")
    }
    color, texto = colores_alerta.get(datos["nivel_alerta"], ("#6B7280", "DESCONOCIDO"))

    st.markdown(
        f"""
        <div style="background-color: {color}; padding: 15px; border-radius: 8px; color: white; text-align: center; font-size: 24px; font-weight: bold; margin-bottom: 20px;">
            ESTADO DEL SISTEMA: {texto}
        </div>
        """,
        unsafe_allow_html=True
    )

    # --- TARJETAS DE MÉTRICAS ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nivel del Río", f"{datos['nivel_actual_m']} m")
    c2.metric("Tasa de Cambio (dH/dt)", f"{datos['dH_dt_m_min']} m/min")
    c3.metric("Riesgo ML (60 min)", f"{int(datos['prob_desborde_ml'] * 100)} %")
    c4.metric("Dispositivo Origen", datos["device_id"])

    st.info(f"**Diagnóstico del motor:** {datos['motivo']}")

    # --- GRÁFICA TEMPORAL ---
    if len(st.session_state.historico) > 1:
        df = pd.DataFrame(st.session_state.historico)
        fig = px.line(df, x="hora", y="nivel", title="Curva de Nivel de Agua (m)", markers=True)
        fig.add_hline(y=2.0, line_dash="dash", line_color="orange", annotation_text="P80 (2.0m)")
        fig.add_hline(y=3.0, line_dash="dash", line_color="red", annotation_text="Crítico (3.0m)")
        st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("Esperando telemetría desde FastAPI (puerto 8000)... Asegúrate de que el backend esté corriendo.")

# Refresco continuo cada 3 segundos
time.sleep(3)
st.rerun()