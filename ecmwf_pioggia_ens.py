import os
import requests
import metview as mv
from ecmwf.opendata import Client
import warnings

warnings.filterwarnings('ignore', category=RuntimeWarning)

FILENAME = "piemonte-tp-hres.grib"
PNG_OUTPUT = "piemonte-tp-hres"

def download_and_plot():
    client = Client("ecmwf", beta=False)
    
    # Run base: 23 Luglio 2026 alle 00:00 UTC.
    # Finestra accumulo: dalle 00:00 del 25 Luglio (+48h) alle 00:00 del 27 Luglio (+96h)
    
    try:
        client.retrieve(
            date=20260723,
            time=0,
            step=[48, 96],
            stream="oper",
            type="fc",
            levtype="sfc",     
            param=['tp'],
            target=FILENAME
        )
    except Exception as e:
        print(f"Errore download: {e}")
        return False

    if not os.path.exists(FILENAME):
        print("Errore: GRIB non scaricato.")
        return False

    data = mv.read(FILENAME)
    
    tp_48 = data.select(step=48)
    tp_96 = data.select(step=96)
    
    # Sottrazione per isolare l'accumulo delle 48 ore e conversione in mm
    tp_accumulo_mm = (tp_96 - tp_48) * 1000
    
    coast = mv.mcoast(
        map_coastline_colour="black",
        map_coastline_thickness=2,
        map_coastline_resolution="high",
        map_boundaries="on",
        map_boundaries_colour="black",
        map_boundaries_thickness=2,
        map_administrative_boundaries="on", 
        map_administrative_boundaries_colour="RGB(0.3, 0.3, 0.3)",
        map_administrative_boundaries_thickness=1,
        map_coastline_land_shade="off", # Sfondo completamente trasparente/bianco
        map_coastline_sea_shade="off",
        map_grid="off",
        map_label="off"
    )
    
    view = mv.geoview(
        map_area_definition="corners",
        area=[43.5, 6.0, 46.8, 10.5], 
        coastlines=coast
    )

    # STILE PRECIPITAZIONI: Isoiete colorate
    tp_style = mv.mcont(
        legend="off", # Niente legenda
        contour="on",
        contour_shade="off", # Niente riempimento a colore
        contour_line_thickness=3, # Linee spesse per essere ben visibili sul bianco
        contour_highlight="off",
        contour_label="on",
        contour_label_height=0.4,
        contour_label_colour="black",
        contour_label_frequency=1,
        contour_level_selection_type="level_list",
        contour_level_list=[0.5, 2, 5, 10, 15, 20, 30, 40, 50, 65, 80, 100, 150],
        contour_line_colour_method="list",
        contour_line_colour_list=[
            "RGB(0.6, 0.8, 1.0)",  # 0.5: Azzurrino
            "RGB(0.0, 0.3, 1.0)",  # 2.0: Blu
            "RGB(0.4, 0.9, 0.4)",  # 5.0: Verde chiaro
            "RGB(0.0, 0.6, 0.0)",  # 10.0: Verde scuro
            "RGB(1.0, 0.9, 0.0)",  # 15.0: Giallo
            "RGB(0.9, 0.7, 0.0)",  # 20.0: Giallo scuro
            "RGB(1.0, 0.6, 0.0)",  # 30.0: Arancione chiaro
            "RGB(1.0, 0.4, 0.0)",  # 40.0: Arancione scuro
            "RGB(1.0, 0.2, 0.2)",  # 50.0: Rosso chiaro
            "RGB(0.7, 0.0, 0.0)",  # 65.0: Rosso scuro
            "RGB(0.8, 0.2, 1.0)",  # 80.0: Viola chiaro
            "RGB(0.5, 0.0, 0.8)",  # 100.0: Viola
            "RGB(0.3, 0.0, 0.5)"   # 150.0: Viola scuro
        ]
    )
    
    title = mv.mtext(
        text_lines=[
            "Isoiete Accumulo 48h (mm) - ECMWF HRES",
            "Inizio: 25 Lug 00:00 UTC  |  Fine: 26 Lug 23:59 UTC (Run Base: 23 Lug 2026 00:00 UTC)"
        ],
        text_font_size=0.45,
        text_colour='black'
    )
    
    png = mv.png_output(
        output_name=PNG_OUTPUT,
        output_title="piemonte-tp",
        output_width=1200 
    )
    
    mv.setoutput(png)
    
    # Rimosso l'oggetto legend dal plot
    mv.plot(view, tp_accumulo_mm, tp_style, title)
    return True

def invia_telegram():
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("Credenziali Telegram non fornite.")
        return
        
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    payload = {"chat_id": chat_id, "caption": "Isoiete Precipitazioni 48h (25-26 Luglio) - ECMWF HRES"}
    
    file_path = f"{PNG_OUTPUT}.1.png"
    
    if os.path.exists(file_path):
        try:
            with open(file_path, "rb") as photo:
                requests.post(url, data=payload, files={"photo": photo})
                print("Inviato su Telegram!")
        except Exception as e:
            print(f"Errore invio Telegram: {e}")
    else:
        print(f"File {file_path} non trovato.")

if __name__ == "__main__":
    if download_and_plot():
        invia_telegram()
