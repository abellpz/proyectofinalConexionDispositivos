import httpx
import logging
import asyncio

logger = logging.getLogger("SAT-SERVICES")

TELEGRAM_TOKEN = "8908205861:AAHQiFl5Nz3oy12cnI0bUsrVeu-y37tV-jg"
TELEGRAM_CHAT_ID = "238352789"
#https://api.telegram.org/bot8908205861:AAHQiFl5Nz3oy12cnI0bUsrVeu-y37tV-jg/getUpdates
async def obtener_pronostico_lluvia(lat: float = 19.4326, lon: float = -99.1332) -> float:
    """Consulta lluvia pronosticada acumulada para las próximas 6 horas sin API key."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=precipitation&forecast_hours=6"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                datos = resp.json()
                precipitaciones = datos.get("hourly", {}).get("precipitation", [])
                return float(sum(precipitaciones))
    except Exception as e:
        logger.warning(f"Error consultando Open-Meteo: {e}")
    return 0.0

async def enviar_alerta_telegram(mensaje: str):
    """Envía un mensaje formateado a las autoridades mediante bot de Telegram."""
    #if TELEGRAM_TOKEN == "8908205861:AAHQiFl5Nz3oy12cnI0bUsrVeu-y37tV-jg":
    #    logger.info(f"[SIMULACIÓN TELEGRAM]: {mensaje}")
    #    return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    async with httpx.AsyncClient(timeout=4.0) as client:
        await client.post(url, json=payload)
        

# --- [Mantén las funciones anteriores aquí] ---

async def main():
    print("[*] Probando consulta a Open-Meteo...")
    lluvia_prevista = await obtener_pronostico_lluvia(lat=19.4326, lon=-99.1332)
    print(f"[✓] Lluvia pronosticada (próximas 6h): {lluvia_prevista:.2f} mm")

    print("\n[*] Probando despacho de notificación...")
    mensaje_prueba = (
        "⚠️ *TEST SAT-HIDRO*\n"
        f"Lluvia prevista a 6h: `{lluvia_prevista:.2f} mm`\n"
        "Estado del enlace: Operativo."
    )
    await enviar_alerta_telegram(mensaje_prueba)
    print("[✓] Notificación procesada.")

if __name__ == "__main__":
    asyncio.run(main())