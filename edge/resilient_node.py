import time
from collections import deque

cola_buffer_offline = deque(maxlen=500)
red_disponible = True

def despachar_telemetria(datos):
    global red_disponible
    if red_disponible:
        # Si había paquetes rezagados en el buffer, se envían primero
        while cola_buffer_offline:
            paquete_antiguo = cola_buffer_offline.popleft()
            print(f"[REINTENTO BUFFER] Despachando paquete rezagado: {paquete_antiguo['timestamp']}")
        
        print(f"[ONLINE] Enviando lectura actual: {datos['timestamp']}")
    else:
        cola_buffer_offline.append(datos)
        print(f"[OFFLINE] Sin red. Lectura retenida en buffer ({len(cola_buffer_offline)} en cola).")