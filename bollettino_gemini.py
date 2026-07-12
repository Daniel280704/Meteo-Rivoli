#!/usr/bin/env python3
import os
import requests
import sys
import google.generativeai as genai
from datetime import datetime, timedelta
import locale

# Tentativo di usare l'italiano per i giorni della settimana
try:
    locale.setlocale(locale.LC_TIME, 'it_IT.UTF-8')
except:
    pass

LAT = 45.073443
LON = 7.543472

def interpella_gemini(dati_meteo, info_giornaliere):
    api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('models/gemini-3-flash-preview')    

    oggi_str = datetime.now().strftime("%A %d %B")
    domani_str = (datetime.now() + timedelta(days=1)).strftime("%A %d %B")

    prompt = f"""
    Sei un meteorologo professionista. Scrivi un bollettino meteo discorsivo per Rivoli (TO) per le prossime 48 ore.
    Oggi è {oggi_str}, domani sarà {domani_str}.
    
    RIFERIMENTI UFFICIALI (Usa questi valori per le temperature min/max):
    {info_giornaliere}

    REGOLE DI SCRITTURA (BOLLETTINO AVANZATO):
    1. NON usare elenchi puntati. Scrivi paragrafi fluidi e professionali.
    2. Usa le temperature min/max fornite nei riferimenti ufficiali come base della narrazione.
    
    REGOLA PRECIPITAZIONI E PROBABILITÀ (CRITICA):
    3. Analizza la colonna 'Probabilità'. Se indica 'Assente', IGNORA TOTALMENTE il tema della pioggia. Se invece è presente:
       - STAGIONALITÀ: Tra MARZO e OTTOBRE usa "rovesci" o "temporali". Tra NOVEMBRE e FEBBRAIO usa "piogge" o "precipitazioni".
       - FORMATO ORARIO: Raggruppa gli orari indicando le fasce coperte dai fenomeni (es. "tra le 16 e le 21"). NON esprimere le ore come 16:00, usa solo il numero intero (es. le 16, le 18).
       - Riporta il livello di rischio in base a quanto indicato in tabella.
    
    REGOLA NEVE E INVERNO (INVERSIONI TERMICHE E WET BULB):
    4. Se sono previste precipitazioni e fa freddo, analizza scrupolosamente il profilo verticale:
       - INVERSIONE TERMICA E GELICIDIO: Controlla le temperature in quota (T_925hPa ~800m, T_900hPa ~1000m, T_850hPa ~1500m, T_800hPa ~2000m). Se al suolo la temperatura è rigida (es. <= 1°C) ma in ALMENO UNA di queste quote la temperatura è positiva (es. > 1°C), c'è un'inversione termica in atto. NON prevedere neve, ma avvisa del grave rischio di pioggia congelantesi (gelicidio).
       - BULBO UMIDO (Wet_Bulb): Se l'aria è positiva (es. +2/+3°C) ma il Wet_Bulb è <= 0°C, annuncia che le precipitazioni intense potrebbero far crollare la temperatura e trasformare la pioggia in neve.
       - Se l'intera colonna è favorevole (Z.Termico basso, T su tutte le quote <= 0°C, Wet Bulb <= 0°C), avvisa della probabilità di neve.
    
    REGOLE DI DISAGIO TERMICO (BIOMETEOROLOGIA):
    5. AFA E CALDO:
       - DISAGIO MODERATO: (T_Max >= 28°C e Dew >= 15°C) OPPURE (T_Max >= 25°C e Dew >= 20°C).
       - FORTE DISAGIO: (T_Max >= 32°C e Dew >= 20°C) OPPURE (T_Max >= 30°C e Dew >= 24°C).
       - Aggiungi il livello ESCLUSIVAMENTE tra parentesi dopo la massima giornaliera, senza dare ulteriori spiegazioni discorsive. Esempio: "...raggiungendo i 33°C (Forte Disagio)."
       
    6. WIND CHILL: Se (T_Media <= 8°C e Vento_Medio >= 15 km/h), spiega che il vento renderà il freddo più pungente.
    
    REGOLA NEBBIA/BRINA:
    7. Menziona foschie/nebbie SOLO per: aria stagnante (Vento_Medio < 5 km/h), T_Media notturna <= 0°C, e UR% vicina al 100%.
    
    DIVIETO ASSOLUTO SUI TERMINI TECNICI:
    8. È severamente VIETATO menzionare i nomi delle colonne della tabella (come "T_Media", "Probabilità", "Wet_Bulb", "Z.Termico", "T_925hPa", ecc.). Fai finta di aver analizzato i modelli di persona e usa un linguaggio discorsivo e comprensibile al pubblico.

    DATI ANALITICI ORARI (Ora | T_Media | UR% | Dew | Probabilità | Vento | Z.Termico | Wet_Bulb | T_925hPa | T_900hPa | T_850hPa | T_800hPa):
    {dati_meteo}
    """

    try:
        response = model.generate_content(prompt, generation_config={"temperature": 0.3})
        return response.text
    except Exception as e:
        return f"Errore AI: {e}"

def estrai_membri(hourly_data, prefisso_variabile, indice_ora):
    valori = []
    for key, lst in hourly_data.items():
        if key.startswith(prefisso_variabile):
            if indice_ora < len(lst) and lst[indice_ora] is not None:
                valori.append(lst[indice_ora])
    return valori

def main():
    # Aggiunte le quote 925hPa (~800m) e 800hPa (~2000m)
    dati_det = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": LAT, "longitude": LON,
        "hourly": "temperature_2m,relative_humidity_2m,dew_point_2m,freezinglevel_height,wet_bulb_temperature_2m,temperature_925hPa,temperature_900hPa,temperature_850hPa,temperature_800hPa",
        "models": "icon_d2",
        "timezone": "Europe/Rome", "forecast_days": 2
    }).json()

    dati_eps_d2 = requests.get("https://ensemble-api.open-meteo.com/v1/ensemble", params={
        "latitude": LAT, "longitude": LON,
        "hourly": "temperature_2m,precipitation,wind_speed_10m",
        "models": "icon_d2",
        "timezone": "Europe/Rome", "forecast_days": 2
    }).json()

    dati_eps_ch2 = requests.get("https://ensemble-api.open-meteo.com/v1/ensemble", params={
        "latitude": LAT, "longitude": LON,
        "hourly": "temperature_2m,precipitation,wind_speed_10m",
        "models": "icon_ch2",
        "timezone": "Europe/Rome", "forecast_days": 2
    }).json()

    hourly_det = dati_det.get('hourly', {})
    hourly_d2 = dati_eps_d2.get('hourly', {})
    hourly_ch2 = dati_eps_ch2.get('hourly', {})
    orari = hourly_det.get('time', [])
    
    report = "Ora | T_Media | UR% | Dew | Probabilità | Vento | Z.Termico | Wet_Bulb | T_925hPa | T_900hPa | T_850hPa | T_800hPa\n"
    
    temp_oggi = []
    temp_domani = []

    # Liste dati deterministici
    t_det_list = hourly_det.get('temperature_2m', [])
    ur_list = hourly_det.get('relative_humidity_2m', [])
    dew_list = hourly_det.get('dew_point_2m', [])
    z_term_list = hourly_det.get('freezinglevel_height', [])
    wet_bulb_list = hourly_det.get('wet_bulb_temperature_2m', [])
    t925_list = hourly_det.get('temperature_925hPa', [])
    t900_list = hourly_det.get('temperature_900hPa', [])
    t850_list = hourly_det.get('temperature_850hPa', [])
    t800_list = hourly_det.get('temperature_800hPa', [])

    # PRE-CALCOLO Probabilità per creare le "Finestre di Supporto"
    p1_d2_all, p3_d2_all, p5_d2_all = [], [], []
    p1_ch_all, p3_ch_all, p5_ch_all = [], [], []

    def pct(vals, th):
        if not vals: return 0 
        return (sum(1 for v in vals if v >= th) / len(vals)) * 100

    for i in range(48):
        prec_d2 = estrai_membri(hourly_d2, "precipitation_member", i)
        prec_ch2 = estrai_membri(hourly_ch2, "precipitation_member", i)
        
        p1_d2_all.append(pct(prec_d2, 1))
        p3_d2_all.append(pct(prec_d2, 3))
        p5_d2_all.append(pct(prec_d2, 5))
        
        p1_ch_all.append(pct(prec_ch2, 1))
        p3_ch_all.append(pct(prec_ch2, 3))
        p5_ch_all.append(pct(prec_ch2, 5))

    for i in range(48): 
        if i >= len(orari): break

        t_d2_mem = estrai_membri(hourly_d2, "temperature_2m_member", i)
        t_ch2_mem = estrai_membri(hourly_ch2, "temperature_2m_member", i)
        t_det = t_det_list[i] if i < len(t_det_list) else None

        w_d2_mem = estrai_membri(hourly_d2, "wind_speed_10m_member", i)
        w_ch2_mem = estrai_membri(hourly_ch2, "wind_speed_10m_member", i)

        # Calcolo medie dinamiche
        valori_temp = []
        if t_d2_mem: valori_temp.append(sum(t_d2_mem) / len(t_d2_mem))
        if t_ch2_mem: valori_temp.append(sum(t_ch2_mem) / len(t_ch2_mem))
        if t_det is not None: valori_temp.append(t_det)
        
        temp_finale = round(sum(valori_temp) / len(valori_temp)) if valori_temp else 0
        
        valori_vento = []
        if w_d2_mem: valori_vento.append(sum(w_d2_mem) / len(w_d2_mem))
        if w_ch2_mem: valori_vento.append(sum(w_ch2_mem) / len(w_ch2_mem))
        vento_finale = round(sum(valori_vento) / len(valori_vento)) if valori_vento else 0
        
        ur = ur_list[i] if i < len(ur_list) else 0
        dew = dew_list[i] if i < len(dew_list) else 0

        # Parametri invernali e stratigrafia termica
        z_term_val = z_term_list[i] if i < len(z_term_list) else "N/A"
        wet_bulb_val = wet_bulb_list[i] if i < len(wet_bulb_list) else "N/A"
        t925_val = t925_list[i] if i < len(t925_list) else "N/A"
        t900_val = t900_list[i] if i < len(t900_list) else "N/A"
        t850_val = t850_list[i] if i < len(t850_list) else "N/A"
        t800_val = t800_list[i] if i < len(t800_list) else "N/A"

        if i < 24:
            temp_oggi.append(temp_finale)
        else:
            temp_domani.append(temp_finale)

        # Finestra oraria sfasata (+/- 3 ore) per la convettività
        start_j = max(0, i - 3)
        end_j = min(48, i + 4)
        
        ch2_support_for_d2 = any(p1_ch_all[j] >= 10 for j in range(start_j, end_j))
        d2_support_for_ch = any(p1_d2_all[j] >= 10 for j in range(start_j, end_j))
        
        valido = False
        if p1_d2_all[i] >= 10 and ch2_support_for_d2: valido = True
        if p1_ch_all[i] >= 10 and d2_support_for_ch: valido = True
        if not any(p1_ch_all) and p1_d2_all[i] >= 10: valido = True # Fallback

        prob = "Assente"
        if valido:
            max5 = max(p5_d2_all[i], p5_ch_all[i])
            max3 = max(p3_d2_all[i], p3_ch_all[i])
            max1 = max(p1_d2_all[i], p1_ch_all[i])
            
            def livello(p):
                if p >= 30: return "Serio rischio"
                if p >= 20: return "Probabile"
                return "Minima possibilità"

            if max5 >= 10: prob = f"{livello(max5)} pioggia intensa o instabilità diffusa"
            elif max3 >= 10: prob = f"{livello(max3)} pioggia moderata o instabilità sparsa"
            elif max1 >= 10: prob = f"{livello(max1)} pioggia debole o instabilità isolata"

        # Popolamento stringa dati con le nuove colonne
        report += f"{orari[i][-5:]} | {temp_finale}°C | {ur}% | {dew}°C | {prob} | {vento_finale} km/h | {z_term_val}m | {wet_bulb_val}°C | {t925_val}°C | {t900_val}°C | {t850_val}°C | {t800_val}°C\n"

    min_oggi, max_oggi = (min(temp_oggi), max(temp_oggi)) if temp_oggi else ("N/A", "N/A")
    min_domani, max_domani = (min(temp_domani), max(temp_domani)) if temp_domani else ("N/A", "N/A")
    
    info_giornaliere = f"""
    {datetime.now().strftime("%A %d %B")}: Min {min_oggi}°C, Max {max_oggi}°C
    {(datetime.now() + timedelta(days=1)).strftime("%A %d %B")}: Min {min_domani}°C, Max {max_domani}°C
    """

    bollettino = interpella_gemini(report, info_giornaliere)
    
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      data={"chat_id": chat_id, "text": bollettino, "parse_mode": "Markdown"})
        print("Bollettino inviato con successo!")
    else:
        print("Errore: Token o Chat ID mancanti!")

if __name__ == "__main__":
    main()
