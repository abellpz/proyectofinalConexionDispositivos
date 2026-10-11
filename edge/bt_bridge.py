import time
import json
from datetime import datetime, timezone
import serial
import paho.mqtt.client as mqtt

# ==========================================
# CONFIGURACIÓN
# ==========================================
# Cambia este puerto por el COM que le asignó Windows al ESP32 por Bluetooth
# (Ejemplo: "COM5", "COM6", "COM8" en el Administrador de dispositivos)
BT_PORT = "COM6"   
BAUD_RATE = 115200

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "sensores/hidro/estacion_01"

# ==========================================
# INICIALIZACIÓN MQTT
# ==========================================
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="bt_bridge_client")
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print(f"[✓] Conectado al Broker Mosquitto en {MQTT_BROKER}:{MQTT_PORT}")
except Exception as e:
    print(f"[!] Error al conectar a Mosquitto: {e}")
    exit(1)

# ==========================================
# INICIALIZACIÓN PUERTO BLUETOOTH
# ==========================================
print(f"[*] Abriendo canal Bluetooth en {BT_PORT}...")
try:
    bt_serial = serial.Serial(BT_PORT, BAUD_RATE, timeout=5)
    print(f"[✓] Enlace Bluetooth establecido con el ESP32 en {BT_PORT}.")
except Exception as e:
    print(f"[!] Error al abrir el puerto Bluetooth {BT_PORT}: {e}")
    print("    Verifica que el ESP32 esté encendido, emparejado en Windows y el puerto COM sea el correcto.")
    exit(1)

# ==========================================
# BUCLE PRINCIPAL DE REENVÍO
# ==========================================
print("[*] Reenviando datos Bluetooth hacia MQTT...")
try:
    while True:
        linea = bt_serial.readline().decode("utf-8", errors="ignore").strip()
        if linea.startswith("{") and linea.endswith("}"):
            try:
                data = json.loads(linea)
                # Inyectar timestamp actual para cálculo preciso de dH/dt en el backend
                data["timestamp"] = datetime.now(timezone.utc).isoformat()
                
                payload_actualizado = json.dumps(data)
                mqtt_client.publish(MQTT_TOPIC, payload_actualizado, qos=0)
                print(f"[BT -> MQTT]: {payload_actualizado}")
            except json.JSONDecodeError:
                pass
except KeyboardInterrupt:
    print("\n[*] Cerrando puente Bluetooth...")
    bt_serial.close()
    mqtt_client.loop_stop()
    mqtt_client.disconnect()