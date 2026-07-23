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
    try:
        client.retrieve(
            date=20260723,
            time=0,
            step=[48, 96],
            stream="oper",     # Deterministico HRES
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
    
    # Accumulo delle 48 ore in mm
    tp_accumulo_mm = (tp_96 - tp_48) * 1000
    
    # CONFINI GEOGRAFICI MARRONI
    coast = mv.mcoast(
        map_coastline_colour="brown",
        map_coastline_thickness=2,
        map_coastline_resolution="high",
        map_boundaries="on",
        map_boundaries_colour="brown",
        map_boundaries_thickness=2,
        map_administrative_boundaries="on", 
        map_administrative_boundaries_colour="brown",
        map_administrative_boundaries_thickness=1,
        map_coastline_land_shade="off", 
        map_coastline_sea_shade="off",
        map_grid="off",
        map_label="off"
    )
    
    view = mv.geoview(
        map_area_definition="corners",
        area=[43.5, 6.0, 46.8, 10.5], 
        coastlines=coast
    )

    # CAPOLUOGHI DI PROVINCIA
    lats = [45.07, 44.38, 44.90, 44.91, 45.32, 45.45, 45.56, 45.92]
    lons = [7.68,  7.55,  8.20,  8.61,  8.42,  8.61,  8.05,  8.55]

    capoluoghi = mv.input_visualiser(
        input_plot_type="geo_points",
        input_longitude_values=lons,
        input_latitude_values=lats
    )

    stile_capoluoghi = mv.msymb(
        legend="off",
        symbol_type="marker",
        symbol_colour="brown",
        symbol_height=0.4,
        symbol_marker_index=15
    )

    # STILE ISOIETE: Corretta la sintassi per colorare le singole linee
    tp_style = mv.mcont(
        legend="off",
        contour="on",
        contour_shade="off",
        contour_line_thickness=3,
        contour_highlight="off",
        contour_label="on",
        contour_label_height=0.4,
        contour_label_colour="black",
        contour_label_frequency=1,
        contour_level_selection_type="level_list",
        contour_level_list=[0.5, 2, 5, 10, 15, 20, 30, 40, 50, 65, 80, 100, 150],
        contour_line_colour="rainbow",                     # <-- ATTIVA LA MODALITA' MULTICOLORE
        contour_line_colour_rainbow_method="list",         # <-- SPECIFICA CHE SI USA UNA LISTA
        contour_line_colour_rainbow_colour_list=[          # <-- LA TUA LISTA DI COLORI
            "RGB(0.6, 0.8, 1.0)",  
            "RGB(0.0, 0.3, 1.0)",  
            "RGB(0.4, 0.9, 0.4)",  
            "RGB(0.0, 0.6, 0.0)",  
            "RGB(1.0, 0.9, 0.0)",  
            "RGB(0.9, 0.7, 0.0)",  
            "RGB(1.0, 0.6, 0.0)",  
            "RGB(1.0, 0.4, 0.0)",  
            "RGB(1.0, 0.2, 0.2)",  
            "RGB(0.7, 0.0, 0.0)",  
            "RGB(0.8, 0.2, 1.0)",  
            "RGB(0.5, 0.0, 0.8)",  
            "RGB(0.3, 0.0, 0.5)"   
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
    
    # Plot con Capoluoghi
    mv.plot(view, tp_accumulo_mm, tp_style, capoluoghi, stile_capoluoghi, title)
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
