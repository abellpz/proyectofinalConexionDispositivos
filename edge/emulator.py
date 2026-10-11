import time
import json
import random
import paho.mqtt.client as mqtt
from datetime import datetime, timezone

BROKER = "localhost"
PORT = 1883
TOPIC = "sensores/hidro/estacion_01"
CLIENT_ID = "esp32_emulator_cuenca"

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=CLIENT_ID)

def conectar_broker():
    try:
        client.connect(BROKER, PORT, 60)
        client.loop_start()
        print(f"[*] Conectado al broker MQTT en {BROKER}:{PORT}")
    except Exception as e:
        print(f"[!] Error al conectar al broker: {e}")
        exit(1)

def generar_telemetria(paso: int):
    # Nivel base del río: 1.20 metros
    nivel_base = 1.20
    
    # Inyectar una crecida severa a partir del ciclo 15
    if paso >= 15:
        aumento_crecida = (paso - 14) * 0.28
        lluvia_intensa = random.uniform(25.0, 50.0)
    else:
        aumento_crecida = 0.0
        lluvia_intensa = random.uniform(0.0, 2.0)

    # Ruido gaussiano para emular oscilaciones reales del agua
    ruido = random.gauss(0, 0.02)
    nivel_actual = round(max(0.0, nivel_base + aumento_crecida + ruido), 3)

    payload = {
        "device_id": "ST-RIO-01",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nivel_rio_m": nivel_actual,
        "lluvia_mm_h": round(lluvia_intensa, 2),
        "bateria_v": round(random.uniform(3.9, 4.1), 2),
        "rssi_dbm": random.randint(-75, -60)
    }
    return payload

if __name__ == "__main__":
    conectar_broker()
    paso = 0
    print("[*] Iniciando transmisión de telemetría (Ctrl+C para detener)...")
    try:
        while True:
            paso += 1
            data = generar_telemetria(paso)
            client.publish(TOPIC, json.dumps(data), qos=1)
            print(f"[{data['timestamp']}] Enviado: Nivel={data['nivel_rio_m']}m, Lluvia={data['lluvia_mm_h']}mm/h")
            time.sleep(3)  # Intervalo de envío simulado
    except KeyboardInterrupt:
        print("\n[*] Deteniendo emulador...")
        client.loop_stop()
        client.disconnect()