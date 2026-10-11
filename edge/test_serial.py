import serial
import time

PORT = "COM6"  # Prueba con tu COM saliente (o el alternativo si no responde)
BAUD = 115200

print(f"[*] Intentando conectar a {PORT}...")
try:
    s = serial.Serial(PORT, BAUD, timeout=3)
    print(f"[✓] Conexión física abierta con {PORT}. Leyendo buffer...")
    while True:
        raw_bytes = s.readline()
        if raw_bytes:
            print(f"[RAW]: {raw_bytes}")
        else:
            print("[...] Esperando datos del ESP32...")
except Exception as e:
    print(f"[!] Error: {e}")