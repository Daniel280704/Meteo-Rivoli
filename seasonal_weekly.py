import os
import sys
import hashlib
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import warnings

warnings.filterwarnings('ignore', category=RuntimeWarning)

LATITUDE = 45.07347491421504
LONGITUDE = 7.543461388723449

FILE_HASH = "ultimo_hash_seasonal_weekly.txt"
FILENAME = "seasonal_weekly_anomalies.png"

def verifica_dati_nuovi(data_dict: dict) -> bool:
    sample = data_dict.get("temperature_max6h_2m_anomaly", [])
    stringa_dati = str(sample).encode('utf-8')
    hash_attuale = hashlib.md5(stringa_dati).hexdigest()
    
    if os.path.exists(FILE_HASH):
        with open(FILE_HASH, "r") as f:
            if f.read().strip() == hash_attuale:
                return False

    with open(FILE_HASH, "w") as f:
        f.write(hash_attuale)
    return True

def main():
    print("Scaricamento anomalie settimanali (45 giorni) in corso...")
    
    URL = "https://seasonal-api.open-meteo.com/v1/seasonal"
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "weekly": "temperature_max6h_2m_anomaly,temperature_max6h_2m_mean,temperature_min6h_2m_anomaly,temperature_min6h_2m_mean,precipitation_anomaly,precipitation_mean",
        "timezone": "Europe/Rome",
        "forecast_days": 45
    }
    headers = {"User-Agent": "MeteoBot-Seasonal/1.0"}

    try:
        response = requests.get(URL, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        weekly = data.get("weekly", {})
    except Exception as e:
        print(f"❌ Errore API: {e}", file=sys.stderr)
        sys.exit(1)

    if not verifica_dati_nuovi(weekly):
        print("ℹ️ Nessun aggiornamento trovato. Elaborazione fermata.")
        sys.exit(0)
        
    times = pd.to_datetime(weekly.get("time"))
    
    # Estrazione Dati
    tmax_anom = np.array(weekly.get("temperature_max6h_2m_anomaly"), dtype=float)
    tmin_anom = np.array(weekly.get("temperature_min6h_2m_anomaly"), dtype=float)
    prec_anom = np.array(weekly.get("precipitation_anomaly"), dtype=float)

    # Impostazione Grafici
    fig, axs = plt.subplots(3, 1, figsize=(12, 14), sharex=True)
    
    def plot_anomaly_bars(ax, times, anomalies, is_precip=False):
        # Colori dinamici in base al segno dell'anomalia
        if is_precip:
            colors = ['#2ca02c' if val >= 0 else '#8c564b' for val in anomalies] # Verde per surplus, Marrone per deficit
            ylabel = "Anomalia Prec. (mm)"
        else:
            colors = ['#d62728' if val >= 0 else '#1f77b4' for val in anomalies] # Rosso per caldo, Blu per freddo
            ylabel = "Anomalia Temp. (°C)"
            
        ax.bar(times, anomalies, color=colors, width=5, alpha=0.8, edgecolor='black', linewidth=0.5)
        ax.axhline(0, color='black', linewidth=1.5, linestyle='--') # Linea dello zero (Media)
        ax.set_ylabel(ylabel, fontsize=11, fontweight='bold')
        ax.grid(True, linestyle=':', alpha=0.6)
        
        # Etichette di testo sopra/sotto le barre
        for i, val in enumerate(anomalies):
            if not np.isnan(val):
                offset = 0.5 if not is_precip else 5
                y_pos = val + offset if val >= 0 else val - offset
                va = 'bottom' if val >= 0 else 'top'
                ax.text(times[i], y_pos, f"{val:+.1f}", ha='center', va=va, fontsize=9, fontweight='bold', color=colors[i])
                
        # Padding dinamico asse Y
        v_max = np.nanmax(np.abs(anomalies)) if not np.isnan(anomalies).all() else 1
        pad = v_max * 0.3 if v_max != 0 else 1
        ax.set_ylim(-v_max - pad, v_max + pad)

    # 1. T-Max Anomaly
    plot_anomaly_bars(axs[0], times, tmax_anom, is_precip=False)
    axs[0].set_title("Anomalia Settimanale Temperatura MASSIMA", fontsize=12, fontweight='bold')

    # 2. T-Min Anomaly
    plot_anomaly_bars(axs[1], times, tmin_anom, is_precip=False)
    axs[1].set_title("Anomalia Settimanale Temperatura MINIMA", fontsize=12, fontweight='bold')

    # 3. Precipitation Anomaly
    plot_anomaly_bars(axs[2], times, prec_anom, is_precip=True)
    axs[2].set_title("Anomalia Settimanale PRECIPITAZIONI", fontsize=12, fontweight='bold')

    axs[-1].set_xlabel("Settimana di riferimento (Data di inizio)", fontsize=12, fontweight='bold', labelpad=10)
    axs[-1].xaxis.set_major_locator(mdates.DayLocator(interval=7))
    axs[-1].xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(FILENAME, dpi=200, bbox_inches='tight')

    # --- INVIO A TELEGRAM ---
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        url_telegram = f"https://api.telegram.org/bot{token}/sendPhoto"
        ora = datetime.now().strftime("%d/%m/%Y alle %H:%M")
        caption = (
            "📊 <b>Anomalie Settimanali (Proiezione 45 Giorni)</b>\n"
            "Scostamenti previsti rispetto alla media climatologica di riferimento.\n"
            "• <b>Temperature:</b> Rosso (sopra media) / Blu (sotto media).\n"
            "• <b>Precipitazioni:</b> Verde (surplus) / Marrone (deficit).\n\n"
            f"<i>Aggiornato il {ora}</i>"
        )
        try:
            with open(FILENAME, "rb") as photo:
                requests.post(url_telegram, data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}, files={"photo": photo})
        except Exception as e:
            print(f"❌ Eccezione Telegram: {e}")

if __name__ == "__main__":
    main()