#!/usr/bin/env python3
import os
import requests
import sys
import google.generativeai as genai
from datetime import datetime, timedelta
import locale

# Impostiamo la localizzazione in italiano per i nomi dei giorni
try:
    locale.setlocale(locale.LC_TIME, 'it_IT.UTF-8')
except:
    pass # Se il sistema non ha il locale italiano, usiamo quello di default

LAT = 45.0716
LON = 7.5157

def interpella_gemini(dati_meteo):
    api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('models/gemini-3.5-flash')
    
    # Ora includiamo esplicitamente il giorno della settimana (%A)
    oggi_str = datetime.now().strftime("%A %d %B")
    domani_str = (datetime.now() + timedelta(days=1)).strftime("%A %d %B")
    
    prompt = f"""
    Sei un meteorologo professionista. Scrivi un bollettino meteo coeso per Rivoli (TO) per le prossime 48 ore.
    Oggi è {oggi_str}, domani sarà {domani_str}.
    
    REGOLE DI SCRITTURA:
    1. NON usare elenchi puntati. Scrivi paragrafi fluidi.
    2. Stile: "La giornata di [Giorno] comincerà con...".
    3. Includi T-min, T-max, nuvolosità, vento/raffiche e rischio precipitazioni.
    4. Focalizzati su eventi rilevanti. Se il meteo è stabile, sintetizza. Se ci sono temporali, sii preciso sull'orario.
    
    DATI ANALITICI (Ora | T | Prec.D2 | EPS-Max | Vento | Raffica):
    {dati_meteo}
    """

    try:
        response = model.generate_content(prompt, generation_config={"temperature": 0.3})
        return response.text
    except Exception as e:
        return f"Errore AI: {e}"

def main():
    # Fetch dati 48 ore
    dati = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": LAT, "longitude": LON,
        "hourly": "temperature_2m,precipitation,cloud_cover,wind_speed_10m,wind_gusts_10m",
        "models": "icon_d2",
        "timezone": "Europe/Rome", "forecast_days": 2
    }).json()
    
    dati_eps = requests.get("https://ensemble-api.open-meteo.com/v1/ensemble", params={
        "latitude": LAT, "longitude": LON,
        "hourly": "precipitation",
        "models": "icon_d2",
        "timezone": "Europe/Rome", "forecast_days": 2
    }).json()

    # Preparazione report
    report = "Ora | T | Prec.D2 | EPS-Max | Vento | Raffica\n"
    hourly = dati.get('hourly', {})
    orari = hourly.get('time', [])
    
    for i in range(48): 
        if i >= len(orari): break
        
        eps_vals = [dati_eps['hourly'].get(f"precipitation_member{m:02d}", [0]*48)[i] or 0 for m in range(1,21)]
        eps_max = max(eps_vals) if eps_vals else 0.0
            
        t = hourly.get('temperature_2m', [0]*48)[i]
        p_d2 = hourly.get('precipitation', [0]*48)[i] or 0
        v_vel = hourly.get('wind_speed_10m', [0]*48)[i]
        v_raf = hourly.get('wind_gusts_10m', [0]*48)[i]
        
        report += f"{orari[i][-5:]} | {t}°C | {p_d2} | {eps_max:.1f} | {v_vel}km/h | {v_raf}km/h\n"

    # Invio
    bollettino = interpella_gemini(report)
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      data={"chat_id": chat_id, "text": bollettino, "parse_mode": "Markdown"})
    else:
        print(bollettino)

if __name__ == "__main__":
    main()
