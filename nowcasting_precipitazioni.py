#!/usr/bin/env python3
import os
import sys
import requests
from datetime import datetime

# --- CONFIGURAZIONE ---
LAT = 45.07347491421504
LON = 7.543461388723449
STATE_FILE = "stato_nowcasting.txt"

def get_avg_arrays(*arrays):
    valid_arrays = [a for a in arrays if a and isinstance(a, list) and len(a) > 0]
    if not valid_arrays: return []
    max_len = max(len(a) for a in valid_arrays)
    result = []
    for i in range(max_len):
        vals = [a[i] for a in valid_arrays if i < len(a) and a[i] is not None]
        if vals: result.append(sum(vals) / len(vals))
        else: result.append(0.0)
    return result

def arrotonda_prob(prob):
    if prob < 15: return 0
    return max(20, min(100, int(round(prob / 10.0) * 10)))

def ottieni_fascia(ora):
    if 0 <= ora < 6: return "la notte"
    elif 6 <= ora < 12: return "il mattino"
    elif 12 <= ora < 18: return "il pomeriggio"
    else: return "la serata"

def main():
    mese_corrente = datetime.now().month
    
    # Esegui solo da Marzo (3) a Ottobre (10)
    if not (3 <= mese_corrente <= 10):
        print("Mese fuori dal periodo di instabilità convettiva (Mar-Ott). Nessuna azione.")
        sys.exit(0)

    dt_oggi = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    ora_attuale = datetime.now().hour
    oggi_str = datetime.now().strftime("%Y-%m-%d")

    # Gestione dello stato
    prob_mattino = 0
    alert_sent = False
    
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            parts = f.read().strip().split(",")
            if len(parts) == 3 and parts[0] == oggi_str:
                prob_mattino = int(parts[1])
                alert_sent = parts[2] == "1"

    if alert_sent:
        print("✅ Allerta nowcasting già inviata oggi. Attendo domani.")
        sys.exit(0)

    # Solo 1 giorno di forecast per alleggerire la richiesta
    p_ch2 = {"latitude": LAT, "longitude": LON, "timezone": "auto", "forecast_days": 1, "models": "meteoswiss_icon_ch2", 
             "daily": "precipitation_probability_max", "hourly": "rain,snowfall,cape"}
    p_sea = {"latitude": LAT, "longitude": LON, "timezone": "auto", "forecast_days": 1, "models": "dwd_icon_seamless", 
             "daily": "precipitation_probability_max", "hourly": "rain,snowfall,cape"}

    try:
        d_ch2 = requests.get("https://api.open-meteo.com/v1/forecast", params=p_ch2, timeout=30).json()
        d_sea = requests.get("https://api.open-meteo.com/v1/forecast", params=p_sea, timeout=30).json()
    except Exception as e:
        print(f"⚠️ Errore download dati API: {e}")
        sys.exit(1)

    # Estrazione probabilità massima di oggi
    prob_det_avg = get_avg_arrays(d_ch2.get('daily', {}).get('precipitation_probability_max'), 
                                  d_sea.get('daily', {}).get('precipitation_probability_max'))
    if not prob_det_avg:
        sys.exit(0)
        
    prob_max_oggi = prob_det_avg[0]

    # Estrazione dati orari per oggi
    orari = d_ch2.get('hourly', {}).get('time', [])
    rain_avg = get_avg_arrays(d_ch2.get('hourly', {}).get('rain'), d_sea.get('hourly', {}).get('rain'))
    cape_avg = get_avg_arrays(d_ch2.get('hourly', {}).get('cape'), d_sea.get('hourly', {}).get('cape'))
    snow_avg = get_avg_arrays(d_ch2.get('hourly', {}).get('snowfall'), d_sea.get('hourly', {}).get('snowfall'))

    is_instabile = max(cape_avg) > 400 if cape_avg else False
    soglia = 15 if is_instabile else 50

    # Se è il primo avvio della giornata (es. al mattino), salva la baseline
    if not os.path.exists(STATE_FILE) or (os.path.exists(STATE_FILE) and parts[0] != oggi_str):
        print(f"Salvataggio probabilità di base del mattino: {prob_max_oggi}%")
        with open(STATE_FILE, "w") as f:
            f.write(f"{oggi_str},{int(prob_max_oggi)},0")
        sys.exit(0)

    # Definiamo la finestra di 6 ore (limitata alle 23 per non uscire dagli array giornalieri)
    ora_fine_finestra = min(23, ora_attuale + 6)

    # Verifica se c'è un peggioramento decisivo rispetto al mattino
    if prob_mattino < soglia and prob_max_oggi >= soglia:
        ore_pioggia = []
        for i, t_str in enumerate(orari):
            dt_h = datetime.fromisoformat(t_str)
            # Filtriamo solo le ore nella finestra delle prossime 6 ore
            if ora_attuale <= dt_h.hour <= ora_fine_finestra:
                prec_h = rain_avg[i] + snow_avg[i]
                if prec_h >= 0.2:
                    ore_pioggia.append(dt_h.hour)

        if ore_pioggia:
            inizio = min(ore_pioggia)
            fine = max(ore_pioggia)
            fascia = ottieni_fascia(inizio)
            
            tipo = "rovesci o temporali" if is_instabile else "piogge o rovesci"
            prob_tonda = arrotonda_prob(prob_max_oggi)
            
            testo_allerta = f"⚠️ <b>NOWCASTING PRECIPITAZIONI</b>\n\nNelle prossime ore la probabilità di {tipo} per {fascia} risulta in aumento ({prob_tonda}%), con inizio previsto attorno alle ore {inizio} e fine verso le ore {fine}."
            
            # Invio Telegram
            token = os.getenv("TELEGRAM_TOKEN")
            chat_id = os.getenv("TELEGRAM_CHAT_ID")
            
            if token and chat_id:
                resp = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": testo_allerta, "parse_mode": "HTML"})
                if resp.status_code == 200:
                    print("Allerta nowcasting inviata con successo!")
                    # Aggiorna lo stato bloccando ulteriori avvisi per oggi
                    with open(STATE_FILE, "w") as f:
                        f.write(f"{oggi_str},{prob_mattino},1")
                else:
                    print(f"Errore Telegram: {resp.text}")
            else:
                print("Mancano credenziali Telegram. Stampo a video:\n" + testo_allerta)

if __name__ == "__main__":
    main()
