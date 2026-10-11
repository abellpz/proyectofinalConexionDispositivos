# 🌊 SAT-Hidro: Sistema de Alerta Temprana para Contingencias Hidrometeorológicas

Prototipo integral de Sistema de Alerta Temprana (SAT) para la detección temprana de inundaciones, avenidas súbitas (*flash floods*) y desbordamientos de cauces. El sistema integra sensórica en el borde (física y emulada), comunicación desacoplada vía MQTT, analítica predictiva basada en Machine Learning + reglas hidrológicas en tiempo real (FastAPI), despacho multicanal de notificaciones (Telegram Bot API) y un centro de comando interactivo (Streamlit).

---

## 🏗️ Arquitectura General del Pipeline

```
  [ CAPA EDGE / SENSÓRICA ]
      ├── Hardware Físico: ESP32 (WiFi 802.11 b/g/n / Bluetooth SPP)
      ├── emulator.py (Inyección controlada de eventos hidrometeorológicos)
      └── resilient_node.py (Nodo tolerante a fallos: persistencia SQLite + buffer FIFO)
                 │
                 │ JSON Payload (MQTT QoS 1 / TCP 1883)
                 ▼
  [ BROKER DE COMUNICACIÓN ]
      Eclipse Mosquitto (listener 1883 0.0.0.0 / Topic: sensores/hidro/#)
                 │
                 │ Suscripción / Callback asíncrono
                 ▼
  [ PLATAFORMA Y MOTOR ANALÍTICO ]
      server/main.py (FastAPI + Paho-MQTT Thread)
      ├── server/services/external.py (Módulo de despacho Telegram con cooldown)
      └── modelo_inundacion.joblib (Generado con train_model.py)
                 │
                 │ REST API (GET /api/v1/estado)
                 ▼
  [ APLICACIÓN Y VISUALIZACIÓN ]
      ui/dashboard.py (Streamlit: KPIs en vivo, semáforo de riesgo y curvas históricas)
```

---

## 📂 Descripción Detallada de los Módulos

### 1. `train_model.py`
Script de ciencia de datos encargado de la síntesis de series temporales hidrológicas, ingeniería de variables y entrenamiento del modelo predictivo.
* **Ingeniería de variables:** Procesa nivel del río ($H_t$), precipitación acumulada ($P_t$) y gradiente cinético de crecida ($dH/dt = \frac{H_t - H_{t-1}}{\Delta t}$).
* **Algoritmo:** Entrena un clasificador supervisado `RandomForestClassifier` de `scikit-learn` ponderando eventos de estiaje frente a tormentas convectivas severas.
* **Persistencia:** Exporta el modelo entrenado, escaladores y metadatos hacia `modelo_inundacion.joblib`.

### 2. `modelo_inundacion.joblib`
Artefacto binario serializado que contiene el pipeline de inferencia optimizado.
* **Propósito:** Inferencia rápida en memoria dentro del backend FastAPI sin requerir reentrenamiento en caliente.
* **Salida:** Probabilidad condicional $\hat{y} = P(\text{desbordamiento} \mid H_t, P_t, dH/dt) \in [0.0, 1.0]$.

### 3. `emulator.py`
Emulador de estación hidrometeorológica en software para pruebas de estrés y validación continua sin dependencia de hardware físico.
* **Comportamiento:** Simula ciclos hidrológicos normales intercalados con inyecciones de contingencia severa (lluvias de $25\text{ a }45\text{ mm/h}$ e incrementos de nivel de $+0.25\text{ m/ciclo}$).
* **Salida:** Serializa payloads JSON equivalentes al firmware del ESP32 y los publica en el tópico MQTT `sensores/hidro/estacion_01` cada 3 segundos.

### 4. `resilient_node.py`
Nodo virtual de borde con arquitectura resiliente y tolerancia a caídas de enlace de red.
* **Mecanismo de resiliencia:** Si la conexión con el broker Mosquitto se interrumpe (código de desconexión o timeout de socket), almacena las lecturas telemétricas en una base de datos local embebida (`SQLite`) actuando como cola FIFO.
* **Flushing:** En cuanto detecta la reconexión de red (`on_connect`), extrae las lecturas almacenadas y las retransmite en ráfaga ordenada para garantizar cero pérdida de datos históricos.

### 5. `server/main.py`
Servidor central y motor analítico construido con **FastAPI**.
* **Ingesta MQTT:** Aloja un cliente `paho-mqtt` en un hilo daemon en segundo plano que escucha suscripciones sobre `sensores/hidro/#`.
* **Procesamiento híbrido:** 
  1. Valida el esquema entrante mediante modelos de `Pydantic`.
  2. Calcula la tasa dinámica de cambio $dH/dt$ en $\text{m/min}$.
  3. Carga e invoca `modelo_inundacion.joblib` para obtener la probabilidad ML.
  4. Evalúa la matriz de decisión física:
     * **NORMAL (Verde):** $H < 2.20\text{ m}$, $\hat{y} < 0.50$.
     * **ALERTA (Amarillo):** $H \ge 2.20\text{ m}$ o $dH/dt \ge 0.10\text{ m/min}$ o $\hat{y} \ge 0.60$.
     * **EMERGENCIA (Rojo):** $H \ge 3.00\text{ m}$ o ($dH/dt \ge 0.20\text{ m/min}$ con lluvia intensa) o $\hat{y} \ge 0.85$.
* **Endpoints HTTP:** Expone `/api/v1/estado` para consulta del último vector de variables y estado de alarma.

### 6. `server/services/external.py`
Módulo de servicios externos desacoplado encargado del canal de notificación remota.
* **Integración Telegram:** Despacha alertas instantáneas vía la API HTTP de Telegram (`SendMessage`) a los canales o identificadores de chat configurados.
* **Filtro Anti-Saturación (*Cooldown*):** Implementa un temporizador de histéresis (mínimo 60 segundos entre mensajes repetidos de la misma severidad) para evitar bloquear el bot o saturar al personal de Protección Civil ante ráfagas telemétricas frecuentes.

### 7. `ui/dashboard.py`
Centro de comando y visualización interactiva desarrollado con **Streamlit**.
* **Telemetría en tiempo real:** Consulta periódicamente al backend FastAPI, actualizando métricas clave ($H_t$, precipitación, $dH/dt$, estado de alerta actual).
* **Curvas hidrológicas:** Grafica la evolución temporal del río frente a las lluvias registradas.
* **Guía operativa de contingencia:** Despliega visualmente las recomendaciones y ventanas de tiempo disponibles para evacuación comunitaria según el nivel activo.

---

## ⏱️ Protocolo Hidrológico y Ventanas de Evacuación

Para un sensor emplazado a $5\text{ - }8\text{ km}$ aguas arriba de la comunidad (altura de montaje $3.5\text{ - }4.0\text{ m}$, zona ciega $\ge 25\text{ cm}$):

| Nivel de Riesgo | Color | Criterio de Disparo | Tiempo Disponible | Acciones Operativas y de Protección Civil |
| :--- | :---: | :--- | :---: | :--- |
| **PREVENTIVA** | 🟢/🟡 | $H \ge 2.20\text{ m}$ o $\frac{dH}{dt} \ge 0.10\text{ m/min}$ | **30 a 90 min** | Alistamiento de brigadas; resguardo de documentación oficial; corte preventivo de gas/luz en plantas bajas; evacuación anticipada y con calma de personas mayores, personas con movilidad reducida y ganado. |
| **ALERTA** | 🟡/🟠 | $H \ge 2.60\text{ m}$ o $\frac{dH}{dt} \ge 0.20\text{ m/min}$ | **15 a 30 min** | Cierre inmediato de vados, pasos a desnivel y puentes peatonales bajos; repliegue de brigadas de primera respuesta a cotas seguras; evacuación activa de las primeras dos líneas de ribera hacia albergues temporales. |
| **EMERGENCIA** | 🔴 | $H \ge 3.00\text{ m}$ (Cota crítica) o $\hat{y} \ge 0.85$ | **0 a 15 min** | Activación de sirenas y perifoneo comunitario continuo; evacuación vertical forzosa (segundos pisos o techos) para población rezagada; prohibición absoluta de cruce peatonal o vehicular de corrientes. |

---

## 🚀 Guía de Instalación y Puesta en Marcha

### 1. Requisitos Previos
* Python 3.10 o superior instalado.
* Broker MQTT Eclipse Mosquitto instalado y corriendo en el puerto `1883`.
* Entorno virtual de Python configurado.

### 2. Instalación de Dependencias
```bash
pip install fastapi uvicorn paho-mqtt pydantic scikit-learn joblib pandas requests streamlit pyserial
```

### 3. Entrenamiento del Modelo (Primer inicio)
Genera el artefacto del modelo si no existe en el directorio:
```bash
python train_model.py
```
*Verifica la creación exitosa del archivo `modelo_inundacion.joblib`.*

### 4. Ejecución del Sistema en Paralelo

Abre 4 terminales independientes en el directorio raíz del proyecto:

* **Terminal 1: Broker Mosquitto (si no corre como servicio de Windows):**
  ```bash
  mosquitto -c "C:\Program Files\mosquitto\mosquitto.conf" -v
  ```

* **Terminal 2: Servidor Backend FastAPI:**
  ```bash
  uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
  ```
  *La documentación interactiva estará disponible en `http://localhost:8000/docs`.*

* **Terminal 3: Ingesta Telemétrica (Elige opción A, B o C):**
  * **Opción A (Hardware físico ESP32 por WiFi):** Carga el sketch `.ino` a la placa; se conectará automáticamente al broker.
  * **Opción B (Emulador de Software):**
    ```bash
    python emulator.py
    ```
  * **Opción C (Nodo Resiliente con Buffer SQLite):**
    ```bash
    python resilient_node.py
    ```

* **Terminal 4: Dashboard Interactivo:**
  ```bash
  streamlit run ui/dashboard.py
  ```
  *Accede al panel de control desde tu navegador en `http://localhost:8501`.*

---

## 🔒 Consideraciones de Red y Resiliencia en Windows
* **Banda Wi-Fi:** El microcontrolador ESP32 opera exclusivamente en la banda de **2.4 GHz**. La laptop y el nodo deben coincidir en esta frecuencia si se utiliza la red del router doméstico.
* **Firewall:** Asegúrate de habilitar el tráfico entrante al puerto 1883 de Mosquitto:
  ```powershell
  netsh advfirewall firewall add rule name="Mosquitto 1883" dir=in action=allow protocol=TCP localport=1883
  ```
* **Mosquitto 2.x:** El archivo de configuración debe contener explícitamente:
  ```conf
  listener 1883 0.0.0.0
  allow_anonymous true
  ```