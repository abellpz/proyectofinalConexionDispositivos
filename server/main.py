import json
import logging
import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field
import paho.mqtt.client as mqtt
import joblib
import numpy as np

# Importar las funciones de external.py
from server.services.external import obtener_pronostico_lluvia, enviar_alerta_telegram

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("SAT-HIDRO")

# ==========================================
# CARGA DEL MODELO ML
# ==========================================
try:
    ml_model = joblib.load("modelo_inundacion.joblib")
    logger.info("[✓] Modelo ML (RandomForest) cargado exitosamente.")
except Exception as e:
    ml_model = None
    logger.warning(f"[!] No se encontró modelo_inundacion.joblib ({e}). Inferencia ML desactivada.")

# Variable global para lluvia acumulada de Open-Meteo
lluvia_pronostico_6h = 0.0

# ==========================================
# MODELOS DE DATOS
# ==========================================
class TelemetriaLectura(BaseModel):
    device_id: str
    timestamp: str
    nivel_rio_m: float = Field(..., ge=0.0)
    lluvia_mm_h: float = Field(..., ge=0.0)
    bateria_v: float
    rssi_dbm: int

class EstadoAlerta(BaseModel):
    device_id: str
    nivel_alerta: str  # NORMAL, PREVENTIVA, ALERTA, EMERGENCIA
    nivel_actual_m: float
    dH_dt_m_min: float
    prob_desborde_ml: float
    motivo: str
    timestamp: str

# ==========================================
# MOTOR DE INFERENCIA Y DECISIÓN
# ==========================================
class MotorAlertas:
    NIVEL_P80 = 2.00
    NIVEL_P95 = 3.00
    NIVEL_CRITICO = 4.20
    DHDT_CRITICO = 0.15

    def __init__(self):
        self.historial = deque(maxlen=10)
        self.ultimo_estado: Optional[EstadoAlerta] = None
        self.ultima_alerta_enviada = "NORMAL"

    def calcular_dh_dt(self, nivel_actual: float, t_actual: datetime) -> float:
        if not self.historial:
            return 0.0
        nivel_prev, t_prev = self.historial[-1]
        delta_t_min = (t_actual - t_prev).total_seconds() / 60.0
        if delta_t_min <= 0:
            return 0.0
        return round((nivel_actual - nivel_prev) / delta_t_min, 4)

    def predecir_ml(self, nivel: float, dh_dt: float, lluvia_1h: float) -> float:
        if ml_model is None:
            return 0.0
        try:
            # Vector: ['nivel_rio_m', 'dH_dt_m_min', 'lluvia_1h_mm', 'lluvia_prev_6h_mm']
            features = np.array([[nivel, dh_dt, lluvia_1h, lluvia_pronostico_6h]])
            prob = ml_model.predict_proba(features)[0][1]
            return round(float(prob), 3)
        except Exception as e:
            logger.error(f"Error en inferencia ML: {e}")
            return 0.0

    async def evaluar(self, lectura: TelemetriaLectura) -> EstadoAlerta:
        try:
            t_actual = datetime.fromisoformat(lectura.timestamp.replace("Z", "+00:00"))
        except Exception:
            t_actual = datetime.now(timezone.utc)

        dH_dt = self.calcular_dh_dt(lectura.nivel_rio_m, t_actual)
        self.historial.append((lectura.nivel_rio_m, t_actual))

        prob_ml = self.predecir_ml(lectura.nivel_rio_m, dH_dt, lectura.lluvia_mm_h)

        nivel = lectura.nivel_rio_m
        alerta = "NORMAL"
        motivo = "Condiciones normales de cauce."

        if nivel >= self.NIVEL_CRITICO or prob_ml >= 0.85:
            alerta = "EMERGENCIA"
            motivo = f"Riesgo crítico. Nivel: {nivel}m, Prob ML: {int(prob_ml*100)}%"
        elif nivel >= self.NIVEL_P95 or (nivel >= self.NIVEL_P80 and dH_dt >= self.DHDT_CRITICO) or prob_ml >= 0.65:
            alerta = "ALERTA"
            motivo = f"Ascenso rápido. Nivel: {nivel}m, dH/dt: {dH_dt}m/min, Prob ML: {int(prob_ml*100)}%"
        elif nivel >= self.NIVEL_P80 or lectura.lluvia_mm_h >= 25.0:
            alerta = "PREVENTIVA"
            motivo = f"Precipitación sostenida o umbral P80 alcanzado ({lectura.lluvia_mm_h}mm/h)."

        estado = EstadoAlerta(
            device_id=lectura.device_id,
            nivel_alerta=alerta,
            nivel_actual_m=nivel,
            dH_dt_m_min=dH_dt,
            prob_desborde_ml=prob_ml,
            motivo=motivo,
            timestamp=lectura.timestamp
        )
        self.ultimo_estado = estado

        # Disparar alerta a Telegram solo si hay cambio a estado de riesgo
        if alerta in ("ALERTA", "EMERGENCIA") and self.ultima_alerta_enviada != alerta:
            msg = (
                f"🚨 *ALERTA SAT-HIDRO: {alerta}*\n"
                f"• Dispositivo: `{lectura.device_id}`\n"
                f"• Nivel Río: `{nivel} m`\n"
                f"• Cambio (dH/dt): `{dH_dt} m/min`\n"
                f"• Prob. Desborde: `{int(prob_ml * 100)}%`\n"
                f"• Motivo: {motivo}"
            )
            asyncio.create_task(enviar_alerta_telegram(msg))
            self.ultima_alerta_enviada = alerta
        elif alerta == "NORMAL":
            self.ultima_alerta_enviada = "NORMAL"

        return estado

motor = MotorAlertas()

# ==========================================
# MQTT CLIENT (Loop Async)
# ==========================================
loop = None

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        lectura = TelemetriaLectura(**data)
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(motor.evaluar(lectura), loop)
    except Exception as e:
        logger.error(f"Error parseando mensaje MQTT: {e}")

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="fastapi_core")
mqtt_client.on_message = on_message

# Tarea de fondo para refrescar Open-Meteo cada 15 min
async def tarea_fondo_meteo():
    global lluvia_pronostico_6h
    while True:
        lluvia_pronostico_6h = await obtener_pronostico_lluvia()
        logger.info(f"[Open-Meteo] Pronóstico lluvia actualizado: {lluvia_pronostico_6h:.2f} mm")
        await asyncio.sleep(900)

app = FastAPI(title="SAT-Hidro Core Engine")

@app.on_event("startup")
async def startup_event():
    global loop
    loop = asyncio.get_running_loop()
    try:
        mqtt_client.connect("localhost", 1883, 60)
        mqtt_client.subscribe("sensores/hidro/#", qos=0)
        mqtt_client.loop_start()
        logger.info("[✓] Suscrito a Mosquitto en localhost:1883")
    except Exception as e:
        logger.error(f"[!] No se pudo conectar a Mosquitto: {e}")
    asyncio.create_task(tarea_fondo_meteo())

@app.on_event("shutdown")
def shutdown_event():
    mqtt_client.loop_stop()
    mqtt_client.disconnect()

@app.get("/api/v1/estado", response_model=Optional[EstadoAlerta])
def obtener_estado():
    return motor.ultimo_estado