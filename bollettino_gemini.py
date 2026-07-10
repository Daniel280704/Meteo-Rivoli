#!/usr/bin/env python3
import os
import requests
import sys

LAT = 45.0716
LON = 7.5157

def fetch_weather_data():
    # Nomi aggiornati! MeteoSwiss ora usa ICON-CH1/CH2. Aggiunto anche ICON-2I.
    params = {
        "latitude": LAT,
        "longitude": LON,
        "hourly": "precipitation",
        "models": "icon_d2,arome_france,icon_ch1,icon_ch2,icon_2i",
        "timezone": "Europe/Rome",
        "forecast_days": 1
    }
    try:
        resp = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"❌ Errore API Meteo: {e}")
        # Se l'API rifiuta la chiamata, stampiamo il vero motivo per capire chi ha causato l'errore
        if hasattr(e, 'response') and e.response is not None:
            print("Dettaglio errore:", e.response.text)
        sys.exit(1)

def interpella_gemini(dati_meteo):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("⚠️ GEMINI_API_KEY mancante! Inseriscila nei Secrets di GitHub.")
        sys.exit(1)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    prompt = f"""
    Sei un meteorologo esperto e un divulgatore scientifico. Scrivi il bollettino meteo di nowcasting per oggi a Rivoli.
    Il testo deve essere discorsivo, professionale ma accessibile, perfetto per essere letto da una community di decine di migliaia di appassionati. 
    Usa le emoji in modo appropriato.

    Dividi la cronaca in 4 fasce orarie:
    - Mattino (06-12)
    - Pomeriggio (12-18)
    - Sera (18-24)
    - Notte (00-06)

    Ecco i millimetri di pioggia previsti ora per ora dai 5 modelli ad altissima risoluzione (ICON-D2, AROME, ICON-CH1, ICON-CH2, ICON-2I).
    Analizza i dati: se tutti i modelli prevedono pioggia in una fascia oraria, dichiara una probabilità altissima (es. 100%).
    Se solo alcuni la vedono (es. temporali termici isolati), parla di "previsione incerta" o "possibilità al X%".
    Menziona i modelli per nome per dare autorevolezza tecnica. Non stampare la tabella dei dati grezzi, scrivi solo il bollettino.

    DATI GREZZI DEI MODELLI:
    {dati_meteo}
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2} 
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        risultato = resp.json()
        return risultato["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"❌ Errore API Gemini: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print("Dettaglio errore Gemini:", e.response.text)
        sys.exit(1)

def invia_telegram(testo):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": testo, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def main():
    print("📥 Scaricamento modelli meteo (D2, AROME, CH1, CH2, 2I)...")
    dati_grezzi = fetch_weather_data()
    
    orari = dati_grezzi["hourly"]["time"]
    
    # Filtro Anti-Crash nel caso in cui un modello restituisca un dato vuoto
    pioggia_d2 = [p if p is not None else 0.0 for p in dati_grezzi["hourly"]["precipitation_icon_d2"]]
    pioggia_arome = [p if p is not None else 0.0 for p in dati_grezzi["hourly"]["precipitation_arome_france"]]
    pioggia_ch1 = [p if p is not None else 0.0 for p in dati_grezzi["hourly"]["precipitation_icon_ch1"]]
    pioggia_ch2 = [p if p is not None else 0.0 for p in dati_grezzi["hourly"]["precipitation_icon_ch2"]]
    pioggia_2i = [p if p is not None else 0.0 for p in dati_grezzi["hourly"]["precipitation_icon_2i"]]
    
    # Costruiamo la tabella che leggerà Gemini
    riassunto_dati = "Ora | D2 | AROME | CH1 | CH2 | 2I\n"
    for i in range(len(orari)):
        ora = orari[i][-5:]
        riassunto_dati += f"{ora} | {pioggia_d2[i]}mm | {pioggia_arome[i]}mm | {pioggia_ch1[i]}mm | {pioggia_ch2[i]}mm | {pioggia_2i[i]}mm\n"
    
    print("🧠 Elaborazione analisi tramite Gemini 1.5 Flash...")
    bollettino_narrativo = interpella_gemini(riassunto_dati)
    
    print("✈️ Invio su Telegram...")
    invia_telegram(bollettino_narrativo)
    print("✅ Finito! Controlla Telegram.")

if __name__ == "__main__":
    main()
